"""
直接读 Chroma 持久化文件 **chroma.sqlite3**（不经过 LangChain），
检查 `embedding_metadata` 里 `chroma:document` 文本是否包含题面符号。

用于区分：
- **索引内无**：SQLite 里任意 chunk 都不含该符号 → 多为建库过旧 / 仅索引了 src 子集
- **索引内有**：向量侧有文本，但检索仍失败 → 多为 embedding/查询侧

默认对比两个常见路径（若存在）：
  data/chorma/chroma.sqlite3  （与 `Chroma_persist_dir` 默认一致）
  data/Chroma/chroma.sqlite3  （历史或空库，常与配置不一致）

用法（项目根）：
  python scripts/analyze_badcase_chroma_sqlite.py
  python scripts/analyze_badcase_chroma_sqlite.py --db data/chorma/chroma.sqlite3 --out data/audit/badcase_chroma_sqlite_audit.md
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import settings

_SKIP_WORDS = frozenset(
    {
        "what", "where", "when", "which", "how", "does", "the", "and", "for", "with",
        "from", "that", "this", "your", "have", "been", "will", "into", "about",
        "fastapi", "python", "docker", "github", "json", "api", "http", "https",
        "streamlit", "chrom", "bm25", "query", "dockerfile", "actions", "lora",
    }
)


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
    if row.get("error") or not row.get("final_judgement"):
        return False
    return (
        row.get("final_judgement") != "correct"
        or not row.get("grounding_appropriate")
        or row.get("context_pollution")
    )


def load_all_documents(db_path: Path) -> tuple[list[tuple[int, str, str]], int]:
    """返回 [(embedding_id, source, document_text), ...]，以及 embeddings 行数。"""
    if not db_path.is_file():
        return [], 0
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute("SELECT COUNT(*) FROM embeddings")
        n_emb = int(cur.fetchone()[0])
        cur = conn.execute(
            """
            SELECT e.id, s.string_value AS source, d.string_value AS doc
            FROM embeddings e
            JOIN embedding_metadata s ON s.id = e.id AND s.key = 'source'
            JOIN embedding_metadata d ON d.id = e.id AND d.key = 'chroma:document'
            ORDER BY e.id
            """
        )
        rows = [(int(r[0]), r[1] or "", r[2] or "") for r in cur.fetchall()]
        return rows, n_emb
    finally:
        conn.close()


def token_hit_in_index(docs: list[tuple[int, str, str]], token: str) -> tuple[bool, list[str]]:
    """是否在任一 chunk 文本中出现；返回 (命中, 命中的 source 列表)。"""
    hits: list[str] = []
    for _eid, src, text in docs:
        if token in text:
            hits.append(src)
    return bool(hits), hits


def main() -> None:
    ap = argparse.ArgumentParser(description="从 chroma.sqlite3 直接审计 badcase 相关符号是否在索引文本中")
    ap.add_argument(
        "--db",
        type=Path,
        default=None,
        help="chroma.sqlite3 路径；默认使用 settings.Chroma_persist_dir/chroma.sqlite3",
    )
    ap.add_argument(
        "--also-scan",
        type=Path,
        nargs="*",
        default=[ROOT / "data" / "Chroma" / "chroma.sqlite3"],
        help="额外扫描的 sqlite 路径（用于对比空库/历史目录）",
    )
    ap.add_argument(
        "--judge-jsonl",
        type=Path,
        default=ROOT / "data" / "e2e_llm_judge_full_round2.jsonl",
        help="Judge 全量/第二轮结果，用于筛 badcase",
    )
    ap.add_argument(
        "--e2e-jsonl",
        type=Path,
        default=ROOT / "data" / "e2e_eval_log_promptv2.jsonl",
        help="取题干",
    )
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "audit" / "badcase_chroma_sqlite_audit.md")
    args = ap.parse_args()

    db_main = args.db or (ROOT / settings.Chroma_persist_dir / "chroma.sqlite3").resolve()
    if not db_main.is_file():
        print(f"找不到主库: {db_main}", file=sys.stderr)
        sys.exit(1)

    judge_path = args.judge_jsonl
    if not judge_path.is_file():
        print(f"找不到 {judge_path}", file=sys.stderr)
        sys.exit(1)

    bad_ids: set[str] = set()
    for line in judge_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        jr = json.loads(line)
        if _bad_filter(jr):
            bad_ids.add(jr["sample_id"])

    by_id: dict[str, dict] = {}
    for line in args.e2e_jsonl.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        sid = rec.get("sample_id")
        if sid in bad_ids:
            by_id[sid] = rec

    docs_main, n_emb_main = load_all_documents(db_main)

    extra_dbs: list[tuple[str, list[tuple[int, str, str]], int]] = []
    for p in args.also_scan:
        if p and Path(p).is_file():
            d, n = load_all_documents(Path(p))
            extra_dbs.append((str(p.resolve()), d, n))

    lines: list[str] = [
        "# Badcase × Chroma `chroma.sqlite3` 直接审计",
        "",
        "说明：读取 SQLite 表 `embedding_metadata` 中 `key='chroma:document'` 的**已入库全文**，"
        "判断题面中的代码型符号是否**字面出现在任意 chunk 里**（与向量检索是否召回到无关）。",
        "",
        f"- **配置中的持久化目录**：`Chroma_persist_dir` = `{settings.Chroma_persist_dir}`",
        f"- **本报告主库**：`{db_main}`（embeddings 行数 **{n_emb_main}**，可解析文档块 **{len(docs_main)}**）",
        "",
    ]

    for path, docs, nemb in extra_dbs:
        lines.append(f"- **对照库**：`{path}`（embeddings **{nemb}**，块 **{len(docs)}**）")
    lines.append("")

    if n_emb_main == 0:
        lines += ["⚠ 主库 **无向量行**：Agent 若指向该路径则检索为空；请检查 `.env` 是否指向含数据的目录。", ""]

    lines += [
        "## 结论怎么用",
        "",
        "| 符号在 **当前 src** | 符号在 **chroma.sqlite3 文本** | 含义 |",
        "|---|---|---|",
        "| 有 | 无 | 建库后源码已改 / 从未索引到该段 → **先重建索引**再评 E2E |",
        "| 有 | 有 | 索引里有字，但检索仍差 → 查 query/嵌入/阈值，而非「库里没有」 |",
        "| 无 | 无 | 题面超出仓库或 gold 过严 |",
        "",
        "## 逐条 badcase（第二轮）",
        "",
    ]

    for sid in sorted(bad_ids):
        rec = by_id.get(sid, {})
        q = (rec.get("question") or "").strip()
        tokens = _interesting_tokens(q)
        top1 = rec.get("top1_distance")
        sf = rec.get("soft_fallback_triggered")
        lines.append(f"### {sid}")
        lines.append("")
        lines.append(f"- **题干**：{q}")
        lines.append(f"- **E2E**：`top1_distance={top1}`，`soft_fallback_triggered={sf}`")
        lines.append("")

        if not tokens:
            lines.append("- **题面可抽取符号**：无（多为中文题或短词）→ 需人工看 SQLite 全文或改题库关键词。")
            lines.append("")
            continue

        lines.append("| 符号 | 在主库 chunk 中出现？ | 命中的 source（若有） |")
        lines.append("|------|----------------------|------------------------|")
        for tok in tokens:
            hit, srcs = token_hit_in_index(docs_main, tok)
            uniq = sorted(set(srcs))[:8]
            suf = "…" if len(set(srcs)) > 8 else ""
            note = ""
            if not hit and tok.lower() == "scripts" and (ROOT / "scripts").is_dir():
                note = " （提示：`build_knowledge_base` 只索引 `src/`，**`scripts/` 不在向量库范围**）"
            lines.append(f"| `{tok}` | {'是' if hit else '**否**'} | {', '.join(uniq)}{suf}{note} |")
        if extra_dbs:
            alt = extra_dbs[0]
            lines.append("")
            lines.append(f"对照库 `{alt[0]}`：")
            for tok in tokens:
                hit, _ = token_hit_in_index(alt[1], tok)
                lines.append(f"- `{tok}` → {'有' if hit else '无'}")
        lines.append("")

    lines += [
        "---",
        "",
        f"生成：`python scripts/analyze_badcase_chroma_sqlite.py`",
    ]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines), encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
