# ⚡ DevAgent 快速开始指南（5 分钟上手）

> 最快速的方式让 DevAgent 在你的机器上跑起来！  
> 详细说明见 [README.md](./README.md)

---

## 📋 前置检查清单

- [ ] Python 3.10+ 已安装 (`python --version`)
- [ ] pip 已安装 (`pip --version`)
- [ ] DeepSeek API 密钥（[获取](https://platform.deepseek.com)）
- [ ] Qwen API 密钥（[获取](https://dashscope.aliyuncs.com)）

> 💡 没有 API 密钥？可将 `embedding_provider=local` 使用本地嵌入模型（需约 4GB 磁盘）

---

## 🚀 5 分钟快速启动

### 步骤 1️⃣：克隆项目

```bash
git clone <your-repo-url>
cd DevAgent
```

### 步骤 2️⃣：创建虚拟环境并安装依赖

```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Mac/Linux
python -m venv venv
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 若报缺包，补充 RAG/Agent 所需依赖
pip install openai langchain-core langchain-chroma langchain-openai langchain-huggingface langchain-text-splitters rank-bm25 dashscope sentence-transformers streamlit
```

### 步骤 3️⃣：配置 API 密钥

复制 `.env.example` 为 `.env`，并填入密钥：

```bash
# Windows
copy .env.example .env

# Mac/Linux
cp .env.example .env
```

编辑 `.env`：

```env
# DeepSeek（LLM 主引擎，必需）
deepseek_api_key=sk-your-key-here
deepseek_base_url=https://api.deepseek.com

# Qwen（向量嵌入，推荐）
qwen_api_key=sk-your-key-here
qwen_base_url=https://dashscope.aliyuncs.com/compatible-mode/v1

# 使用本地嵌入模型时
# embedding_provider=local
```

> 🔒 `.env` 已在 `.gitignore` 中，不会被提交

### 步骤 4️⃣：构建知识库（一次性）

```bash
python scripts/build_knowledge_base.py
```

**预期输出**：
```
正在从 src 建立本地知识库

本地知识库建立完成！
```

向量库保存到 `./data/Chroma/`，BM25 索引到 `./data/bm25_index.pkl`。约 1–2 分钟，只需执行一次。

### 步骤 5️⃣：启动 Web UI（推荐）

```bash
streamlit run web_ui.py
```

访问 http://localhost:8501 即可开始对话。

---

## 💬 第一次对话

在 Web UI 中输入：

```
分析一下 src/rag/vectorstore.py 的代码质量
```

**预期**：Agent 调用 `analyse_code`，输出圈复杂度、问题检测等分析结果。

也可尝试：
- `找一下向量数据库的初始化函数` → 调用 `search_codebase`
- `帮我生成这段代码的单元测试` → 调用 `generate_tests`
- `这段报错怎么解决？`（粘贴日志）→ 调用 `analyse_log`

---

## 🔄 其他启动方式

### 方式 B：FastAPI 后端（用于集成）

```bash
# 在项目根目录执行
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

- API 文档：http://localhost:8000/docs  
- 聊天接口：`POST /api/v1/chat`

**示例**：
```bash
curl -X POST "http://localhost:8000/api/v1/chat" \
  -H "Content-Type: application/json" \
  -d "{\"question\":\"找一下 vectorstore.py 中的 search 方法\"}"
```

> 注意：请求体字段为 `question`，不是 `query`。

### 方式 C：Python 脚本直接调用

```python
from src.agent.core import DevAgent

agent = DevAgent()
response = agent.chat("请帮我分析 core.py 的代码")
print(response)
```

在项目根目录运行：`python your_script.py`

---

## ❓ 常见问题排查

### Q1: `ImportError: No module named 'src'`

**原因**：未在项目根目录运行，或 Python 路径不正确。

**解决**：
```bash
cd DevAgent   # 确保在项目根目录

# 可选：显式设置 PYTHONPATH
# Windows (PowerShell)
$env:PYTHONPATH = (Get-Location).Path

# Mac/Linux
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

streamlit run web_ui.py
```

### Q2: API 连接超时

**排查**：
```bash
python tests/test_llm.py   # 测试 LLM 连接

# 检查 .env 是否存在且密钥正确
# Windows: type .env
# Mac/Linux: cat .env
```

### Q3: 向量库构建失败 `qwen_api_key not found`

**解决**：
```bash
# 方案 A：在 .env 中填入 qwen_api_key（推荐）

# 方案 B：使用本地模型
# 在 .env 中设置：
embedding_provider=local

# 首次会下载 HuggingFace 模型（约 4GB）
python scripts/build_knowledge_base.py
```

### Q4: 内存不足 `MemoryError`

**解决**：关闭其他程序，或减少检索数量：
```python
# .env 或 src/config.py
top_k=3   # 默认 5，可降至 3
```

### Q5: 响应很慢（>5 秒）

**改进**：
- 检查网络：`ping api.deepseek.com`
- 在 `src/agent/llm.py` 中可调低 `temperature`、`max_tokens` 以加快响应

---

## ✅ 验证安装成功

| 检查项 | 命令 | 预期 |
|--------|------|------|
| 配置加载 | `python tests/test_config.py` | 显示 API key 前几位、模型名 |
| LLM 连接 | `python tests/test_llm.py` | 模型返回回答 |
| 工具调用 | `python tests/test_tool_calls.py` | Agent 决策 + 耗时日志 |

---

## 📁 项目结构速览

```
DevAgent/
├── web_ui.py              ← Streamlit UI（入口）
├── .env.example           ← 配置模板，复制为 .env
├── src/
│   ├── main.py            ← FastAPI 应用
│   ├── config.py          ← 配置管理
│   ├── agent/
│   │   ├── core.py        ← Agent 核心
│   │   └── tools/         ← 6 个工具
│   └── rag/               ← 向量库、BM25、Query Rewriter
├── scripts/
│   └── build_knowledge_base.py
├── tests/
└── data/
    └── Chroma/            ← 向量库持久化
```

---

## 🎓 下一步学习

| 想要... | 阅读 |
|--------|------|
| 理解架构 | [ARCHITECTURE.md](./ARCHITECTURE.md) |
| 添加新工具 | [ARCHITECTURE.md#扩展与定制](./ARCHITECTURE.md#扩展与定制) |
| 性能优化 | [ARCHITECTURE.md#性能优化策略](./ARCHITECTURE.md#性能优化策略) |
| 评估与测试 | [README.md#测试与评估](./README.md#测试与评估) |

---

## 💡 实用提示

### 调试 RAG 检索

```bash
python tests/debug_rag.py   # 输出检索结果详情
```

### 查看工具耗时

工具调用会自动打印耗时，例如：
```
⏱️ [耗时监控] 函数 'search_codebase' 执行完毕 | 耗时: 0.234 秒
```

---

## ✨ 你现在可以做什么

1. ✅ 在 Web UI 中提问
2. ✅ 搜索代码库（`search_codebase`）
3. ✅ 分析代码质量（`analyse_code`）
4. ✅ 生成单元测试（`generate_tests`）
5. ✅ 分析错误日志（`analyse_log`）
6. ✅ 生成 Docker 配置（`generate_dockerfile`）
7. ✅ 智能代码补全（`complete_code`）

---

**🎉 祝你使用愉快！有问题欢迎提 Issue。**
