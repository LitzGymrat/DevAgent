# Phase 2A 路由标注口径（与 ft_qa 清洗一致）

以下为人工复核后固化的规则，供继续生成或二次标注时对齐。

## 1. 非任务型 query

不进入路由监督：纯陈述、纯感慨、纯主观观点/访谈式提问。直接删除。

## 2. bucket：domain vs far_general

凡**不依赖本仓库**即可回答的通用框架对比、通识概念、产品 URL 等，标 **`no_tool`** 且 **`bucket`** = `far_general`，`_meta.slice` = `dev_general_no_rag`（与「开发通识」切片一致）。

## 3. 模糊但方向明确

- **检索意图明确**（如「auth 在哪」「Nginx 配置在哪」「路由注册不对劲」）：优先 **`tool_call(search_codebase)`**，不必先 `clarify_needed`。
- **已给代码片段**、但声称「报错 / 要优化 / 性能差」而**未给日志或现象**：优先 **`tool_call(analyse_code)`**；若信息量不足以做任何分析，再用 **`clarify_needed`**。

## 4. `analyse_log` vs `search_codebase`（含 from_pretrained）

- **核心诉求是读懂已有报错/Traceback 归因** → **`analyse_log`**（须把日志贴全）。
- **核心诉求是在源码里追踪实现**（如 Config/from_pretrained 解析路径、模块位置）→ **`search_codebase`**。

已写入补丁脚本：`patch_ft_qa_500_train_audit.py`（可对照 `_meta.routing_note` 与字段变更）。
