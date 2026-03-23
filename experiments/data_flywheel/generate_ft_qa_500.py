"""
生成 **Phase 2A — 单轮工具路由** 对齐样本（JSONL），**仅调用 Gemini**。

监督目标见 `SFT_PHASE_2A.md`：只优化路由决策（JSON 可解析、decision_type、tool、参数），
**不**以长篇自然语言解答为训练目标。每条使用 `decision_type` ∈ tool_call | no_tool | clarify_needed，
`clarify_answer` 仅用于 clarify_needed（短句澄清），与 `direct_answer` 脱钩。

切片与条数：三切片按 **权重** 缩放到 `TARGET_TOTAL`（默认权重对应旧版 500 条全量 300:100:100）。
  - private_domain → bucket=`domain`
  - dev_general_no_rag → bucket=`far_general`
  - misleading_edge → bucket=`misleading_edge`

依赖：`.env` 中 `google_api_key`（见 src/config.py），`pip install google-genai`。

用法：仓库根目录  
`python experiments/data_flywheel/generate_ft_qa_500.py`  
`python experiments/data_flywheel/generate_ft_qa_500.py --target 450 --segment-ratio 70,15,15 --split-test 50`  
`--dry-run` 只打印计划。

输出：`experiments/data_flywheel/out/ft_qa_{TARGET_TOTAL}.jsonl`；若 `--split-test N` 则另写  
`ft_qa_{TARGET_TOTAL}_train.jsonl` 与 `ft_qa_{TARGET_TOTAL}_test.jsonl`（分层抽样，默认可复现 seed）。
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.data_flywheel.context_fastapi_transformers import (
    PROJECT_CONTEXT_FASTAPI_TRANSFORMERS,
    SCENARIOS,
)

BATCH_CHUNK = 20

# 默认生成条数（CLI `--target` 可覆盖）
TARGET_TOTAL = 100

# 三切片权重（与 TARGET_TOTAL 成比例缩放）；旧版 500 全量 = 300:100:100；扩量可用 70:15:15
DEFAULT_SEGMENT_WEIGHTS: tuple[int, int, int] = (300, 100, 100)

SLICE_ORDER: tuple[str, str, str] = (
    "private_domain",
    "dev_general_no_rag",
    "misleading_edge",
)

# 切片 → 对外 bucket 名（与训练/DPO 脚本对齐）
SLICE_TO_BUCKET: dict[str, str] = {
    "private_domain": "domain",
    "dev_general_no_rag": "far_general",
    "misleading_edge": "misleading_edge",
}

# 各切片内 decision_type 目标占比（单批内按整数条数分配，总和 = 本批 n）
# Phase 2A：tool_call 为主；far_general 提高 no_tool；misleading 提高 clarify_needed
MIX_BY_SLICE: dict[str, dict[str, float]] = {
    "private_domain": {"tool_call": 0.70, "no_tool": 0.15, "clarify_needed": 0.15},
    "dev_general_no_rag": {"tool_call": 0.35, "no_tool": 0.40, "clarify_needed": 0.25},
    "misleading_edge": {"tool_call": 0.40, "no_tool": 0.15, "clarify_needed": 0.45},
}


def _allocate_kind_counts(n: int, fractions: dict[str, float]) -> dict[str, int]:
    """将占比变为整数条数，保证总和为 n。"""
    keys = ("tool_call", "no_tool", "clarify_needed")
    raw = [fractions[k] * n for k in keys]
    base = [int(x) for x in raw]
    rem = n - sum(base)
    order = sorted(
        range(len(keys)),
        key=lambda i: (raw[i] - base[i], i),
        reverse=True,
    )
    for i in range(rem):
        base[order[i]] += 1
    return dict(zip(keys, base))


def _batch_sizes_for_provider_total(n: int) -> list[int]:
    out: list[int] = []
    rest = n
    while rest >= BATCH_CHUNK:
        out.append(BATCH_CHUNK)
        rest -= BATCH_CHUNK
    if rest > 0:
        out.append(rest)
    return out


def _scaled_segment_totals(
    target_total: int,
    weights: tuple[int, int, int],
) -> list[tuple[str, int]]:
    """按 weights 比例缩放到 target_total，条数之和严格等于 target_total。"""
    if target_total <= 0:
        raise ValueError("target_total 必须为正整数")
    if len(weights) != 3 or any(w < 0 for w in weights):
        raise ValueError("weights 须为三个非负整数")
    base_sum = sum(weights)
    if base_sum == 0:
        raise ValueError("weights 之和不能为 0")
    if target_total == base_sum:
        return list(zip(SLICE_ORDER, weights))
    scale = target_total / base_sum
    raw = [weights[i] * scale for i in range(3)]
    floors = [int(x) for x in raw]
    rem = target_total - sum(floors)
    order = sorted(range(3), key=lambda i: (raw[i] - floors[i], i), reverse=True)
    for k in range(rem):
        floors[order[k]] += 1
    return list(zip(SLICE_ORDER, floors))


def _build_batch_plan(
    target_total: int, weights: tuple[int, int, int]
) -> list[tuple[str, int, str]]:
    """每切片条数全部由 Gemini 分批生成（每批最多 BATCH_CHUNK）。"""
    segments = _scaled_segment_totals(target_total, weights)
    plan: list[tuple[str, int, str]] = []
    for slice_id, total in segments:
        for size in _batch_sizes_for_provider_total(total):
            plan.append(("gemini", size, slice_id))
    return plan


def _expected_slice_totals_dict(
    target_total: int, weights: tuple[int, int, int]
) -> dict[str, int]:
    return {sid: n for sid, n in _scaled_segment_totals(target_total, weights)}


def _stratified_train_test_split(
    rows: list[dict],
    test_n: int,
    *,
    segment_counts: dict[str, int],
    seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    """按 slice 分层划分 test 集，各 slice 内 test 条数与 segment_counts 占总量比例一致（最大余数法）。"""
    if test_n < 0 or test_n > len(rows):
        raise ValueError("split-test 无效")
    total_n = len(rows)
    if total_n != sum(segment_counts.values()):
        raise ValueError("segment_counts 与 rows 条数不一致")
    rng = random.Random(seed)
    slices = SLICE_ORDER
    raw_test = [test_n * segment_counts[s] / total_n for s in slices]
    floors = [int(x) for x in raw_test]
    rem = test_n - sum(floors)
    order = sorted(range(3), key=lambda i: (raw_test[i] - floors[i], i), reverse=True)
    for k in range(rem):
        floors[order[k]] += 1
    test_per_slice = dict(zip(slices, floors))
    by_slice: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_slice[r["_meta"]["slice"]].append(r)
    train: list[dict] = []
    test: list[dict] = []
    for sid in slices:
        pool = by_slice[sid][:]
        rng.shuffle(pool)
        tn = test_per_slice[sid]
        if len(pool) < tn:
            raise ValueError(f"slice {sid}: 需要 {tn} 条测试集，实际仅 {len(pool)} 条")
        test.extend(pool[:tn])
        train.extend(pool[tn:])
    rng.shuffle(train)
    rng.shuffle(test)
    return train, test


SLICE_LABEL_ZH: dict[str, str] = {
    "private_domain": "私域语境（FastAPI+Transformers）",
    "dev_general_no_rag": "开发通识（无需查库）",
    "misleading_edge": "误导向/边界",
}

GEMINI_MODEL = "gemini-3-flash-preview"
SLEEP_SECONDS = 4.0

# —— Phase 2A 路由输出 schema（嵌入各切片 prompt；不缩短工具列表，见 TOOL_LIST_AND_PARAMS_BLOCK）——
def _output_schema_block(*, bucket: str, kind_counts: dict[str, int], n: int) -> str:
    ct = kind_counts["tool_call"]
    cn = kind_counts["no_tool"]
    cc = kind_counts["clarify_needed"]
    return f"""
