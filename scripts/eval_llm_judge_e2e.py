"""
对 E2E JSONL 跑 LLM-as-a-Judge（第三层）。

用法（项目根，需 .env 中 DeepSeek）：
  python scripts/eval_llm_judge_e2e.py --jsonl data/e2e_eval_log_promptv2.jsonl
  python scripts/eval_llm_judge_e2e.py --jsonl data/e2e_eval_log_promptv2.jsonl --full --out data/eval/e2e_llm_judge_full.jsonl
  # 使用 manifest 的 grounding_tier_index_aware 作为 Judge Gold（与 chroma 可达性对齐），**新文件**不覆盖 round2
  python scripts/eval_llm_judge_e2e.py --jsonl data/e2e_eval_log_promptv2.jsonl --full --index-aware
  python scripts/eval_llm_judge_e2e.py --jsonl data/e2e_eval_log_promptv2.jsonl --dry-run
  # 并发调用 Judge API（默认 1；大评测可试 4～8，视 DeepSeek 限流调整）
  python scripts/eval_llm_judge_e2e.py --jsonl data/e2e_eval_log_promptv2.jsonl --full --index-aware --workers 6
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agent.llm import chat_completion
from src.evaluation.e2e_manifest import build_e2e_manifest
from src.evaluation.llm_judge_e2e import (
    PHASE1_JUDGE_SAMPLE_IDS,
    all_manifest_sample_ids,
    build_judge_messages,
    parse_judge_json,
    validate_judge_output,
)


def _load_jsonl_by_id(path: Path) -> dict[str, dict]:
    by_id: dict[str, dict] = {}
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            by_id[rec["sample_id"]] = rec
    return by_id


def main() -> None:
    p = argparse.ArgumentParser(description="LLM-as-judge on E2E JSONL (phase1 sample or full 90)")
    p.add_argument("--jsonl", type=Path, required=True, help="e2e_eval_log*.jsonl")
    p.add_argument(
        "--full",
        action="store_true",
        help="评测 manifest 全量 90 条（覆盖默认的 Phase1 抽样 22 条）",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="输出 JSONL（默认：phase1 -> data/eval/e2e_llm_judge_phase1.jsonl；--full -> data/eval/e2e_llm_judge_full.jsonl）",
    )
    p.add_argument("--dry-run", action="store_true", help="只打印 prompt 条数，不调 API")
    p.add_argument(
        "--index-aware",
        action="store_true",
        help="Judge prompt 使用 grounding_tier_index_aware（需已生成 data/chroma_verified_skip_must_ground.json 等合并进 manifest）",
    )
    p.add_argument("--max-tokens", type=int, default=1200)
    p.add_argument("--temperature", type=float, default=0.1)
    p.add_argument(
        "--workers",
        type=int,
        default=1,
        metavar="N",
        help="并发线程数（仅非 dry-run）。每条 Judge 相互独立；>1 可显著缩短总耗时，但需遵守 API 限流（建议 4～8 试起）",
    )
    args = p.parse_args()

    sample_ids = all_manifest_sample_ids() if args.full else PHASE1_JUDGE_SAMPLE_IDS
    manifest_by_id = {r["id"]: r for r in build_e2e_manifest()}
    eval_dir = ROOT / "data" / "eval"
    out_path = args.out
    if out_path is None:
        if args.full and args.index_aware:
            out_path = ROOT / "data" / "e2e_llm_judge_full_round2_index_aware.jsonl"
        else:
            out_path = (
                eval_dir / "e2e_llm_judge_full.jsonl"
                if args.full
                else eval_dir / "e2e_llm_judge_phase1.jsonl"
            )

    if not args.jsonl.is_file():
        print(f"文件不存在: {args.jsonl}", file=sys.stderr)
        sys.exit(1)

    by_id = _load_jsonl_by_id(args.jsonl.resolve())
    missing = [s for s in sample_ids if s not in by_id]
    if missing:
        print(f"JSONL 中缺少 sample_id（共 {len(missing)} 个）: {missing[:20]}...", file=sys.stderr)
        sys.exit(1)

    if args.dry_run:
        print(
            f"将评测 {len(sample_ids)} 条（{'full 90' if args.full else 'phase1 22'}）"
            f"，index_aware={args.index_aware}，workers={args.workers}，out={out_path}"
        )
        for sid in sample_ids[:1]:
            msgs = build_judge_messages(by_id[sid], use_index_aware_tier=args.index_aware)
            print("--- user Gold 片段（含 tier）---\n", msgs[1]["content"][:900], "...\n")
        return

    out_path.parent.mkdir(parents=True, exist_ok=True)

    def _judge_one(sid: str) -> dict:
        rec = by_id[sid]
        messages = build_judge_messages(rec, use_index_aware_tier=args.index_aware)
        msg = None
        try:
            msg = chat_completion(
                messages,
                max_tokens=args.max_tokens,
                temperature=args.temperature,
                tools=None,
            )
            raw = (msg.content or "").strip()
            obj = parse_judge_json(raw)
            validate_judge_output(obj)
        except Exception as e:
            return {
                "sample_id": sid,
                "error": str(e),
                "raw_judge_output": ((msg.content or "") if msg else "")[:2000],
                "_ok": False,
            }
        m = manifest_by_id.get(sid, {})
        gt_legacy = m.get("grounding_tier")
        gt_ia = m.get("grounding_tier_index_aware", gt_legacy)
        if args.index_aware:
            gt_out = gt_ia
        else:
            gt_out = rec.get("grounding_tier") or gt_legacy
        out: dict = {
            "sample_id": sid,
            "bucket_type": rec.get("bucket_type"),
            "grounding_tier": gt_out,
            "judge_gold_mode": "index_aware" if args.index_aware else "legacy",
            "question": rec.get("question"),
            "actual_call_search_codebase": rec.get("actual_call_search_codebase"),
            "top1_distance": rec.get("top1_distance"),
            "soft_fallback_triggered": rec.get("soft_fallback_triggered"),
            **obj,
        }
        if args.index_aware:
            out["grounding_tier_original"] = gt_legacy
        out["_ok"] = True
        out["_fj"] = obj.get("final_judgement")
        out["_sc"] = obj.get("score")
        return out

    rows: list[dict] = []
    if args.workers <= 1:
        for sid in sample_ids:
            rows.append(_judge_one(sid))
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(_judge_one, sid) for sid in sample_ids]
            for fut in futs:
                rows.append(fut.result())

    ok = 0
    err = 0
    with out_path.open("w", encoding="utf-8") as fp:
        for row in rows:
            sid = row["sample_id"]
            if not row.pop("_ok", True):
                err += 1
                row.pop("_fj", None)
                row.pop("_sc", None)
                fp.write(json.dumps(row, ensure_ascii=False) + "\n")
                fp.flush()
                print(f"[fail] {sid}: {row.get('error')}", file=sys.stderr)
                continue
            row.pop("_fj", None)
            row.pop("_sc", None)
            ok += 1
            fj = row.get("final_judgement")
            sc = row.get("score")
            fp.write(json.dumps(row, ensure_ascii=False) + "\n")
            fp.flush()
            print(f"[ok] {ok}/{len(sample_ids)} {sid} -> {fj} score={sc}", flush=True)

    print(f"\n完成: 成功 {ok}, 失败 {err}, 写入 {out_path}")


if __name__ == "__main__":
    main()
