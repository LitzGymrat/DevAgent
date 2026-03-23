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

向量库（Chroma）保存到 **`Chroma_persist_dir`** 指向的目录（默认 **`./data/chorma`**，历史拼写），BM25 索引保存到 `./data/bm25_index.pkl`。

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

## 📈 性能基准与最新进展

### 🔄 最新迭代（2026 年 3 月）

#### 1. 检索策略调整

**问题**：早期模型在通用问答中容易过检索，不该查库时也会触发 `search_codebase`。

**解决方案**：
- **软熔断**：基于 Dense 距离分桶和阈值分析（T=1.12），对无效检索做兜底拦截
- **Prompt 调整**：根据端到端 bad case 迭代 system prompt 与工具描述，重点优化"是否调用工具"的判断

**结果**：
- 工具调用一致率从 **63.3% 提升到 97.8%**
- 假正例（FP）从 33 降到 **2**
- 对于必须查库的 35 条 must_ground 样本，假负例（FN）保持为 0

#### 2. 评测分层体系

| 层次 | 评估内容 | 关键指标 |
|------|----------|----------|
| **第一层** | 工具调用是否符合 gold | 工具一致率 ✅ 97.8% |
| **第二层** | 检索后的软熔断效果 | 距离分桶准确率 ✅ 62% |
| **第三层** | LLM-as-Judge 回答质量 | 按 bucket + grounding_tier 评估 |

#### 3. 大仓库场景与数据飞轮

- **外部仓基准**：在 `experiments/external/` 中使用 Transformers、FastAPI 等外部仓库建立基准
- **索引隔离**：外部仓基准与主仓 `src/` 索引隔离，避免混淆结果
- **数据组织**：按私域、远域、误导场景组织数据，覆盖"该查库"和"不该查库"两类任务
  - **域内**（私域）：40 条样本
  - **远域通用**：28 条样本（线上排障、语法/算法基础）
  - **术语接近不该查库**：12 条样本
  - **误导边界**：10 条样本

> 数据来源：项目内 [评估/](../评估/) 文件夹，详见 [评估/README_EVL.md](../评估/README_EVL.md)。

#### 4. 核心指标快照

**A. 检索侧：距离分桶与软熔断（90 条样本）**

| 分桶 | n | mean | median | min–max |
|------|---|------|--------|---------|
| domain | 40 | 0.838 | 0.884 | 0.502–1.183 |
| far_general | 28 | 1.205 | 1.194 | 1.034–1.377 |
| term_near_no_rag | 12 | 1.055 | 1.133 | 0.638–1.334 |
| misleading_edge | 10 | 0.865 | 0.873 | 0.497–1.193 |
| **域外合并** | 50 | 1.101 | 1.156 | 0.497–1.377 |

**结论**：域内与域外分布有重叠。阈值 T=1.12 可拦截 62% 域外样本，但会误伤 7.5% 域内样本，说明软熔断适合做兜底，不适合作为唯一判断依据。

**B. 端到端工具调用一致率**

| 阶段 | 一致率 | FP | FN |
|------|--------|-----|-----|
| 首轮（旧 Prompt） | 57/90 (63.3%) | 33 | 0 |
| **Prompt v2** | **88/90 (97.8%)** | **2** | **0** |

对于必须查库的 35 条 must_ground 样本，两版测试的 FN 都为 0。

### RAG 检索结论摘要

基于 18 条代表性 Query（top_k=8）的系统评估，并基于最新的软熔断 Phase 1 与端到端评测（90 条样本）：

