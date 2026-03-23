"""
为 experiments/external 下的基准仓库构建 Chroma + BM25 索引（与主工程 VectorStore 逻辑一致）。

默认索引子路径（控制体积与噪声）：
  - transformers → external/transformers/src/transformers
  - fastapi      → external/fastapi/fastapi

产物：
  - experiments/indices/<name>/chroma/
  - experiments/indices/<name>/bm25_index.pkl

默认嵌入：**Qwen**（与主工程 `config` 一致，需 `.env` 中 `qwen_api_key` 等）。
加 `--local` 时改为本地 HuggingFace 嵌入（离线/省配额）。

建库过程会显示 tqdm 进度（加载文件、切分、Chroma 分批嵌入、BM25）。
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.rag.tqdm_util import ensure_line_buffered_stdio


def _corpus_paths(name: str) -> tuple[Path, Path, Path]:
    """Returns (source_dir, chroma_dir, bm25_file)."""
    base = ROOT / "experiments" / "indices" / name
    if name == "transformers":
        src = ROOT / "experiments" / "external" / "transformers" / "src" / "transformers"
    elif name == "fastapi":
        src = ROOT / "experiments" / "external" / "fastapi" / "fastapi"
    else:
        raise ValueError(name)
    return src, base / "chroma", base / "bm25_index.pkl"


def _clean_stale_indices(chroma_dir: Path, bm25_file: Path) -> None:
    """
    删除该语料下已有 Chroma/BM25 文件。
    切换嵌入模型（如 local 384 维 vs Qwen 1024 维）时，复用旧 persist 会触发
    InvalidArgumentError: Collection expecting embedding with dimension of ...
    """
    if chroma_dir.exists():
        print(f"清理旧 Chroma 目录（避免嵌入维度与旧库不一致）: {chroma_dir}", flush=True)
        shutil.rmtree(chroma_dir)
    if bm25_file.exists():
        print(f"清理旧 BM25 文件: {bm25_file}", flush=True)
        bm25_file.unlink()


def _index_chroma_batched(vs, chunks: list, *, batch_size: int) -> None:
    """与 VectorStore.index_document 等价，但按批写入并显示进度。"""
    from langchain_chroma import Chroma
    from src.config import settings
    from src.rag.tqdm_util import tqdm

    if not chunks:
        return
    persist = settings.Chroma_persist_dir
    n = len(chunks)
    total_batches = (n + batch_size - 1) // batch_size
    batch_idx = 0
    for i in tqdm(
        range(0, n, batch_size),
        desc="Chroma 嵌入",
        unit="batch",
        total=total_batches,
    ):
        batch_idx += 1
        # 非 TTY 时 tqdm 可能不显示；每 10 批（及首尾）打一行兜底
        if batch_idx == 1 or batch_idx % 10 == 0 or batch_idx == total_batches:
            print(
                f"[Chroma] 批次 {batch_idx}/{total_batches} · chunk ~{i}-{min(i + batch_size, n) - 1} / {n} total",
                file=sys.stderr,
                flush=True,
            )
        batch = chunks[i : i + batch_size]
        if vs._db is None:
            vs._db = Chroma.from_documents(
                embedding=vs.embeddings,
                persist_directory=persist,
                documents=batch,
            )
        else:
            vs._db.add_documents(batch)
    print(f"DenseChroma 建库成功：{n} 个代码块 → {persist}", flush=True)


def build_one(name: str, *, batch_size: int) -> None:
    from src.config import settings
    from src.rag.loader import RePoLoader
    from src.rag.splitter import CodeSplitter
    from src.rag.vectorstore import VectorStore

    source, chroma_dir, bm25_file = _corpus_paths(name)
    if not source.is_dir():
        raise FileNotFoundError(
            f"缺少源码目录: {source}\n请先克隆到 experiments/external/{name}/"
        )

    settings.Chroma_persist_dir = str(chroma_dir.resolve())
    settings.bm25_persist_dir = str(bm25_file.resolve())
    bm25_file.parent.mkdir(parents=True, exist_ok=True)
    _clean_stale_indices(chroma_dir, bm25_file)

    print(f"=== [{name}] 嵌入: {settings.embedding_provider} | 源: {source}", flush=True)
    print(f"    Chroma: {chroma_dir}", flush=True)
    print(f"    BM25:   {bm25_file}", flush=True)

    loader = RePoLoader(source)
    docs = loader.load(show_progress=True)
    print(f"    已加载 {len(docs)} 个文件", flush=True)

    splitter = CodeSplitter(
        code_chunk_size=settings.code_chunk_size,
        code_chunk_overlap=settings.code_chunk_overlap,
        text_chunk_size=settings.text_chunk_size,
        text_chunk_overlap=settings.text_chunk_overlap,
    )
    chunks = splitter.split(docs, show_progress=True)
    print(f"    切分为 {len(chunks)} 个 chunk", flush=True)

    vs = VectorStore()
    _index_chroma_batched(vs, chunks, batch_size=batch_size)
    vs.bm25_retriever.index_document(chunks)
    print(f"bm25 建库成功 → {settings.bm25_persist_dir}", flush=True)
    print(f"=== [{name}] 完成\n", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="为实验基准库构建 Chroma + BM25 索引")
    parser.add_argument(
        "--corpus",
        choices=("transformers", "fastapi", "all"),
        default="all",
        help="要构建的语料（默认 all）",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="使用本地 HuggingFace 嵌入（离线）；默认使用 Qwen 嵌入，与主工程一致",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=256,
        help="Chroma 嵌入批大小（默认 256；更大通常更快、单次请求更大，遇限流可改回 128）",
    )
    args = parser.parse_args()

    ensure_line_buffered_stdio()

    from src.config import settings

    if args.local:
        settings.embedding_provider = "local"
    else:
        settings.embedding_provider = "qwen"

    print(f"嵌入提供方: {settings.embedding_provider}", flush=True)

    names = ["transformers", "fastapi"] if args.corpus == "all" else [args.corpus]
    for name in names:
        build_one(name, batch_size=max(1, args.batch_size))


if __name__ == "__main__":
    main()
