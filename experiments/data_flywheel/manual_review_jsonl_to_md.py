"""将 *.manual_review.jsonl 转为易读 Markdown。用法：
  python experiments/data_flywheel/manual_review_jsonl_to_md.py
  python experiments/data_flywheel/manual_review_jsonl_to_md.py --input .../x.manual_review.jsonl
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _esc(s: str) -> str:
    return s.replace("\r\n", "\n").replace("\r", "\n")


def jsonl_to_md(path: Path) -> str:
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))

    by_code: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        for item in r.get("_manual_review") or []:
            by_code[item["code"]].append(r["sample_id"])

    out: list[str] = []
    out.append(f"# 人工复核清单\n\n")
    out.append(f"源文件：`{path.name}`  \n")
    out.append(f"共 **{len(rows)}** 条（按 `sample_id` 去重）。\n\n")
    out.append("---\n\n## 按复核代码速览\n\n")
    for code in sorted(by_code.keys()):
        ids = ", ".join(f"`{x}`" for x in by_code[code])
        out.append(f"- **`{code}`**（{len(by_code[code])} 条）: {ids}\n")
    out.append("\n---\n\n## 逐条详情\n\n")

    for i, r in enumerate(rows, 1):
        sid = r.get("sample_id", "?")
        out.append(f"### {i}. `{sid}`\n\n")
        out.append(f"| 字段 | 值 |\n|------|----|\n")
        out.append(f"| bucket | `{r.get('bucket')}` |\n")
        out.append(f"| decision_type | `{r.get('decision_type')}` |\n")
        tn = r.get("tool_name")
        out.append(f"| tool_name | {('`' + str(tn) + '`') if tn else '—'} |\n")
        meta = r.get("_meta") or {}
        if meta.get("_merged_from"):
            out.append(f"| 来源 | 合并自 `{meta.get('_merged_from')}`，原 id `{meta.get('previous_sample_id', '')}` |\n")
        out.append("\n**复核原因**\n\n")
        for item in r.get("_manual_review") or []:
            out.append(f"- **`{item['code']}`**: {item['message']}\n")
        out.append("\n**用户 query**\n\n")
        out.append("```text\n")
        out.append(_esc(str(r.get("query") or "")))
        out.append("\n```\n\n")
        if r.get("decision_type") == "clarify_needed" and r.get("clarify_answer"):
            out.append("**当前金标 clarify_answer**\n\n")
            out.append("> " + _esc(str(r.get("clarify_answer"))).replace("\n", "\n> ") + "\n\n")
        out.append("\n---\n\n")

    return "".join(out)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input",
        type=Path,
        default=ROOT
        / "experiments"
        / "data_flywheel"
        / "out"
        / "ft_qa_500_train.manual_review.jsonl",
    )
    ap.add_argument(
        "--output",
        type=Path,
        default=None,
        help="默认与 input 同目录、扩展名 .md",
    )
    args = ap.parse_args()
    inp = args.input
    if not inp.is_file():
        raise SystemExit(f"missing {inp}")
    outp = args.output or inp.with_suffix(".md")
    outp.write_text(jsonl_to_md(inp), encoding="utf-8")
    print(outp)


if __name__ == "__main__":
    main()
