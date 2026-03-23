"""
按 manual_review.md 序号对用户指定条目的补丁（一次性脚本，可审计）。

本次：
- §4,5,10 → clarify_needed（原 no_tool）
- §9,12,13,14,17,19,28,29,31 → bucket=far_general，重编号 sample_id，同步 _meta.slice
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "experiments" / "data_flywheel" / "out" / "ft_qa_500_train.jsonl"

CLARIFY_PATCH: dict[str, str] = {
    "misleading_edge_0051": "请说明你在开发中需要协助的具体任务（例如代码片段、报错、仓库内路径），而非闲聊。",
    "misleading_edge_0050": "请描述具体需求或贴上相关代码/报错信息，以便继续排查。",
    "misleading_edge_0029": "请说明你需要解决的具体工程问题，或提供代码/日志等上下文。",
}

OLD_TO_NEW_FAR: dict[str, str] = {
    "domain_0175": "far_general_0098",
    "domain_0277": "far_general_0099",
    "domain_0195": "far_general_0100",
    "domain_0177": "far_general_0101",
    "domain_0196": "far_general_0102",
    "domain_0297": "far_general_0103",
    "domain_0330": "far_general_0104",
    "domain_0332": "far_general_0105",
    "domain_0351": "far_general_0106",
}


def main() -> None:
    raw_lines = [ln for ln in DATA.read_text(encoding="utf-8").splitlines() if ln.strip()]
    by_id: dict[str, dict] = {}
    for ln in raw_lines:
        r = json.loads(ln)
        by_id[r["sample_id"]] = r

    for sid, ca in CLARIFY_PATCH.items():
        r = by_id[sid]
        r["decision_type"] = "clarify_needed"
        r["tool_name"] = None
        r["arguments"] = None
        r["oracle_context"] = None
        r["clarify_answer"] = ca
        m = dict(r.get("_meta") or {})
        m["manual_review_patch"] = "clarify_needed per manual_review §4,5,10"
        r["_meta"] = m

    for old_id, new_id in OLD_TO_NEW_FAR.items():
        r = by_id.pop(old_id)
        r["sample_id"] = new_id
        r["bucket"] = "far_general"
        m = dict(r.get("_meta") or {})
        m["slice"] = "dev_general_no_rag"
        m["slice_label_zh"] = "开发通识（无需查库）"
        m["bucket_migrated_from"] = "domain"
        m["manual_review_patch"] = "far_general per manual_review §9,12,13,14,17,19,28,29,31"
        r["_meta"] = m
        by_id[new_id] = r

    out_rows: list[dict] = []
    for ln in raw_lines:
        sid = json.loads(ln)["sample_id"]
        if sid in OLD_TO_NEW_FAR:
            out_rows.append(by_id[OLD_TO_NEW_FAR[sid]])
        else:
            out_rows.append(by_id[sid])

    assert len(out_rows) == len(raw_lines)
    ids = [r["sample_id"] for r in out_rows]
    assert len(ids) == len(set(ids)), f"duplicate sample_id: {ids}"

    bak = DATA.with_suffix(".jsonl.seq_patch_bak")
    bak.write_text("\n".join(raw_lines) + "\n", encoding="utf-8")
    DATA.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in out_rows) + "\n",
        encoding="utf-8",
    )
    print(f"backup -> {bak.name}")
    print(f"wrote {len(out_rows)} rows -> {DATA}")


if __name__ == "__main__":
    main()
