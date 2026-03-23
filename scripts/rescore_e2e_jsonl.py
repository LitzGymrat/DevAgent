"""
用当前 e2e_manifest 的 gold 对已有 e2e_eval_log*.jsonl 离线重算指标，
无需再跑 agent。

简报（与文档常用表一致）：第一层总览 + 按桶拆开 + **第二层软熔断**；可用 --compare 生成「本轮 | 对照」双列。

用法（项目根）：
  python scripts/rescore_e2e_jsonl.py data/e2e_eval_log_promptv2.jsonl
  python scripts/rescore_e2e_jsonl.py data/e2e_eval_log_promptv2.jsonl --compare data/e2e_eval_log.jsonl
  python scripts/rescore_e2e_jsonl.py --brief-only data/e2e_eval_log_promptv2.jsonl --compare data/e2e_eval_log.jsonl
  python scripts/rescore_e2e_jsonl.py --max-list 50 data/e2e_eval_log.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.e2e_manifest import build_e2e_manifest

BUCKET_ORDER = ("domain", "far_general", "term_near_no_rag", "misleading_edge")
BUCKET_DISPLAY = {
    "domain": "domain（域内）",
    "far_general": "far_general",
    "term_near_no_rag": "term_near_no_rag",
    "misleading_edge": "misleading_edge",
}


def _l1(actual: bool, expect: str) -> tuple[bool, str]:
    if expect == "optional":
        return True, "none"
    if expect == "yes":
        return (True, "none") if actual else (False, "fn")
    if expect == "no":
        return (True, "none") if not actual else (False, "fp")
    raise ValueError(f"unknown expect: {expect}")


def _fmt_pct(num: float) -> str:
    return f"{num:.1f}%"


def _rate_str(ok: int, n: int) -> str:
    if n <= 0:
        return "—"
    pct = 100.0 * ok / n
    return f"{ok}/{n} ≈ {_fmt_pct(pct)}"


def _l2_fuse_ratio(exp: int, triggered: int) -> str:
    if exp <= 0:
        return "N/A"
    pct = 100.0 * triggered / exp
    return f"{triggered}/{exp}（{_fmt_pct(pct)}）"


@dataclass
class L1Metrics:
    path: Path
    n: int
    l1_ok: int
    l1_fp: int
    l1_fn: int
    must_n: int
    must_ok: int
    must_fn: int
    per_bucket: dict[str, dict[str, int]] = field(default_factory=dict)
    per_tier: dict[str, dict[str, int]] = field(default_factory=dict)
    per_expect: dict[str, int] = field(default_factory=dict)
    fp_rows: list[tuple[str, str, str]] = field(default_factory=list)
    fn_rows: list[tuple[str, str, str]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    mismatched_bucket: list[str] = field(default_factory=list)
    l2_searched: int = 0
    l2_fuse_expected: int = 0
    l2_fuse_expected_and_triggered: int = 0


def compute_metrics(path: Path) -> L1Metrics:
    gold_by_id = {r["id"]: r for r in build_e2e_manifest()}
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))

    per_bucket: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "ok": 0, "fp": 0, "fn": 0})
    per_tier: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "ok": 0, "fp": 0, "fn": 0})
    per_expect: dict[str, int] = defaultdict(int)
    fp_rows: list[tuple[str, str, str]] = []
    fn_rows: list[tuple[str, str, str]] = []
    missing: list[str] = []
    mismatched_bucket: list[str] = []

    l1_ok = l1_fp = l1_fn = 0
    must_n = must_ok = must_fn = 0
    l2_searched = l2_fuse_expected = l2_fuse_expected_and_triggered = 0

    for rec in rows:
        sid = rec.get("sample_id")
        g = gold_by_id.get(sid)
        if not g:
            missing.append(str(sid))
            continue
        if rec.get("bucket_type") != g.get("bucket_type"):
            mismatched_bucket.append(sid)

        actual = bool(rec.get("actual_call_search_codebase"))
        expect = g["should_call_tool"]
        per_expect[expect] += 1

        ok, err = _l1(actual, expect)
        if ok:
            l1_ok += 1
        elif err == "fp":
            l1_fp += 1
        else:
            l1_fn += 1

        bt = g["bucket_type"]
        per_bucket[bt]["n"] += 1
        if ok:
            per_bucket[bt]["ok"] += 1
        elif err == "fp":
            per_bucket[bt]["fp"] += 1
        else:
            per_bucket[bt]["fn"] += 1

        gt = g.get("grounding_tier") or "unknown"
        per_tier[gt]["n"] += 1
        if ok:
            per_tier[gt]["ok"] += 1
        elif err == "fp":
            per_tier[gt]["fp"] += 1
        else:
            per_tier[gt]["fn"] += 1

        if not ok and err == "fp":
            fp_rows.append((sid, bt, (rec.get("question") or "")[:100]))
        if not ok and err == "fn":
            fn_rows.append((sid, bt, (rec.get("question") or "")[:100]))

        if gt == "must_ground":
            must_n += 1
            if actual:
                must_ok += 1
            else:
                must_fn += 1

        if actual:
            l2_searched += 1
            if g.get("should_soft_fallback_if_searched") == "yes":
                l2_fuse_expected += 1
                if rec.get("soft_fallback_triggered") is True:
                    l2_fuse_expected_and_triggered += 1

    n = len(rows)
    return L1Metrics(
        path=path,
        n=n,
        l1_ok=l1_ok,
        l1_fp=l1_fp,
        l1_fn=l1_fn,
        must_n=must_n,
        must_ok=must_ok,
        must_fn=must_fn,
        per_bucket=dict(per_bucket),
        per_tier=dict(per_tier),
        per_expect=dict(per_expect),
        fp_rows=fp_rows,
        fn_rows=fn_rows,
        missing=missing,
        mismatched_bucket=mismatched_bucket,
        l2_searched=l2_searched,
        l2_fuse_expected=l2_fuse_expected,
        l2_fuse_expected_and_triggered=l2_fuse_expected_and_triggered,
    )


def print_brief(
    primary: L1Metrics,
    label_primary: str,
    compare: L1Metrics | None,
    label_compare: str,
) -> None:
    """第一层：与文档里常用的「表格式」简报一致。"""
    print("\n第一层：是否调用 search_codebase（相对当前 manifest）\n")

    if compare is None:
        print("| 指标 | " + label_primary + " |")
        print("|------|------|")
        print(f"| 一致率 | {_rate_str(primary.l1_ok, primary.n)} |")
        print(f"| FP（不该调却调） | {primary.l1_fp} |")
        print(f"| FN（该调未调） | {primary.l1_fn} |")
    else:
        print("| 指标 | " + label_primary + " | " + label_compare + " |")
        print("|------|------|------|")
        print(f"| 一致率 | {_rate_str(primary.l1_ok, primary.n)} | {_rate_str(compare.l1_ok, compare.n)} |")
        print(f"| FP（不该调却调） | {primary.l1_fp} | {compare.l1_fp} |")
        print(f"| FN（该调未调） | {primary.l1_fn} | {compare.l1_fn} |")

    print("\n按桶拆开（search_codebase 决策）\n")
    if compare is None:
        print("| bucket | 条数 | 一致率 | FP | FN |")
        print("|--------|------|--------|----|----|")
        for bt in BUCKET_ORDER:
            if bt not in primary.per_bucket:
                continue
            d = primary.per_bucket[bt]
            bn, ok, fp, fn = d["n"], d["ok"], d["fp"], d["fn"]
            acc = _fmt_pct(100.0 * ok / bn) if bn else "—"
            name = BUCKET_DISPLAY.get(bt, bt)
            print(f"| {name} | {bn} | {acc} | {fp} | {fn} |")
    else:
        print(
            "| bucket | 条数 | 一致率 "
            + f"（{label_primary}） | FP | FN | 一致率（{label_compare}） | FP | FN |"
        )
        print("|--------|------|--------|----|----|--------|----|----|")
        for bt in BUCKET_ORDER:
            if bt not in primary.per_bucket and bt not in compare.per_bucket:
                continue
            d0 = primary.per_bucket.get(bt, {"n": 0, "ok": 0, "fp": 0, "fn": 0})
            d1 = compare.per_bucket.get(bt, {"n": 0, "ok": 0, "fp": 0, "fn": 0})
            bn = d0["n"] or d1["n"]
            acc0 = _fmt_pct(100.0 * d0["ok"] / bn) if bn else "—"
            acc1 = _fmt_pct(100.0 * d1["ok"] / bn) if bn else "—"
            name = BUCKET_DISPLAY.get(bt, bt)
            print(
                f"| {name} | {bn} | {acc0} | {d0['fp']} | {d0['fn']} | "
                f"{acc1} | {d1['fp']} | {d1['fn']} |"
            )

    print(
        "\n注：domain 内 gold 由 grounding_tier 分档（must_ground / prefer_ground / ok_generic），"
        "与「domain 一律应检索」的旧表不可直接比数字。"
    )

    if compare is not None:
        dfp = compare.l1_fp - primary.l1_fp
        dfn = primary.l1_fn - compare.l1_fn
        parts = []
        if dfp != 0:
            parts.append(f"误触检索（FP）较对照 {'↓' if dfp > 0 else '↑'}{abs(dfp)}（{compare.l1_fp} → {primary.l1_fp}）")
        if dfn != 0:
            parts.append(f"漏检（FN）较对照 {'↑' if dfn > 0 else '↓'}{abs(dfn)}（{compare.l1_fn} → {primary.l1_fn}）")
        if parts:
            print("\n整体：" + "；".join(parts) + "。")
        print(
            f"\nmust_ground 子集（{label_primary}）：检索 {primary.must_ok}/{primary.must_n}，FN {primary.must_fn}；"
            f"（{label_compare}）：{compare.must_ok}/{compare.must_n}，FN {compare.must_fn}。"
        )

    # 第二层：软熔断（与 eval_e2e_pipeline 一致，来自 JSONL 中 soft_fallback_triggered）
    print("\n第二层：检索 + 软熔断（仅 actual_call_search_codebase；「预期应熔断」= manifest 中 should_soft_fallback_if_searched=yes 且本条实际检索）\n")
    if compare is None:
        print("| 指标 | " + label_primary + " |")
        print("|------|------|")
        print(f"| 实际触发 search_codebase 次数 | {primary.l2_searched} |")
        print(f"| 「预期应软熔断」样本数 | {primary.l2_fuse_expected} |")
        print(f"| 预期应熔断且已熔断 | {_l2_fuse_ratio(primary.l2_fuse_expected, primary.l2_fuse_expected_and_triggered)} |")
    else:
        print("| 指标 | " + label_primary + " | " + label_compare + " |")
        print("|------|------|------|")
        print(f"| 实际触发 search_codebase 次数 | {primary.l2_searched} | {compare.l2_searched} |")
        print(f"| 「预期应软熔断」样本数 | {primary.l2_fuse_expected} | {compare.l2_fuse_expected} |")
        print(
            f"| 预期应熔断且已熔断 | "
            f"{_l2_fuse_ratio(primary.l2_fuse_expected, primary.l2_fuse_expected_and_triggered)} | "
            f"{_l2_fuse_ratio(compare.l2_fuse_expected, compare.l2_fuse_expected_and_triggered)} |"
        )
    print(
        "\n软熔断作用（结合第一层）：误调检索（FP）越少，**需要靠距离阈值触发软兜底**的样本越少；"
        "上表「预期应熔断」子集规模随 FP 同步缩小。子集内「已熔断/应熔断」比例反映阈值下触发率，"
        "样本极少时不宜单独解读为模型优劣。"
    )


def print_detail(m: L1Metrics, max_list: int) -> None:
    path = m.path
    print(f"\n{'=' * 60}")
    print("离线重算（数据来源 JSONL，未重跑 agent）")
    print(f"文件: {path}")
    print(f"  JSONL 行数: {m.n}")
    if m.missing:
        print(f"  警告: manifest 中无 sample_id: {m.missing[:10]}{'...' if len(m.missing) > 10 else ''}")
    if m.mismatched_bucket:
        print(f"  提示: bucket_type 与当前 manifest 不一致: {len(m.mismatched_bucket)} 条")

    print("\n=== 第一层：Tool Decision（search_codebase）===")
    print(f"  样本数: {m.n}")
    print(f"  决策与预期一致: {m.l1_ok}/{m.n}  ({_fmt_pct(100.0 * m.l1_ok / m.n if m.n else 0.0)})")
    print(f"  False Positive（不该调却调）: {m.l1_fp}")
    print(f"  False Negative（该调未调）: {m.l1_fn}")
    print("  —— gold：should_call_tool 条数 ——")
    for k in ("yes", "optional", "no"):
        c = m.per_expect.get(k, 0)
        if c:
            label = {
                "yes": "must_ground（应检索）",
                "optional": "prefer_ground（调/不调均可）",
                "no": "ok_generic + 域外（不应检索）",
            }[k]
            print(f"    {k}: {c}  ({label})")

    print("  —— 子集 grounding_tier=must_ground ——")
    print(f"  must_ground 条数: {m.must_n}  |  已检索: {m.must_ok}  |  未检索(FN): {m.must_fn}")
    if m.must_n:
        print(f"  must_ground 检索率: {_fmt_pct(100.0 * m.must_ok / m.must_n)}")

    print("\n  —— 按 grounding_tier ——")
    tier_order = ("must_ground", "prefer_ground", "ok_generic", "n/a", "unknown")
    seen: set[str] = set()
    for tt in tier_order:
        if tt not in m.per_tier:
            continue
        seen.add(tt)
        d = m.per_tier[tt]
        tn = d["n"]
        acc = 100.0 * d["ok"] / tn if tn else 0.0
        print(f"    {tt}: n={tn}  一致={d['ok']}  FP={d['fp']}  FN={d['fn']}  准确率={_fmt_pct(acc)}")
    for tt in sorted(m.per_tier.keys()):
        if tt in seen:
            continue
        d = m.per_tier[tt]
        tn = d["n"]
        acc = 100.0 * d["ok"] / tn if tn else 0.0
        print(f"    {tt}: n={tn}  一致={d['ok']}  FP={d['fp']}  FN={d['fn']}  准确率={_fmt_pct(acc)}")

    def _print_errors(title: str, items: list[tuple[str, str, str]], kind: str) -> None:
        print(f"\n  —— {title}（共 {len(items)} 条）——")
        if not items:
            print(f"    （无{kind}）")
            return
        show = items[:max_list]
        for sid, bt, q in show:
            tail = "…" if len(q) >= 100 else ""
            print(f"    [{sid}] bucket={bt}")
            print(f"      {q}{tail}")
        if len(items) > max_list:
            print(f"    … 其余 {len(items) - max_list} 条省略（--max-list 调大）")

    _print_errors("False Positive 明细", m.fp_rows, "FP")
    _print_errors("False Negative 明细", m.fn_rows, "FN")

    print("\n=== 第二层：检索 + 软熔断（仅 actual_call_search_codebase 的样本）===")
    print(f"  实际触发检索次数: {m.l2_searched}")
    print(f"  其中「预期应软熔断」的样本数: {m.l2_fuse_expected}")
    if m.l2_fuse_expected:
        pct = 100.0 * m.l2_fuse_expected_and_triggered / m.l2_fuse_expected
        print(f"  预期应熔断且已熔断: {m.l2_fuse_expected_and_triggered}/{m.l2_fuse_expected}  ({_fmt_pct(pct)})")
    else:
        print("  预期应熔断且已熔断: N/A（无「误调检索且预期熔断」样本）")

    print("\n=== 第三层：最终回答 ===")
    print("  JSONL 中若为 pending，需人工或 LLM-as-judge；离线脚本不重判。")
    print(f"\n（文件 {path.name} 明细结束）\n")


def main() -> None:
    p = argparse.ArgumentParser(description="Offline rescore for e2e JSONL")
    p.add_argument("jsonl", type=Path, help="主 JSONL（「本轮」）")
    p.add_argument("--compare", type=Path, default=None, help="对照 JSONL（如首轮 e2e_eval_log.jsonl）")
    p.add_argument("--label-primary", type=str, default="本轮", help="主列标题")
    p.add_argument("--label-compare", type=str, default="对照：首轮", help="对照列标题")
    p.add_argument("--brief-only", action="store_true", help="只输出第一层简报表，不输出明细")
    p.add_argument("--no-brief", action="store_true", help="不输出简报表（仅明细）")
    p.add_argument(
        "--detail-both",
        action="store_true",
        help="与 --compare 联用：同时打印对照 JSONL 的明细（默认只打印主文件明细）",
    )
    p.add_argument(
        "--max-list",
        type=int,
        default=80,
        help="FP/FN 明细最多列出多少条（默认 80）",
    )
    args = p.parse_args()

    path = args.jsonl
    if not path.is_file():
        print(f"文件不存在: {path}", file=sys.stderr)
        sys.exit(1)

    primary = compute_metrics(path.resolve())
    compare_m: L1Metrics | None = None
    if args.compare:
        cp = args.compare
        if not cp.is_file():
            print(f"对照文件不存在: {cp}", file=sys.stderr)
            sys.exit(1)
        compare_m = compute_metrics(cp.resolve())

    if not args.no_brief:
        print_brief(primary, args.label_primary, compare_m, args.label_compare)

    if args.brief_only:
        return

    print_detail(primary, args.max_list)
    if compare_m is not None and args.detail_both:
        print_detail(compare_m, args.max_list)


if __name__ == "__main__":
    main()
