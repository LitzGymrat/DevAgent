# 软熔断 Phase1 与端到端链路评测（快照）

> 本文档记录一次完整复现的数值快照；不同机器/嵌入/API 会有波动。原始落盘见 `data/`。

## 1. Phase1：Dense top-1 距离（无 LLM）

**命令**：`python scripts/eval_soft_fuse_phase1.py --threshold 1.12 --sweep 15 --json-out data/soft_fuse/soft_fuse_phase1_raw.json`

**样本**：域内 40；域外 50（远域 28 + 术语近 12 + 误导 10）；合计 90 条。

### 1.1 分桶距离摘要（Chroma distance，越大越不相似）

| 分桶 | n | min | max | mean | median |
|------|---|-----|-----|------|--------|
| 域内 domain | 40 | 0.502 | 1.183 | 0.838 | 0.884 |
| 远域 far_general | 28 | 1.034 | 1.377 | 1.205 | 1.194 |
| 术语近 term_near_no_rag | 12 | 0.638 | 1.334 | 1.055 | 1.133 |
| 误导 misleading_edge | 10 | 0.497 | 1.193 | 0.865 | 0.873 |
| 域外合并 | 50 | 0.497 | 1.377 | 1.101 | 1.156 |

### 1.2 分离度 `min(域外桶) − max(域内)`

- 域外 50 vs 域内：**−0.686**（重叠显著）
- 远域 28 vs 域内：**−0.150**
- 术语近 12 vs 域内：**−0.545**
- 误导 10 vs 域内：**−0.686**

### 1.3 阈值 T=1.12（distance > T 视为拦截）

- **域外 50 拦截率**：**62.0%**（31/50）
- **域内 40 误伤率**：**7.5%**（3/40）

### 1.4 Bad case 报告

`python scripts/analyze_soft_fuse_badcase.py --threshold 1.12` → `data/soft_fuse/soft_fuse_badcase_report.md`

---

## 2. 端到端评测（Agent + `search_codebase` + 软熔断）

**命令**：`python scripts/eval_e2e_pipeline.py --soft-fuse --soft-fuse-threshold 1.12 --jsonl-out data/e2e_eval_log.jsonl`

**说明**：每条样本独立 `DevAgent`；`search_codebase` 在评测进程中启用 `soft_fuse_enabled=True`、阈值 **1.12**（与 Phase1 对照）。**第一层仅统计 `search_codebase`**，不含其它工具。

### 2.0 第一层 gold 口径（当前仓库）

- **Manifest**：`src/evaluation/e2e_manifest.py` 中 `build_e2e_manifest()`。
- **`should_call_tool`**：`yes` / `no` / `optional`。域内题按 **`grounding_tier`** 分档 — **`must_ground`**（必须锚定本库检索）、**`prefer_ground`**（优先检索，`optional`，调与不调均计对）、**`ok_generic`**（可不检索）。
- **域外三桶**：一律 **`should_call_tool = no`**（不应为通识题去查私有库）。
- **离线重算**（不重新跑 Agent，对已有 JSONL 按**当前 manifest** 对齐 `sample_id`）：`python scripts/rescore_e2e_jsonl.py --brief-only data/e2e_eval_log.jsonl`

下文 **首轮** 表为对落盘 `data/e2e_eval_log.jsonl` 的离线重算；与早期文档中「域内 40 条一律应检索」时的 **56/90、FP 32、FN 2** 不在同一 gold 上，**不可横向对比**。

### 2.1 第一层：Tool Decision（search_codebase）

**首轮**（`data/e2e_eval_log.jsonl`，按**当前 manifest** 离线重算）

| 指标 | 值 |
|------|-----|
| 样本数 | 90 |
| 与 `should_call_tool` 一致 | **57 / 90（63.3%）** |
| False Positive（不该调却调） | **33** |
| False Negative（该调未调） | **0** |

**`must_ground` 子集**（应检索、漏检计 FN）：首轮离线重算为 **35/35 已检索，FN 0**。

### 2.2 第二层：检索 + 软熔断（仅实际发生检索的样本）

| 指标 | 值 |
|------|-----|
| 实际触发 `search_codebase` 次数 | **70** |
| 其中「域外误调、预期应熔断」条数 | **32** |
| 预期应熔断且已熔断 | **17 / 32（53.1%）** |

### 2.3 第三层：最终回答

`final_judgement` / `final_answer_type` 在 JSONL 中默认为 `pending`，供人工或 LLM-as-judge 补全。

### 2.4 落盘

- **链路日志（90 行 JSONL）**：`data/e2e_eval_log.jsonl`

---

## 3. 复现提示

- 需配置 **DeepSeek + Qwen 嵌入**，并已执行向量库构建。
- 全量 E2E 约 **30+ 分钟**量级（视 API 延迟而定）。
- 若仅更新 Phase1：`eval_soft_fuse_phase1.py` + `analyze_soft_fuse_badcase.py`（约数十秒，主要为嵌入调用）。
