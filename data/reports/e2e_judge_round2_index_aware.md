# 第二轮 LLM Judge × **index-aware grounding_tier** 解读

**目的**：原版 `grounding_tier`（`grounding_tier` 字段）保持不变，前两轮落盘 JSONL **仍可**横向对照；
此处用 **`grounding_tier_index_aware`**（见 `e2e_manifest.INDEX_AWARE_GROUNDING_TIER_OVERRIDES`）
把「当前 Chroma 快照里根本不存在 / 建库范围外」的题从 **must_ground** 中拆出，避免 gold 与 RAG 可达性脱节。

**注意**：Judge API 当时仍按**原版** tier 提示词打分；本文件是**离线重解读**，不是新 Judge 结果。若要 Judge 与 tier 完全一致，需用新 tier 重跑 `eval_llm_judge_e2e.py`。

## 覆盖规则（摘要）

- **`p12`** → `prefer_ground`
- **`p17`** → `prefer_ground`
- **`p19`** → `ok_generic`
- **`p27`** → `prefer_ground`

## 汇总（domain badcase）

- **badcase 总数（domain）**：14
- 其中原版 **must_ground**：13
- index-aware 后仍 **must_ground**：9
- 从 must_ground **放宽**（仅 tier 变化）：4 条 → `['p12', 'p17', 'p19', 'p27']`

### 仅看「index-aware must_ground」子集里的 incorrect / partial

- 条数 **9**：correct=0，partially_correct=1，incorrect=8

## 全 badcase 对照表（原版 tier → index-aware tier）

| id | 原版 tier | index-aware | final_judgement | 说明 |
|----|-----------|---------------|-----------------|------|
| p02 | must_ground | must_ground | incorrect |  |
| p08 | prefer_ground | prefer_ground | partially_correct |  |
| p12 | must_ground | prefer_ground | incorrect | tier 放宽 |
| p17 | must_ground | prefer_ground | incorrect | tier 放宽 |
| p19 | must_ground | ok_generic | incorrect | tier 放宽 |
| p27 | must_ground | prefer_ground | incorrect | tier 放宽 |
| p29 | must_ground | must_ground | incorrect |  |
| p30 | must_ground | must_ground | incorrect |  |
| p31 | must_ground | must_ground | incorrect |  |
| p32 | must_ground | must_ground | incorrect |  |
| p34 | must_ground | must_ground | partially_correct |  |
| p36 | must_ground | must_ground | incorrect |  |
| p37 | must_ground | must_ground | incorrect |  |
| p40 | must_ground | must_ground | incorrect |  |

---

生成：`python scripts/report_judge_round2_index_aware.py`