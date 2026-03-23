# Phase 2A — Single-shot Tool Routing SFT

**中文名**：第一阶段 · **单轮工具路由对齐**

第一轮 SFT **不**训练「最终自然语言答得多好」，也 **不**在本阶段考核 grounded 回答质量、Faithfulness、Answer Relevance、Persona/风格。

---

## 一句话（给 Composer / README / 面试）

当前第一轮 SFT **完全聚焦在单轮工具路由决策**，只训练四件事：**（1）JSON 格式稳定；（2）决策类型正确（tool_call / no_tool / clarify_needed）；（3）工具选择正确；（4）参数组织正确。**  
当前 **不保留**最终自然语言回答作为主优化目标，也 **不**训练 grounded 回答质量。

---

## 训练目标（仅四件事）

在**单轮约束**下，让模型稳定产出 **正确、可执行、低歧义** 的路由决策，而不是长回答。

| 维度 | 含义 |
|------|------|
| **1. JSON 格式稳定** | 输出必须是可解析的结构化 JSON；字段名、层级、类型符合约定；避免格式坍塌、缺字段、非法字符串等。 |
| **2. 决策类型正确** | 正确区分 **tool_call** / **no_tool** / **clarify_needed**；不该调工具时不误触；信息不足时进入澄清分支。 |
| **3. 工具选择正确** | 当决策为 tool_call 时，选对工具：`search_codebase`、`analyse_code`、`analyse_log`、`generate_tests`、`generate_dockerfile`、`complete_code` 及主仓已有工具。 |
| **4. 参数组织正确** | 参数字段完整、类型正确；`query` / `code` / `log` / `project_description` 等可被下游正确提取；尽量高信息密度、可直接执行；减少冗长、含糊或错误参数。 |

---

## 评测对齐（本阶段只看四类）

| 指标 | 说明 |
|------|------|
| **JSON Parse Pass Rate** | 模型输出能否稳定解析为约定 JSON。 |
| **Decision Type Accuracy** | tool_call / no_tool / clarify_needed 与金标一致率。 |
| **Tool Selection Accuracy** | 在 tool_call 子集上，工具名是否正确。 |
| **Argument Match / Argument Quality** | 参数完整性、类型、可执行性（可按关键键或规则/裁判打分）。 |

**本阶段不看**：grounded 回答质量、Faithfulness、Answer Relevance、Persona/风格。

---

## 与当前数据产物的说明

`generate_ft_qa_500.py` 产出的 **当前** `ft_qa_*.jsonl` 已按 Phase 2A 输出：`decision_type` ∈ `tool_call` | `no_tool` | `clarify_needed`，`clarify_answer` 仅用于 `clarify_needed`；`_meta.sft_phase` 为 `2a_routing`。转为 ShareGPT 时使用 `loRA/format_to_sharegpt.py`（`PHASE_2A_ROUTING_SYSTEM_PROMPT` + 单行路由 JSON 作为 assistant 金标）。

若你仍持有 **旧版** JSONL（含 `response_kind` / `direct_answer` 长文监督），与「路由-only」Phase 2A 不完全一致；迁移时可：

- 将监督信号 **收束为路由 JSON**（决策类型 + 工具 + 参数），或  
- 在 schema 层把旧 `direct_answer` / `clarify` **映射**到 `no_tool` / `clarify_needed` 与 `clarify_answer`，再单独约定「不训练回答正文」。

---

## 命名速查

| EN | 中文 |
|----|------|
| Phase 2A — Single-shot Tool Routing SFT | 第一阶段：单轮工具路由对齐 |

---

## AutoDL / LLaMA-Factory（ShareGPT）

1. **导出 ShareGPT JSON**（与 `PHASE_2A_ROUTING_SYSTEM_PROMPT` + 单行路由金标一致）：

   ```bash
   python loRA/format_to_sharegpt.py \
     --input experiments/data_flywheel/out/ft_qa_500_train.jsonl \
     --phase2a \
     --out-train experiments/data_flywheel/out/devagent_phase2a_train.json

   python loRA/format_to_sharegpt.py \
     --input experiments/data_flywheel/out/ft_qa_450_test.jsonl \
     --phase2a \
     --out-train experiments/data_flywheel/out/devagent_phase2a_eval.json
   ```

2. 将 `devagent_phase2a_train.json`（及可选 `devagent_phase2a_eval.json`）拷到 LLaMA-Factory 的 `data/` 目录。

3. 在 **`data/dataset_info.json`** 中合并 **`loRA/llamafactory_dataset_info.phase2a_snippet.json`** 里的两个键（勿与旧 `devagent_tool_calling` 混用，除非刻意混训）。

4. **必须带 `tags`**：`format_to_sharegpt.py` 每条消息为 `{"from":"system"|"user"|"assistant","value":"..."}`。LLaMA-Factory 默认 ShareGPT 角色是 `human` / `gpt`，若不配 `tags`，会把 `user`/`assistant` 认成非法角色，训练行为错误。

5. **`dataset` 训练参数**里写：`devagent_phase2a_routing`（或你在 `dataset_info.json` 里自定义的键名）。

与上一轮「纯工具 JSON」相比：本轮 **`columns` 仍为 `messages` → `conversations`**；**新增差异**是 **`tags` 对齐 `from`/`value`/`user`/`assistant`/`system`**，且监督为 **Phase 2A 路由 JSON**（`decision_type` 等），不是旧的 `{"name","arguments"}`。
