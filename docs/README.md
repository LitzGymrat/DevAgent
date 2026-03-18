# 🤖 DevAgent - AI 驱动的代码研发助手

![DevAgent Demo](./DevAgent演示.gif) 

<div align="center">

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue?style=flat-square)
![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)

**一个多工具协作的代码理解与生成系统**

[功能演示](#-核心功能) • [快速开始](#-快速开始) • [架构设计](#-系统架构) • [评估与测试](#-测试与评估) • [论文/报告](../评估/README_EVL.md)

</div>

---

## 📖 项目简介

**DevAgent** 是一个 **AI 驱动的开发助手**，具备以下能力：

- 🧠 **多工具 Agent 系统** - 基于 LLM Function Calling 自主决策调用 6 个专业工具
- 🔍 **RAG 检索** - 纯 Dense 向量检索（Chroma + Qwen text-embedding-v4），评估后不启用 Hybrid/Reranker
- 🎯 **LoRA 微调支持** - 可在 Qwen2.5-7B 上微调以提升工具路由准确率
- 🚀 **完整工程体系** - FastAPI 后端 + Streamlit Web UI + CI/CD 流水线

**适用场景**：代码分析、智能补全、日志诊断、Docker 配置生成、单元测试生成、代码库智能问答

---

## ✨ 核心功能

### 🛠️ 6 个智能工具模块

| 工具 | 功能描述 | 应用场景 |
|------|----------|----------|
| **🔎 Code Search** | 纯 Dense 检索（Qwen text-embedding-v4） | 快速定位相关代码片段 |
| **📊 Code Analyzer** | AST 静态分析 | 检测代码质量问题（圈复杂度、可变默认参数等） |
*实现了基于 GitHub Actions 的全自动 CI/CD。*
*通过 PYTHONPATH=. 环境注入实现代码与环境解耦，在每次 Push 时自动触发 AST 扫描，拦截漏洞与语法错误。*
| **✍️ Code Completer** | 智能代码补全 | 基于上下文自动续写代码 |
| **🐳 Dockerfile Generator** | 自动生成部署配置 | 一键生成 Dockerfile |
| **🧪 Test Generator** | 自动化生成单元测试 | pytest 风格的完整测试套件 |
| **🔧 Log Analyzer** | 错误日志诊断 | 定位 Bug、提供修复建议 |






### 🧠 Agent 决策流程

```
用户输入
  ↓
[LLM 理解] → 分析任务类型，选择工具（Function Calling）
  ↓
[工具执行] → 调用对应模块
  ↓
[多轮记忆] → 保留上下文，支持后续追问
  ↓
生成响应 → 用户
```

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- 4GB+ RAM（推荐 8GB）
- CUDA 11.8+（可选，用于本地嵌入模型或 LoRA 推理）

### 1️⃣ 安装依赖

```bash
# 克隆项目
git clone <your-repo-url>
cd DevAgent

# 创建虚拟环境
python -m venv venv
# Windows:
.\venv\Scripts\Activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

```

> ⚠️ **说明**：项目依赖较多，若 `pip install -r requirements.txt` 后运行报缺包，请根据报错信息补充安装，或执行 `pip freeze > requirements_full.txt` 导出完整依赖。

### 2️⃣ 配置 API 密钥

复制 `.env.example` 为 `.env`，并填入你的 API 密钥：

```bash
cp .env.example .env
```

编辑 `.env`：

```env
# DeepSeek API（主 LLM，必需）
deepseek_api_key=sk-xxxxx
deepseek_base_url=https://api.deepseek.com

# Qwen API（嵌入向量，推荐）
qwen_api_key=sk-xxxxx
qwen_base_url=https://dashscope.aliyuncs.com/compatible-mode/v1

# 可选：本地嵌入模型
embedding_provider=qwen    # 或 "local"
reranking_provider=qwen    # 或 "local"
```

### 3️⃣ 构建本地知识库

```bash
# 建立向量数据库（仅需一次）
python scripts/build_knowledge_base.py
```

**预期输出**：
```
正在从 src 建立本地知识库

本地知识库建立完成！
```

向量库保存到 `./data/Chroma/`，BM25 索引保存到 `./data/bm25_index.pkl`。

### 4️⃣ 启动服务

#### 方式 A：Web UI（推荐新手）

```bash
streamlit run web_ui.py
# 访问 http://localhost:8501
```

#### 方式 B：FastAPI 后端

```bash
# 在项目根目录执行
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
# API 文档: http://localhost:8000/docs
# 聊天接口: POST http://localhost:8000/api/v1/chat
```

#### 方式 C：Python 直接调用

```python
from src.agent.core import DevAgent

agent = DevAgent()
response = agent.chat("分析一下 src/rag/vectorstore.py 的代码质量")
print(response)
```

> 注意：需在项目根目录下运行，或确保 `PYTHONPATH` 包含项目根路径。

---

## 📊 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend Layer                          │
│  ┌──────────────┐              ┌──────────────────┐         │
│  │ Streamlit UI │              │  FastAPI Backend │         │
│  │  (web_ui.py) │◄────────────►│  (/api/v1/chat)  │         │
│  └──────────────┘              └──────────────────┘         │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │
┌─────────────────────────────────────────────────────────────┐
│                  DevAgent Core Engine                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │  Multi-turn Dialogue + Tool Routing (Function Calling)   ││
│  │  • 多轮记忆管理                                          ││
│  │  • JSON 解析与错误恢复                                   ││
│  └─────────────────────────────────────────────────────────┘│
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
    ┌────────┐    ┌────────┐    ┌─────────┐
    │ Tools  │    │  LLM   │    │   RAG   │
    └────────┘    └────────┘    └─────────┘
        │              │              │
   ┌────┴────┐    ┌────┴────┐   ┌────┴──────────┐
   │ 6 Tools │    │ DeepSeek│   │ RAG (Dense)   │
   │ Chain   │    │ (OpenAI)│   │  • Chroma     │
   └─────────┘    └─────────┘   │  • Qwen-v4    │
                                 └──────────────┘
```

### 关键模块

| 模块 | 路径 | 说明 |
|------|------|------|
| **Agent Core** | `src/agent/core.py` | 多轮对话、工具调用、记忆管理 |
| **LLM Interface** | `src/agent/llm.py` | 封装 OpenAI 兼容接口（DeepSeek） |
| **Tool Suite** | `src/agent/tools/` | 6 个核心工具实现 |
| **RAG System** | `src/rag/` | 向量库（Chroma）、Query Rewriter（可选） |
| **API Server** | `src/api/routes.py` | FastAPI 路由（挂载于 `/api/v1`） |
| **Config** | `src/config.py` | 统一配置管理（Pydantic Settings） |

---

## 📈 性能基准

> 数据来源：项目内 [评估/](../评估/) 文件夹，详见 [评估/README_EVL.md](../评估/README_EVL.md)。

### RAG 检索结论摘要

基于 18 条代表性 Query（top_k=8）的系统评估：

| 实验 | 文档 | 核心结论 |
|------|------|----------|
| **引擎基线** | [01-检索评估-引擎对比-基线](../评估/01-检索评估-引擎对比-基线.md) | Dense MRR **0.944**，选型为默认引擎 |
| **PoolSize 调参** | [02-检索评估-PoolSize对比](../评估/02-检索评估-PoolSize对比.md) | pool_size≈10 时 Hybrid 与 Dense 持平 |
| **Reranker 消融** | [03-检索评估-Reranker消融实验](../评估/03-检索评估-Reranker消融实验.md) | 加 Reranker 反而 MRR 下降，主链路不启用 |
| **Query Rewrite** | [04-检索评估-QueryRewrite消融实验](../评估/04-检索评估-QueryRewrite消融实验.md) | 口语化 query MRR **+16.5%** |

**工程决策**：默认纯 Dense，不启用 Reranker、Hybrid；Query Rewrite 对口语化 query 有显著提升。

### LoRA 微调效果（[05-LoRA微调评估报告](../评估/05-LoRA微调评估报告.md)）

与 Qwen2.5-7B-Instruct 基线及 DeepSeek API 对比：

| 评估维度 | Qwen2.5-7B (基线) | DeepSeek API | **DevAgent LoRA** | 提升幅度 |
|----------|-------------------|--------------|-------------------|----------|
| JSON 格式遵循率 | 92.00%      | 100.00%      | **100.00%** | ✅ 完美对齐 |
| **工具路由准确率** | 88.00%  | 72.00% (缺乏领域上下文) | **98.00%** | 🏆 +10% (反超 API) |
| 工具幻觉率       | 0.00%     | 0.00%          | 2.00% | 保持泛化能力 |

**数据来源**：50 条多样化测试用例，涵盖 6 种开发场景。运行 `loRA/eval_lora.py`、`loRA/eval_base.py` 可复现。

### 推理性能

| 操作 | 平均耗时 | 备注 |
|------|--------|------|
| 代码检索 | 500-1000ms | 包括向量化 + 融合 |
| 工具调用 | 500-2000ms | 取决于工具复杂度 |
| 完整对话循环 | 30-40s | 包括 Agent 决策 + 工具执行 |

*测试环境：惠普轻薄本+远程API*

---

## 🔧 配置说明

### 核心配置项（`src/config.py` / `.env`）

```python
# LLM 配置
model_name = "deepseek-chat"
embedding_provider = "qwen"        # qwen / local / openai
qwen_embedding_name = "text-embedding-v4"

# RAG 参数
code_chunk_size:int = 2000
code_chunk_overlap:int = 350
text_chunk_size : int = 1500
text_chunk_overlap : int = 350
# 每个片段重叠字符数
      
top_k : int = 8
# 功能开关
enable_query_rewrite_in_tool = False  # Query Rewriter 开关
```

> 说明：`CodeSplitter` 使用固定参数（chunk_size=2000, overlap=350），与 config 中的 `chunk_size` 用途不同。

### 环境变量

| 变量 | 必需 | 说明 |
|------|------|------|
| `deepseek_api_key` | ✅ | DeepSeek API 密钥 |
| `qwen_api_key` | 条件必需 | 在使用 Qwen 作为嵌入/重排模型时必需 |
| `embedding_provider` | - | 默认 `qwen` |
| `reranking_provider` | - | 默认 `qwen` |
| `Chroma_persist_dir` | - | 向量库路径，默认 `./data/Chroma` |
| `bm25_persist_dir` | - | BM25 索引路径，默认 `./data/bm25_index.pkl` |

---

## 📚 使用示例

### 示例 1：代码质量分析

```python
from src.agent.core import DevAgent

agent = DevAgent()

query = "分析 src/rag/vectorstore.py 的代码质量，重点检查圈复杂度"
response = agent.chat(query)

print(response)
# 输出：
# ✅ 已调用工具：analyse_code
# 📊 分析结果：
#   - 函数 search() 的圈复杂度为 8（警告）
#   - 发现 1 个可变默认参数
#   - ...建议...
```

### 示例 2：智能代码搜索

```python
query = "我要找一下向量数据库的初始化函数"
response = agent.chat(query)

# 自动调用 search_codebase，返回：
# 📍 找到 3 个相关代码片段：
# 1. src/rag/vectorstore.py:45-67 (VectorStore.__init__)
# 2. src/rag/loader.py:32-45 (RePoLoader.__init__)
# 3. ...
```

### 示例 3：生成单元测试

```python
query = """
请为这个函数生成单元测试：
def calculate_score(items: List[int], weights: List[float]) -> float:
    return sum(i * w for i, w in zip(items, weights))
"""

response = agent.chat(query)
# 返回完整的 pytest 测试代码
```

---

## 🧪 测试与评估

### 运行测试

```bash
# 测试 RAG 检索
python tests/test_hybrid.py          # 混合检索
python tests/test_bm25.py            # 稀疏检索
python tests/test_vectorstore.py     # 向量库

# 测试 Agent 工具
python tests/test_code_analyser.py   # 代码分析
python tests/test_search_tool.py     # 代码搜索
python tests/test_tool_calls.py      # 工具调用

# 测试配置
python tests/test_config.py          # 配置加载
python tests/test_llm.py             # LLM 连接
```

### 评估脚本

```bash
# RAG 检索评估
python src/evaluation/eva_retrieval.py          # 基准评估
python src/evaluation/eva_retrieval_reranker.py # 带重排的评估
python src/evaluation/eva_rewriter.py           # 查询改写效果

# LoRA 微调评估
python loRA/eval_lora.py                        # LoRA 模型评估
python loRA/eval_base.py                        # 基线模型评估
```

---

## 📁 项目结构

```
DevAgent/
├── README.md                      # 👈 你在这儿
├── requirements.txt               # 依赖列表
├── .env                          # 配置文件（API 密钥）
│
├── src/                          # 核心源代码
│   ├── main.py                   # FastAPI 应用入口
│   ├── config.py                 # 统一配置管理
│   ├── agent/
│   │   ├── core.py               # 🧠 Agent 核心引擎
│   │   ├── llm.py                # LLM 接口封装
│   │   └── tools/
│   │       ├── code_analyser.py  # 📊 代码分析工具
│   │       ├── search_tool.py    # 🔍 代码搜索工具
│   │       ├── complete_code_llm.py    # ✍️ 代码补全
│   │       ├── docker_file_llm.py      # 🐳 Dockerfile 生成
│   │       ├── generate_tests_llm.py   # 🧪 测试生成
│   │       ├── log_analyser_llm.py     # 🔧 日志分析
│   │       └── tools_schemas.py  # 工具 Schema 定义
│   ├── rag/
│   │   ├── vectorstore.py        # 向量数据库（Chroma）
│   │   ├── bm25.py               # BM25 稀疏检索
│   │   ├── query_rewriter.py     # 🎯 查询改写器
│   │   ├── loader.py             # 代码加载器
│   │   └── splitter.py           # 文本切分器
│   ├── api/
│   │   ├── routes.py             # FastAPI 路由
│   │   
│   └── evaluation/
│       ├── eva_retrieval.py      # 检索评估
│       ├── eva_rewriter.py       # 改写器评估
│       ├── rag_dataset.py        # 评估数据集
│       └── rewriter_noisy_dataset.py  # 脏数据集
│
├── loRA/                         # LoRA 微调模块
│   ├── generate_lora_data.py    # 数据生成（多场景）
│   ├── format_to_sharegpt.py    # 格式转换
│   ├── eval_lora.py             # LoRA 模型评估
│   ├── eval_base.py             # 基线模型评估
│   ├── eval_api.py              # API 模型评估
│   └── devagent_train_data.json # 训练数据（50+ 样本）
│
├── tests/                        # 单元测试
│   ├── test_*.py                # 各模块测试
│   └── debug_rag.py             # RAG 调试脚本
│
├── scripts/                      # 辅助脚本
│   ├── build_knowledge_base.py  # 构建向量库
│   └── ast_ci.py                # AST 代码检查
│
├── .github/workflows/
│   └── ast_ci.yml               # CI/CD 流水线
│
├── data/                         # 数据存储
│   └── Chroma/                  # 向量数据库文件
│
├── web_ui.py                    # 🎨 Streamlit 前端
│
└── 评估/                        # 评估实验与报告
    ├── README_EVL.md             # 评估文档索引
    ├── 01-检索评估-引擎对比-基线.md
    ├── 02-检索评估-PoolSize对比.md
    ├── 03-检索评估-Reranker消融实验.md
    ├── 04-检索评估-QueryRewrite消融实验.md
    ├── 05-LoRA微调评估报告.md
    ├── 06-Agent工具组合示例.md
    └── 07-附录-VectorStore实现说明.md
```

---

## 🤝 对应JD 需求的对标表

| 能力项 | 项目实现 | 说明 |
|--------|----------|------|
| AI Agent 核心引擎 | `src/agent/core.py` + 6 工具链 | Function Calling 驱动 |
| 代码理解 & 分析 | AST 静态分析 + 语义搜索 | 圈复杂度、默认参数等 |
| 代码生成 & 补全 | `complete_code_llm.py` | 基于上下文续写 |
| 文档 & 测试生成 | `generate_tests_llm.py` | pytest 风格 |
| 开发效率工具链 | Docker + 日志分析 | 配置生成、错误诊断 |
| 知识库 & 问答 | RAG 纯 Dense 检索 | Chroma + Qwen-v4 |
| 模型微调 | LoRA 微调 | Qwen2.5-7B |
| RAG 技术 | 纯 Dense、Query Rewriter（可选） | 评估后不启用 Hybrid/Reranker |
| IDE 集成 | FastAPI + Streamlit UI | Web 交互 |

---

## 🔗 延伸阅读

- 📊 **评估报告** → [评估/README_EVL.md](../评估/README_EVL.md)
  - 01-05: 检索基线、PoolSize、Reranker、QueryRewrite、LoRA 评估
  - 06: Agent 工具组合（Tool Chaining）示例
  - 07: VectorStore 实现说明

- 📄 **核心论文参考**
  - RAG: ["Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks"](https://arxiv.org/abs/2005.11401)
  - LoRA: ["LoRA: Low-Rank Adaptation"](https://arxiv.org/abs/2106.09685)
  - Query Rewriting: ["RankGPT: Query Rewriting with Generative Models"](https://arxiv.org/abs/2403.08394)

---

## 🛠️ 常见问题

### Q1: 如何更换 LLM？

编辑 `src/config.py` 或 `.env` 中的 `model_name`、`deepseek_base_url`，或修改 `src/agent/llm.py` 的 OpenAI 兼容客户端配置。

### Q2: 向量库初始化失败？

确保 `.env` 中配置了 `qwen_api_key`，或设置 `embedding_provider=local`（需安装 HuggingFace 模型）。

### Q3: 工具调用返回空结果？

先运行 `python scripts/build_knowledge_base.py` 构建向量库，再启动服务。

### Q4: 如何部署到生产环境？

```bash
gunicorn --workers 4 --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 src.main:app
```

### Q5: 支持哪些编程语言？
**A:** 目前主要支持 Python（RAG 库基于 Python），但 Agent 可以分析任何代码。建议后续扩展支持 Java/Go/Rust/JavaScript。


---

## 📊 相关数据

- **代码行数**: ~3000 行（不含测试和微调数据）
- **测试覆盖**: 12+ 单元测试脚本
- **评估数据**: 50+ 多样化训练样本 + 13 条测试查询
- **模型**: Qwen2.5-7B-Instruct (LoRA 微调版)
- **向量模型**: Text-Embedding-V4 / All-MiniLM-L6-v2

---

## 🚀 未来规划

- [ ] 🎯 支持更多编程语言（Java/Go/Rust/JavaScript）
- [ ] 📱 VS Code 插件集成
- [ ] ⚡ 模型量化 + 推理优化（ONNX/TensorRT）
- [ ] 💾 本地化部署（支持离线使用）
- [ ] 🔐 安全加固（认证、审计、加密）

---

## 📞 联系方式

- 📧 Email: 1195660719@qq.com
- 🎓 项目用途: 华为大模型应用实习生招聘投递

---

## 📄 License

MIT License © 2026 DevAgent Contributors

---

<div align="center">

⭐ **如果这个项目对你有帮助，欢迎 Star！** ⭐

</div>
