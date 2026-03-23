"""
按人工复核表修补 ft_qa_500_train.jsonl：
- A：删除非任务型样本
- B：domain 通识题迁到 far_general（重编号 sample_id）
- C：统一 clarify vs tool_call 边界
- D：from_pretrained：domain_0127 → search_codebase；0061/0184 保持 analyse_log
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "experiments" / "data_flywheel" / "out" / "ft_qa_500_train.jsonl"

DELETE_IDS = frozenset(
    {
        "domain_0037",
        "domain_0256",
        "domain_0137",
        "domain_0035",
    }
)

MIGRATE_DOMAIN_TO_FAR_GENERAL: tuple[str, ...] = (
    "domain_0015",
    "domain_0016",
    "domain_0017",
    "domain_0036",
    "domain_0115",
    "domain_0136",
    "domain_0176",
    "domain_0236",
    "domain_0237",
    "domain_0312",
)


def _patch_row(sample_id: str, row: dict) -> dict:
    r = dict(row)

    if sample_id == "misleading_edge_0067":
        r["decision_type"] = "clarify_needed"
        r["tool_name"] = None
        r["arguments"] = None
        r["clarify_answer"] = "请指出是哪段代码或文件「太乱」，或直接贴出需要评审/重构的片段。"
        r["oracle_context"] = None

    elif sample_id == "misleading_edge_0019":
        r["decision_type"] = "tool_call"
        r["tool_name"] = "search_codebase"
        r["arguments"] = {
            "query": "nginx proxy_pass configuration deploy",
            "top_k": 6,
        }
        r["clarify_answer"] = None
        r["oracle_context"] = "方向明确：先在仓库内检索 Nginx/部署相关配置。"

    elif sample_id == "misleading_edge_0058":
        r["decision_type"] = "tool_call"
        r["tool_name"] = "search_codebase"
        r["arguments"] = {"query": "auth authentication security login", "top_k": 6}
        r["clarify_answer"] = None
        r["oracle_context"] = None

    elif sample_id == "misleading_edge_0023":
        r["decision_type"] = "clarify_needed"
        r["tool_name"] = None
        r["arguments"] = None
        r["clarify_answer"] = (
            "上下文过短，无法做有意义的性能分析；请说明目标规模、瓶颈现象或提供 profiling/耗时数据。"
        )
        r["oracle_context"] = None

    elif sample_id == "misleading_edge_0065":
        r["decision_type"] = "tool_call"
        r["tool_name"] = "analyse_code"
        r["arguments"] = {"code": "result = users[0].get_profile()"}
        r["clarify_answer"] = None
        r["oracle_context"] = None

    elif sample_id == "domain_0300":
        r["decision_type"] = "tool_call"
        r["tool_name"] = "search_codebase"
        r["arguments"] = {
            "query": "FastAPI APIRouter route registration include_router",
            "top_k": 6,
        }
        r["clarify_answer"] = None
        r["oracle_context"] = None

    elif sample_id == "domain_0127":
        r["decision_type"] = "tool_call"
        r["tool_name"] = "search_codebase"
        r["arguments"] = {
            "query": "from_pretrained AutoConfig load config modeling_utils",
            "top_k": 6,
        }
        r["clarify_answer"] = None
        r["oracle_context"] = "优先在源码侧定位 from_pretrained / Config 加载逻辑。"

    elif sample_id in ("domain_0061", "domain_0184"):
        m = dict(r.get("_meta") or {})
        m["routing_note"] = "D类：含明确报错/Traceback → analyse_log（归因）。"
        r["_meta"] = m

    return r


def main() -> None:
    if not DATA.is_file():
        raise SystemExit(f"missing {DATA}")

    shutil.copy2(DATA, DATA.with_suffix(".jsonl.bak"))

    rows: list[dict] = []
    for line in DATA.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))

    max_fg = 0
    for r in rows:
        sid = r.get("sample_id", "")
        if sid.startswith("far_general_"):
            try:
                max_fg = max(max_fg, int(sid.removeprefix("far_general_")))
            except ValueError:
                pass

    migrate_order = sorted(MIGRATE_DOMAIN_TO_FAR_GENERAL)
    migrate_new_ids: dict[str, str] = {
        old: f"far_general_{max_fg + 1 + i:04d}"
        for i, old in enumerate(migrate_order)
    }

    out_rows: list[dict] = []
    for r in rows:
        sid = r["sample_id"]
        if sid in DELETE_IDS:
            continue
        r = _patch_row(sid, r)
        if sid in migrate_new_ids:
            meta = dict(r.get("_meta") or {})
            meta["slice"] = "dev_general_no_rag"
            meta["slice_label_zh"] = "开发通识（无需查库）"
            meta["bucket_migrated_from"] = "domain"
            r["bucket"] = "far_general"
            r["sample_id"] = migrate_new_ids[sid]
            r["_meta"] = meta
        out_rows.append(r)

    DATA.write_text(
        "\n".join(json.dumps(x, ensure_ascii=False) for x in out_rows) + "\n",
        encoding="utf-8",
    )
    print(f"backup -> {DATA.with_suffix('.jsonl.bak')}")
    print(f"wrote {len(out_rows)} rows (removed {len(rows) - len(out_rows)}) -> {DATA}")


if __name__ == "__main__":
    main()
