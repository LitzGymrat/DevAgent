# LLM-as-a-Judge（E2E 第三层）v1

在 `search_codebase` 决策（第一层）与软熔断（第二层）之后，对**最终回答**做质量判断。本版先**抽样**跑通，不全量 90 条。

## 初版结论与 v2 rubric（按 grounding_tier 分层）

**能成立的观察**：Judge 初步显示，通用题与边界概念题表现相对稳定；**回答质量问题主要集中在 domain**，典型为 grounded 不足、检索后未有效利用仓库、软熔断后与 **must_ground** 预期冲突等。

**初版问题**：若对 domain 内 **ok_generic** / **prefer_ground** 仍统一套用 **must_ground** 式「必须体现仓库」打分，会**系统性低估**合理通识回答；评测标准过于单一。

**v2（当前实现）**：Judge 提示词已改为 **按 `grounding_tier` 分层**（见 `src/evaluation/llm_judge_e2e.py` 中 `_JUDGE_SYSTEM_BODY`），并强调**容错维度**：除「是否 grounded」外，还须问**在当前 tier 下回答是否足够合理**（切题、正确、诚实、符合该 tier 预期）。`reason` 中应交代 bucket 与 tier。

## domain 三层判定标准（摘要）

| 层级 | 核心 |
|------|------|
| **must_ground** | **有可得检索证据时**须锚定仓库；**证据不在索引里**（弱 top1、软熔断、诚实未找到）时，优先评**诚实 + 通识质量**，勿把「索引滞后」算成模型过错；见下节。 |
| **prefer_ground** | 优先结合仓库；未充分 grounded 但通识合理可 **partially_correct**，**不应轻易 incorrect**；明显正确且表述得体可 **correct**。 |
| **ok_generic** | 允许以通识为主；答对、不胡编、无污染即可 **correct**；检索/引用仓库**非**硬门槛。 |

## 向量库到底是哪一个？和「最新 src」是不是一回事？

- **用的什么库**：项目里接的是 **Chroma**（Python 侧为 `langchain_chroma.Chroma`），检索封装在 `src/rag/vectorstore.py`；**不是**别的独立向量库产品混用，只是目录名历史上写成了 **`chorma`**。
- **数据存在哪**：由环境变量 **`Chroma_persist_dir`** 指定（见 `.env.example`），代码默认值是 **`./data/chorma`**。  
  **BM25** 另存为 **`bm25_persist_dir`**（默认 `./data/bm25_index.pkl`），与 Chroma **同一次建库**一起更新。
- **和当前 `src/` 是否同步**：**默认不同步**。向量与稀疏索引只在跑 **`python scripts/build_knowledge_base.py`**（从 `src` 读入、切块、`index_document`）时写入磁盘；之后你改源码、若不重建索引，**Chroma 里仍是旧快照**，检索到的就不是「当前仓库」。
- **直接看库里存了什么**：打开 **`{Chroma_persist_dir}/chroma.sqlite3`**，查 `embedding_metadata` 中 `key='chroma:document'` 的文本（即已入库 chunk 全文）。脚本：  
  `python scripts/analyze_badcase_chroma_sqlite.py` → **`data/audit/badcase_chroma_sqlite_audit.md`**（第二轮 badcase 题面符号是否在 SQLite 里**字面出现**）。  
  若磁盘上同时有 **`data/chorma`** 与 **`data/Chroma`**：以 **`.env` 的 `Chroma_persist_dir`** 为准；另一处常为**空库**（`embeddings` 行数为 0），勿与主库混淆。

因此评测里说的「索引缺口」首先指：**磁盘上的 Chroma/BM25 快照** 相对 **当前工作区源码** 是否滞后。

## 向量库未更新时，`must_ground` 怎么思考？

评测链路里有一层容易混淆：

1. **Manifest / 人工标注**说的是：若仓库里**确实有**某实现，理想助手**应当**能指着代码说清（这是**规范目标**）。
2. **实际 RAG** 用的是**当前**切块与向量索引；若索引**未更新**或**没收录**（例如 `_prune_memory` 在库里但尚未入库），检索返回空或弱相关——这时模型只能答通识或说「没找到」，**责任不在「没引用仓库」本身**。

**建议心智模型**：

- **must_ground** 判的是：在**本条日志呈现的检索结果**下，模型是否**恰当**利用了能用的证据、是否**诚实**面对证据不足、通识是否**正确**。不是判「全知全能一定读过最新 Git」。
- **Bad case 解读**：若某条 bad 主要来自「题面在仓库里有答案但索引没命中」，应标注为 **infra / index gap**（或重跑建库后再评），与 **policy / 模型未跟检索** 区分开。
- **操作上**：正式汇报前应对齐 **`build_knowledge_base` / 索引构建** 与当前 `main` 代码，减少可避免的假阴性。

