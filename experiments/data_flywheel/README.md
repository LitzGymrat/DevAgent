# Data flywheel

数据飞轮：采集、标注、与主仓 `data/` 评测的衔接。

混合数据生成后的**清洗步骤**见 [`DATA_CLEANING_CHECKLIST.md`](DATA_CLEANING_CHECKLIST.md)。Phase 2A 训练 JSONL 可跑自动化审计：[`clean_phase2a_train.py`](clean_phase2a_train.py)（生成 `*.CLEAN_REPORT.md`）；`--extract-review` 得到 `*.manual_review.jsonl` 后，可用 [`manual_review_jsonl_to_md.py`](manual_review_jsonl_to_md.py) 转成 **`*.manual_review.md`** 便于阅读。

**第一轮 SFT（路由-only）目标与评测口径**见 [`SFT_PHASE_2A.md`](SFT_PHASE_2A.md)（Phase 2A — Single-shot Tool Routing SFT）。

## FastAPI + Transformers · Phase 2A 路由 Schema

- **语境**：`context_fastapi_transformers.py`（私域切片）；六种**语气** `SCENARIOS`。
- **条数与三切片比例**：`python .../generate_ft_qa_500.py --target N --segment-ratio W1,W2,W3`。默认 `--segment-ratio 300,100,100`（与旧版 500 全量一致，缩放到 N 即 60%/20%/20）；扩量可用 **`70,15,15`**（私域 70%、另两切片各 15%）。**仅 Gemini** 分批生成。切片 → **bucket**：
  - `private_domain` → `domain`
  - `dev_general_no_rag` → `far_general`
  - `misleading_edge` → `misleading_edge`
- **每条字段（Phase 2A）**：`sample_id`, `bucket`, `query`, `decision_type`（`tool_call` | `no_tool` | `clarify_needed`）, `tool_name`, `arguments`, `clarify_answer`, `oracle_context`；根级可选 `sft_phase`=`2a_routing`；`_meta` 含 `slice` / `provider` / `sft_phase` 等。详见 `SFT_PHASE_2A.md`。
- **单批内 decision_type 条数**：由 `MIX_BY_SLICE` 控制（domain 以 tool_call 为主；far_general 偏高 no_tool；misleading 偏高 clarify_needed）。全量汇总与目标比例可能差少量条数（按批取整）。
- **脚本**：`generate_ft_qa_500.py`  
  - `.env`：`google_api_key`（见 `src/config.py`）；`pip install google-genai`。  
  - 输出：`out/ft_qa_{N}.jsonl`；若 `--split-test K` 则另写 `ft_qa_{N}_train.jsonl` / `ft_qa_{N}_test.jsonl`（按 slice **分层**划分，默认 `--split-seed 42`）（已 `.gitignore`）。

```bash
# 只看分批计划
python experiments/data_flywheel/generate_ft_qa_500.py --dry-run

# 正式生成（默认 target=100，segment-ratio=300,100,100）
python experiments/data_flywheel/generate_ft_qa_500.py

# 示例：再生成 450 条（70:15:15），其中 50 条测试集分层划分
python experiments/data_flywheel/generate_ft_qa_500.py --target 450 --segment-ratio 70,15,15 --split-test 50
```

模型名与批间间隔：编辑 `generate_ft_qa_500.py` 顶部 `GEMINI_MODEL`、`SLEEP_SECONDS`。

### 与 `loRA/devagent_train_data.json` 对齐说明

- **Phase 2A 新数据**：`format_to_sharegpt.py` 对含 `decision_type`（或 `sft_phase`/`_meta.sft_phase` 为 `2a_routing`）的行使用 **`PHASE_2A_ROUTING_SYSTEM_PROMPT`**，assistant 金标为**单行路由 JSON**（`decision_type`、`tool_name`、`arguments`、`clarify_answer`、`oracle_context`）。整份 JSONL 均为 Phase 2A 时可传 `convert_to_sharegpt(..., force_phase_2a_system=True)`。
- **历史数据**：旧 ShareGPT 里 assistant 常为 `{"name": ...}` 工具 JSON；**system** 为 `FINAL_SYSTEM_PROMPT`。若混入「无工具直答 / 澄清」旧 schema，需 `MIXED_SYSTEM_PROMPT` 或 `mixed_system=True`。
- **评测**：`loRA/eval_mixed_schema.py` 支持 Phase 2A（`--dry-run` 可统计 `decision_type`）；`eval_lora.py` 仍以旧工具 JSON 为主时需按子集区分。
