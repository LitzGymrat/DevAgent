"""
离线审计：用**当前磁盘上的** Chroma/BM25 索引，对题面跑与 search_codebase 一致的 dense top1，
并结合「题面中的代码型符号是否在 src/ 中出现、是否出现在 dense top1 片段里」，
打 **index_gap_suspected**（索引缺口嫌疑：源码里能搜到符号，但 dense 召回弱且 top1 片段未覆盖该符号）。

不调用 LLM。需已建库（与 Agent 评测同一 persist 路径）。

用法（项目根）：
  python scripts/audit_vector_index_coverage.py
  python scripts/audit_vector_index_coverage.py --judge-jsonl data/e2e_llm_judge_full_round2.jsonl --bad-only
  python scripts/audit_vector_index_coverage.py --out data/audit/vector_index_audit.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import settings
from src.rag.vectorstore import VectorStore

# 题面里太泛的英文词，不参与「源码是否出现」
_SKIP_WORDS = frozenset(
    {
        "what", "where", "when", "which", "how", "does", "the", "and", "for", "with",
        "from", "that", "this", "your", "have", "been", "will", "into", "about",
        "fastapi", "python", "docker", "github", "json", "api", "http", "https",
        "streamlit", "chrom", "bm25", "query", "dockerfile", "actions", "lora",
    }
)


def _load_src_blob(src_root: Path) -> str:
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


def _interesting_tokens(question: str) -> list[str]:
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


def _bad_filter(row: dict) -> bool:
    if row.get("error"):
        return False
    if not row.get("final_judgement"):
        return False
    return (
        row.get("final_judgement") != "correct"
        or not row.get("grounding_appropriate")
        or row.get("context_pollution")
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="审计向量库对题面的 dense/BM25 召回（索引缺口嫌疑）")
    ap.add_argument(
        "--jsonl",
        type=Path,
        default=ROOT / "data" / "e2e_eval_log_promptv2.jsonl",
        help="含 question / sample_id 的 JSONL（默认 promptv2 E2E）",
    )
    ap.add_argument(
        "--judge-jsonl",
        type=Path,
        default=None,
        help="若指定且 --bad-only：只保留其中 bad case 的 sample_id",
    )
    ap.add_argument("--bad-only", action="store_true", help="仅输出 Judge 定义的 bad case（需配合 --judge-jsonl）")
    ap.add_argument(
        "--threshold",
        type=float,
        default=1.12,
        help="与 E2E 软熔断一致的 dense top1 距离阈值（大于则视为召回弱）",
    )
    ap.add_argument("--src-root", type=Path, default=ROOT / "src", help="源码根目录，用于符号命中")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "audit" / "vector_index_audit.jsonl")
    args = ap.parse_args()

    if not args.jsonl.is_file():
        print(f"找不到 {args.jsonl}", file=sys.stderr)
        sys.exit(1)

    rows_in = []
    for line in args.jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows_in.append(json.loads(line))

    bad_ids: set[str] | None = None
    if args.bad_only:
        if not args.judge_jsonl or not args.judge_jsonl.is_file():
            print("使用 --bad-only 时必须提供存在的 --judge-jsonl", file=sys.stderr)
            sys.exit(1)
        bad_ids = set()
        for line in args.judge_jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            jr = json.loads(line)
            if _bad_filter(jr):
                bad_ids.add(jr["sample_id"])
        rows_in = [r for r in rows_in if r.get("sample_id") in bad_ids]

    print(f"加载源码扫描串（{args.src_root}）…")
    src_blob = _load_src_blob(args.src_root.resolve())
    print(f"加载向量库（Chroma={settings.Chroma_persist_dir}）…")
    vs = VectorStore()
    vs.load()

    thr = args.threshold
    out_rows: list[dict] = []

    for rec in rows_in:
        sid = rec.get("sample_id")
        q = (rec.get("question") or "").strip()
        if not sid or not q:
            continue

        doc, dist = vs.dense_top1_with_distance(q)
        top1_src = str(doc.metadata.get("source", "")) if doc else None
        top1_text = (doc.page_content or "") if doc else ""

        bm25_docs = vs.bm25_retriever.search(q, top_k=1) if vs.bm25_retriever and vs.bm25_retriever.bm25 else []
        bm25_top1_src = str(bm25_docs[0].metadata.get("source", "")) if bm25_docs else None

        weak = dist is None or (dist is not None and float(dist) > thr)
        tokens = _interesting_tokens(q)
        in_src = [t for t in tokens if t in src_blob]
        in_top1 = [t for t in in_src if t in top1_text]
        missed = [t for t in in_src if t not in top1_text]

        # 1) 距离弱 + 源码有符号但 top1 未覆盖 → 典型「索引/召回缺口」嫌疑
        # 2) 距离不弱但源码符号未进 top1 → 可能误召、切块边界、或嵌入漂移，仍值得对照 badcase
        index_gap_suspected = bool(weak and missed)
        dense_top1_misses_src_symbols = bool(missed)

        out_rows.append(
            {
                "sample_id": sid,
                "question": q,
                "dense_top1_distance": dist,
                "dense_top1_source": top1_src,
                "bm25_top1_source": bm25_top1_src,
                "soft_fuse_threshold": thr,
                "retrieval_weak_dense": weak,
                "symbols_from_question": tokens,
                "symbols_hit_in_src": in_src,
                "symbols_hit_in_dense_top1": in_top1,
                "symbols_in_src_not_in_dense_top1": missed,
                "dense_top1_misses_src_symbols": dense_top1_misses_src_symbols,
                "index_gap_suspected": index_gap_suspected,
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fp:
        for r in out_rows:
            fp.write(json.dumps(r, ensure_ascii=False) + "\n")

    n_gap = sum(1 for r in out_rows if r["index_gap_suspected"])
    n_weak = sum(1 for r in out_rows if r["retrieval_weak_dense"])
    n_miss = sum(1 for r in out_rows if r["dense_top1_misses_src_symbols"])
    print(
        f"写入 {args.out} 共 {len(out_rows)} 条；"
        f"retrieval_weak_dense={n_weak}，"
        f"dense_top1_misses_src_symbols={n_miss}，"
        f"index_gap_suspected={n_gap}"
    )


if __name__ == "__main__":
    main()