【必须遵守的输出 Schema（Phase 2A 单轮路由；每条对象字段一致；仅按 decision_type 填有效字段）】
本批共 {n} 条；请**严格**按下面条数分配 decision_type：tool_call **{ct}** 条、no_tool **{cn}** 条、clarify_needed **{cc}** 条（三类条数之和必须等于 {n}）。
bucket 本批固定为："{bucket}"

每条对象须包含以下键：
- "sample_id": 字符串，建议形如 "{bucket}_001" 递增，本批内唯一即可。
- "bucket": 固定 "{bucket}"
- "query": 用户问题（中文为主，可夹英文术语）
- "decision_type": 只能是 "tool_call" | "no_tool" | "clarify_needed"

当 decision_type == "tool_call":
- "tool_name": 上述六工具之一（与 TOOL_LIST 完全一致）
- "arguments": 与该工具 schema 一致的对象，字段完整、类型正确、可执行
- "clarify_answer": null
- "oracle_context": 字符串或 null；若为 search_codebase，可写极短检索意图说明（便于审计，非替代 arguments）

当 decision_type == "no_tool":
- "tool_name": null
- "arguments": null
- "clarify_answer": null
- "oracle_context": null
- 含义：本轮无需调用任何工具即可完成路由判断（例如与工具无关、或已明确无需工具）。**禁止**编造本仓库具体文件、默认配置、镜像名等未经验证的事实。

