"""
LLM-as-a-Judge（E2E 第三层）：对 JSONL 中的回答按桶标准评 relevance / grounding / pollution / final_judgement。

抽样：先跑通 22 条（四桶各 5 + 典型 d18、m04），见 PHASE1_JUDGE_SAMPLE_IDS。
"""

from __future__ import annotations

import json
import re
from typing import Any

from src.evaluation.e2e_manifest import build_e2e_manifest


def all_manifest_sample_ids() -> list[str]:
    """与 build_e2e_manifest() 同序，共 90 条。"""
    return [r["id"] for r in build_e2e_manifest()]


# 每桶 5 条 + 典型 2 条 = 22（可改列表后重跑）
PHASE1_JUDGE_SAMPLE_IDS: list[str] = [
    # must_ground（domain 内、须锚定仓库）
    "p02",
    "p04",
    "p11",
    "p24",
    "p40",
    # far_general
    "d01",
    "d05",
    "d10",
    "q03",
    "q18",
    # term_near_no_rag
    "q01",
    "q08",
    "q10",
    "q14",
    "q17",
    # misleading_edge
    "m02",
    "m03",
    "m06",
    "m08",
    "m10",
    # 典型 FP / 软熔断相关
    "d18",
    "m04",
]


def _gold_summary(row: dict) -> str:
    bt = row.get("bucket_type", "")
    gt = row.get("grounding_tier", "n/a")
    sct = row.get("should_call_tool", "")
    priv = row.get("should_hit_private_knowledge", "")
    lines = [
        f"- bucket_type: **{bt}**",
        f"- grounding_tier: **{gt}**",
        f"- should_call_tool（manifest）: **{sct}**",
        f"- should_hit_private_knowledge: **{priv}**",
    ]
    if bt == "domain":
        lines.append(
            "- **本条锚点**：domain 样本须按 **grounding_tier**（must_ground / prefer_ground / ok_generic）"
            "使用系统提示中的「domain 三层」表判定 **grounding_appropriate** 与 **final_judgement**；"
            "**禁止**用 must_ground 的严格度去卡 ok_generic / prefer_ground。"
        )
    elif bt == "far_general":
        lines.append(
            "- **本桶好回答要点**：以**通用知识**作答即可；**不需要**依赖私有代码；**不要**被无关仓库片段污染。"
        )
    elif bt == "term_near_no_rag":
        lines.append(
            "- **本桶好回答要点**：术语虽与项目接近，但本质是**概念题**；回答保持**通用、克制**；"
            "**不要**强行把本仓库实现扯进来。"
        )
    elif bt == "misleading_edge":
        lines.append(
            "- **本桶好回答要点（最难）**：对边界问题做**合理取舍**；若检索了，**不能**胡乱强绑定项目；"
            "若不检索，也**不能**漏掉题面里**显式项目锚点**的必要解释。"
        )
    return "\n".join(lines)


