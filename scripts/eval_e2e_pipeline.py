"""
轻量级端到端评测：Query → 工具决策 → 检索(+软熔断) → 最终回答，并落盘 JSONL 链路日志。

依赖：.env 已配置 DeepSeek + Qwen 嵌入；已建向量库。

用法（项目根）：
  python scripts/eval_e2e_pipeline.py --limit 5
  python scripts/eval_e2e_pipeline.py --soft-fuse --soft-fuse-threshold 1.12 --jsonl-out data/e2e_eval_log.jsonl
  python scripts/eval_e2e_pipeline.py --bucket domain --limit 10

指标（终端摘要）：
  第一层 Tool Decision：与 should_call_tool 对照（yes/no/optional）；optional=prefer_ground，调与不调均计为正确。
  子集「仅 must_ground」：应检索条数、已检索数、未检索(FN)、检索率。
  第二层（仅实际发生 search_codebase 的样本）：软熔断触发率、与 should_soft_fallback_if_searched 的对照
  第三层 final_judgement / final_answer_type 默认 pending，供人工或后续 LLM-as-judge 补全
"""
from __future__ import annotations

import argparse
import json
import sys
from contextlib import ExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agent.core import DevAgent
from src.config import settings
from src.evaluation.e2e_manifest import build_e2e_manifest


def _extract_search_from_trace(trace: list | None) -> tuple[bool, float | None, bool | None]:
    """是否调用了 search_codebase；最后一次的 top1_distance、soft_fuse_triggered。"""
    if not trace:
        return False, None, None
    called = False
    top1: float | None = None
    fused: bool | None = None
    for ev in trace:
        if not isinstance(ev, dict):
            continue
        if ev.get("tool_name") == "search_codebase":
            called = True
            sp = ev.get("search_payload")
            if isinstance(sp, dict):
                top1 = sp.get("top1_distance")
                if top1 is not None:
                    top1 = float(top1)
                fused = sp.get("soft_fuse_triggered")
    return called, top1, fused


def _tool_names_from_trace(trace: list | None) -> list[str]:
    names: list[str] = []
    if not trace:
        return names
    for ev in trace:
        if isinstance(ev, dict) and ev.get("event") == "assistant_tool_calls":
            names.extend(ev.get("names") or [])
    return names