当 decision_type == "clarify_needed":
- "tool_name": null
- "arguments": null
- "clarify_answer": **1～2 句**中文，仅用于追问缺失信息或点明歧义；禁止教程式长文、禁止身份表演套话
- "oracle_context": null

返回**严格 JSON 数组**，顶层仅此数组，不要 markdown。示例（结构示意）：
[
  {{
    "sample_id": "{bucket}_001",
    "bucket": "{bucket}",
    "query": "...",
    "decision_type": "tool_call",
    "tool_name": "search_codebase",
    "arguments": {{"query": "...", "top_k": 6}},
    "clarify_answer": null,
    "oracle_context": null
  }},
  {{
    "sample_id": "{bucket}_002",
    "bucket": "{bucket}",
    "query": "...",
    "decision_type": "no_tool",
    "tool_name": null,
    "arguments": null,
    "clarify_answer": null,
    "oracle_context": null
  }},
  {{
    "sample_id": "{bucket}_003",
    "bucket": "{bucket}",
    "query": "...",
    "decision_type": "clarify_needed",
    "tool_name": null,
    "arguments": null,
    "clarify_answer": "请贴出完整 Traceback 或报错行号。",
    "oracle_context": null
  }}
]
"""


# 与 loRA/generate_lora_data_fastapi_transformers.py 中【Agent 工具列表与参数】一节一字不差（便于 tool_call 监督对齐）
TOOL_LIST_AND_PARAMS_BLOCK = """
【Agent 工具列表与参数（务必遵守工具名与字段）】
1. 工具名: `analyse_code`
   - 触发场景: 静态代码问题分析。
   - 参数: {{"code": "<必填，一段存在潜在问题的 Python 源代码>"}}
2. 工具名: `search_codebase`
   - 触发场景: 询问某个模块、逻辑在哪，或查询实现/配置。
   - 参数: {{"query": "<必填，检索关键词/短句>", "top_k": <选填整数，默认6>}}
3. 工具名: `analyse_log`
   - 触发场景: 报错信息、异常堆栈分析。
   - 参数: {{"log": "<必填，一段包含 traceback 的报错文本>"}}
4. 工具名: `generate_dockerfile`
   - 触发场景: 容器化、Docker、部署依赖描述。
   - 参数: {{"project_description": "<必填，项目运行环境或依赖描述>"}}
5. 工具名: `generate_tests`
   - 触发场景: 单元测试（pytest）或边界覆盖。
   - 参数: {{"code": "<必填，需要被测试的函数代码>", "description": "<选填，额外说明>"}}
6. 工具名: `complete_code`
   - 触发场景: 续写残缺代码。
   - 参数: {{"context": "<必填，用户已有的残缺代码>"}}
"""


DATA_GENERATOR_PROMPT_PRIVATE_DOMAIN = (
    """你是一个 AI 数据集构建者。正在为代码 Agent 生成 Function Calling 训练数据。
用户问题应主要围绕【transformers 与 FastAPI 两大上游仓库】的目录、类名、概念与典型工程任务（见下方背景），语气贴近真实开发者。

为便于一次读全，请按顺序使用三块信息：① 双仓库背景（供你取材）② 工具名与参数（当 decision_type 为 tool_call 时必须遵守的契约）③ 文末 Phase 2A 路由 Schema（decision_type、tool_name、arguments、clarify_answer 等字段与 JSON 示例）。

【双仓库背景】
{project_context}