# domain 内按题面标注分层；与初版「domain 一律须 grounded」的单一标准区分（见 评估/10）
_JUDGE_SYSTEM_BODY = """你是严谨的评测员，对「编程助手」的最终回答打分。只输出**一个 JSON 对象**，不要 Markdown 代码围栏以外的文字。

## 总体原则（容错维度）
除「是否恰当 grounded」外，还须综合判断**在当前 bucket_type 与 grounding_tier 下，回答是否足够合理**：
- 是否切题、事实是否正确、是否诚实（如承认未找到、说明局限）；
- **grounding_appropriate** 的含义**随 tier / 桶变化**，见下文，不是只问「有没有私有知识」。
- **domain 且 grounding_tier 为 ok_generic / prefer_ground**：**不得**仅因「未引用代码片段」就判 incorrect；须按该 tier 的宽松度评判。
- **索引/检索局限**：向量库或切块可能**滞后、不全**，Gold 中的「应有实现」未必出现在**本条实际检索结果**里。Judge 只能依据**用户问题 + 本条日志中的检索信号**（如 `top1_distance`、是否软熔断）推断「证据是否可得」，**不得**假设模型能引用库里不存在的片段。

## domain 三层（仅当 bucket_type = domain 时适用；以本条 Gold 中的 grounding_tier 为准）

### must_ground
- **核心含义**：在**检索侧能给出与问题相关的可用仓库证据**时，回答应**锚定**该证据（路径、符号、真实逻辑）；若**装作**已基于仓库却未用证据，原则上**不可**判 **correct**。
- **证据不可得时**（例如：未检索到、top1 很弱、已软熔断、模型**诚实**说明在当前检索结果中未找到相关实现）：这是**检索/索引与题面**之间的缺口，**不**应等同于「模型能力差」。若回答**诚实说明局限**、通识部分**正确且切题**、**不捏造**本仓库路径或行为，倾向 **partially_correct**；若通识回答质量高、边界说明清晰，**可**判 **correct**（须写明：证据链不足故以诚实通识作答）。
- **检索后未有效利用明显相关的片段**、或把无关片段当依据（污染）：仍倾向 **partially_correct** 或 **incorrect**（视严重程度）。
- **incorrect** 主要用于：答非所问、**捏造**仓库事实、在**明显可用**的检索结果面前完全忽略、或通识部分严重错误——**而非**「仅因索引里没收录某函数就判输」。

### prefer_ground
- **期望**：**最好**结合仓库实现；能引用则加分。
- **未充分 grounded** 但通识回答**合理、切题、无明显幻觉**：可判 **partially_correct**；**不应轻易 incorrect**。
- 若回答**明显正确**且与项目关系表述得体（或诚实说明检索/实现边界），可判 **correct**。
- **禁止**仅因「没贴代码片段」就打 **incorrect**。

### ok_generic
- **期望**：**允许**以通识为主作答；是否检索、是否引用仓库**不是**硬门槛。
- 只要**问题答对**、**不胡编**、**不被无关检索污染**（context_pollution = false），且诚实，即可判 **correct**。
- 本层**必须放宽**，否则会系统性误伤。

## 非 domain 桶（bucket_type 为 far_general / term_near_no_rag / misleading_edge；Gold 中 grounding_tier 多为 n/a）
- **不要**套用 domain 三层 must_ground 标准。
- 按各桶原意：**far_general** 以通识为主、勿乱引仓库为权威；**term_near_no_rag** 概念题克制、勿强行扯本仓库；**misleading_edge** 边界取舍、检索了勿乱绑项目、不检索勿漏显式锚点说明。
- **grounding_appropriate** 表示：在该桶要求下，对「是否该用私有知识」的处理是否恰当。

## 统一五项（所有样本；含义随上表）
1. **answer_relevant**：是否直接回应用户问题（答非所问则为 false）。
2. **grounding_appropriate**：在**本条** bucket + grounding_tier 下，对私有知识/通识的平衡是否恰当（见 domain 三层与非 domain 规则）。
3. **context_pollution**：回答是否被**无关检索**明显干扰（牵强附会、乱引用代码）？无则 false，有则 true。
4. **final_judgement**：只能是 **correct**、**partially_correct**、**incorrect** 之一。
5. **score（1～5 整数）**：综合质量分，须与上列及 final_judgement 大致对齐（见下表）。

## 分数锚点（必须遵守）
| score | 含义（综合） | 与 judgement 的典型对应 |
|-------|----------------|-------------------------|
| 5 | 切题、在该 tier 下处理恰当、无上下文污染，可直接采用 | 多为 correct |
| 4 | 整体可用，有轻微瑕疵 | correct 或 partially_correct |
| 3 | 部分有用：有明显缺口或 tier 下存疑 | 多为 partially_correct |
| 2 | 问题较大：答非所问、严重违背 tier、或污染明显 | partially_correct 或 incorrect |
| 1 | 基本不可用 | incorrect |

## 输出 JSON 形状（字段必须齐全）
{
  "answer_relevant": true,
  "grounding_appropriate": true,
  "context_pollution": false,
  "score": 5,
  "final_judgement": "correct",
  "reason": "一两句话中文说明（须交代 bucket、grounding_tier 与给分依据）"
}

final_judgement 取值只能是字符串：correct、partially_correct、incorrect。score 必须是 1～5 的**整数**。
"""


