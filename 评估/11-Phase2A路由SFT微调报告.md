# Phase 2A 路由 SFT 微调报告

**阶段**：单轮工具路由对齐（Single-shot Tool Routing SFT）  
**监督形态**：单行 **Phase 2A 路由 JSON**（含 `decision_type`、`tool_name`、各分支字段等），**不**以最终自然语言长答为主目标。

**详细定义与数据说明**：见 `experiments/data_flywheel/SFT_PHASE_2A.md`。

---

## 1. 本轮在训什么（主目标）

**本轮优化重点不是「参数与金标逐字一致」**，而是下面三件事；`arguments` 等字段在 schema 里仍会学，但**不作为本轮结论的主 KPI**。

| 目标 | 说明 |
|------|------|
| JSON 可解析 | 输出为单行可 `json.loads` 的对象，字段与 Phase 2A schema 一致 |
| 决策类型 | `tool_call` / `no_tool` / `clarify_needed` 与任务意图对齐 |
| 工具选择 | `tool_call` 时在白名单工具中选对方 |

---

## 2. 数据与格式

| 项目 | 内容 |
|------|------|
| 训练源 | `ft_qa_500_train.jsonl`（清洗后约 **474** 条，以当前仓库导出为准） |
| 评测集 | `ft_qa_450_test.jsonl` 对应 ShareGPT 导出 **50** 条 → `devagent_phase2a_eval.json` |
| System | `loRA/format_to_sharegpt.py` 中 `PHASE_2A_ROUTING_SYSTEM_PROMPT`（与生成侧工具块对齐） |
| 导出 | `python loRA/format_to_sharegpt.py --input ... --phase2a --out-train ...` |

**LLaMA-Factory**：ShareGPT 格式；`columns` 中 `messages` → `conversations`；**必须**配置 `tags`（`from` / `value` / `user` / `assistant` / `system`），避免与默认 `human`/`gpt` 角色混淆。详见 `loRA/llamafactory_dataset_info.phase2a_snippet.json` 与 `SFT_PHASE_2A.md` 中 AutoDL 小节。

---

## 3. 训练环境（用户侧）