| 实验 | 文档 | 核心结论 |
|------|------|----------|
| **引擎基线** | [01-检索评估-引擎对比-基线](../评估/01-检索评估-引擎对比-基线.md) | Dense MRR **0.944**，选型为默认引擎 |
| **PoolSize 调参** | [02-检索评估-PoolSize对比](../评估/02-检索评估-PoolSize对比.md) | pool_size≈10 时 Hybrid 与 Dense 持平 |
| **Reranker 消融** | [03-检索评估-Reranker消融实验](../评估/03-检索评估-Reranker消融实验.md) | 加 Reranker 反而 MRR 下降，主链路不启用 |
| **Query Rewrite** | [04-检索评估-QueryRewrite消融实验](../评估/04-检索评估-QueryRewrite消融实验.md) | 口语化 query MRR **+16.5%** |
| **软熔断 Phase 1** | [08-软熔断Phase1与端到端评测](../评估/08-软熔断Phase1与端到端评测.md) | 距离分桶分析，阈值 T=1.12 可拦截 62% 域外样本 |
| **端到端工具调用** | [09-prompt与工具描述优化后复测](../评估/09-prompt与工具描述优化后复测.md) | Prompt v2 工具调用一致率达 **97.8%**（从 63.3% 提升）|

**工程决策**：
- 默认纯 Dense，不启用 Reranker、Hybrid；Query Rewrite 对口语化 query 有显著提升
- **软熔断策略**：基于 Dense 距离分桶做兜底，拦截无效检索（FP 从 33 降到 2）
- **Prompt 优化**：通过调整 system prompt 与工具描述，优化工具调用判断逻辑
- **评测分层**：工具调用层 → 检索/软熔断层 → LLM-as-Judge 回答质量层

### LoRA 微调效果

#### 第一阶段评估（[05-LoRA微调评估报告](../评估/05-LoRA微调评估报告.md)）

与 Qwen2.5-7B-Instruct 基线及 DeepSeek API 对比：

| 评估维度 | Qwen2.5-7B (基线) | DeepSeek API | **DevAgent LoRA** | 提升幅度 |
|----------|-------------------|--------------|-------------------|----------|
| JSON 格式遵循率 | 92.00%      | 100.00%      | **100.00%** | ✅ 完美对齐 |
| **工具路由准确率** | 88.00%  | 72.00% (缺乏领域上下文) | **98.00%** | 🏆 +10% |
| 工具幻觉率       | 0.00%     | 0.00%          | 2.00% | 保持泛化能力 |

#### Phase 2A 路由微调（[11-Phase2A路由SFT微调报告](../评估/11-Phase2A路由SFT微调报告.md)）

基于 Qwen2.5-7B-Instruct 的 LoRA 微调，聚焦路由决策与结构化输出（50 条验证集）：

| 评估维度 | Base | LoRA | API | 目标 |
|----------|------|------|-----|------|
| 可解析为 JSON | 96.0% | 100% | 100% | ✅ |
| JSON 结构合法 | 82.0% | **100%** | 98.0% | ✅ |
| **decision_type 一致** | 56.0% | **98.0%** | 92.0% | 🏆 +42% |
| **工具名一致** | 86.7% | **96.8%** | 90.3% | ✅ |

**数据来源**：50+ 多样化测试用例，涵盖 6 种开发场景。本轮微调目标聚焦 JSON 可解析、决策类型正确、工具名正确，不将 arguments 与金标逐字一致作为主指标。运行 `loRA/eval_lora_phase2a.py`、`loRA/eval_base_phase2a.py`、`loRA/eval_api_phase2a.py` 可复现。

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
| `Chroma_persist_dir` | - | Chroma 持久化目录，默认 `./data/chorma`（见 `src/config.py`；目录名历史拼写，非 `chroma`） |
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
# Phase 2A 单轮路由（decision_type / tool_name / …），默认测 devagent_phase2a_eval.json
python loRA/eval_lora_phase2a.py --lora-path /path/to/lora
python loRA/eval_base_phase2a.py --base-model /path/to/Qwen2.5-7B-Instruct
python loRA/eval_api_phase2a.py

# 软熔断 Phase 1：仅 Dense top-1 距离分布（不调用 LLM，需已建向量库）
python scripts/eval_soft_fuse_phase1.py --sweep 15
python scripts/eval_soft_fuse_phase1.py --threshold 1.12 --json-out data/soft_fuse/soft_fuse_phase1_raw.json

