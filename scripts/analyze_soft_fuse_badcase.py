"""
从 eval_soft_fuse_phase1.py 落盘的 JSON 里抽取 bad case，写入 Markdown 报告。

域外三桶：far_general / term_near_no_rag / misleading_edge

用法：
  python scripts/analyze_soft_fuse_badcase.py
  python scripts/analyze_soft_fuse_badcase.py --json data/soft_fuse/soft_fuse_phase1_raw.json --out data/soft_fuse/soft_fuse_badcase_report.md --threshold 1.12
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--json", type=Path, default=ROOT / "data" / "soft_fuse" / "soft_fuse_phase1_raw.json")
    p.add_argument("--out", type=Path, default=ROOT / "data" / "soft_fuse" / "soft_fuse_badcase_report.md")
    p.add_argument("--threshold", type=float, default=1.12, help="用于列出该阈值下的误伤/漏拦 id")
    p.add_argument("--topk", type=int, default=12, help="每类最多列多少条")
    args = p.parse_args()

    data = json.loads(args.json.read_text(encoding="utf-8"))
    rows = data["rows"]

    by_split: dict[str, list[dict]] = {}
    for r in rows:
        by_split.setdefault(r["split"], []).append(r)

    dom = by_split.get("domain", [])
    far = by_split.get("far_general", [])
    term = by_split.get("term_near_no_rag", [])
    mis = by_split.get("misleading_edge", [])
    # 旧版 JSON 兼容
    if not far and by_split.get("dev_scenario"):
        far = by_split.get("dev_scenario", [])
        term = by_split.get("general", [])
        mis = by_split.get("misleading", [])
    out_all = far + term + mis

    dom_dists = [float(r["top1_distance"]) for r in dom]
    dmax = max(dom_dists) if dom_dists else 0.0
    dmin = min(dom_dists) if dom_dists else 0.0
    dmean = sum(dom_dists) / len(dom_dists) if dom_dists else 0.0

    lines: list[str] = []
    lines.append("# 软熔断 Phase1 Bad Case 报告\n")
    lines.append(f"- 数据源: `{args.json.as_posix()}`\n")
    lines.append(f"- 域内距离: min={dmin:.4f} max={dmax:.4f} mean={dmean:.4f}\n")
    lines.append(f"- 参考阈值: **{args.threshold}**（distance > 阈值 ⇒ 拦截）\n")

    dom_sorted_hi = sorted(dom, key=lambda x: float(x["top1_distance"]), reverse=True)[: args.topk]
    lines.append("\n## A. 域内 top1 距离偏高（软熔断易误伤 / 召回看起来「差」）\n")
    for r in dom_sorted_hi:
        lines.append(
            f"- **{r['id']}** dist={float(r['top1_distance']):.4f} src=`{r['top1_source']}`  \n  {r['query']}\n"
        )

    overlap = [r for r in out_all if float(r["top1_distance"]) <= dmax]
    overlap.sort(key=lambda x: float(x["top1_distance"]))
    lines.append(
        f"\n## B. 域外合并但距离 ≤ 域内 max({dmax:.4f}) — 与域内分布重叠\n"
    )
    lines.append(f"共 **{len(overlap)}** 条（含远域 / 术语近 / 误导 三桶）。\n")
    for r in overlap[: args.topk * 2]:
        lines.append(
            f"- **{r['id']}** ({r['split']}) dist={float(r['top1_distance']):.4f} src=`{r['top1_source']}`  \n  {r['query']}\n"
        )
    if len(overlap) > args.topk * 2:
        lines.append(f"\n… 其余 {len(overlap) - args.topk * 2} 条略。\n")

    term_sorted_lo = sorted(term, key=lambda x: float(x["top1_distance"]))[: args.topk]
    lines.append("\n## C. 术语接近不该查库 — top1 距离最低（易与仓库片段撞语义）\n")
    for r in term_sorted_lo:
        lines.append(
            f"- **{r['id']}** dist={float(r['top1_distance']):.4f} src=`{r['top1_source']}`  \n  {r['query']}\n"
        )

    far_sorted_lo = sorted(far, key=lambda x: float(x["top1_distance"]))[: args.topk]
    lines.append("\n## D. 明显通用远域 — top1 距离最低（远域桶内仍「像库内」的条目）\n")
    for r in far_sorted_lo:
        lines.append(
            f"- **{r['id']}** dist={float(r['top1_distance']):.4f} src=`{r['top1_source']}`  \n  {r['query']}\n"
        )

    mis_sorted_lo = sorted(mis, key=lambda x: float(x["top1_distance"]))[: args.topk]
    lines.append("\n## E. 误导边界 — top1 距离最低（诱导查库时向量仍很近）\n")
    for r in mis_sorted_lo:
        lines.append(
            f"- **{r['id']}** dist={float(r['top1_distance']):.4f} src=`{r['top1_source']}`  \n  {r['query']}\n"
        )

    T = args.threshold
    priv_block = [r for r in dom if float(r["top1_distance"]) > T]
    out_miss = [r for r in out_all if float(r["top1_distance"]) <= T]

    lines.append(f"\n## F. 阈值 T={T} 下的明细（域内 vs 域外合并）\n")
    lines.append(f"- 域内被拦 (**误伤**): {len(priv_block)}/{len(dom)}\n")
    for r in priv_block:
        lines.append(f"  - {r['id']} dist={float(r['top1_distance']):.4f} — {r['query'][:80]}…\n")
    lines.append(f"- 域外未拦 (**漏拦**): {len(out_miss)}/{len(out_all)}\n")
    for r in out_miss:
        lines.append(
            f"  - {r['id']} ({r['split']}) dist={float(r['top1_distance']):.4f} — {r['query'][:80]}…\n"
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(lines), encoding="utf-8")
    print(f"已写入 {args.out} ({len(lines)} 行)")


if __name__ == "__main__":
    main()
