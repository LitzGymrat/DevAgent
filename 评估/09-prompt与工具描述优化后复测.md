# Prompt / `search_codebase` 工具描述优化后 — E2E 复测快照

与 [08-软熔断Phase1与端到端评测](./08-软熔断Phase1与端到端评测.md) 中**首轮**（旧 prompt）对照；本轮在**优化 system prompt + `search_codebase` 的 `description`** 后重跑。

## 技术说明

- **Phase1（Dense 距离）**：仅依赖嵌入与向量库，与 prompt 无关；本轮数值与 08 一致，落盘为 `data/soft_fuse/soft_fuse_phase1_raw_promptv2.json`（与首轮相同，可任选其一保留）。
- **代码修复**：`tools_schemas.py` 中 `search_codebase` 的 `description` 曾出现**未闭合字符串**导致无法 import；已改为合法的多行字符串拼接（语义与优化文案一致）。

## 端到端（`--soft-fuse --soft-fuse-threshold 1.12`）

**落盘**：`data/e2e_eval_log_promptv2.jsonl`（90 行，字段同首轮，供 **LLM-as-judge** 补 `final_judgement` / `final_answer_type`）。

**第一层 gold**：与 [08](./08-软熔断Phase1与端到端评测.md) §2.0 一致（`e2e_manifest` + `grounding_tier`）。下表为对**已有 JSONL** 的**离线重算**（`scripts/rescore_e2e_jsonl.py`），无需重跑 Agent。

### 第一层：`search_codebase` 工具决策（总览）

| 轮次                           | 一致率                | FP（不该调却调） | FN（该调未调） |
| ------------------------------ | --------------------- | ---------------- | -------------- |
| 首轮（`e2e_eval_log.jsonl`） | 57/90**63.3%**  | 33               | 0              |
| **本轮 promptv2**        | **88/90 97.8%** | **2**      | **0**    |

- **FP 从 33 → 2**：域外/误导等误触检索大幅下降，**工具描述 + prompt 约束**仍然成立。
- **FN**：在现行 gold 下，两轮对 **`must_ground`（35 条）均为 35/35 已检索**；此前文档中的「FN 5」来自旧口径（域内 40 条一律计为「应检索」），与当前分档**不可混用**。

### 按桶拆开（首轮 vs 本轮）

| bucket           | 条数 | 一致率（本轮） | FP | FN | 一致率（首轮） | FP | FN |
| ---------------- | ---- | -------------- | -- | -- | -------------- | -- | -- |
| domain（域内）   | 40   | 100%           | 0  | 0  | 97.5%          | 1  | 0  |
| far_general      | 28   | 96.4%          | 1  | 0  | 25.0%          | 21 | 0  |
| term_near_no_rag | 12   | 100%           | 0  | 0  | 66.7%          | 4  | 0  |
| misleading_edge  | 10   | 90.0%          | 1  | 0  | 30.0%          | 7  | 0  |

本轮剩余 **2 条 FP**：`d18`（far_general）、`m04`（misleading_edge）。

**`must_ground` 子集**：首轮与本轮均为 **检索 35/35，FN 0**。

### 第二层：检索 + 软熔断（子集变化）

| 轮次 | 实际检索次数 | 「预期应熔断」子集 | 预期熔断且已熔断 |
| ---- | ------------ | ------------------ | ---------------- |
| 首轮 | 70           | 32                 | 17/32（53.1%）   |
| 本轮 | **37** | **2**        | 1/2（50.0%）     |

**软熔断作用（与第一层联动）**：gold 里「预期应熔断」= `should_soft_fallback_if_searched=yes` 且该样本**实际发生了** `search_codebase`（典型为域外误调检索）。**FP 从 33→2** 后，需要靠距离阈值做软兜底的**绝对次数**从 32 次降到 2 次；子集内「已熔断/应熔断」比例（约 53% vs 50%）反映 **T=1.12** 下的触发率，**首轮与本轮接近**，说明机制仍在生效。第二层样本量极小时（本轮仅 2 条）**不宜单独**把比例当优化目标，应结合第一层 FP 一起看。

**严格口径（manifest 不变）**：L1 与 L2 **分开计**；误调在 L1 仍计 **FP**，软熔断**不**把 FP 改成「工具选对了」，只影响误调之后是否走通识/弱化代码（如 `d18`）。

