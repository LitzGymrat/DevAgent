# `data/` 目录说明（评测与归档）

向量库（`chorma/`、`bm25_index.pkl` 等）仍放在 `data/` 根下，与 RAG 代码约定一致。  
**E2E / Judge / 报告** 已按类型分子目录，避免根目录堆一堆 `e2e_*`、`soft_fuse_*`。

## 根目录（当前主链路，脚本默认常指向这里）

| 文件 | 含义 |
|------|------|
| `e2e_eval_log_promptv2.jsonl` | 最新一次 **promptv2 + 软熔断** 全量 E2E 链路日志（90 行） |
| `e2e_eval_log.jsonl` | 首轮 / 对照用 E2E 日志（若仍保留） |
| `e2e_llm_judge_full_round2.jsonl` | Judge **legacy Gold**（第二轮分层 rubric）全量 |
| `e2e_llm_judge_full_round2_index_aware.jsonl` | Judge **index-aware Gold** 全量（`--full --index-aware` 默认写出） |
| `chroma_verified_skip_must_ground.json` | 可选：自动 tier 补丁，供 `grounding_tier_index_aware` 合并 |

## `reports/` — Markdown 报告（人读）

| 文件 | 含义 |
|------|------|
| `e2e_llm_judge_badcase_report.md` | Judge badcase（早期汇总） |
| `e2e_llm_judge_badcase_report_round2.md` | 第二轮 badcase 表 |
| `e2e_llm_judge_badcase_report_round3.md` | 第三轮（建库复测后）badcase 表 |
| `e2e_eval_round3_review_notes.md` | **Round3 评测复盘与人工复核纪要**（四类归因 + 产物索引） |
| `e2e_badcase_report_baseline.md` / `e2e_badcase_report_promptv2.md` | 第一层 E2E badcase（`analyze_e2e_badcase.py`） |
| `e2e_judge_round2_index_aware.md` | 不重跑 API 的 index-aware **重解读**（`report_judge_round2_index_aware.py`） |

## `soft_fuse/` — 软熔断 Phase1 原始 JSON + 报告

| 文件 | 含义 |
|------|------|
| `soft_fuse_phase1_raw.json` / `soft_fuse_phase1_raw_promptv2.json` | Phase1 距离落盘 |
| `soft_fuse_badcase_report.md` / `soft_fuse_badcase_report_promptv2.md` | Phase1 badcase 报告 |

## `audit/` — 离线审计产物

| 文件 | 含义 |
|------|------|
| `badcase_chroma_sqlite_audit.md` | 题面符号 vs Chroma 全文（`analyze_badcase_chroma_sqlite.py`） |
| `vector_index_audit_badcase_round2.jsonl` | 向量覆盖审计样例（`audit_vector_index_coverage.py` 等） |

## `eval/` — 抽样 / 初版 Judge 输出（默认路径）

| 文件 | 含义 |
|------|------|
| `e2e_llm_judge_phase1.jsonl` | 默认：Phase1 抽样 22 条 Judge（`eval_llm_judge_e2e.py` 无 `--full`） |
| `e2e_llm_judge_full.jsonl` | 默认：初版全量 90 条 Judge（`--full` 且无 `--index-aware` 时） |

## `archive/` — 只读快照，避免覆盖后找不到旧结果

| 路径 | 含义 |
|------|------|
| `archive/judge_round1/` | 早期 `e2e_llm_judge_phase1.jsonl`、`e2e_llm_judge_full.jsonl` 备份 |
| `archive/snapshots/2026-03-kb-rebuild/` | **重建向量库前** 的 E2E + index-aware Judge 快照（与根目录当前文件对照用） |

更老的文档里若仍写 `data/e2e_llm_judge_badcase_report_round2.md`，请改指向 **`data/reports/`** 下同名文件。
