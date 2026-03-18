# Agent 工具组合（Tool Chaining）示例

## 示例：日志分析 + 代码检索联动

用户输入崩溃日志 → Agent 自动调用 `analyse_log` → 得到错误位置（如 `src/auth.py` 第 42 行）→ Agent 继续调用 `search_codebase` 检索相关代码 → 可进一步调用 `analyze_code` 做 AST 分析 → 输出完整诊断报告。

## 实际输出示例

```
加载系统提示词
Agent综合分析中
Agent决策：决定调用工具：analyse_log
Agent综合分析中

根据日志分析，这是一个 **Pydantic 模型字段缺少类型注解** 的错误。

## 问题分析
- 根本原因：`src/config.py` 中 `Settings` 类的 `enable_query_rewrite_in_tool` 未添加类型注解
- 错误位置：`C:\Users\MilesZhu\DevAgent\src\config.py`

## 解决方案
（方案一/二/三...）

## 建议
1. 立即修复：为 `enable_query_rewrite_in_tool` 添加 `: bool` 类型注解
2. 检查其他字段
3. 考虑引入 mypy 做静态类型检查
```

## 架构价值

- **复合型 AI 系统（Compound AI System）**：多工具自动串联，无需用户介入
- **Agentic Workflow**：一问一答 → 多步推理、跨界联动
- 主 Agent 精准路由到专家函数，提示词工程发挥 100% 威力