Judge 提示词（`_JUDGE_SYSTEM_BODY`）已写入上述「索引局限」与 **must_ground** 的边界，重跑 Judge 后第二轮数字会与旧 run 略有不同属正常。

### 不想推翻前两轮 JSONL 时：用 index-aware tier 调 gold

若 Chroma 快照过旧或建库只含 `src/`，部分题**客观上**无法 must_ground，可把原版 `grounding_tier` **保留**（历史对照不变），另在 manifest 增加 **`grounding_tier_index_aware` / `should_call_tool_index_aware`**。

- **自动核对 `chroma.sqlite3`**（**可选**，多见于**未重建**、索引落后于 `src` 时）：  
  `python scripts/refresh_chroma_verified_overrides.py`  
  读 **`embedding_metadata` 全文** + `src/**/*.py`，写入 **`data/chroma_verified_skip_must_ground.json`**。`e2e_manifest` 合并顺序为：先载入代码里的 **`INDEX_AWARE_GROUNDING_TIER_OVERRIDES`**，再用 JSON 里 **`entries`** 覆盖同 id。**刚跑完 `build_knowledge_base.py`、向量库与当前 `src` 一致时，`entries` 常为 `{}`，此时不必再跑该脚本**——index-aware tier 主要靠静态表即可。
- **离线重解读**（不重跑 Judge）：`python scripts/report_judge_round2_index_aware.py` → **`data/reports/e2e_judge_round2_index_aware.md`**
- **badcase 报告带验证列**：`python scripts/export_llm_judge_badcase_md.py` → **`data/reports/e2e_llm_judge_badcase_report_round2.md`**
- **与 Judge 完全一致**：需用 index-aware tier 作为 Judge 输入重跑 `eval_llm_judge_e2e.py`（另议）。

## 各桶「好回答」要点（非 domain 与 domain 分层）

| 桶 | 要点 |
|----|------|
| **domain** | **必须**按上表 **grounding_tier** 判定；**禁止**用 must_ground 标准去卡 ok_generic。 |
| **far_general** | 通用知识作答；不依赖私有代码；无无关仓库污染。 |
| **term_near_no_rag** | 识别为概念题；回答通用、克制；不强行扯本仓库实现。 |
| **misleading_edge** | 边界合理取舍；检索了也不能胡乱强绑项目；不检索也不能漏掉显式项目锚点的必要解释。 |

Manifest 中的 `grounding_tier`、`should_call_tool` 会一并传给 Judge；**落盘 JSONL** 中显式写入 **`grounding_tier`**（与 E2E 日志一致），便于汇总与对照。

## 统一五项（所有样本）

1. **Answer Relevance** → `answer_relevant`
2. **Grounding Appropriateness** → `grounding_appropriate`（**依 bucket + grounding_tier 解释**，见上文 domain 三层）
3. **Context Pollution** → `context_pollution`（受无关检索干扰为 **true**）
4. **Final Judgement** → `final_judgement`：`correct` / `partially_correct` / `incorrect`
5. **综合分** → `score`：**整数 1～5**，与上列及 `final_judgement` 一致，锚点如下。

### 分数锚点（`score`）

| score | 含义（综合） | 与 `final_judgement` 的典型对应 |
|-------|----------------|----------------------------------|
| **5** | 切题、grounding 恰当、无上下文污染，可直接采用 | 多为 `correct` |
| **4** | 整体可用，有轻微瑕疵（略泛化、略少仓库细节等） | `correct` 或 `partially_correct` |
| **3** | 部分有用：有明显缺口、偏题风险或 grounding 存疑 | 多为 `partially_correct` |
| **2** | 问题较大：答非所问、乱 grounded、或污染明显 | `partially_correct` 或 `incorrect` |
| **1** | 基本不可用 | `incorrect` |

**说明**：`reason` 中建议简要交代给分依据；汇总时可报告 **平均分**、分桶平均分、以及 `final_judgement` 分布。

## 输出 JSON（模型只输出一个对象，字段必填）

```json
{
  "answer_relevant": true,
  "grounding_appropriate": true,
  "context_pollution": false,
  "score": 5,
  "final_judgement": "correct",
  "reason": "..."
}
```

`final_judgement` 仅允许三选一字符串；`score` 必须为 **1～5 的整数**（校验见 `validate_judge_output`）。

## 传给 Judge 的上下文

每条包含：

- `bucket_type`、`grounding_tier`、manifest 预期（是否应依赖私有知识等）；user 消息中另有**本条评测锚点**（强调按 tier 或按非 domain 规则）
- 用户问题 + `final_answer_preview`（与 JSONL 一致，可能截断）
- `actual_call_search_codebase`、`top1_distance`、`soft_fallback_triggered`

实现：`src/evaluation/llm_judge_e2e.py` 中 `build_judge_messages`。

**输出 JSONL**（`scripts/eval_llm_judge_e2e.py`）每条除 Judge 字段外，含 **`grounding_tier`**（便于离线聚合 tier 分布）。

