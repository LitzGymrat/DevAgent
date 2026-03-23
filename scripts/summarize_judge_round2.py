"""一次性汇总 Judge JSONL（round1 / round2 对照）。"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.e2e_manifest import build_e2e_manifest


def load(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        if o.get("error") or not o.get("final_judgement"):
            continue
        rows.append(o)
    return rows


def stats(rows: list[dict], name: str) -> None:
    print(f"=== {name} (n={len(rows)}) ===")
    fj = Counter(r["final_judgement"] for r in rows)
    print("final_judgement:", dict(fj))
    sc = Counter(r["score"] for r in rows)
    print("score:", dict(sorted(sc.items())))
    bad = [
        r
        for r in rows
        if r.get("final_judgement") != "correct"
        or not r.get("grounding_appropriate")
        or r.get("context_pollution")
    ]
    print(f"bad (def): {len(bad)}")
    dom = [r for r in rows if r.get("bucket_type") == "domain"]
    dom_cor = sum(1 for r in dom if r["final_judgement"] == "correct")
    print(f"domain: correct {dom_cor}/{len(dom)} ({100 * dom_cor / len(dom):.1f}%)" if dom else "domain: 0")
    man = {row["id"]: row for row in build_e2e_manifest()}
    by_t: dict[str, dict[str, int]] = defaultdict(lambda: {"n": 0, "cor": 0, "inc": 0, "part": 0})
    for r in dom:
        t = (r.get("grounding_tier") or man.get(r["sample_id"], {}).get("grounding_tier")) or "?"
        by_t[t]["n"] += 1
        fj = r["final_judgement"]
        if fj == "correct":
            by_t[t]["cor"] += 1
        elif fj == "incorrect":
            by_t[t]["inc"] += 1
        else:
            by_t[t]["part"] += 1
    print("domain by grounding_tier (manifest 回填若 JSON 缺字段):")
    for t in ("must_ground", "prefer_ground", "ok_generic", "?"):
        if t not in by_t:
            continue
        b = by_t[t]
        pct = 100 * b["cor"] / b["n"] if b["n"] else 0
        print(
            f"  {t}: n={b['n']} correct={b['cor']} ({pct:.0f}%) "
            f"incorrect={b['inc']} partially_correct={b['part']}"
        )
    out = [r for r in rows if r.get("bucket_type") != "domain"]
    out_cor = sum(1 for r in out if r["final_judgement"] == "correct")
    print(
        f"non-domain: correct {out_cor}/{len(out)} ({100 * out_cor / len(out):.1f}%)" if out else "non-domain: 0"
    )
    pol = sum(1 for r in rows if r.get("context_pollution"))
    print(f"context_pollution true: {pol}")
    print()


def main() -> None:
    r2 = load(ROOT / "data" / "e2e_llm_judge_full_round2.jsonl")
    p1 = ROOT / "data" / "archive" / "judge_round1" / "e2e_llm_judge_full.jsonl"
    stats(r2, "Round2 (tiered rubric)")
    if p1.is_file():
        r1 = load(p1)
        stats(r1, "Round1 (legacy rubric, if present)")


if __name__ == "__main__":
    main()
