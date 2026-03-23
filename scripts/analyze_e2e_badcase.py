"""
从 e2e_eval_log*.jsonl 按当前 manifest 抽取 bad case，输出 Markdown（可落盘）。

类别：
  - L1 FP：gold 不应检索却调了 search_codebase
  - L1 FN：gold 应检索（yes）却未调（optional 不计 FN）
  - L2 软熔断：在「应熔断」子集内，区分已熔断 / 未熔断（distance 与阈值关系）

用法：
  python scripts/analyze_e2e_badcase.py data/e2e_eval_log_promptv2.jsonl
  python scripts/analyze_e2e_badcase.py data/e2e_eval_log.jsonl --out data/e2e_badcase_fp_baseline.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import settings
from src.evaluation.e2e_manifest import build_e2e_manifest


def _l1(actual: bool, expect: str) -> tuple[bool, str]:
    if expect == "optional":
        return True, "none"
    if expect == "yes":
        return (True, "none") if actual else (False, "fn")
    if expect == "no":
        return (True, "none") if not actual else (False, "fp")
    raise ValueError(expect)


def _threshold_from_jsonl(rows: list[dict]) -> float | None:
    for rec in rows:
        cfg = rec.get("soft_fuse_config")
        if isinstance(cfg, dict) and cfg.get("threshold") is not None:
            return float(cfg["threshold"])
    t = getattr(settings, "soft_fuse_distance_threshold", None)
    return float(t) if t is not None else None


def analyze(path: Path) -> dict:
    gold = {r["id"]: r for r in build_e2e_manifest()}
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    threshold = _threshold_from_jsonl(rows)

    fp: list[dict] = []
    fn: list[dict] = []
    fuse_rows: list[dict] = []

    for rec in rows:
        sid = rec["sample_id"]
        g = gold[sid]
        actual = bool(rec.get("actual_call_search_codebase"))
        expect = g["should_call_tool"]
        ok, err = _l1(actual, expect)
        if err == "fp":
            fp.append({"rec": rec, "gold": g})
        elif err == "fn":
            fn.append({"rec": rec, "gold": g})

        if actual and g.get("should_soft_fallback_if_searched") == "yes":
            top1 = rec.get("top1_distance")
            soft = rec.get("soft_fallback_triggered")
            fuse_rows.append(
                {
                    "sample_id": sid,
                    "bucket": rec.get("bucket_type"),
                    "top1_distance": top1,
                    "soft_fallback_triggered": soft,
                    "l1_fp": err == "fp",
                }
            )

    return {
        "path": path,
        "n": len(rows),
        "fp": fp,
        "fn": fn,
        "fuse_rows": fuse_rows,
        "threshold": threshold,
    }


def to_markdown(result: dict, title: str, *, compact_fp: bool = False) -> str:
    th = result.get("threshold")
    th_s = str(th) if th is not None else "（见 JSONL soft_fuse_config）"
    path_disp = result["path"].name
    lines: list[str] = []
    lines.append(f"## {title}\n")
    lines.append(f"- **文件**：`data/{path_disp}`\n")
    lines.append(f"- **样本数**：{result['n']}\n")
    lines.append(f"- **软熔断阈值（文档/默认）**：T = {th_s}（与 `eval_e2e_pipeline --soft-fuse-threshold` 一致时 Chroma distance > T 记为触发）\n")

    lines.append("\n### L1 False Positive（不应检索却检索）\n")
    if not result["fp"]:
        lines.append("*（无）*\n")
    elif compact_fp:
        lines.append(f"共 **{len(result['fp'])}** 条（紧凑表）。\n\n")
        lines.append("| sample_id | bucket | top1_distance | soft_fallback | vs T |\n")
        lines.append("|-----------|--------|---------------|---------------|------|\n")
        for item in result["fp"]:
            rec = item["rec"]
            top1 = rec.get("top1_distance")
            sfb = rec.get("soft_fallback_triggered")
            cmp_t = "—"
            if top1 is not None and th is not None:
                cmp_t = ">" if float(top1) > float(th) else "≤"  # type: ignore[arg-type]
            lines.append(
                f"| `{rec['sample_id']}` | {rec.get('bucket_type')} | {top1} | {sfb} | {cmp_t} {th_s} |\n"
            )
        lines.append("\n")
    else:
        lines.append(f"共 **{len(result['fp'])}** 条。\n")
        for item in result["fp"]:
            rec, g = item["rec"], item["gold"]
            sid = rec["sample_id"]
            q = rec.get("question", "")
            top1 = rec.get("top1_distance")
            sfb = rec.get("soft_fallback_triggered")
            lines.append(f"\n#### `{sid}`（{rec.get('bucket_type')}）\n")
            lines.append(f"- **题面**：{q}\n")
            lines.append(
                f"- **gold**：`should_call_tool=no`，`should_soft_fallback_if_searched=yes`（域外误调后**预期**走软兜底）\n"
            )
            lines.append(f"- **实际**：已调用 `search_codebase`；`top1_distance`={top1}；`soft_fallback_triggered`={sfb}\n")
            if top1 is not None and th is not None:
                if float(top1) > float(th):  # type: ignore[arg-type]
                    lines.append(
                        f"- **解读**：距离 **>** T，软熔断**已触发**，回答转向通用知识，但**第一层仍计 FP**（根本问题是不该调检索）。\n"
                    )
                else:
                    lines.append(
                        f"- **解读**：距离 **≤** T，软熔断**未触发**，检索结果仍进入上下文，**双层风险**（误调 + 未熔断）。\n"
                    )
            lines.append(
                f"- **摘要**：{rec.get('final_answer_preview', '')[:280].replace(chr(10), ' ')}…\n"
            )

    lines.append("\n### L1 False Negative（应检索却未检索，`should_call_tool=yes`）\n")
    if not result["fn"]:
        lines.append("*（无）*\n")
    else:
        for item in result["fn"]:
            rec = item["rec"]
            lines.append(f"- `{rec['sample_id']}`：{rec.get('question', '')[:80]}…\n")

    lines.append("\n### L2 软熔断子集（实际检索 + gold 要求误调应熔断）\n")
    if not result["fuse_rows"]:
        lines.append("*（无实际检索或无不适用）*\n")
    else:
        lines.append("| sample_id | bucket | top1_distance | soft_fallback_triggered | 同时是 L1 FP |\n")
        lines.append("|-----------|--------|---------------|-------------------------|-------------|\n")
        for fr in result["fuse_rows"]:
            lines.append(
                f"| `{fr['sample_id']}` | {fr['bucket']} | {fr['top1_distance']} | {fr['soft_fallback_triggered']} | {fr['l1_fp']} |\n"
            )
        fused = sum(1 for x in result["fuse_rows"] if x["soft_fallback_triggered"] is True)
        exp = len(result["fuse_rows"])
        lines.append(f"\n子集内已熔断 **{fused}/{exp}**。\n")

    return "".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description="E2E bad-case markdown from JSONL + current manifest")
    p.add_argument("jsonl", type=Path, help="e2e_eval_log*.jsonl")
    p.add_argument("--out", type=Path, default=None, help="写入 Markdown 文件（默认只打印 stdout）")
    p.add_argument("--title", type=str, default="Bad case 报告")
    p.add_argument(
        "--compact",
        action="store_true",
        help="L1 FP 用单表列出（适合首轮大量 FP），不写长解读",
    )
    args = p.parse_args()
    if not args.jsonl.is_file():
        print(f"文件不存在: {args.jsonl}", file=sys.stderr)
        sys.exit(1)
    r = analyze(args.jsonl.resolve())
    md = to_markdown(r, args.title, compact_fp=args.compact)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(md, encoding="utf-8")
        print(f"已写入 {args.out}", file=sys.stderr)
    print(md)


if __name__ == "__main__":
    main()
