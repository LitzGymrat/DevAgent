"""
按用户规则批量清洗 ft_qa_500_train.jsonl（2026-03-21）。

1. 删重复 query：保留 domain_0001，删 domain_0356
2. 导出 clarify_needed 子集供查看（另文件）
3. far_general_0066 / 0067 → misleading_edge + clarify_needed，新 sample_id
4. A 类删；B 类 → far_general + no_tool；C/D/E 删

用法：仓库根目录 python experiments/data_flywheel/apply_batch_clean_user_rules.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "experiments" / "data_flywheel" / "out" / "ft_qa_500_train.jsonl"
OUT_DIR = DATA.parent

# 与 domain_0001 重复
DELETE_DUP = {"domain_0356"}

# A：非任务/情绪/元对话
DELETE_A = {
    "domain_0135",
    "domain_0117",
    "domain_0157",
    "domain_0220",
    "domain_0295",
    "domain_0255",
    "domain_0077",
    "domain_0057",
    "domain_0095",
    "domain_0370",
    "domain_0350",
}

# C：观点/访谈
DELETE_C = {"domain_0055", "domain_0235", "domain_0156"}

# D：边界「可接受」— 用户要求删
DELETE_D = {"domain_0097", "domain_0096", "domain_0212", "domain_0211"}

# E：半成品/语境依赖
DELETE_E = {"domain_0056", "domain_0257", "domain_0352"}

DELETE_ALL = DELETE_DUP | DELETE_A | DELETE_C | DELETE_D | DELETE_E

# B：通识 → far_general + no_tool（按 domain 编号排序分配新 id）
B_ORDER = [
    "domain_0076",
    "domain_0116",
    "domain_0197",
    "domain_0276",
    "domain_0296",
    "domain_0313",
    "domain_0331",
    "domain_0371",
    "domain_0372",
]
B_NEW_START = 107  # far_general_0107 ..

SHORT_FAR = ["far_general_0066", "far_general_0067"]
MISLEAD_NEW_START = 89  # misleading_edge_0089 ..


def main() -> None:
    lines = [ln for ln in DATA.read_text(encoding="utf-8").splitlines() if ln.strip()]
    rows = [json.loads(ln) for ln in lines]

    b_map = {
        old: f"far_general_{B_NEW_START + i:04d}" for i, old in enumerate(B_ORDER)
    }
    short_map = {
        "far_general_0066": f"misleading_edge_{MISLEAD_NEW_START:04d}",
        "far_general_0067": f"misleading_edge_{MISLEAD_NEW_START + 1:04d}",
    }

    out: list[dict] = []
    for r in rows:
        sid = r["sample_id"]
        if sid in DELETE_ALL:
            continue
        if sid in b_map:
            r = json.loads(json.dumps(r))
            r["sample_id"] = b_map[sid]
            r["bucket"] = "far_general"
            r["decision_type"] = "no_tool"
            r["tool_name"] = None
            r["arguments"] = None
            r["clarify_answer"] = None
            r["oracle_context"] = None
            m = dict(r.get("_meta") or {})
            m["slice"] = "dev_general_no_rag"
            m["slice_label_zh"] = "开发通识（无需查库）"
            m["batch_clean"] = "B: domain→far_general no_tool"
            r["_meta"] = m
        elif sid in short_map:
            r = json.loads(json.dumps(r))
            r["sample_id"] = short_map[sid]
            r["bucket"] = "misleading_edge"
            r["decision_type"] = "clarify_needed"
            m = dict(r.get("_meta") or {})
            m["slice"] = "misleading_edge"
            m["slice_label_zh"] = "误导向/边界"
            m["batch_clean"] = "极短 query → misleading_edge clarify_needed"
            r["_meta"] = m
            # clarify_answer 已存在
        out.append(r)

    # 唯一性
    ids = [r["sample_id"] for r in out]
    assert len(ids) == len(set(ids)), f"duplicate ids {len(ids)-len(set(ids))}"

    bak = DATA.with_suffix(".jsonl.batch_clean_bak")
    shutil.copy2(DATA, bak)

    DATA.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in out) + "\n",
        encoding="utf-8",
    )
    print(f"backup -> {bak.name}")
    print(f"wrote {len(out)} rows (was {len(rows)}, deleted {len(rows)-len(out)}) -> {DATA}")

    # clarify_needed 子集
    clar = [r for r in out if r.get("decision_type") == "clarify_needed"]
    clar_path = OUT_DIR / "ft_qa_500_train.clarify_needed_only.jsonl"
    clar_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in clar) + "\n",
        encoding="utf-8",
    )
    print(f"clarify_needed only: {len(clar)} -> {clar_path.name}")

    # 简易 md
    md_lines = [
        "# clarify_needed 子集（清洗后）\n\n",
        f"共 **{len(clar)}** 条，来源 `{clar_path.name}`。\n\n",
    ]
    for i, r in enumerate(clar, 1):
        md_lines.append(f"### {i}. `{r['sample_id']}` · `{r.get('bucket')}`\n\n")
        md_lines.append("```\n" + (r.get("query") or "") + "\n```\n\n")
        if r.get("clarify_answer"):
            md_lines.append("**clarify_answer**: " + str(r["clarify_answer"]) + "\n\n---\n\n")
    (OUT_DIR / "ft_qa_500_train.clarify_needed_only.md").write_text(
        "".join(md_lines), encoding="utf-8"
    )
    print("-> ft_qa_500_train.clarify_needed_only.md")


if __name__ == "__main__":
    main()
