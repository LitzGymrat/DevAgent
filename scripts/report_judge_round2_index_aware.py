"""
在不重跑 Judge、不覆盖历史 JSONL 的前提下，用 manifest 中的
`grounding_tier_index_aware` 对第二轮 Judge 结果做**解读与重计数**。

输出：data/reports/e2e_judge_round2_index_aware.md

用法（项目根）：
  python scripts/report_judge_round2_index_aware.py
  python scripts/report_judge_round2_index_aware.py --judge data/e2e_llm_judge_full_round2.jsonl
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.e2e_manifest import (
    INDEX_AWARE_GROUNDING_TIER_OVERRIDES,
    build_e2e_manifest,
)


def _bad(row: dict) -> bool:
    if row.get("error") or not row.get("final_judgement"):
        return False
    return (
        row.get("final_judgement") != "correct"
        or not row.get("grounding_appropriate")
        or row.get("context_pollution")
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", type=Path, default=ROOT / "data" / "e2e_llm_judge_full_round2.jsonl")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "reports" / "e2e_judge_round2_index_aware.md")
    args = ap.parse_args()

    man = {r["id"]: r for r in build_e2e_manifest()}
    rows: list[dict] = []
    for line in args.judge.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))

    lines: list[str] = [
        "# 第二轮 LLM Judge × **index-aware grounding_tier** 解读",
        "",
        "**目的**：原版 `grounding_tier`（`grounding_tier` 字段）保持不变，前两轮落盘 JSONL **仍可**横向对照；",
        "此处用 **`grounding_tier_index_aware`**（见 `e2e_manifest.INDEX_AWARE_GROUNDING_TIER_OVERRIDES`）",
        "把「当前 Chroma 快照里根本不存在 / 建库范围外」的题从 **must_ground** 中拆出，避免 gold 与 RAG 可达性脱节。",
        "",
        "**注意**：Judge API 当时仍按**原版** tier 提示词打分；本文件是**离线重解读**，不是新 Judge 结果。若要 Judge 与 tier 完全一致，需用新 tier 重跑 `eval_llm_judge_e2e.py`。",
        "",
        "## 覆盖规则（摘要）",
        "",
    ]
    for sid, tier in sorted(INDEX_AWARE_GROUNDING_TIER_OVERRIDES.items()):
        lines.append(f"- **`{sid}`** → `{tier}`")
    lines.append("")

    bad = [r for r in rows if _bad(r)]
    dom_bad = [r for r in bad if man.get(r["sample_id"], {}).get("bucket_type") == "domain"]

    def tier_of(sid: str, ia: bool) -> str:
        m = man.get(sid, {})
        return (m.get("grounding_tier_index_aware") if ia else m.get("grounding_tier")) or "?"

    # 仅统计「在 index-aware 下仍为 must_ground」的 domain badcase
    bad_mg_legacy = [r for r in dom_bad if tier_of(r["sample_id"], False) == "must_ground"]
    bad_mg_ia = [r for r in dom_bad if tier_of(r["sample_id"], True) == "must_ground"]

    relaxed = [r for r in dom_bad if tier_of(r["sample_id"], False) == "must_ground" and tier_of(r["sample_id"], True) != "must_ground"]

    lines += [
        "## 汇总（domain badcase）",
        "",
        f"- **badcase 总数（domain）**：{len(dom_bad)}",
        f"- 其中原版 **must_ground**：{len(bad_mg_legacy)}",
        f"- index-aware 后仍 **must_ground**：{len(bad_mg_ia)}",
        f"- 从 must_ground **放宽**（仅 tier 变化）：{len(relaxed)} 条 → `{sorted(r['sample_id'] for r in relaxed)}`",
        "",
        "### 仅看「index-aware must_ground」子集里的 incorrect / partial",
        "",
    ]

    sub = [r for r in dom_bad if tier_of(r["sample_id"], True) == "must_ground"]
    inc = sum(1 for r in sub if r.get("final_judgement") == "incorrect")
    part = sum(1 for r in sub if r.get("final_judgement") == "partially_correct")
    cor = sum(1 for r in sub if r.get("final_judgement") == "correct")
    lines.append(
        f"- 条数 **{len(sub)}**：correct={cor}，partially_correct={part}，incorrect={inc}"
    )
    lines.append("")

    lines += [
        "## 全 badcase 对照表（原版 tier → index-aware tier）",
        "",
        "| id | 原版 tier | index-aware | final_judgement | 说明 |",
        "|----|-----------|---------------|-----------------|------|",
    ]
    for r in sorted([x for x in bad if man.get(x["sample_id"], {}).get("bucket_type") == "domain"], key=lambda x: x["sample_id"]):
        sid = r["sample_id"]
        gl = tier_of(sid, False)
        gia = tier_of(sid, True)
        fj = r.get("final_judgement") or ""
        note = ""
        if gl != gia:
            note = "tier 放宽"
        lines.append(f"| {sid} | {gl} | {gia} | {fj} | {note} |")

    lines += ["", "---", "", f"生成：`python scripts/report_judge_round2_index_aware.py`"]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
