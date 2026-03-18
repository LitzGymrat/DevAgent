# 附录：VectorStore 类实现说明

> 以下内容来自 Agent 调用 `search_codebase` 工具后的输出摘要。

## 类定义位置

`VectorStore` 类位于 `rag/vectorstore.py`，使用 Chroma 构建向量数据库引擎。

## 核心方法

| 方法 | 功能 |
|------|------|
| `build_index(all_chunks)` | 构建 Dense + BM25 双索引 |
| `load()` | 加载已有向量库 |
| `search_dense(query, top_k)` | 密集向量检索 |
| `search_bm25(query, top_k)` | BM25 稀疏检索 |
| `search_hybrid(query, top_k)` | 混合检索（Dense + BM25 融合）|

## 设计特点

- **混合检索**：支持密集向量 + 稀疏检索（BM25）
- **配置驱动**：通过 `settings` 选择 embedding 提供商（local / qwen）
- **持久化**：支持 Chroma 持久化存储