## Phase1 抽样（22 条）

| 桶 | 条数 | sample_id |
|----|------|-----------|
| must_ground（domain 内） | 5 | `p02`, `p04`, `p11`, `p24`, `p40` |
| far_general | 5 | `d01`, `d05`, `d10`, `q03`, `q18` |
| term_near_no_rag | 5 | `q01`, `q08`, `q10`, `q14`, `q17` |
| misleading_edge | 5 | `m02`, `m03`, `m06`, `m08`, `m10` |
| 典型 case | 2 | `d18`, `m04` |

列表常量：`PHASE1_JUDGE_SAMPLE_IDS`（`src/evaluation/llm_judge_e2e.py`），可改后重跑。

## 运行

需配置 DeepSeek（与 Agent 相同，见 `.env`）。

```bash
# 检查抽样与 prompt（不调 API）
python scripts/eval_llm_judge_e2e.py --jsonl data/e2e_eval_log_promptv2.jsonl --dry-run

# 调用 Judge，默认写入 data/eval/e2e_llm_judge_phase1.jsonl
python scripts/eval_llm_judge_e2e.py --jsonl data/e2e_eval_log_promptv2.jsonl

# 全量 90 条（覆盖抽样），默认写入 data/eval/e2e_llm_judge_full.jsonl
python scripts/eval_llm_judge_e2e.py --jsonl data/e2e_eval_log_promptv2.jsonl --full

# 第二轮（按 grounding_tier 分层 rubric 重跑全量）— 建议单独 outfile，避免覆盖初版
python scripts/eval_llm_judge_e2e.py --jsonl data/e2e_eval_log_promptv2.jsonl --full --out data/e2e_llm_judge_full_round2.jsonl

# bad case 报告（默认读 round2、写出 data/reports/e2e_llm_judge_badcase_report_round2.md）
python scripts/export_llm_judge_badcase_md.py

# 本轮收尾（不重建 Chroma/BM25）：用当前 chroma.sqlite3 与 src 对拍，生成 verified 标注 + 报告列
python scripts/refresh_chroma_verified_overrides.py
python scripts/report_judge_round2_index_aware.py
python scripts/export_llm_judge_badcase_md.py
```

全量落盘：初版 **`data/eval/e2e_llm_judge_full.jsonl`**；第二轮（分层 rubric）**`data/e2e_llm_judge_full_round2.jsonl`**（与 Phase1 抽样文件**独立**）。

### 本轮实验收尾（冻结、不重建索引）

为与**当前磁盘**上的向量快照一致、又不推翻已跑完的 Judge/E2E 落盘，本轮采用 **badcase 修补路径**（见上文「index-aware」「Chroma 验证」）：

| 产物 | 说明 |
|------|------|
| **`data/e2e_llm_judge_full_round2.jsonl`** | 第二轮 Judge 全量 90 条（分层 rubric），**不重跑** |
| **`data/chroma_verified_skip_must_ground.json`** | 对照 **`data/chorma/chroma.sqlite3`** 全文 + `src/`，仅对 badcase 中可自动核对的条目写入 **tier 降级建议** |
| **`data/reports/e2e_judge_round2_index_aware.md`** | 按 **index-aware tier** 重解读第二轮（不重调 Judge API） |
| **`data/reports/e2e_llm_judge_badcase_report_round2.md`** | badcase 表含 **index-aware tier** 与 **Chroma 验证** 列 |

**下一轮回**若要对齐「最新源码」，再执行 **`python scripts/build_knowledge_base.py`** 重建索引后重跑 E2E / Judge 即可；**本轮**保持现状，仅做上述修补与文档冻结。

### 要不要「重新打分」？

- **之前**：未重调 Judge API，只有离线解读 + 报告列。  
- **若认为旧 Judge 按「不合理」的 must_ground 打分**：可 **重跑 Judge**，在 prompt 里改用 **`grounding_tier_index_aware`**（与 `chroma_verified_skip_must_ground.json` 合并后的 manifest），**不覆盖**旧文件：

```bash
python scripts/eval_llm_judge_e2e.py --jsonl data/e2e_eval_log_promptv2.jsonl --full --index-aware
# 默认写入 data/e2e_llm_judge_full_round2_index_aware.jsonl
# 原 data/e2e_llm_judge_full_round2.jsonl 保留作对照
```

每条输出含 **`judge_gold_mode`: `index_aware`**、**`grounding_tier_original`**（原版 tier）。再按需 `export_llm_judge_badcase_md.py --judge-jsonl data/e2e_llm_judge_full_round2_index_aware.jsonl --out ...` 生成新 badcase 报告。

## 与 [09](./09-prompt与工具描述优化后复测.md) 的关系

09 记录工具层与软熔断快照；**Judge 结果**作为第三层补全 `final_judgement` / 细粒度布尔项，可汇总后追加到同一轮实验说明。
