"""
Phase 1：软熔断「后置过滤器」标定 — 不调用 LLM，仅强制 Dense top-1 距离分布。

数据规模：域内 40；域外 50（明显通用远域 28 + 术语接近不该查库 12 + 误导边界 10）— 共 90 条。

用法（项目根目录，已建库、已配置 .env）：
  python scripts/eval_soft_fuse_phase1.py
  python scripts/eval_soft_fuse_phase1.py --threshold 1.12
  python scripts/eval_soft_fuse_phase1.py --sweep 20
  python scripts/eval_soft_fuse_phase1.py --json-out data/soft_fuse/soft_fuse_phase1_raw.json

拦截规则：distance > threshold 视为触发软熔断。默认阈值标定使用「域内 40 vs 域外合并 50」。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.soft_fuse_dataset import (
    DOMAIN_IN_PROJECT,
    OUTDOMAIN_FAR_GENERAL,
    OUTDOMAIN_MISLEADING_EDGE,
    OUTDOMAIN_TERM_NEAR_NO_RAG,
)
from src.rag.vectorstore import VectorStore


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    if p <= 0:
        return sorted_vals[0]
    if p >= 100:
        return sorted_vals[-1]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def _summarize(name: str, distances: list[float]) -> None:
    s = sorted(distances)
    print(f"\n--- {name} (n={len(distances)}) ---")
    print(f"  min={min(s):.6f}  max={max(s):.6f}  mean={mean(s):.6f}  median={median(s):.6f}")
    print(
        f"  p25={_percentile(s, 25):.6f}  p50={_percentile(s, 50):.6f}  "
        f"p75={_percentile(s, 75):.6f}  p95={_percentile(s, 95):.6f}"
    )


def _metrics_at_threshold(
    private_dists: list[float], generic_dists: list[float], threshold: float
) -> dict:
    """域外池：拦截率越高越好；域内：误伤率越低越好。"""
    gen_block = sum(1 for d in generic_dists if d > threshold)
    priv_block = sum(1 for d in private_dists if d > threshold)
    return {
        "threshold": threshold,
        "outdomain_interception_rate": gen_block / len(generic_dists) if generic_dists else 0.0,
        "private_false_block_rate": priv_block / len(private_dists) if private_dists else 0.0,
        "outdomain_intercepted": gen_block,
        "private_intercepted": priv_block,
    }


def _gap_line(label: str, private_dists: list[float], other_dists: list[float]) -> None:
    if not private_dists or not other_dists:
        return
    gap = min(other_dists) - max(private_dists)
    print(f"  {label}: min(外) - max(域内) = {gap:+.6f}")


def _collect_split(vs: VectorStore, items: list[dict], split_name: str) -> tuple[list[float], list[dict]]:
    dists: list[float] = []
    rows: list[dict] = []
    for item in items:
        q = item["query"]
        doc, dist = vs.dense_top1_with_distance(q)
        if dist is None:
            print(f"[WARN] {item['id']} ({split_name}) 无检索结果")
            continue
        dists.append(dist)
        src = str(doc.metadata.get("source", "")) if doc else ""
        rows.append(
            {
                "split": split_name,
                "id": item["id"],
                "query": q,
                "top1_distance": dist,
                "top1_source": src,
            }
        )
    return dists, rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Phase1 soft-fuse distance distribution (Dense top-1)")
    parser.add_argument(
        "--threshold",
        type=float,
        default=None,
        help="若设置：域内 vs 域外合并 50 条 的拦截率 / 误伤率",
    )
    parser.add_argument(
        "--sweep",
        type=int,
        default=0,
        metavar="N",
        help="在 [min,max] 距离上均匀取 N 个阈值并打印指标表（域内 vs 域外50）",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="将每条 query 的 top-1 距离与来源写入 JSON",
    )
    args = parser.parse_args()

    vs = VectorStore()
    vs.load()

    domain_d, rows_d = _collect_split(vs, DOMAIN_IN_PROJECT, "domain")
    far_d, rows_far = _collect_split(vs, OUTDOMAIN_FAR_GENERAL, "far_general")
    term_d, rows_term = _collect_split(vs, OUTDOMAIN_TERM_NEAR_NO_RAG, "term_near_no_rag")
    mis_d, rows_mis = _collect_split(vs, OUTDOMAIN_MISLEADING_EDGE, "misleading_edge")

    rows = rows_d + rows_far + rows_term + rows_mis
    outdomain_all = far_d + term_d + mis_d

    _summarize("域内 (domain)", domain_d)
    _summarize("域外·明显通用远域 (far_general)", far_d)
    _summarize("域外·术语接近不该查库 (term_near_no_rag)", term_d)
    _summarize("域外·误导边界 (misleading_edge)", mis_d)
    _summarize("域外·合并 (outdomain 50)", outdomain_all)

    all_d = domain_d + outdomain_all
    if all_d:
        _summarize("全部 90 条 (all)", all_d)

    print("\n--- 分布分离度 min(域外桶) - max(域内) ---")
    _gap_line("域外50 vs 域内", domain_d, outdomain_all)
    _gap_line("远域28 vs 域内", domain_d, far_d)
    _gap_line("术语近12 vs 域内", domain_d, term_d)
    _gap_line("误导边界10 vs 域内", domain_d, mis_d)

    if domain_d and outdomain_all:
        gap = min(outdomain_all) - max(domain_d)
        print("\n--- 标定提示（主阈值：域内 vs 域外50）---")
        if gap > 0:
            print("  正值：存在阈值可同时做到「域外50高拦截 + 域内低误伤」，可用 --sweep 扫一遍。")
        else:
            print("  非正：两类距离重叠，单靠 top-1 距离无法完美分开，需 Rerank/多信号或放宽指标。")

    if args.threshold is not None:
        m = _metrics_at_threshold(domain_d, outdomain_all, args.threshold)
        print("\n=== 阈值标定（distance > threshold 视为拦截）===")
        print(f"  对比：域内 {len(domain_d)} 条 vs 域外合并 {len(outdomain_all)} 条")
        print(f"  threshold = {m['threshold']:.6f}")
        print(
            f"  域外拦截率: {m['outdomain_interception_rate']*100:.1f}%  "
            f"({m['outdomain_intercepted']}/{len(outdomain_all)})"
        )
        print(
            f"  域内误伤率: {m['private_false_block_rate']*100:.1f}%  "
            f"({m['private_intercepted']}/{len(domain_d)})"
        )

    if args.sweep and args.sweep > 0 and domain_d and outdomain_all:
        lo, hi = min(domain_d + outdomain_all), max(domain_d + outdomain_all)
        print("\n=== 阈值扫描（域内 vs 域外50，均匀分桶）===")
        print(f"{'threshold':>12}  {'out_ir%':>10}  {'priv_fb%':>10}")
        for i in range(args.sweep):
            t = lo + (hi - lo) * i / max(args.sweep - 1, 1)
            m = _metrics_at_threshold(domain_d, outdomain_all, t)
            print(
                f"{m['threshold']:12.6f}  {m['outdomain_interception_rate']*100:10.1f}  "
                f"{m['private_false_block_rate']*100:10.1f}"
            )

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "metric_notes": {
                "rule": "intercept if top1_distance > threshold",
                "default_pair": "domain(40) vs outdomain(50): far_general + term_near_no_rag + misleading_edge",
                "distance_meaning": "Chroma similarity_search_with_score; larger => less similar",
            },
            "rows": rows,
        }
        args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n已写入 {args.json_out}")


if __name__ == "__main__":
    main()
