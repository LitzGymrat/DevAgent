# DevAgent 评估文档

本目录包含 DevAgent 项目的各类评估实验记录与结论。

## 文档索引

| 文件 | 内容 |
|------|------|
| [01-检索评估-引擎对比-基线](./01-检索评估-引擎对比-基线.md) | Dense / BM25 / Hybrid 三种检索引擎基线对比 |
| [02-检索评估-PoolSize对比](./02-检索评估-PoolSize对比.md) | Hybrid 检索中 pool_size（10 vs 20）调参实验 |
| [03-检索评估-Reranker消融实验](./03-检索评估-Reranker消融实验.md) | BGE-base、GTE-v2、不精排 消融对比 |
| [04-检索评估-QueryRewrite消融实验](./04-检索评估-QueryRewrite消融实验.md) | Query Rewrite 对检索 MRR 的影响 |
| [05-LoRA微调评估报告](./05-LoRA微调评估报告.md) | LoRA 微调后 JSON 遵循率、工具路由准确率等 |
| [06-Agent工具组合示例](./06-Agent工具组合示例.md) | Agent 多工具串联（Tool Chaining）示例 |
| [07-附录-VectorStore实现说明](./07-附录-VectorStore实现说明.md) | VectorStore 类实现摘要（来自 search_codebase 输出）|

## 检索模块结论摘要

- **默认引擎**：纯 Dense（Qwen text-embedding-v4）
- **不启用**：Reranker、Hybrid（BM25 在代码语料中引入噪声）
- **Query Rewrite**：对口语化 query 有显著提升（MRR +16.5%）
