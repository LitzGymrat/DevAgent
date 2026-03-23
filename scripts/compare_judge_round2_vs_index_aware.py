"""对比上一轮 round2 Judge 与 index_aware 重跑（默认路径见 main）。

  python scripts/compare_judge_round2_vs_index_aware.py
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "data" / "e2e_llm_judge_full_round2.jsonl"
INDEX_AWARE = ROOT / "data" / "e2e_llm_judge_full_round2_index_aware.jsonl"


def load(path: Path) -> dict[str, dict]:
    d: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        if o.get("error"):
            continue
        d[o["sample_id"]] = o
    return d


def main() -> None:
    old = load(LEGACY)
    new = load(INDEX_AWARE)
    ids = sorted(set(old) & set(new))
    print(f"paired samples: {len(ids)} (legacy {len(old)}, index_aware {len(new)})")
    print()

    def summ(rows: list[dict], label: str) -> None:
        fj = Counter(r.get("final_judgement") for r in rows)
        sc = sum(r.get("score", 0) for r in rows)
        bad = sum(1 for r in rows if r.get("final_judgement") != "correct")
        dom = [r for r in rows if r.get("bucket_type") == "domain"]
        dom_ok = sum(1 for r in dom if r.get("final_judgement") == "correct")
        print(label)
        print("  final_judgement:", dict(fj))
        print("  mean score:", round(sc / len(rows), 2))
        print("  not correct:", bad)
        if dom:
            print(f"  domain correct: {dom_ok}/{len(dom)} ({100 * dom_ok / len(dom):.1f}%)")
        print()

    summ([old[i] for i in ids], "Previous (round2, legacy gold in prompt)")
    summ([new[i] for i in ids], "New (index_aware gold in prompt)")

    tier_changed: list[tuple] = []
    same_tier_changed: list[tuple] = []
    for sid in ids:
        o, n = old[sid], new[sid]
        fo, fn = o.get("final_judgement"), n.get("final_judgement")
        so, sn = o.get("score"), n.get("score")
        if fo == fn and so == sn:
            continue
        gto = n.get("grounding_tier_original")
        gt_new = n.get("grounding_tier")
        row = (sid, fo, fn, so, sn, gto, gt_new)
        if gto is not None and gt_new is not None and gto != gt_new:
            tier_changed.append(row)
        else:
            same_tier_changed.append(row)

    def print_block(title: str, rows: list[tuple]) -> None:
        print(f"{title} ({len(rows)})")
        for sid, fo, fn, so, sn, gto, gt_new in rows:
            tc = f"  [{gto} -> {gt_new}]" if gto != gt_new else ""
            print(f"  {sid}: {fo} -> {fn}  score {so} -> {sn}{tc}")

    print_block("Diff where index_aware **changed gold tier** (legacy vs eval)", tier_changed)
    print()
    print_block(
        "Diff with **same** legacy tier (Judge 方差或旧 JSON 未写 grounding_tier 字段)",
        same_tier_changed,
    )


if __name__ == "__main__":
    main()
