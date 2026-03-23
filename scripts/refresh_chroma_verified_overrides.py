"""
从 **chroma.sqlite3** 读取已入库全文，与 **src/**/*.py** 对照，
对第二轮 **domain badcase** 自动判定：哪些题面锚点「在 src 有、在 Chroma 无」或「问 scripts/（建库不含）」，
写入 **`data/chroma_verified_skip_must_ground.json`**，供 `e2e_manifest.grounding_tier_index_aware` 使用。

不调用 LLM。跑完后请执行：
  python scripts/report_judge_round2_index_aware.py
  python scripts/export_llm_judge_badcase_md.py

用法（项目根）：
  python scripts/refresh_chroma_verified_overrides.py
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import settings
from src.evaluation.chroma_verify_tokens import (
    extra_anchor_tokens,
    interesting_tokens,
    load_src_py_blob,
)
from src.evaluation.e2e_manifest import _domain_grounding_tier


def _bad_filter(row: dict) -> bool:
    if row.get("error") or not row.get("final_judgement"):
        return False
    return (
        row.get("final_judgement") != "correct"
        or not row.get("grounding_appropriate")
        or row.get("context_pollution")
    )


def load_chroma_concat(db_path: Path) -> str:
    conn = sqlite3.connect(str(db_path))
    try:
        cur = conn.execute(
            "SELECT string_value FROM embedding_metadata WHERE key='chroma:document'"
        )
        parts = [r[0] or "" for r in cur.fetchall()]
        return "\n".join(parts)
    finally:
        conn.close()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--sqlite",
        type=Path,
        default=None,
        help="chroma.sqlite3 路径，默认 Chroma_persist_dir/chroma.sqlite3",
    )
    ap.add_argument(
        "--judge",
        type=Path,
        default=ROOT / "data" / "e2e_llm_judge_full_round2.jsonl",
    )
    ap.add_argument(
        "--e2e",
        type=Path,
        default=ROOT / "data" / "e2e_eval_log_promptv2.jsonl",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=ROOT / "data" / "chroma_verified_skip_must_ground.json",
    )
    ap.add_argument("--src-root", type=Path, default=ROOT / "src")
    args = ap.parse_args()

    db = args.sqlite or (ROOT / settings.Chroma_persist_dir / "chroma.sqlite3").resolve()
    if not db.is_file():
        print(f"找不到 {db}", file=sys.stderr)
        sys.exit(1)

    chroma_blob = load_chroma_concat(db)
    src_blob = load_src_py_blob(args.src_root.resolve())
    scripts_dir = ROOT / "scripts"

    by_q: dict[str, str] = {}
    for line in args.e2e.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        by_q[o["sample_id"]] = (o.get("question") or "").strip()

    bad_domain: list[tuple[str, str]] = []
    for line in args.judge.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        jr = json.loads(line)
        if not _bad_filter(jr):
            continue
        sid = jr["sample_id"]
        if not sid.startswith("p"):
            continue
        bad_domain.append((sid, by_q.get(sid, "")))

    entries: dict[str, dict] = {}
    for sid, q in sorted(bad_domain, key=lambda x: x[0]):
        legacy = _domain_grounding_tier(sid)
        tokens = list(dict.fromkeys(interesting_tokens(q) + extra_anchor_tokens(q)))

        # 规则 1：问 scripts 目录且建库不含 scripts/
        scripts_ask = bool(re.search(r"scripts\s*目录|scripts\s*里|scripts\s+目录", q, re.I))
        if scripts_ask and scripts_dir.is_dir():
            in_chroma = "scripts" in chroma_blob or "build_knowledge_base" in chroma_blob
            if not in_chroma:
                entries[sid] = {
                    "tier": "ok_generic",
                    "reason": "scripts_scope",
                    "detail": "题面指向 scripts/；建库仅索引 src，向量库不含该目录；已核对 chroma.sqlite3 全文无 scripts 建库脚本片段",
                    "legacy_tier": legacy,
                }
                continue

        missing: list[str] = []
        for tok in tokens:
            if tok in src_blob and tok not in chroma_blob:
                missing.append(tok)

        if legacy == "must_ground" and missing:
            entries[sid] = {
                "tier": "prefer_ground",
                "reason": "src_yes_chroma_no",
                "missing_tokens_in_chroma": missing,
                "tokens_checked": tokens,
                "legacy_tier": legacy,
                "detail": "符号在 src 中存在，但在 chroma.sqlite3 任意 chunk 全文里未出现（索引过旧或未覆盖）",
            }

    n_emb = 0
    conn = sqlite3.connect(str(db))
    try:
        cur = conn.execute("SELECT COUNT(*) FROM embeddings")
        n_emb = int(cur.fetchone()[0])
    finally:
        conn.close()

    try:
        sqlite_disp = db.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        sqlite_disp = str(db.resolve())
    payload = {
        "chroma_sqlite": sqlite_disp,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "embeddings_count": n_emb,
        "chroma_document_chars": len(chroma_blob),
        "entries": entries,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"写入 {args.out}，共 {len(entries)} 条 verified 降级项")
    for sid, e in sorted(entries.items()):
        print(f"  {sid}: {e['tier']} ({e['reason']})")


if __name__ == "__main__":
    main()
