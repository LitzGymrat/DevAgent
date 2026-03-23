## E2E Bad case（promptv2）
- **文件**：`data/e2e_eval_log_promptv2.jsonl`
- **样本数**：90
- **软熔断阈值（文档/默认）**：T = 1.12（与 `eval_e2e_pipeline --soft-fuse-threshold` 一致时 Chroma distance > T 记为触发）

### L1 False Positive（不应检索却检索）
共 **2** 条。

#### `d18`（far_general）
- **题面**：接口做了幂等键还是偶尔重复扣款，除了幂等表还要查消息重投、超时重试吗？
- **gold**：`should_call_tool=no`，`should_soft_fallback_if_searched=yes`（域外误调后**预期**走软兜底）
- **实际**：已调用 `search_codebase`；`top1_distance`=1.254333734512329；`soft_fallback_triggered`=True
- **解读**：距离 **>** T，软熔断**已触发**，回答转向通用知识，但**第一层仍计 FP**（根本问题是不该调检索）。
- **摘要**：根据检索结果，当前代码仓库中未找到与幂等键、重复扣款、消息重投、超时重试相关的高相关度实现。我将基于通用知识为您分析这个问题。  ## 问题分析  即使接口做了幂等键，仍然出现偶尔重复扣款，这通常涉及以下几个关键方面：  ### 1. **幂等键的实现问题** - **存储时机不当**：幂等键应该在业务操作**之前**就存储到幂等表中，而不是在业务操作之后 - **并发控制缺失**：多个请求同时到达时，需要数据库级别的锁或分布式锁来保证原子性 - **幂等键范围过窄**：幂等键应该覆盖整个业务操作链，而不仅仅是单个接口  ### 2. **消息重投机制*…

#### `m04`（misleading_edge）
- **题面**：LoRA 为什么适合做小模型微调，这和 DevAgent 有什么关系？
- **gold**：`should_call_tool=no`，`should_soft_fallback_if_searched=yes`（域外误调后**预期**走软兜底）
- **实际**：已调用 `search_codebase`；`top1_distance`=0.9860500693321228；`soft_fallback_triggered`=False
- **解读**：距离 **≤** T，软熔断**未触发**，检索结果仍进入上下文，**双层风险**（误调 + 未熔断）。
- **摘要**：根据检索结果，我发现在当前代码仓库中确实有一个名为 `DevAgent` 的类，它是一个智能编程助手，但目前代码中**没有发现与 LoRA 相关的实现**。让我基于通用知识来回答这个问题：  ## LoRA 为什么适合做小模型微调？  **LoRA（Low-Rank Adaptation，低秩适配）** 是一种高效的大语言模型微调技术，特别适合小模型微调的原因如下：  ### 1. **参数效率高** - LoRA 不直接微调原始模型的所有参数，而是通过添加低秩矩阵来间接调整权重 - 对于小模型（参数较少），LoRA 可以只微调 0.1%-1% 的参数，…

### L1 False Negative（应检索却未检索，`should_call_tool=yes`）
*（无）*

### L2 软熔断子集（实际检索 + gold 要求误调应熔断）
| sample_id | bucket | top1_distance | soft_fallback_triggered | 同时是 L1 FP |
|-----------|--------|---------------|-------------------------|-------------|
| `d18` | far_general | 1.254333734512329 | True | True |
| `m04` | misleading_edge | 0.9860500693321228 | False | True |

子集内已熔断 **1/2**。