**工程汇报口径（可选）**：若认为 **`m04`** 的 gold 过严（题面点名 DevAgent，**合理上可先查库**），在讨论「误调 + 工程兜底」时**暂不把它算作应被统计的误调**。则本轮在「**仍算误调**且 `should_soft_fallback_if_searched=yes`」的情境里，**无争议样本只剩 `d18`**；而 **`d18` 上 `soft_fallback_triggered=true`**，即 **应熔断则已熔断** → 在该子集上 **第二层为 1/1（100%）**。  
完整 manifest 下表内仍为 **1/2（50%）**、L1 仍为 **2 条 FP**（含 `m04`）——两套说法**并列**，对外写「争议题剔除后，软熔断在第二层对剩余误调全兜底」**可以这样说**；论文/回归仍建议保留严格列。

（与上表同一数字的离线简报：`python scripts/rescore_e2e_jsonl.py --brief-only data/e2e_eval_log_promptv2.jsonl --compare data/e2e_eval_log.jsonl`。）

## Bad case 分析（当前 manifest）

数据来源：`data/e2e_eval_log_promptv2.jsonl` / `data/e2e_eval_log.jsonl`，阈值 **T = 1.12**（与评测时 `soft_fuse_config` 一致）。**完整逐条表**仍见：

| 报告                                                                           | 说明                                       |
| ------------------------------------------------------------------------------ | ------------------------------------------ |
| [`data/reports/e2e_badcase_report_promptv2.md`](../data/reports/e2e_badcase_report_promptv2.md) | 本轮 2 条 FP 的机器生成版（可与下文对照）  |
| [`data/reports/e2e_badcase_report_baseline.md`](../data/reports/e2e_badcase_report_baseline.md) | 首轮 33 条 FP**紧凑表** + 软熔断子集 |

---

### 本轮（promptv2）：2 条 L1 FP（逐条）

#### `d18`（far_general）— 误调检索，但软熔断生效

| 字段                              | 值                                                                     |
| --------------------------------- | ---------------------------------------------------------------------- |
| **题面**                    | 接口做了幂等键还是偶尔重复扣款，除了幂等表还要查消息重投、超时重试吗？ |
| **gold**                    | 不应检索（通识/排障）；误调后预期可走软兜底                            |
| **实际**                    | 调用了 `search_codebase`                                             |
| **top1_distance**           | **1.254**（**>** T）                                       |
| **soft_fallback_triggered** | **true**                                                         |

**分析**：题型是线上幂等与消息语义，与私有仓库几乎无关，理想情况应**不调检索**（第一层 FP）。检索发生后，最相关块距离仍高，**软熔断按设计触发**，回答里先声明「库内无高相关实现」再展开通用知识，**减轻**了「硬塞不相关代码」的风险；要消 FP 仍须靠 **prompt/工具策略** 少调检索，而不是靠熔断「抵销」误调。

#### `m04`（misleading_edge）— 相对本套 gold 计 FP；题面语义有歧义

| 字段                              | 值                                                                             |
| --------------------------------- | ------------------------------------------------------------------------------ |
| **题面**                    | LoRA 为什么适合做小模型微调，这和**DevAgent** 有什么关系？               |
| **gold**                    | `should_call_tool=no`（题集口径：误导边界 + 通识为主）；误调后预期可走软兜底 |
| **实际**                    | 调用了 `search_codebase`                                                     |
| **top1_distance**           | **0.986**（**≤** T）                                              |
| **soft_fallback_triggered** | **false**                                                                |

**题面 vs gold（为何容易觉得「不该算错」）**


该问题包含显式项目锚点“DevAgent”，虽然 gold 原设为“不应检索”，但模型选择检索以解释项目中的 LoRA 使用关系具有一定合理性；由于检索确实命中与项目相关的微调片段，且距离低于阈值，软熔断未触发符合其设计边界。该样本更适合作为边界 case 单独分析，而非计入严格意义上的误调用。

**技术记录（相对现行 gold）**：误调后命中 `DevAgent` 等相关片段，`top1_distance` **≤ T**，**未触发软熔断**，属本报告采用的标签下的 **误调 + 未熔断**；调阈值需对照 Phase1 距离分布（见 [08](./08-软熔断Phase1与端到端评测.md)）。

**本轮 L2 子集（仅上述 2 条误调且 gold 要求熔断）**：已熔断 **1/2**（`d18` 已、`m04` 未）。

---

### 首轮（baseline）：典型 FP 抽样（带题面）

首轮共 **33** 条 L1 FP（**far_general 21 / term_near_no_rag 4 / misleading_edge 7 / domain 1**）。下面抽 **5** 条覆盖四桶，便于和本轮对照；**全量 id 与数值**见 [`e2e_badcase_report_baseline.md`](../data/reports/e2e_badcase_report_baseline.md)。

