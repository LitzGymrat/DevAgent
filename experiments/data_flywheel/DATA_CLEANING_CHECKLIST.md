# ft_qa 数据 · 清洗 Checklist（v0）

面向 `ft_qa_*.jsonl` 及同 schema 的样本。目标：**在扩量前**把「标签错位、伪 grounded、工具名不一致」等问题压下去，再进 SFT / DPO。

---

## Phase 2A（`decision_type` 路由）— 当前生成脚本默认

`generate_ft_qa_500.py` 产出行含 **`decision_type`**：`tool_call` | `no_tool` | `clarify_needed`；**不再**使用 `response_kind` / `direct_answer`。

| # | 检查项 | 说明 |
|---|--------|------|
| P1 | `decision_type` 与 `tool_name`/`arguments`/`clarify_answer` 是否一致 | `tool_call` 须有合法六工具名与参数；`no_tool` 四类可空字段须为 null；`clarify_needed` 须有短 `clarify_answer` |
| P2 | `no_tool` / `clarify_answer` 是否编造本仓库路径、镜像名、未验证「默认」 | 与旧 checklist C 条同类红牌 |
| P3 | `tool_call` 的 `tool_name` 是否与主仓 tools 拼写一致 | 同 H 节工具名表 |
| P4 | 批内 **三类条数** 是否与 Schema 目标严重偏离 | 可脚本统计 `decision_type` 占比 |

**自动化审计（Phase 2A 训练 JSONL）**：在仓库根目录执行  
`python experiments/data_flywheel/clean_phase2a_train.py --input experiments/data_flywheel/out/ft_qa_500_train.jsonl`  
会生成同目录 **`ft_qa_500_train.CLEAN_REPORT.md`**（ERROR/WARN/REVIEW + 分布与重复 query）及可选 **`*.cleaned.jsonl`**（当前主要自动修补 `_meta.slice` 与 `bucket` 对齐）。  
加 `--extract-review` 可另存 **`*.manual_review.jsonl`**（仅含 REVIEW 项，每条带 `_manual_review` 原因列表）。

以下 **A～G** 仍以 **旧混合 schema**（`response_kind`）表述为主；若你的文件已是 Phase 2A，请将「`response_kind=clarify`」类比为 **`decision_type=clarify_needed`**，「直答」类比为 **`no_tool`**（或旧 `direct_answer`），并以 `clarify_answer` 替代「澄清写在 `direct_answer`」的说法。

---

## 使用前必读

- **当前数据定位**：适合 **v0.5～v0.7 雏形**、小规模 SFT 试水、DPO 原料筛选；**不建议**不洗就作为唯一主数据大规模训。
- **清洗顺序建议**：先按 **「一票否决」** 筛 → 再按 **bucket / decision_type 或 response_kind** 分桶 → 最后做 **语气与字段** 级修补。

---

## A. 一票否决（出现即删或整行重标）

| # | 检查项 | 操作 |
|---|--------|------|
| A1 | `tool_name` 与主仓 `tools_schemas` **拼写不一致**（如 `analyse` vs `analyze`） | 对照 `src/agent` 或单一 schema 源，**改错名**或删 |
| A2 | `direct_answer` / `clarify` 文本里出现 **本仓库独有路径、默认参数、具体镜像名**，但 **无** `oracle_context` 或可追溯依据 | **降级**为 `clarify`（说明不确定）或改为 `tool_call`，或删 |
| A3 | 声称「咱们项目 / 主目录 / 默认就是 6 条」等 **可证伪事实** 而无证据 | 同上，**禁止**裸 `direct_answer` 编造 |
| A4 | JSON 缺键、缺 `query`、`response_kind` 非法值 | 修或删 |

---

## B. bucket 与 response_kind 是否一致（重点）