（上表为语料：写 query 时可自然引用其中的路径、类名、术语或典型工程问题，不必复述长段背景。）
"""
    + TOOL_LIST_AND_PARAMS_BLOCK
    + """

【Phase 2A 单轮工具路由说明（必须与文末 Schema 一致）】
本批数据用于「单轮工具路由对齐」：监督信号是**路由决策本身**，不是长篇自然语言回答。
- 每条样本必须作出且仅作出路由决策：decision_type 只能是 tool_call、no_tool、clarify_needed 之一。
- decision_type == tool_call：必须给出可被执行的 tool_name 与 arguments；参数须与上列六工具 schema 完全一致，信息密度高，避免空洞占位。
- decision_type == no_tool：表示当前单轮判断下无需调用任何工具。**不得**编造「本仓库」「我们项目」的具体实现、路径、默认镜像或配置参数。
- decision_type == clarify_needed：信息不足或存在歧义、必须先澄清再安全选工具。clarify_answer 仅 1～2 句中文，用于追问或点明歧义；禁止教程式展开、禁止堆砌身份表演。
- 不要输出 response_kind；不要输出 direct_answer 字段；澄清仅使用 clarify_answer。

字段与各类条数分配见下方 Schema。

{schema_block}
"""
)


DATA_GENERATOR_PROMPT_DEV_GENERAL = (
    """你是一个 AI 数据集构建者。正在为代码 Agent 生成 Function Calling 训练数据。

【本批数据切片：开发通识 · 无需查库】
user_query 应面向**软件开发常见话题**（语言与运行时、调试思路、依赖与包管理、Git、容器与部署概念、测试与 CI 思路、通用 HTTP/API 用法等），且**不需要**依赖「某个具体业务仓库内的私有目录结构或内部文件名」才能理解或处理。
优先生成可通过常识、公开文档级知识、或题干中已给出的代码/日志片段本身就能处理的请求；避免把「必须检索某代码库才能知道放哪」作为唯一前提。

仍从下列 6 个工具中选其一；若选 search_codebase，query 应是**泛化**的关键词或短句（如概念名、类名风格），而非「在某某项目里找某某路径」式的私域检索。

"""
    + TOOL_LIST_AND_PARAMS_BLOCK
    + """

【Phase 2A 单轮工具路由说明（必须与文末 Schema 一致）】
本切片侧重「开发通识、无需强依赖私库路径」的 query 分布：no_tool 与 tool_call 均常见；当信息不足以安全选工具时，应使用 clarify_needed。
- decision_type、tool_name、arguments、clarify_answer 的约束同私域切片；**禁止**在 no_tool 或 clarify_answer 中捏造具体仓库事实。
- 不要输出 response_kind 或 direct_answer 字段。

字段与各类条数分配见下方 Schema。

{schema_block}
"""
)


DATA_GENERATOR_PROMPT_MISLEADING_EDGE = (
    """你是一个 AI 数据集构建者。正在为代码 Agent 生成 Function Calling 训练数据。

【本批数据切片：误导向 / 边界 / 压力】
user_query 应包含**歧义指令、缺失关键信息、表面矛盾的需求、易误判工具的情形、或边界条件**（例如：日志与代码片段指向不同工具、同一句话同时像两种工具、超出工具能力边界等），用于训练模型**谨慎选择工具**与**澄清**能力。
每条样本在 tool_call 时须有合理的 tool_name 与 arguments；可刻意制造「需要推理才能选对工具」的情形，但 arguments 必须自洽、可解析。

"""
    + TOOL_LIST_AND_PARAMS_BLOCK
    + """

【Phase 2A 单轮工具路由说明（必须与文末 Schema 一致）】
本切片侧重误导向、缺信息、易误判工具的情形：应提高 clarify_needed 的合理比例；tool_call 仅在「选工具确实合理」时出现，arguments 必须自洽。
- 同上：decision_type 三分类、clarify_answer 短句、禁止捏造仓库细节、禁止 response_kind / direct_answer 字段。

字段与各类条数分配见下方 Schema。