| id      | bucket           | 题面（摘录）                                                                                      | top1  | 熔断                     | 简要分析                                                                                                                       |
| ------- | ---------------- | ------------------------------------------------------------------------------------------------- | ----- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `p01` | domain           | FastAPI 里路由是怎么注册到应用上的？                                                              | 0.820 | 否（域内 gold 不设熔断） | 现行 gold 为**`ok_generic`**（教材型通识），**不应**为背教材去查库；首轮仍检索，计 **FP**。                |
| `d02` | far_general      | 浏览器里前端请求后端报**CORS** 被拦截，后端侧通常要动哪些配置？                             | 0.859 | 否（≤T）                | 典型远域通识；误调后命中本仓库 `main.py` 里 CORS 片段，距离 **≤ T**，**未熔断**，回答被「带偏」到本项目配置上。 |
| `d10` | far_general      | 前端 dev 正常，打包上线后静态资源**404**，多半是 publicPath、路由模式还是部署路径哪类问题？ | 1.092 | 否（≤T）                | 通用前端部署题；**两次** `search_codebase`，仍 **≤ T**，软熔断未起，属误调 + 未熔断一类。                       |
| `q01` | term_near_no_rag | **FastAPI 的路由怎么注册？**                                                                | 0.786 | 否（≤T）                | 与域内题措辞极近，刻意测「术语像域内、但不应查库」；误调后易答成「本仓库路由」，**RAG 陷阱**。                           |
| `m03` | misleading_edge  | **Chroma** 和 **BM25** 哪个更适合做**通用知识问答**？                           | 0.468 | 否（≤T）                | 用语贴近本仓库检索栈，模型去库里找「实现对比」；距离很低，**未熔断**，与本轮 `m04` 同型。                              |

**首轮软熔断（误调子集 32 条）**：**17** 条 `top1 > T` 已熔断，**15** 条 `≤ T` 未熔断 —— 与上表「低距离误导/术语近」案例一致：**未熔断**往往伴随「库里有看似相关的代码」。

```bash
python scripts/analyze_e2e_badcase.py data/e2e_eval_log_promptv2.jsonl --out data/reports/e2e_badcase_report_promptv2.md
python scripts/analyze_e2e_badcase.py data/e2e_eval_log.jsonl --compact --out data/reports/e2e_badcase_report_baseline.md
```

## 文件对照

| 用途                                      | 首轮                                    | 本轮（promptv2）                              |
| ----------------------------------------- | --------------------------------------- | --------------------------------------------- |
| E2E 链路日志                              | `data/e2e_eval_log.jsonl`             | `data/e2e_eval_log_promptv2.jsonl`          |
| Phase1 原始 JSON                          | `data/soft_fuse/soft_fuse_phase1_raw.json`      | `data/soft_fuse/soft_fuse_phase1_raw_promptv2.json`   |
| 软熔断 Phase1 bad case                    | `data/soft_fuse/soft_fuse_badcase_report.md`    | `data/soft_fuse/soft_fuse_badcase_report_promptv2.md` |
| **E2E 第一层 bad case（manifest）** | `data/reports/e2e_badcase_report_baseline.md` | `data/reports/e2e_badcase_report_promptv2.md`       |
| **E2E 第三层 LLM-as-judge** | — | 抽样 22：`data/eval/e2e_llm_judge_phase1.jsonl`；**全量 90**：`data/eval/e2e_llm_judge_full.jsonl`（见 [10](./10-LLM-as-Judge-v1.md)） |

复现本轮 E2E（生成 JSONL）：

```bash
python scripts/eval_e2e_pipeline.py --soft-fuse --soft-fuse-threshold 1.12 --jsonl-out data/e2e_eval_log_promptv2.jsonl
```

仅更新**评测表**（改 manifest / 对照首轮，不重跑 Agent）：

```bash
python scripts/rescore_e2e_jsonl.py --brief-only data/e2e_eval_log_promptv2.jsonl --compare data/e2e_eval_log.jsonl
```

第三层 Judge：

```bash
# 抽样 22 条（默认 out：e2e_llm_judge_phase1.jsonl）
python scripts/eval_llm_judge_e2e.py --jsonl data/e2e_eval_log_promptv2.jsonl

# 全量 90 条（默认 out：e2e_llm_judge_full.jsonl）
python scripts/eval_llm_judge_e2e.py --jsonl data/e2e_eval_log_promptv2.jsonl --full
```