def main() -> None:
    parser = argparse.ArgumentParser(description="DevAgent E2E pipeline eval (JSONL trace)")
    parser.add_argument("--limit", type=int, default=0, help="0 = 跑 manifest 全部样本")
    parser.add_argument(
        "--bucket",
        type=str,
        default="all",
        choices=["all", "domain", "far_general", "term_near_no_rag", "misleading_edge"],
    )
    parser.add_argument("--jsonl-out", type=Path, default=ROOT / "data" / "e2e_eval_log.jsonl")
    parser.add_argument("--soft-fuse", action="store_true", help="启用 config 软熔断（需阈值）")
    parser.add_argument("--soft-fuse-threshold", type=float, default=1.12)
    args = parser.parse_args()

    manifest = build_e2e_manifest()
    if args.bucket != "all":
        manifest = [m for m in manifest if m["bucket_type"] == args.bucket]
    if args.limit > 0:
        manifest = manifest[: args.limit]

    jsonl_path = args.jsonl_out
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    from unittest.mock import patch as mock_patch

    stack = ExitStack()
    if args.soft_fuse:
        stack.enter_context(mock_patch.object(settings, "soft_fuse_enabled", True))
        stack.enter_context(mock_patch.object(settings, "soft_fuse_distance_threshold", args.soft_fuse_threshold))
    else:
        stack.enter_context(mock_patch.object(settings, "soft_fuse_enabled", False))
        stack.enter_context(mock_patch.object(settings, "soft_fuse_distance_threshold", None))

    l1_correct = 0
    l1_fp = 0
    l1_fn = 0
    must_n = 0
    must_ok = 0
    must_fn = 0
    l2_searched = 0
    l2_fuse_expected_and_triggered = 0
    l2_fuse_expected = 0

    with stack:
        with jsonl_path.open("w", encoding="utf-8") as fp_out:
            for row in manifest:
                q = row["query"]
                agent = DevAgent()
                agent.clear_memory()
                trace: list = []
                try:
                    final_text = agent.chat(q, trace=trace)
                except Exception as e:
                    final_text = f"[eval_error] {e}"

                actual_call, top1_dist, soft_fb = _extract_search_from_trace(trace)
                expect = row["should_call_tool"]
                if expect == "optional":
                    l1_correct += 1
                elif expect == "yes":
                    if actual_call:
                        l1_correct += 1
                    else:
                        l1_fn += 1
                elif expect == "no":
                    if not actual_call:
                        l1_correct += 1
                    else:
                        l1_fp += 1

                gt = row.get("grounding_tier")
                if gt == "must_ground":
                    must_n += 1
                    if actual_call:
                        must_ok += 1
                    else:
                        must_fn += 1

                if actual_call:
                    l2_searched += 1
                    if row["should_soft_fallback_if_searched"] == "yes":
                        l2_fuse_expected += 1
                        if soft_fb is True:
                            l2_fuse_expected_and_triggered += 1

                record = {
                    "question": q,
                    "sample_id": row["id"],
                    "bucket_type": row["bucket_type"],
                    "grounding_tier": row.get("grounding_tier"),
                    "should_call_tool": row["should_call_tool"],
                    "actual_call_search_codebase": actual_call,
                    "tool_names_round": _tool_names_from_trace(trace),
                    "should_hit_private_knowledge": row["should_hit_private_knowledge"],
                    "should_soft_fallback_if_searched": row["should_soft_fallback_if_searched"],
                    "top1_distance": top1_dist,
                    "soft_fallback_triggered": soft_fb,
                    "final_answer_preview": (final_text or "")[:1200],
                    "final_answer_type": "pending",
                    "final_judgement": "pending",
                    "trace_events": len(trace),
                    "soft_fuse_config": {
                        "enabled": args.soft_fuse,
                        "threshold": args.soft_fuse_threshold if args.soft_fuse else None,
                    },
                }
                fp_out.write(json.dumps(record, ensure_ascii=False) + "\n")

    n = len(manifest)
    print("\n=== 第一层：Tool Decision（search_codebase）===")
    print(f"  样本数: {n}")
    print(f"  决策与预期一致: {l1_correct}/{n}  ({(l1_correct/n*100 if n else 0):.1f}%)")
    print(f"  False Positive（不该调却调）: {l1_fp}")
    print(f"  False Negative（该调未调）: {l1_fn}")
    print("  —— 子集 grounding_tier=must_ground（应检索）——")
    print(f"  must_ground 条数: {must_n}  |  已检索: {must_ok}  |  未检索(FN): {must_fn}")
    if must_n:
        print(f"  must_ground 检索率: {100.0 * must_ok / must_n:.1f}%")

    print("\n=== 第二层：检索 + 软熔断（仅 actual_call_search_codebase 的样本）===")
    print(f"  实际触发检索次数: {l2_searched}")
    print(f"  其中「预期应软熔断」的样本数: {l2_fuse_expected}")
    if l2_fuse_expected:
        print(
            f"  预期应熔断且已熔断: {l2_fuse_expected_and_triggered}/{l2_fuse_expected}  "
            f"({100.0 * l2_fuse_expected_and_triggered / l2_fuse_expected:.1f}%)"
        )
    else:
        print("  预期应熔断且已熔断: N/A（无「误调检索且预期熔断」样本）")

    print("\n=== 第三层：最终回答 ===")
    print("  final_judgement / final_answer_type 默认为 pending，请对 JSONL 人工标注或接 LLM-as-judge。")

    print(f"\n已写入 {jsonl_path}")


if __name__ == "__main__":
    main()