{schema_block}
"""
)


def _base_prompt_for_slice(slice_id: str, n: int) -> str:
    bucket = SLICE_TO_BUCKET[slice_id]
    mix = MIX_BY_SLICE[slice_id]
    kind_counts = _allocate_kind_counts(n, mix)
    schema_block = _output_schema_block(bucket=bucket, kind_counts=kind_counts, n=n)

    if slice_id == "private_domain":
        return DATA_GENERATOR_PROMPT_PRIVATE_DOMAIN.format(
            project_context=PROJECT_CONTEXT_FASTAPI_TRANSFORMERS,
            schema_block=schema_block,
        )
    if slice_id == "dev_general_no_rag":
        return DATA_GENERATOR_PROMPT_DEV_GENERAL.format(schema_block=schema_block)
    if slice_id == "misleading_edge":
        return DATA_GENERATOR_PROMPT_MISLEADING_EDGE.format(schema_block=schema_block)
    raise ValueError(f"unknown slice: {slice_id!r}")


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```json"):
        t = t[7:]
    elif t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    return t.strip()


def _parse_json_array(raw: str) -> list:
    data = json.loads(_strip_json_fence(raw))
    if isinstance(data, dict):
        for v in data.values():
            if isinstance(v, list):
                return v
    return data if isinstance(data, list) else []


_bucket_seq: dict[str, int] = {b: 0 for b in SLICE_TO_BUCKET.values()}


def _finalize_row(row: dict, *, slice_id: str) -> dict:
    """补全 bucket、稳定 sample_id、兼容旧字段名。"""
    bucket = SLICE_TO_BUCKET[slice_id]
    row["bucket"] = bucket
    if row.get("query") is None and row.get("user_query") is not None:
        row["query"] = row["user_query"]
    _bucket_seq[bucket] = _bucket_seq.get(bucket, 0) + 1
    row["sample_id"] = f"{bucket}_{_bucket_seq[bucket]:04d}"
    row.setdefault("sft_phase", "2a_routing")
    return row


def _generate_gemini(
    prompt: str, *, model: str, batch_size: int, max_retries: int = 3
) -> list:
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise RuntimeError("请 pip install google-genai 并在 .env 配置 google_api_key") from e

    from src.config import settings

    api_key = settings.google_api_key.strip()
    if not api_key:
        raise RuntimeError("请在 .env 中配置 google_api_key（见 src/config.py）")

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=prompt,
        response_mime_type="application/json",
        temperature=1.0,
    )
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                config=config,
                contents=[
                    f"请生成本批共 {batch_size} 条，严格按 system 中的 Phase 2A 路由 Schema 与 decision_type 条数分配，只输出 JSON 数组。"
                ],
            )
            return _parse_json_array(response.text)
        except Exception as e:
            print(f"  [Gemini] 第 {attempt + 1} 次失败: {e}")
            if attempt < max_retries - 1:
                time.sleep((attempt + 1) * 4)
    return []


def _parse_segment_ratio(s: str) -> tuple[int, int, int]:
    parts = [p.strip() for p in s.split(",")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("segment-ratio 须为三个整数，逗号分隔，如 300,100,100 或 70,15,15")
    try:
        w = tuple(int(x) for x in parts)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e)) from e
    if any(x < 0 for x in w) or sum(w) == 0:
        raise argparse.ArgumentTypeError("segment-ratio 须为非负整数且和大于 0")
    return w  # type: ignore[return-value]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 2A 路由 JSONL 生成（Gemini）")
    parser.add_argument(
        "--target",
        type=int,
        default=TARGET_TOTAL,
        help=f"生成总条数（默认 {TARGET_TOTAL}）",
    )
    parser.add_argument(
        "--segment-ratio",
        type=_parse_segment_ratio,
        default=DEFAULT_SEGMENT_WEIGHTS,
        metavar="W,W,W",
        help="三切片权重 private:dev_general:misleading，如 300,100,100（默认）或 70,15,15",
    )
    parser.add_argument(
        "--split-test",
        type=int,
        default=0,
        metavar="N",
        help="生成完成后按切片分层划分 N 条为测试集，写出 _train / _test；0 表示不划分",
    )
    parser.add_argument(
        "--split-seed",
        type=int,
        default=42,
        help="分层划分测试集时的随机种子（默认 42）",
    )
    parser.add_argument("--dry-run", action="store_true", help="只打印分批计划，不调 API")
    args = parser.parse_args()

    target_total = args.target
    weights: tuple[int, int, int] = args.segment_ratio
    split_test_n = args.split_test
    if split_test_n < 0 or split_test_n >= target_total:
        parser.error("--split-test 须满足 0 <= N < --target")

    batch_plan = _build_batch_plan(target_total, weights)
    expected_slice_totals = _expected_slice_totals_dict(target_total, weights)

    out_dir = ROOT / "experiments" / "data_flywheel" / "out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"ft_qa_{target_total}.jsonl"

    total = sum(n for _, n, _ in batch_plan)
    print(f"TARGET_TOTAL={target_total} | segment_ratio={weights} | 计划批次数: {len(batch_plan)}，总条数: {total}", flush=True)
    print("切片条数:", expected_slice_totals, flush=True)
    print("切片与 bucket: private_domain→domain, dev_general_no_rag→far_general, misleading_edge→misleading_edge", flush=True)
    print("各切片 MIX:", MIX_BY_SLICE, flush=True)
    if args.dry_run:
        for i, (prov, n, sid) in enumerate(batch_plan):
            label = SLICE_LABEL_ZH.get(sid, sid)
            b = SLICE_TO_BUCKET[sid]
            kc = _allocate_kind_counts(n, MIX_BY_SLICE[sid])
            print(
                f"  {i+1:02d} {prov} x {n} | {sid} → bucket={b} | kind_counts={kc}",
                flush=True,
            )
        if split_test_n:
            print(f"  [dry-run] 将划分测试集 split_test={split_test_n}，seed={args.split_seed}", flush=True)
        print("dry-run 结束。", flush=True)
        raise SystemExit(0)

    all_rows: list[dict] = []
    for bi, (provider, n, slice_id) in enumerate(batch_plan):
        scenario = random.choice(SCENARIOS)
        base = _base_prompt_for_slice(slice_id, n)
        prompt = base + (
            f"\n\n——————————————————————————————\n"
            f"【本批次语气与场景限制（仅影响 query 风格）】\n"
            f"以上 Phase 2A 路由规则与 Schema 仍然全部适用。下列场景用于统一**用户问题**的语气与人设（query 文本），"
            f"**不要**让 clarify_answer 变成身份表演或长篇客套；clarify_answer 仍须 1～2 句专业追问。\n"
            f"请基于以下场景生成这 {n} 条数据的 query，且 decision_type 条数与字段仍须符合 Schema：\n{scenario}"
        )

        print(f"\n>>> 批次 {bi + 1}/{len(batch_plan)} | {provider} | n={n} | slice={slice_id}", flush=True)
        print(f"    {SLICE_LABEL_ZH.get(slice_id, slice_id)} | kind配比 {_allocate_kind_counts(n, MIX_BY_SLICE[slice_id])}", flush=True)

        batch = _generate_gemini(prompt, model=GEMINI_MODEL, batch_size=n)

        if not batch:
            print("    本批无数据，跳过。", flush=True)
            continue

        if len(batch) > n:
            batch = batch[:n]
        for row in batch:
            if not isinstance(row, dict):
                continue
            _finalize_row(row, slice_id=slice_id)
            row["_meta"] = {
                "provider": provider,
                "batch_index": bi + 1,
                "scenario": scenario,
                "slice": slice_id,
                "slice_label_zh": SLICE_LABEL_ZH[slice_id],
                "sft_phase": "2a_routing",
            }
            all_rows.append(row)

        print(f"    本批得到 {len(batch)} 条，累计 {len(all_rows)}", flush=True)
        time.sleep(SLEEP_SECONDS)

    with open(out_path, "w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"\n完成，共写入 {len(all_rows)} 行 -> {out_path}", flush=True)

    if split_test_n:
        train_rows, test_rows = _stratified_train_test_split(
            all_rows,
            split_test_n,
            segment_counts=expected_slice_totals,
            seed=args.split_seed,
        )
        train_path = out_dir / f"ft_qa_{target_total}_train.jsonl"
        test_path = out_dir / f"ft_qa_{target_total}_test.jsonl"
        with open(train_path, "w", encoding="utf-8") as f:
            for row in train_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        with open(test_path, "w", encoding="utf-8") as f:
            for row in test_rows:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(
            f"分层划分（seed={args.split_seed}）: 训练 {len(train_rows)} -> {train_path.name} | "
            f"测试 {len(test_rows)} -> {test_path.name}",
            flush=True,
        )