| # | 检查项 | 说明 |
|---|--------|------|
| B1 | `bucket=domain` 但内容为 **纯通识概念**（无需任何仓库 grounding） | 标记为待迁移：后续可加 `grounding_tier=ok_generic`，或挪到 `far_general` 策略（见方案 2 schema） |
| B2 | `bucket=far_general` 却大量 **私域路径/类名** | 考虑改 `domain` 或加 `grounding_tier` |
| B3 | `response_kind=tool_call` 但问题明显应 **先澄清** | 考虑改为 `clarify` |
| B4 | `response_kind=clarify` 但答案像 **完整教程式 direct** | 拆成「一句澄清 + 可选后续步骤」，或改 `direct_answer` 并收紧长度 |

---

## C. 伪 grounded / 装懂（红牌样本）

对 **每一行** `direct_answer`（及偏陈述的 `clarify`）快速扫：

- [ ] 是否出现：**具体版本号、镜像名、文件路径、默认 top_k、内部模块名**？
- [ ] 若有：**`oracle_context` 是否能支撑**？若不能 → **必须改**（clarify / tool_call / 加免责声明句式）。

**推荐替换句式（示例）**  
- 坏：「咱们项目用的是 Python 3.9-alpine 镜像。」  
- 好：「需要看仓库根目录的 Dockerfile 才能确定；若你贴出 Dockerfile 片段，我可以帮你对齐。」

---

## D. clarify 与 direct_answer 字段（工程卫生）

当前实现里 `clarify` 的文本在 **`direct_answer` 字段，语义上能理解，但统计与转换脚本易混**。

**清洗时**（在最终 schema 落地前可先记在侧表或备注）：

- [ ] 每条 `response_kind=clarify`：**是否应独立成 `clarify_answer` 字段**（与 `format_to_sharegpt` / Judge 对齐时再改 schema）。

---

## E. tool_call 边界与工具选择

| # | 检查项 |
|---|--------|
| E1 | `search_codebase` 的 query 是否 **过泛或过拟合私域**（与 slice 意图是否一致） |
| E2 | `generate_dockerfile` / `generate_tests` 等 **是否可以不依赖仓库**（记录为后续 `tool_dependency`：repo_agnostic / repo_grounded） |
| E3 | `analyse_code` 是否给了 **足够片段**（非空、非一句话糊弄） |

---

## F. Persona / 语气（`_meta.scenario`）

- [ ] **Query** 侧：保留多 persona（实习生、DevOps、中英混杂）→ **有利于分布多样性**。
- [ ] **Answer** 侧：若出现大量「不好意思呢我是实习生」「非常愿意帮您」等 **表演性客套**，**压缩为一句专业澄清 + 索要信息**。
- [ ] 目标风格对齐：**Staff Engineer / 资深研发助手**：信息密度优先，少身份表演。

---

## G. 批量统计（洗前洗后各跑一次）

在终端可对 `ft_qa_100.jsonl` 做粗统计（可选）：

- 各 `bucket` × `response_kind` 计数  
- `domain` 且 `direct_answer` 条数（偏高则重点审 B1/C）  
- `tool_name` 分布与非法值

（需要时可写 20 行 Python 脚本计数，本 checklist 不强制。）

---

## H. 与主仓工具名对齐（必核一次）

在合并进训练前，**全表**核对以下名称与运行时 tools 定义 **完全一致**：

`analyse_code` · `search_codebase` · `analyse_log` · `generate_dockerfile` · `generate_tests` · `complete_code`

---

## 洗完后建议

1. **小批量 SFT**（100～150 条较干净子集）：看是否缓解工具僵尸、clarify 是否过强、direct 是否过多。  
2. **余量**作 DPO 候选池：边界感强的 clarify / 错 tool 成对构造。  
3. **下一轮扩量**前：再定稿 **schema 扩展**（`grounding_tier`、`clarify_answer`、`tool_dependency`），见后续「方案 2」文档。

---

## 版本

- 2025-03：初版，对应 mixed schema v0 与 `generate_ft_qa_500.py`（Gemini-only）产出的 `ft_qa_100.jsonl`。
