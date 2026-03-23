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
| [08-软熔断Phase1与端到端评测](./08-软熔断Phase1与端到端评测.md) | Dense 距离标定 + 全链路 90 条快照（`data/` 落盘）；E2E 第一层 gold 见 `e2e_manifest.py`（`grounding_tier`） |
| [09-prompt与工具描述优化后复测](./09-prompt与工具描述优化后复测.md) | 优化 prompt / `search_codebase` 描述后 E2E 对照；离线重算（`rescore_e2e_jsonl.py`）+ **bad case**（`analyze_e2e_badcase.py` → `data/reports/e2e_badcase_report_*.md`） |
| [10-LLM-as-Judge-v1](./10-LLM-as-Judge-v1.md) | E2E **第三层**：按桶标准 + 统一四项；抽样 22 条；`scripts/eval_llm_judge_e2e.py` → `data/eval/e2e_llm_judge_phase1.jsonl` |
| [11-Phase2A路由SFT微调报告](./11-Phase2A路由SFT微调报告.md) | Phase 2A **单轮路由** SFT：数据/ShareGPT/评测指标；Base vs LoRA vs API（50 条） |
| [12-咨询展示-进展与路线图](./12-咨询展示-进展与路线图.md) | **咨询口述**：**三关键点**（检索闭环 · 飞轮+路由SFT · RAGAS/Self-RAG 计划） |
| [12-咨询展示-展示版.html](./12-咨询展示-展示版.html) | **一页展示**（浏览器打开）：关键数据表、Phase1/E2E/Phase2A 数字 |

## 检索模块结论摘要

- **默认引擎**：纯 Dense（Qwen text-embedding-v4）
- **不启用**：Reranker、Hybrid（BM25 在代码语料中引入噪声）
- **Query Rewrite**：对口语化 query 有显著提升（MRR +16.5%）
