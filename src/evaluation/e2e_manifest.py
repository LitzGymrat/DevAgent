"""
端到端评测：为每条样本提供 bucket_type 与预期标签（用于工具决策 / 软熔断对照）。

域内（domain）额外使用 grounding_tier，避免「表面通用、但题面在 domain 桶」与严格 gold 冲突：

  - must_ground：应调用 search_codebase，答本仓库实现/路径/配置等（漏调计 FN）。
  - prefer_ground：优先检索更稳，但通识作答可接受（调/不调均不计错）。
  - ok_generic：可不检索，用通识或工具菜单即可（误调检索计 FP）。

should_call_tool 取值：
  - yes / no：与检索期望一致。
  - optional：仅 prefer_ground；评测第一层「严格一致」时调/不调都算对。
"""

from __future__ import annotations

import json
from pathlib import Path

from src.evaluation.soft_fuse_dataset import (
    DOMAIN_IN_PROJECT,
    OUTDOMAIN_FAR_GENERAL,
    OUTDOMAIN_MISLEADING_EDGE,
    OUTDOMAIN_TERM_NEAR_NO_RAG,
)

# 显式列出非 must 的域内题；未出现在此表中的 domain id 均为 must_ground
# ok_generic：此前典型 FN — 教材型 FastAPI、工具名可从 schema 直接答
# prefer_ground：此前典型 FN — 通识与仓库实现重叠，检索更稳但不强制
DOMAIN_GROUNDING_TIER: dict[str, str] = {
    "p01": "ok_generic",
    "p09": "ok_generic",
    "p07": "prefer_ground",
    "p08": "prefer_ground",
    "p15": "prefer_ground",
}

# 与「当前磁盘 Chroma 快照 + 建库范围」对齐的 tier（不覆盖上表，单独合并）
# 来源：badcase × chroma.sqlite3 审计（见 scripts/analyze_badcase_chroma_sqlite.py、data/audit/badcase_chroma_sqlite_audit.md）
# 含义：题面锚点**未**出现在已入库 chunk、或锚点在 **scripts/**（建库仅扫 src）时，不应再标 must_ground，否则与 RAG 可达性不符。
# 保留 DOMAIN_GROUNDING_TIER / grounding_tier 为「原版 gold」，便于前两轮 JSONL 历史对照；新字段见 build_e2e_manifest。
INDEX_AWARE_GROUNDING_TIER_OVERRIDES: dict[str, str] = {
    "p12": "prefer_ground",  # `_prune_memory` 在 src 有、但未出现在 chroma.sqlite3 任意 chunk（索引过旧）
    "p19": "ok_generic",  # 问 scripts/ 目录；建库仅索引 src，scripts 不在向量库范围
    "p17": "prefer_ground",  # Query Rewriter：已入库 chunk 无对应符号 / 未覆盖 query_rewriter 模块
    "p27": "prefer_ground",  # 同上（Rewrite 阶段）
}

_MANIFEST_DIR = Path(__file__).resolve().parent.parent.parent
_CHROMA_VERIFIED_JSON = _MANIFEST_DIR / "data" / "chroma_verified_skip_must_ground.json"


def _index_aware_overrides_merged() -> dict[str, str]:
    """静态表 +（若存在）`data/chroma_verified_skip_must_ground.json`（由 refresh_chroma_verified_overrides.py 生成）。"""
    out = dict(INDEX_AWARE_GROUNDING_TIER_OVERRIDES)
    if _CHROMA_VERIFIED_JSON.is_file():
        data = json.loads(_CHROMA_VERIFIED_JSON.read_text(encoding="utf-8"))
        for sid, rec in data.get("entries", {}).items():
            if isinstance(rec, dict) and rec.get("tier"):
                out[sid] = str(rec["tier"])
    return out


def _domain_grounding_tier(sample_id: str) -> str:
    return DOMAIN_GROUNDING_TIER.get(sample_id, "must_ground")


def grounding_tier_index_aware(sample_id: str) -> str:
    """原版 tier 与 INDEX_AWARE 覆盖合并（仅 domain id 有意义）。"""
    merged = _index_aware_overrides_merged()
    if sample_id in merged:
        return merged[sample_id]
    return _domain_grounding_tier(sample_id)


def _tier_to_should_call_tool(tier: str) -> str:
    if tier == "must_ground":
        return "yes"
    if tier == "prefer_ground":
        return "optional"
    if tier == "ok_generic":
        return "no"
    raise ValueError(f"unknown tier: {tier}")


def _tag(
    items: list[dict],
    bucket_type: str,
    should_call_tool: str,
    should_hit_private: str,
    soft_fallback_if_searched: str,
    grounding_tier: str | None = None,
) -> list[dict]:
    out = []
    for it in items:
        row = {
            **it,
            "bucket_type": bucket_type,
            "should_call_tool": should_call_tool,
            "should_hit_private_knowledge": should_hit_private,
            "should_soft_fallback_if_searched": soft_fallback_if_searched,
        }
        if grounding_tier is not None:
            row["grounding_tier"] = grounding_tier
        out.append(row)
    return out


def build_e2e_manifest() -> list[dict]:
    """共 90 条：域内 40 + 远域 28 + 术语近 12 + 误导 10。"""
    rows: list[dict] = []

    for it in DOMAIN_IN_PROJECT:
        tid = it["id"]
        gt = _domain_grounding_tier(tid)
        sct = _tier_to_should_call_tool(gt)
        gt_ia = grounding_tier_index_aware(tid)
        sct_ia = _tier_to_should_call_tool(gt_ia)
        rows.append(
            {
                **it,
                "bucket_type": "domain",
                "grounding_tier": gt,
                "should_call_tool": sct,
                "grounding_tier_index_aware": gt_ia,
                "should_call_tool_index_aware": sct_ia,
                "should_hit_private_knowledge": "yes",
                "should_soft_fallback_if_searched": "no",
            }
        )

    rows.extend(
        _tag(
            OUTDOMAIN_FAR_GENERAL,
            bucket_type="far_general",
            should_call_tool="no",
            should_hit_private="no",
            soft_fallback_if_searched="yes",
            grounding_tier="n/a",
        )
    )
    rows.extend(
        _tag(
            OUTDOMAIN_TERM_NEAR_NO_RAG,
            bucket_type="term_near_no_rag",
            should_call_tool="no",
            should_hit_private="no",
            soft_fallback_if_searched="yes",
            grounding_tier="n/a",
        )
    )
    rows.extend(
        _tag(
            OUTDOMAIN_MISLEADING_EDGE,
            bucket_type="misleading_edge",
            should_call_tool="no",
            should_hit_private="no",
            soft_fallback_if_searched="yes",
            grounding_tier="n/a",
        )
    )
    return rows