def build_judge_messages(record: dict, *, use_index_aware_tier: bool = False) -> list[dict[str, str]]:
    """构造 Judge 的 system + user messages。Gold 以 manifest 为准。

    use_index_aware_tier：为 True 时，domain 样本在 prompt 中使用 **grounding_tier_index_aware**
    与 **should_call_tool_index_aware**（与当前 Chroma 可达性对齐），用于重跑 Judge 而不改 E2E 日志。
    """
    gold_rows = {r["id"]: r for r in build_e2e_manifest()}
    sid = record.get("sample_id")
    g = gold_rows.get(sid)
    if not g:
        raise KeyError(f"unknown sample_id in manifest: {sid}")

    g_gold = dict(g)
    if use_index_aware_tier and g.get("bucket_type") == "domain":
        g_gold["grounding_tier"] = g.get("grounding_tier_index_aware", g.get("grounding_tier"))
        sct_ia = g.get("should_call_tool_index_aware")
        if sct_ia is not None:
            g_gold["should_call_tool"] = sct_ia

    system = _JUDGE_SYSTEM_BODY

    act = record.get("actual_call_search_codebase")
    fuse = record.get("soft_fallback_triggered")
    top1 = record.get("top1_distance")
    preview = record.get("final_answer_preview") or ""
    q = record.get("question") or ""
    gt = g_gold.get("grounding_tier", "n/a")
    bt = g.get("bucket_type", "")

    anchor = ""
    if bt == "domain":
        mode_note = "（本条 Gold 使用 **grounding_tier_index_aware**）" if use_index_aware_tier else ""
        anchor = (
            f"**本条评测锚点**：`grounding_tier` = **{gt}**{mode_note}。对 **grounding_appropriate** 与 **final_judgement** "
            "必须严格按 system 中「domain 三层」里**该 tier** 的一节评判（不要用其它 tier 的标准）。"
        )
    else:
        anchor = (
            "**本条评测锚点**：非 domain 桶，`grounding_tier` 通常为 n/a；"
            "请按 system 中「非 domain 桶」规则评判，**不要**套用 domain 的 must_ground 严格度。"
        )

    user = f"""## Gold / 桶信息（评测集标注）
{_gold_summary(g_gold)}

{anchor}

## 工具与软熔断（本条实际发生）
- actual_call_search_codebase: {act}
- top1_distance: {top1}
- soft_fallback_triggered: {fuse}

## 用户问题
{q}

## 模型回答（截断存储，以完整语义为准）
{preview}
"""

    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def parse_judge_json(raw: str) -> dict[str, Any]:
    """从模型输出中解析 JSON。"""
    text = raw.strip()
    if not text:
        raise ValueError("empty judge response")
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError(f"no JSON object in: {text[:200]}")
    return json.loads(m.group())


def validate_judge_output(obj: dict[str, Any]) -> dict[str, Any]:
    required = (
        "answer_relevant",
        "grounding_appropriate",
        "context_pollution",
        "score",
        "final_judgement",
        "reason",
    )
    for k in required:
        if k not in obj:
            raise ValueError(f"missing key: {k}")
    fj = obj["final_judgement"]
    if fj not in ("correct", "partially_correct", "incorrect"):
        raise ValueError(f"invalid final_judgement: {fj}")
    raw = obj["score"]
    if isinstance(raw, bool):
        raise ValueError("score must be integer 1-5, not bool")
    try:
        sc = int(raw)
    except (TypeError, ValueError) as e:
        raise ValueError(f"score must be integer 1-5, got {raw!r}") from e
    if sc < 1 or sc > 5:
        raise ValueError(f"score must be 1..5, got {sc}")
    obj["score"] = sc
    return obj