# 端到端链路评测（需 LLM API）：工具决策 + 检索/软熔断 + 回答预览 → JSONL
python scripts/eval_e2e_pipeline.py --limit 5
python scripts/eval_e2e_pipeline.py --soft-fuse --soft-fuse-threshold 1.12 --jsonl-out data/e2e_eval_log.jsonl

# Prompt v2 优化后复测
python scripts/eval_e2e_pipeline.py --jsonl-out data/e2e_eval_log_promptv2.jsonl

# LLM-as-Judge 第三层评测
python scripts/eval_llm_judge_e2e.py --jsonl data/e2e_eval_log_promptv2.jsonl

# 离线重算指标
python scripts/rescore_e2e_jsonl.py --brief-only data/e2e_eval_log_promptv2.jsonl --compare data/e2e_eval_log.jsonl

# Bad case 分析
python scripts/analyze_soft_fuse_badcase.py
python scripts/analyze_e2e_badcase.py
```

> **说明**：
> - **题库**：见 `src/evaluation/soft_fuse_dataset.py`，覆盖 **域内 40**（私域）+ **域外 50** 条（拆三桶）
> - **E2E Gold**：由 `src/evaluation/e2e_manifest.py` 定义，`grounding_tier`：`must_ground` / `prefer_ground` / `ok_generic`，对应 `should_call_tool` 为 `yes` / `optional` / `no`
> - **软熔断标定**：基于「域内 vs 域外」做阈值分析，T=1.12 可拦截 62% 域外，误伤 7.5% 域内
> - **最新完整评测**：见 [**评估/08**](../评估/08-软熔断Phase1与端到端评测.md)（软熔断 Phase 1 与首轮端到端）
> - **Prompt v2 复测**：见 [**评估/09**](../评估/09-prompt与工具描述优化后复测.md)，日志：`data/e2e_eval_log_promptv2.jsonl`
> - **LLM-as-Judge**：见 [**评估/10**](../评估/10-LLM-as-Judge-v1.md)，抽样 22 条、按桶标准

---

## 📁 项目结构

```
DevAgent/
├── README.md                      
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
│   ├── eval_lora.py             # LoRA 模型评估（旧：name/arguments）
│   ├── eval_base.py             # 基线模型评估（旧）
│   ├── eval_api.py              # API 模型评估（旧）
│   ├── eval_lora_phase2a.py     # Phase 2A：LoRA（单文件，可拷到 AutoDL）
│   ├── eval_base_phase2a.py     # Phase 2A：基座
│   ├── eval_api_phase2a.py      # Phase 2A：API
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
│   └── chorma/                  # Chroma 持久化目录（默认名，见 Chroma_persist_dir）
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
- **评估数据**: 50+ 多样化训练样本 + 18 条测试查询
- **模型**: Qwen2.5-7B-Instruct (LoRA 微调版)
- **向量模型**: Text-Embedding-V4 / All-MiniLM-L6-v2

---

## 🚀 未来规划

### 评测侧
- [ ] 📊 继续补充召回后回答质量指标，参考 RAGAS 类方法
- [ ] 🔍 扩展外部仓库基准（Java/Go/Rust/JavaScript）
- [ ] 📈 完善 LLM-as-Judge 评分标准

### 训练侧
- [ ] 🎯 从路由 SFT 延伸到检索后生成微调
- [ ] 💞 偏好对齐与 Self-RAG 类后训练
- [ ] 🧠 多轮对话与记忆优化
- [ ] 🔗 Tool Chaining 能力增强

### 工程侧
- [ ] 🎯 支持更多编程语言（Java/Go/Rust/JavaScript）
- [ ] 📱 VS Code 插件集成
- [ ] ⚡ 模型量化 + 推理优化（ONNX/TensorRT）
- [ ] 💾 本地化部署（支持离线使用）
- [ ] 🔐 安全加固（认证、审计、加密）

---

## 📞 联系方式

- 📧 Email: 1195660719@qq.com


---

## 📄 License

MIT License © 2026 DevAgent Contributors

---

<div align="center">

⭐ **如果这个项目对你有帮助，欢迎 Star！** ⭐

</div>