- **典型平台**：AutoDL + [LLaMA-Factory](https://github.com/hiyouga/LLaMA-Factory)  
- **基座**：Qwen2.5-7B-Instruct 类指令模型（路径以实例为准，如 `/root/autodl-tmp/models/qwen/...`）  
- **LoRA 权重**：由 LLaMA-Factory 训练产出目录挂载（示例：`.../saves/.../lora/<run_id>`）；**本地路径须为绝对路径或经脚本解析**，避免相对路径 `LLaMA-Factory/saves/...` 被误判为 Hub `org/repo`。

---

## 4. 评测设置

| 项目 | 内容 |
|------|------|
| 脚本 | `loRA/eval_base_phase2a.py`、`loRA/eval_lora_phase2a.py`、`loRA/eval_api_phase2a.py`（单文件可拷到服务器） |
| 测试集 | ShareGPT JSON 数组，默认 **50** 条（`devagent_phase2a_eval.json`） |
| 生成 | 本地：`max_new_tokens=512`，`temperature=0.1`，`do_sample=False`；API 与脚本内 `--max-tokens` 一致 |

**指标说明（脚本实现）**

**与 §1 主目标对齐的指标**

- **解析率**：模型输出经解析后存在 `decision_type` 的 JSON 比例。  
- **结构合法**：`is_valid_phase2a_shape`（各分支下必填/禁填字段满足 Phase 2A 约束）。  
- **decision_type 一致**：与金标决策类型相同。  
- **tool_call 子集·工具名**：金标为 `tool_call` 时，预测亦为 `tool_call` 且 `tool_name` 与金标一致。  
- **非法工具名**：预测为 `tool_call` 但 `tool_name` 为空或不在白名单。

**参考指标（非本轮主结论）**

- **tool_call 子集·工具+arguments 全等**：工具名已一致时，`arguments` 与金标 **字典全等**（字面极严，易因代码片段空格/转义差异偏低；**不**用来否定路由微调效果）。

---

## 5. 评测结果（本轮实测）

> 条件：同一条目 **50** 条评测集；**Base** = 基座全参推理；**LoRA** = 基座 + 本轮 Phase 2A LoRA；**API** = DeepSeek 兼容 OpenAI 接口（配置见 `eval_api_phase2a.py` / 环境变量）。  
> **主看**：解析率、结构合法、`decision_type`、工具名；末行 arguments 全等为 **附表参考**。

| 指标 | Base（Qwen2.5-7B-Instruct） | LoRA（本轮） | API |
|------|-----------------------------|--------------|-----|
| 模型输出可解析为 JSON | 48 / 50（**96.0%**） | 50 / 50（**100%**） | 50 / 50（**100%**） |
| 解析且结构合法 | 41 / 50（**82.0%**） | 50 / 50（**100%**） | 49 / 50（**98.0%**） |
| **decision_type 一致** | 28 / 50（**56.0%**） | 49 / 50（**98.0%**） | 46 / 50（**92.0%**） |
| 金标为 `tool_call` 的条数 | 30 | 31 | 31 |
| 工具名一致（占金标 tool_call） | 26 / 30（**86.7%**） | 30 / 31（**96.8%**） | 28 / 31（**90.3%**） |
| *（参考）* 工具名 + arguments 全等（占金标 tool_call） | 9 / 30（**30.0%**） | 12 / 31（**38.7%**） | 13 / 31（**41.9%**） |
| tool_call 但工具名非法/空 | 0 | 0 | 0 |

**推理耗时（ tqdm 粗测，仅供参考）**

- Base：约 **47** s / 50 条（≈1.06 it/s）  
- LoRA：约 **91** s / 50 条（≈1.83 s/it）  
- API：约 **134** s / 50 条（≈2.70 s/it，含网络）

---

## 6. 结论

1. **相对 §1 的三项主目标**，本轮 LoRA 在 50 条上表现突出：**可解析 JSON**、**结构合法**、`decision_type` 一致率（**56% → 98%**），以及 **tool_call 子集工具名**（约 **87% → 97%**），说明 **路由 JSON 形状 + 决策 + 工具** 已与监督对齐。  
2. **与 API 基线相比**：LoRA 在 **decision_type** 与 **结构合法** 上更稳；API 在 **decision** 上仍较高（**92%**），可作为 **离线对照**，二者不必强行单指标排名。  
3. **arguments 全等率**（约 30%–42%）**不作为本轮主结论**：本轮未优化「参数逐字复现金标」；该列仅反映脚本中的严格字面指标，**低**不表示路由任务失败。若后续要考核参数质量，再单独设计 **关键键 / 宽松匹配** 或 Phase 2B。  
4. **金标 `tool_call` 条数**：表中 Base 为 **30**、LoRA/API 为 **31**。若三次评测使用**同一份** `devagent_phase2a_eval.json`，该统计应相同；若出现差异，请核对是否混用了不同版本评测文件或拷贝路径。

---

## 7. 复现与脚本索引

| 用途 | 路径 |
|------|------|
| Phase 2A 定义 | `experiments/data_flywheel/SFT_PHASE_2A.md` |
| ShareGPT 导出 | `loRA/format_to_sharegpt.py` |
| LLaMA-Factory 数据集片段 | `loRA/llamafactory_dataset_info.phase2a_snippet.json` |
| 基座评测 | `loRA/eval_base_phase2a.py` |
| LoRA 评测 | `loRA/eval_lora_phase2a.py` |
| API 评测 | `loRA/eval_api_phase2a.py` |

---

## 8. 与上一轮「纯工具 JSON」微调（`05-LoRA微调评估报告`）的关系

- **旧任务**：assistant 金标多为 `{"name","arguments"}` 式工具调用，指标侧重 **JSON 遵循 + 工具名**。  
- **本轮（Phase 2A）**：金标为 **`decision_type` + 分支字段**，并显式包含 **`no_tool` / `clarify_needed`**；评测脚本与数据集条目均为 **Phase 2A 专用**，**不可**与旧表简单横比为「同一套分母」。

---

*文档版本：与仓库内 Phase 2A 数据与 `eval_*_phase2a.py` 逻辑一致；若训练或评测脚本更新，请同步修订 §4–§5。*
