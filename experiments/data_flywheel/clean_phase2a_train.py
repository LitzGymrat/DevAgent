"""
Phase 2A 训练 JSONL 清洗审计：对照 DATA_CLEANING_CHECKLIST + PHASE2A_ROUTING_RULES。

- 写出带自动修补的副本（默认仅同步 bucket ↔ _meta.slice / slice_label_zh）。
- 写出 Markdown 报告：ERROR / WARN / REVIEW（需人工）分级。
- 不写回源文件，除非传 --in-place（慎用）。

用法（仓库根目录）：
  python experiments/data_flywheel/clean_phase2a_train.py
  python experiments/data_flywheel/clean_phase2a_train.py --input experiments/data_flywheel/out/ft_qa_500_train.jsonl
  python experiments/data_flywheel/clean_phase2a_train.py --extract-review
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
import copy
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ALLOWED_TOOLS = frozenset(
    {
        "analyse_code",
        "search_codebase",
        "analyse_log",
        "generate_dockerfile",
        "generate_tests",
        "complete_code",
    }
)

BUCKET_TO_SLICE: dict[str, tuple[str, str]] = {
    "domain": ("private_domain", "私域语境（FastAPI+Transformers）"),
    "far_general": ("dev_general_no_rag", "开发通识（无需查库）"),
    "misleading_edge": ("misleading_edge", "误导向/边界"),
}

# 工具 → arguments 必填键（与 tools_schemas 一致）
TOOL_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
    "analyse_code": ("code",),
    "search_codebase": ("query",),
    "analyse_log": ("log",),
    "generate_dockerfile": ("project_description",),
    "generate_tests": ("code",),
    "complete_code": ("context",),
}

# 可疑：无明确任务请求（清洗清单 F + 非任务型）
NON_TASK_QUERY_PATTERNS = [
    re.compile(r"^ping\.?$", re.I),
    re.compile(r"^who are you\??$", re.I),
    re.compile(r"^hi[,!]?\s*$", re.I),
    re.compile(r"^hello\??$", re.I),
]

# 泛通识 / 选型对比（B1：domain 桶可能应迁 far_general）
GENERIC_KNOWLEDGE_HINTS = re.compile(
    r"(什么是|有哪些|区别|相比|优势|劣势|更快吗|还是|哪个好|"
    r"Git\s|rebase|merge|分支|概念|入门|介绍|官方文档|"
    r"https?://|\.com/|URL|首页)",
    re.I,
)

# 伪 grounded：路径/镜像/版本号（clarify 文本红牌）
GROUNDING_RISK = re.compile(
    r"(/src/|/home/|\.py:\d+|:\d+:\d+|python:\d+\.\d+-alpine|"
    r"cuda\s*\d|docker\s+run|top_k\s*=\s*\d|咱们项目|主目录默认)",
    re.I,
)

# 表演性客套（F）
FLUFF = re.compile(r"(不好意思|非常愿意|亲～|呢~|么么|跪求)", re.I)


@dataclass
class Issue:
    severity: str  # ERROR | WARN | REVIEW
    code: str
    message: str


@dataclass
class RowAudit:
    sample_id: str
    issues: list[Issue] = field(default_factory=list)
    auto_fixed: list[str] = field(default_factory=list)


def _validate_schema(row: dict, *, issues: list[Issue]) -> None:
    required = ("sample_id", "bucket", "query", "decision_type")
    for k in required:
        if k not in row or row[k] is None:
            issues.append(Issue("ERROR", "missing_key", f"缺少或为空: {k}"))

    if row.get("bucket") not in BUCKET_TO_SLICE:
        issues.append(Issue("ERROR", "bad_bucket", f"bucket 非法: {row.get('bucket')!r}"))

    dt = row.get("decision_type")
    if dt not in ("tool_call", "no_tool", "clarify_needed"):
        issues.append(Issue("ERROR", "bad_decision_type", f"decision_type 非法: {dt!r}"))

    if dt == "tool_call":
        name = row.get("tool_name")
        if name not in ALLOWED_TOOLS:
            issues.append(Issue("ERROR", "bad_tool_name", f"tool_name 非法或缺失: {name!r}"))
        else:
            args = row.get("arguments")
            if not isinstance(args, dict):
                issues.append(Issue("ERROR", "bad_arguments", "arguments 须为对象"))
            else:
                for key in TOOL_REQUIRED_KEYS[name]:
                    if key not in args or args[key] in (None, ""):
                        issues.append(
                            Issue("ERROR", "missing_arg", f"工具 {name} 缺少非空参数: {key}")
                        )
        if row.get("clarify_answer") not in (None, ""):
            issues.append(Issue("WARN", "tool_call_clarify", "tool_call 时 clarify_answer 应为 null"))
    elif dt == "no_tool":
        for f in ("tool_name", "arguments", "clarify_answer", "oracle_context"):
            if row.get(f) is not None:
                issues.append(Issue("WARN", f"no_tool_{f}", f"no_tool 时 {f} 应为 null"))
    elif dt == "clarify_needed":
        ca = row.get("clarify_answer")
        if not ca or not str(ca).strip():
            issues.append(Issue("ERROR", "empty_clarify", "clarify_needed 须含非空 clarify_answer"))
        if row.get("tool_name") is not None or row.get("arguments") is not None:
            issues.append(Issue("WARN", "clarify_needs_null_tools", "clarify_needed 时 tool/arguments 应为 null"))


def _prefix_for_bucket(bucket: str) -> str:
    return {"domain": "domain_", "far_general": "far_general_", "misleading_edge": "misleading_edge_"}[bucket]


def _heuristic_review(row: dict, *, issues: list[Issue]) -> None:
    q = (row.get("query") or "").strip()
    sid = row.get("sample_id", "")
    bucket = row.get("bucket", "")
    dt = row.get("decision_type", "")
    meta = row.get("_meta") or {}

    if sid and bucket:
        exp = _prefix_for_bucket(bucket)
        if not sid.startswith(exp):
            issues.append(
                Issue(
                    "REVIEW",
                    "id_bucket_mismatch",
                    f"sample_id 前缀与 bucket 不一致: {sid!r} vs {bucket!r}",
                )
            )

    if len(q) < 6:
        issues.append(Issue("REVIEW", "very_short_query", f"query 极短（{len(q)} 字符），是否非任务型？"))

    for pat in NON_TASK_QUERY_PATTERNS:
        if pat.match(q.strip()):
            issues.append(Issue("REVIEW", "non_task_query", "可能非开发任务（问候/空 ping）"))

    if bucket == "domain" and dt == "no_tool" and GENERIC_KNOWLEDGE_HINTS.search(q):
        issues.append(
            Issue(
                "REVIEW",
                "b1_domain_generic",
                "domain 桶 + no_tool，但 query 像通识/选型；是否应迁 far_general（见 PHASE2A_ROUTING_RULES）",
            )
        )

    if bucket == "far_general" and re.search(
        r"(transformers/|fastapi/|src/transformers|huggingface|建模|APIRouter|pipeline\()", q, re.I
    ):
        issues.append(
            Issue(
                "REVIEW",
                "b2_far_repo_specific",
                "far_general 桶但 query 含强私域/库内术语，是否应 domain？",
            )
        )

    if dt == "clarify_needed":
        ca = row.get("clarify_answer") or ""
        if len(ca) > 220:
            issues.append(Issue("WARN", "long_clarify", "clarify_answer 偏长（>220），可能教程式；建议压到 1～2 句"))
        if FLUFF.search(ca):
            issues.append(Issue("WARN", "fluff_clarify", "clarify_answer 含表演性客套用语"))
        if GROUNDING_RISK.search(ca):
            issues.append(Issue("WARN", "grounding_in_clarify", "clarify_answer 含路径/镜像/版本等，核对是否伪 grounded"))

    if dt == "tool_call" and row.get("tool_name") == "analyse_log":
        args = row.get("arguments") or {}
        log = str(args.get("log") or "")
        if "traceback" not in log.lower() and "error" not in log.lower() and "exception" not in log.lower():
            if "traceback" not in q.lower() and "error" not in q.lower():
                issues.append(
                    Issue(
                        "REVIEW",
                        "analyse_log_weak",
                        "analyse_log 但 log 参数/题干中未必含典型报错关键词；核对是否应 search_codebase",
                    )
                )

    if dt == "tool_call" and row.get("tool_name") == "search_codebase":
        args = row.get("arguments") or {}
        sq = str(args.get("query") or "").strip()
        if len(sq) < 4:
            issues.append(Issue("ERROR", "empty_search_query", "search_codebase 的 query 过短或为空"))
        elif len(sq) > 400:
            issues.append(Issue("WARN", "long_search_query", "search query 过长，可能应精炼"))

    if dt == "clarify_needed" and re.search(
        r"(在哪|在哪|找一下|搜索|定位|文件|实现|源码|类|函数)", q
    ) and not re.search(r"(哪个|是否|还是|还是)", q):
        issues.append(
            Issue(
                "REVIEW",
                "clarify_vs_search",
                "题干像明确检索意图，但标为 clarify_needed；若方向明确可改 search_codebase（见路由规则 3）",
            )
        )

    if meta.get("slice") and bucket:
        exp_slice, _ = BUCKET_TO_SLICE[bucket]
        if meta["slice"] != exp_slice:
            issues.append(
                Issue(
                    "WARN",
                    "meta_slice_bucket",
                    f"_meta.slice={meta['slice']!r} 与 bucket={bucket!r} 期望 {exp_slice!r} 不一致",
                )
            )


def collect_issues(row: dict) -> list[Issue]:
    """单条审计（不做 auto_fix），用于导出人工复核子集。"""
    issues: list[Issue] = []
    _validate_schema(row, issues=issues)
    _heuristic_review(row, issues=issues)
    return issues


def _auto_fix_meta(row: dict) -> list[str]:
    fixed: list[str] = []
    bucket = row.get("bucket")
    if bucket not in BUCKET_TO_SLICE:
        return fixed
    exp_slice, exp_label = BUCKET_TO_SLICE[bucket]
    meta = dict(row.get("_meta") or {})
    if meta.get("slice") != exp_slice or meta.get("slice_label_zh") != exp_label:
        meta["slice"] = exp_slice
        meta["slice_label_zh"] = exp_label
        row["_meta"] = meta
        fixed.append("synced _meta.slice + slice_label_zh from bucket")
    return fixed


def run(
    path: Path,
    *,
    out_jsonl: Path | None,
    out_report: Path,
    dry_run: bool,
) -> None:
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    audits: list[RowAudit] = []
    stats: dict[str, int] = defaultdict(int)
    by_code: dict[str, list[str]] = defaultdict(list)

    cleaned_rows: list[dict] = []

    for line in lines:
        row = json.loads(line)
        sid = row.get("sample_id", "?")
        row_copy = copy.deepcopy(row)
        auto_fixed: list[str] = []
        if not dry_run:
            auto_fixed = _auto_fix_meta(row_copy)
        issues: list[Issue] = []
        _validate_schema(row_copy, issues=issues)
        _heuristic_review(row_copy, issues=issues)

        cleaned_rows.append(row_copy)

        for iss in issues:
            stats[iss.severity] += 1
            by_code[iss.code].append(sid)
        audits.append(RowAudit(sample_id=sid, issues=issues, auto_fixed=auto_fixed))

    # Write JSONL
    if out_jsonl and not dry_run:
        out_jsonl.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in cleaned_rows) + "\n",
            encoding="utf-8",
        )

    # Report markdown
    lines_out: list[str] = []
    lines_out.append("# Phase 2A 训练数据清洗报告\n")
    lines_out.append("\n## 执行摘要\n\n")
    lines_out.append(f"- **ERROR**（必须修）: {stats.get('ERROR', 0)} 条\n")
    lines_out.append(f"- **WARN**（建议修）: {stats.get('WARN', 0)} 条\n")
    lines_out.append(f"- **REVIEW**（人工复核）: {stats.get('REVIEW', 0)} 条\n")
    lines_out.append(
        "- 详见下方「需优先人工复核」表与「全量逐条」；附录含 decision_type / bucket / 工具分布与重复 query。\n"
    )
    lines_out.append("\n## 元信息\n\n")
    lines_out.append(f"- 源文件: `{path.relative_to(ROOT)}`\n")
    lines_out.append(f"- 条数: {len(audits)}\n")
    lines_out.append(
        "- 自动修补: `_meta.slice` / `slice_label_zh` 与 `bucket` 对齐（见 `*.cleaned.jsonl`）\n"
    )
    lines_out.append("\n## 汇总：按问题代码（sample_id 列表）\n")

    for code in sorted(by_code.keys()):
        ids = by_code[code]
        lines_out.append(f"\n### `{code}`（{len(ids)} 条）\n")
        lines_out.append(", ".join(f"`{x}`" for x in ids[:80]))
        if len(ids) > 80:
            lines_out.append(f"\n… 共 {len(ids)} 条\n")

    lines_out.append("\n## 需优先人工复核（REVIEW + ERROR）\n")
    lines_out.append("| sample_id | 级别 | 代码 | 说明 |\n")
    lines_out.append("|-----------|------|------|------|\n")
    for a in audits:
        for iss in a.issues:
            if iss.severity in ("ERROR", "REVIEW"):
                msg = iss.message.replace("|", "\\|")
                lines_out.append(f"| `{a.sample_id}` | {iss.severity} | `{iss.code}` | {msg} |\n")

    lines_out.append("\n## 全量逐条（含 WARN）\n")
    for a in audits:
        if not a.issues and not a.auto_fixed:
            continue
        lines_out.append(f"\n### `{a.sample_id}`\n")
        if a.auto_fixed:
            lines_out.append(f"- **auto**: {', '.join(a.auto_fixed)}\n")
        for iss in a.issues:
            lines_out.append(f"- **{iss.severity}** [`{iss.code}`]: {iss.message}\n")

    # 分布与重复 query
    dt_c = Counter(r.get("decision_type") for r in cleaned_rows)
    bk_c = Counter(r.get("bucket") for r in cleaned_rows)
    tool_c = Counter()
    for r in cleaned_rows:
        if r.get("decision_type") == "tool_call" and r.get("tool_name"):
            tool_c[r["tool_name"]] += 1
    qmap: dict[str, list[str]] = defaultdict(list)
    for r in cleaned_rows:
        q = (r.get("query") or "").strip()
        if q:
            qmap[q].append(r.get("sample_id", "?"))
    dup_queries = {q: ids for q, ids in qmap.items() if len(ids) > 1}

    stats_lines = [
        "\n---\n\n## 附录：分布统计\n\n",
        "| decision_type | 条数 |\n|---|---:|\n",
    ]
    for k in sorted(dt_c.keys()):
        stats_lines.append(f"| `{k}` | {dt_c[k]} |\n")
    stats_lines.append("\n| bucket | 条数 |\n|---|---:|\n")
    for k in sorted(bk_c.keys()):
        stats_lines.append(f"| `{k}` | {bk_c[k]} |\n")
    stats_lines.append("\n### tool_call 工具分布\n\n| tool_name | 条数 |\n|---|---:|\n")
    for k in sorted(tool_c.keys()):
        stats_lines.append(f"| `{k}` | {tool_c[k]} |\n")
    if dup_queries:
        stats_lines.append("\n### 完全重复 query（需人工判断是否保留多条）\n\n")
        for q, ids in sorted(dup_queries.items(), key=lambda x: -len(x[1]))[:30]:
            stats_lines.append(f"- {len(ids)} 条: " + ", ".join(f"`{i}`" for i in ids) + "\n")
            preview = q[:120].replace("\n", " ")
            stats_lines.append(f"  - 文本预览: {preview}{'…' if len(q)>120 else ''}\n")
    else:
        stats_lines.append("\n### 完全重复 query\n\n无。\n")

    out_report.write_text("".join(lines_out) + "".join(stats_lines), encoding="utf-8")
    print(f"Report -> {out_report}")
    if out_jsonl and not dry_run:
        print(f"Cleaned -> {out_jsonl} ({len(cleaned_rows)} rows)")


def extract_manual_review(
    path: Path,
    out_path: Path,
) -> int:
    """写出含至少一条 REVIEW 的样本；每条增加 `_manual_review`: [{{code, message}}, ...]。"""
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    out_rows: list[dict] = []
    for line in lines:
        row = json.loads(line)
        issues = collect_issues(row)
        rev = [i for i in issues if i.severity == "REVIEW"]
        if not rev:
            continue
        out = copy.deepcopy(row)
        out["_manual_review"] = [{"code": i.code, "message": i.message} for i in rev]
        out_rows.append(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in out_rows) + "\n",
        encoding="utf-8",
    )
    return len(out_rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--input",
        type=Path,
        default=ROOT / "experiments" / "data_flywheel" / "out" / "ft_qa_500_train.jsonl",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help="清洗后 JSONL（默认与输入同目录 ft_qa_500_train.cleaned.jsonl）",
    )
    ap.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Markdown 报告路径",
    )
    ap.add_argument(
        "--extract-review",
        action="store_true",
        help="仅导出需人工复核（REVIEW）样本到 *.manual_review.jsonl",
    )
    ap.add_argument(
        "--review-out",
        type=Path,
        default=None,
        help="人工复核子集输出路径（默认 与输入同目录 *.manual_review.jsonl）",
    )
    ap.add_argument("--dry-run", action="store_true", help="不写 cleaned 文件，只写报告")
    args = ap.parse_args()

    inp = args.input
    if not inp.is_file():
        raise SystemExit(f"missing {inp}")

    out_dir = inp.parent
    if args.extract_review:
        review_path = args.review_out or (out_dir / f"{inp.stem}.manual_review.jsonl")
        n = extract_manual_review(inp, review_path)
        print(f"人工复核子集: {n} 条 -> {review_path}")
        return

    out_jsonl = None if args.dry_run else (args.out or (out_dir / f"{inp.stem}.cleaned.jsonl"))
    report = args.report or (out_dir / f"{inp.stem}.CLEAN_REPORT.md")

    run(inp, out_jsonl=out_jsonl, out_report=report, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
