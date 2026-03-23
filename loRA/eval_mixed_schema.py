"""
混合监督（tool_call / direct_answer / clarify）与 Phase 2A 路由（decision_type）评测骨架。

与 eval_lora.py 的差异：
- 金标可为工具 JSON，也可为纯中文（直答/澄清）；Phase 2A 为单行路由 JSON（decision_type + …）。
- 按 response_kind / decision_type 与 bucket 分桶统计；
- 文本类预留 LLM-as-judge 钩子（默认不调用，仅占位）。

推荐输入：ft_qa_*.jsonl（Phase 2A 含 decision_type）；旧版含 response_kind、tool_name/arguments/direct_answer 等。
ShareGPT JSON 数组：assistant 能 json.loads 且含 decision_type → Phase 2A；含 name → tool_call；否则整段视为文本金标。

用法：在仓库根目录执行（需与本机模型路径一致）：
  python loRA/eval_mixed_schema.py

仅统计分布、不加载模型（快速自检数据）：
  python loRA/eval_mixed_schema.py --dry-run
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import torch
from peft import PeftModel
from tqdm import tqdm
from transformers import AutoModelForCausalLM, AutoTokenizer, PreTrainedModel, PreTrainedTokenizer

# 与训练时 system 对齐：混合数据请用 True
USE_MIXED_SYSTEM = True

# 路径按本机修改
BASE_MODEL_PATH = "/root/autodl-tmp/models/qwen/Qwen2.5-7B-Instruct"
LORA_WEIGHT_PATH = "/root/LLaMA-Factory/saves/Qwen2-7B-Instruct/lora/train_2026-03-12-05-39-51"
# JSONL（推荐）或 ShareGPT 的 .json 数组
TEST_DATA_PATH = str(Path(__file__).resolve().parent / "devagent_test_data.json")

_LORA_DIR = Path(__file__).resolve().parent
if str(_LORA_DIR) not in sys.path:
    sys.path.insert(0, str(_LORA_DIR))

from format_to_sharegpt import (
    FINAL_SYSTEM_PROMPT,
    MIXED_SYSTEM_PROMPT,
    PHASE_2A_ROUTING_SYSTEM_PROMPT,
)

ALLOWED_TOOLS = frozenset(
    {
        "analyse_code",
        "complete_code",
        "generate_tests",
        "generate_dockerfile",
        "analyse_log",
        "search_codebase",
    }
)


def _default_system() -> str:
    return MIXED_SYSTEM_PROMPT if USE_MIXED_SYSTEM else FINAL_SYSTEM_PROMPT


def load_eval_items(path: str | Path) -> list[dict]:
    """统一为 dict 列表，至少含 query、response_kind、以及各 kind 对应金标字段。"""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(p)

    if p.suffix.lower() == ".jsonl":
        rows: list[dict] = []
        with open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                rows.append(json.loads(line))
        return [_normalize_raw_item(r) for r in rows]

    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list) and data and "conversations" in data[0]:
        return [_sharegpt_to_item(c) for c in data]
    raise ValueError("仅支持 .jsonl 或 ShareGPT 格式的 .json 数组")


def _normalize_raw_item(r: dict) -> dict:
    q = r.get("query") or r.get("user_query")
    if q is None:
        raise ValueError("缺少 query / user_query")
    if r.get("decision_type") is not None:
        dt = r["decision_type"]
        out: dict = {
            "query": q,
            "response_kind": "phase_2a",
            "decision_type": dt,
            "bucket": r.get("bucket"),
            "system": r.get("system") or PHASE_2A_ROUTING_SYSTEM_PROMPT,
        }
        if dt == "tool_call":
            out["expected_tool"] = r.get("tool_name")
            out["expected_arguments"] = r.get("arguments")
        elif dt == "clarify_needed":
            out["gold_text"] = r.get("clarify_answer") or ""
        return out
    kind = r.get("response_kind", "tool_call")
    out = {
        "query": q,
        "response_kind": kind,
        "bucket": r.get("bucket"),
        "system": r.get("system") or _default_system(),
    }
    if kind == "tool_call":
        out["expected_tool"] = r.get("tool_name")
        out["expected_arguments"] = r.get("arguments")
    elif kind in ("direct_answer", "clarify"):
        out["gold_text"] = r.get("direct_answer")
    else:
        raise ValueError(f"未知 response_kind: {kind!r}")
    return out


def _sharegpt_to_item(case: dict) -> dict:
    conv = case["conversations"]
    system = conv[0]["value"]
    user = conv[1]["value"]
    gold = conv[2]["value"]
    try:
        g = json.loads(gold.strip())
        if isinstance(g, dict) and g.get("decision_type") in (
            "tool_call",
            "no_tool",
            "clarify_needed",
        ):
            dt = g["decision_type"]
            base = {
                "query": user,
                "response_kind": "phase_2a",
                "decision_type": dt,
                "system": system,
                "bucket": None,
            }
            if dt == "tool_call":
                base["expected_tool"] = g.get("tool_name")
                base["expected_arguments"] = g.get("arguments") or {}
            elif dt == "clarify_needed":
                base["gold_text"] = g.get("clarify_answer") or ""
            return base
        if isinstance(g, dict) and g.get("name") in ALLOWED_TOOLS:
            return {
                "query": user,
                "response_kind": "tool_call",
                "expected_tool": g["name"],
                "expected_arguments": g.get("arguments") or {},
                "system": system,
                "bucket": None,
            }
    except json.JSONDecodeError:
        pass
    return {
        "query": user,
        "response_kind": "direct_answer",
        "gold_text": gold,
        "system": system,
        "bucket": None,
    }


def text_judge_placeholder(gold: str, pred: str) -> bool | None:
    """
    TODO: 接入 LLM judge、关键词、或 embedding 相似度。
    返回 True/False 计入 text_judge_pass；None 表示跳过（不计分母）。
    """
    _ = gold, pred
    return None


def score_phase2a_output(
    raw: str,
    *,
    gold_decision: str,
    expected_tool: str | None,
) -> tuple[bool, bool, bool, bool]:
    """
    返回 (json_ok, decision_match, tool_match_on_subset, bad_tool_name)。
    decision_match: pred.decision_type == gold_decision。
    tool_match_on_subset: 仅当 gold 为 tool_call 时比较 tool_name。
    """
    try:
        parsed = json.loads(raw.strip())
    except json.JSONDecodeError:
        return False, False, False, False
    if not isinstance(parsed, dict):
        return False, False, False, False
    pred_dt = parsed.get("decision_type")
    json_ok = pred_dt is not None
    dec_ok = pred_dt == gold_decision
    if gold_decision != "tool_call":
        return json_ok, dec_ok, False, False
    name = parsed.get("tool_name")
    tool_ok = name == expected_tool
    bad = name not in ALLOWED_TOOLS if name is not None else True
    return json_ok, dec_ok, tool_ok, bad


def score_tool_output(
    raw: str,
    *,
    expected_tool: str | None,
    expected_arguments: dict | None,
) -> tuple[bool, bool, bool]:
    """
    返回 (format_ok, tool_match, bad_tool_name)。
    format_ok: 能解析为含 name 的 JSON；tool_match: name 与金标一致；bad_tool_name: name 不在允许列表。
    """
    try:
        parsed = json.loads(raw.strip())
    except json.JSONDecodeError:
        return False, False, False
    if not isinstance(parsed, dict):
        return False, False, False
    name = parsed.get("name")
    if name is None:
        return False, False, False
    fmt_ok = True
    match = name == expected_tool
    bad = name not in ALLOWED_TOOLS
    _ = expected_arguments  # TODO: 参数子集匹配 / 关键键一致
    return fmt_ok, match, bad


def dry_run_counts(items: list[dict]) -> None:
    by_kind: dict[str, int] = defaultdict(int)
    by_bucket: dict[str, int] = defaultdict(int)
    by_decision: dict[str, int] = defaultdict(int)
    for it in items:
        by_kind[it["response_kind"]] += 1
        b = it.get("bucket")
        if b:
            by_bucket[b] += 1
        dt = it.get("decision_type")
        if dt:
            by_decision[dt] += 1
    print("[dry-run] 条数:", len(items))
    print("[dry-run] by response_kind:", dict(by_kind))
    if by_decision:
        print("[dry-run] by decision_type (Phase 2A):", dict(by_decision))
    print("[dry-run] by bucket:", dict(by_bucket))


def run_eval() -> None:
    items = load_eval_items(TEST_DATA_PATH)
    print("正在加载分词器与模型…")
    tokenizer: PreTrainedTokenizer = AutoTokenizer.from_pretrained(
        BASE_MODEL_PATH, trust_remote_code=True
    )
    model: PreTrainedModel = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_PATH,
        device_map="auto",
        trust_remote_code=True,
        torch_dtype=torch.bfloat16,
    )
    model = PeftModel.from_pretrained(model, LORA_WEIGHT_PATH)
    model.eval()

    metrics: dict = {
        "tool_call": defaultdict(int),
        "direct_answer": defaultdict(int),
        "clarify": defaultdict(int),
        "phase_2a": defaultdict(int),
    }

    for it in tqdm(items, desc="eval"):
        kind = it["response_kind"]
        system = it["system"]
        user = it["query"]

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        model_input = tokenizer([text], return_tensors="pt").to(model.device)

        with torch.no_grad():
            generated_ids = model.generate(
                **model_input,
                max_new_tokens=512,
                temperature=0.1,
                do_sample=False,
            )
        out_ids = generated_ids[0][model_input.input_ids.shape[1] :]
        raw = tokenizer.decode(out_ids, skip_special_tokens=True)

        if kind == "phase_2a":
            gold_dt = it["decision_type"]
            exp_tool = it.get("expected_tool")
            json_ok, dec_ok, tool_ok, bad_tool = score_phase2a_output(
                raw, gold_decision=gold_dt, expected_tool=exp_tool
            )
            metrics["phase_2a"]["n"] += 1
            if json_ok:
                metrics["phase_2a"]["json_ok"] += 1
            if dec_ok:
                metrics["phase_2a"]["decision_match"] += 1
            if gold_dt == "tool_call" and tool_ok:
                metrics["phase_2a"]["tool_match"] += 1
            if bad_tool and json_ok and gold_dt == "tool_call":
                metrics["phase_2a"]["bad_tool_name"] += 1
        elif kind == "tool_call":
            exp_tool = it.get("expected_tool")
            exp_args = it.get("expected_arguments")
            fmt_ok, tool_match, bad_tool = score_tool_output(
                raw, expected_tool=exp_tool, expected_arguments=exp_args
            )
            metrics["tool_call"]["n"] += 1
            if fmt_ok:
                metrics["tool_call"]["format_ok"] += 1
            if tool_match:
                metrics["tool_call"]["tool_match"] += 1
            if bad_tool and fmt_ok:
                metrics["tool_call"]["hallucination"] += 1
        elif kind == "direct_answer":
            metrics["direct_answer"]["n"] += 1
            gold = it.get("gold_text") or ""
            if raw.strip():
                metrics["direct_answer"]["non_empty"] += 1
            judge = text_judge_placeholder(gold, raw)
            if judge is True:
                metrics["direct_answer"]["judge_pass"] += 1
            elif judge is False:
                metrics["direct_answer"]["judge_fail"] += 1
        elif kind == "clarify":
            metrics["clarify"]["n"] += 1
            gold = it.get("gold_text") or ""
            if raw.strip():
                metrics["clarify"]["non_empty"] += 1
            judge = text_judge_placeholder(gold, raw)
            if judge is True:
                metrics["clarify"]["judge_pass"] += 1
            elif judge is False:
                metrics["clarify"]["judge_fail"] += 1

    print("\n====== 混合 Schema 评测（骨架）======")
    for k in ("phase_2a", "tool_call", "direct_answer", "clarify"):
        m = metrics[k]
        if dict(m):
            print(f"\n[{k}] {dict(m)}")
    print("\n说明：direct_answer / clarify 的 judge_* 需在 text_judge_placeholder 中实现后才可信。")
    print("=" * 50)


if __name__ == "__main__":
    if "--dry-run" in sys.argv:
        dry_run_counts(load_eval_items(TEST_DATA_PATH))
    else:
        run_eval()
