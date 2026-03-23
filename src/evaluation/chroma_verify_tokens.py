"""题面符号抽取（与 scripts/audit_vector_index_coverage.py 一致）。"""
from __future__ import annotations

import re
from pathlib import Path


def load_src_py_blob(src_root: Path) -> str:
    parts: list[str] = []
    for p in sorted(src_root.rglob("*.py")):
        s = str(p)
        if any(x in s for x in (".venv", "venv", "node_modules", "__pycache__")):
            continue
        try:
            parts.append(p.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            pass
    return "\n".join(parts)

_SKIP_WORDS = frozenset(
    {
        "what", "where", "when", "which", "how", "does", "the", "and", "for", "with",
        "from", "that", "this", "your", "have", "been", "will", "into", "about",
        "fastapi", "python", "docker", "github", "json", "api", "http", "https",
        "streamlit", "chrom", "bm25", "query", "dockerfile", "actions", "lora",
    }
)


def interesting_tokens(question: str) -> list[str]:
    raw = re.findall(r"[a-zA-Z_][a-zA-Z0-9_]*", question)
    out: list[str] = []
    seen: set[str] = set()
    for t in raw:
        tl = t.lower()
        if len(t) < 3 or tl in _SKIP_WORDS:
            continue
        if len(t) < 5 and "_" not in t:
            continue
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def extra_anchor_tokens(question: str) -> list[str]:
    """题面涉及 rewriter 等但单拆词匹配不到类名时补充。"""
    q = question
    extra: list[str] = []
    if re.search(r"rewriter|rewrite|改写", q, re.I):
        for t in ("query_rewriter", "Query_rewriter"):
            if t not in extra:
                extra.append(t)
    return extra
