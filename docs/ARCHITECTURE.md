# 📐 DevAgent 系统架构设计文档

> 本文档详细阐述 DevAgent 的系统设计、技术选型和核心算法，适合**想要深入理解项目者阅读**。  
> 快速上手请参考 [README.md](./README.md) 与 [QUICKSTART.md](./QUICKSTART.md)。

---

## 目录
1. [整体架构](#整体架构)
2. [核心模块设计](#核心模块设计)
3. [RAG 系统详解](#rag-系统详解)
4. [Agent 决策引擎](#agent-决策引擎)
5. [数据流与状态管理](#数据流与状态管理)
6. [性能优化策略](#性能优化策略)
7. [扩展与定制](#扩展与定制)

---

## 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         Presentation Layer                       │
│  ┌────────────────────┐             ┌────────────────────────┐  │
│  │ Streamlit Web UI   │             │ FastAPI REST API       │  │
│  │ (web_ui.py)        │◄───HTTP────►│ (/api/v1/chat)         │  │
│  └────────────────────┘             └────────────────────────┘  │
│                                              ▲                    │
└──────────────────────────────────────────────┼────────────────────┘
                                               │
┌──────────────────────────────────────────────┼────────────────────┐
│                  Application Layer                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │              DevAgent Core Engine                          │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │ Multi-turn Dialogue Manager                         │  │  │
│  │  │ - Memory Buffer: max_history_turns                  │  │  │
│  │  │ - Context Window Management                         │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  ├───────────────────────────────────────────────────────────┤  │
│  │              Agent Decision Engine                        │  │
│  │  ┌─────────────────────────────────────────────────────┐  │  │
│  │  │ Tool Router (LLM Function Calling)                  │  │  │
│  │  │ - 解析 tool_calls 中的 name / arguments              │  │  │
│  │  │ - 验证工具名、参数，执行并反馈                        │  │  │
│  │  │ - 错误恢复（safe_json_loads 解析 arguments）          │  │  │
│  │  └─────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────┘  │
└──────────────────────┬───────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
   ┌─────────┐    ┌────────┐    ┌──────────┐
   │Tools    │    │LLM     │    │RAG       │
   │Layer    │    │Layer   │    │System    │
   └─────────┘    └────────┘    └──────────┘
```

### 架构分层说明

| 层级 | 组件 | 职责 |
|------|------|------|
| **Presentation** | web_ui.py / FastAPI | 用户交互、API 暴露 |
| **Application** | Agent Core | 业务编排、工具路由、记忆管理 |
| **Service** | Tools / LLM / RAG | 具体能力实现 |
| **Infrastructure** | config.py / .env | 配置管理（Pydantic Settings） |

---

## 核心模块设计

### 1️⃣ Agent 核心引擎 (`src/agent/core.py`)

#### 类图
```python
class DevAgent:
    - available_tools: Dict[str, Callable]  # 工具映射表（6 个工具）
    - memory: List[Dict]                     # 多轮对话历史（含 system/user/assistant/tool）
    - max_history_turns: int                 # 记忆窗口大小
    
    + __init__(max_history_turns=1)
    + chat(question: str) -> str             # 主对话入口
    - _prune_memory()                        # 记忆修剪（过滤 tool_calls 残余）
```

#### 核心工作流（基于 LLM Function Calling）

```python
def chat(self, question: str) -> str:
    # 1. 首轮：注入 system prompt
    if not self.memory:
        self.memory.append({"role": "system", "content": SYSTEM_PROMPT})
    
    # 2. 加入用户提问
    self.memory.append({"role": "user", "content": question})
    
    # 3. 循环（最多 5 次）：LLM 决策 → 工具执行 → 反馈
    for _ in range(5):
        response_obj = chat_completion(self.memory, tools=TOOLS_SCHEMA)
        resp_dict = response_obj.model_dump(exclude_unset=True)
        self.memory.append(resp_dict)
        
        tool_calls = resp_dict.get("tool_calls", None)
        if not tool_calls:
            # 无工具调用，直接返回最终回答
            final_resp = resp_dict.get("content", "...")
            self._prune_memory()
            return final_resp
        
        # 4. 遍历 tool_calls，解析 arguments（safe_json_loads），执行工具
        for tool_call in tool_calls:
            function_name = tool_call["function"]["name"]
            args = safe_json_loads(tool_call["function"]["arguments"])
            function_to_call = self.available_tools.get(function_name)
            function_resp = function_to_call(**args) if function_to_call else "未找到工具"
            
            # 5. 将 tool 结果追加到 memory（role: "tool"）
            self.memory.append({
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": str(function_resp)
            })
        # 继续循环，让 LLM 根据工具结果再决策
    
    return "Agent 思考超过最大迭代次数（5 次）已停止..."
```

### 2️⃣ LLM 接口层 (`src/agent/llm.py`)

#### 设计原则
- **单一职责**：只负责 LLM 通信，不处理业务逻辑
- **兼容性**：使用 OpenAI 标准接口，支持任何兼容 API
- **可观察性**：完整的请求/响应日志

```python
def chat_completion(
    messages: List[Dict],
    max_tokens: int = 800,
    temperature: float = 0.2,
    tools: Optional[List] = None
):
    """
    发送请求到 LLM（OpenAI 兼容接口，默认 DeepSeek）
    
    Args:
        messages: 对话历史（含 system/user/assistant/tool）
        tools: 工具定义（OpenAI Function Calling 格式）
    
    Returns:
        response.choices[0].message（含 content、tool_calls 等）
    """
    response = client.chat.completions.create(
        model=settings.model_name,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        tools=tools
    )
    return response.choices[0].message
```

#### 关键配置
```python
# 模型参数
model_name = "deepseek-chat"      # 生产环境可切换
temperature = 0.2                  # 低随机性（确定性强）
max_tokens = 800                   # 一般回复足够

# API 参数
base_url = "https://api.deepseek.com"
timeout = 30                       # 请求超时
```

### 3️⃣ 工具系统 (`src/agent/tools/`)

#### 工具架构

```
src/agent/tools/
  ├── tools_schemas.py      ← OpenAI Function Calling 格式 Schema
  ├── code_analyser.py      ← AST 静态分析
  ├── search_tool.py        ← RAG 代码检索
  ├── complete_code_llm.py  ← 代码补全
  ├── docker_file_llm.py    ← Dockerfile 生成
  ├── generate_tests_llm.py← 单元测试生成
  └── log_analyser_llm.py   ← 日志分析
```

#### 标准工具接口

```python
# 工具的通用签名模式
def tool_name(param1: str, param2: int = 10) -> str:
    """
    工具描述，会被发送给 LLM
    
    Args:
        param1: 参数说明
        param2: 参数说明（可选）
    
    Returns:
        执行结果（字符串形式）
    """
    try:
        # 具体实现
        result = ...
        return format_result(result)
    except Exception as e:
        return f"❌ 执行失败: {str(e)}"
```

#### 工具 Schema 示例（OpenAI Function Calling 格式）

```python
TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "search_codebase",
            "description": "在本地代码库中检索相关代码片段...",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "检索关键词/短句"},
                    "top_k": {"type": "integer", "description": "返回片段数量", "default": 6}
                },
                "required": ["query"]
            }
        }
    },
    # ... 其他 5 个工具 ...
]
```

> ⚠️ **注意**：Schema 中的 `function.name` 必须与 `available_tools` 中的键完全一致。

---

## RAG 系统详解

### 整体流程

```
用户输入
  ↓
Query Rewriter (可选的查询改写)
  ↓
┌─ 密集检索 (Dense Retrieval)
│   ├─ 嵌入模型: Text-Embedding-V4
│   ├─ 向量库: Chroma
│   └─ 返回: Top-K 向量相似结果
│
├─ 稀疏检索 (Sparse Retrieval)
│   ├─ 方法: BM25 (词频-逆文档频率)
│   ├─ 存储: Pickle 序列化
│   └─ 返回: Top-K 关键词匹配结果
│
→ 融合 (Fusion)
  ├─ 策略: RRF (Reciprocal Rank Fusion)
  └─ 返回: 融合后的 Top-K
│
→ 重排 (Re-ranking，可选)
  ├─ 模型: CrossEncoder
  ├─ 作用: 精排混合结果
  └─ 返回: 最终 Top-K
  
↓
向 LLM 注入为 Context
```

### 1️⃣ 向量存储 (`src/rag/vectorstore.py`)

#### 设计

```python
class VectorStore:
    """
    Chroma 向量数据库 + BM25 的封装，支持 Dense / Hybrid / 重排
    """
    
    def __init__(self, use_reranker: bool = False):
        # 嵌入模型：qwen（API）/ local（HuggingFace）
        if settings.embedding_provider == "qwen":
            self.embeddings = OpenAIEmbeddings(
                model=settings.qwen_embedding_name,
                openai_api_key=settings.qwen_api_key,
                openai_api_base=settings.qwen_base_url
            )
        else:
            self.embeddings = HuggingFaceEmbeddings(model=settings.local_embedding_name)
        
        self._db = None
        self.bm25_retriever = BM25Retiever()
        
    def index_document(self, all_chunks: List[Document]):
        """构建索引（scripts/build_knowledge_base.py 调用）"""
        self._db = Chroma.from_documents(
            documents=all_chunks,
            embedding=self.embeddings,
            persist_directory=settings.Chroma_persist_dir
        )
        self.bm25_retriever.index_document(all_chunks)
        
    def load(self):
        """加载已有索引（search_tool 单例调用）"""
        self._db = Chroma(
            embedding_function=self.embeddings,
            persist_directory=settings.Chroma_persist_dir
        )
        self.bm25_retriever.load()
```

#### 检索方法

```python
def search(self, query: str, top_k: int = 5) -> List[Document]:
    """
    混合检索：融合密集和稀疏结果
    
    Process:
    1. 密集检索 → Dense Top-K
    2. 稀疏检索 → BM25 Top-K
    3. RRF 融合 → 去重
    4. CrossEncoder 重排 → 最终 Top-K
    """
    # A. 密集检索
    dense_results = self.search_dense(query, top_k=2*top_k)
    
    # B. 稀疏检索
    bm25_results = self.bm25_retriever.search(query, top_k=2*top_k)
    
    # C. RRF 融合
    fused_results = self._rrf_fusion(dense_results, bm25_results)
    
    # D. 可选：CrossEncoder 重排
    if settings.enable_reranking:
        pairs = [(query, doc.page_content) for doc in fused_results]
        scores = reranker.predict(pairs)
        fused_results = sorted(
            zip(fused_results, scores),
            key=lambda x: x[1],
            reverse=True
        )
        fused_results = [doc for doc, _ in fused_results]
    
    return fused_results[:top_k]

def _rrf_fusion(self, dense: List[Document], sparse: List[Document]) -> List[Document]:
    """
    倒数排名融合 (Reciprocal Rank Fusion)
    
    公式: RRF(d) = Σ 1 / (k + rank(d))
    k: 常数（通常为 60）
    
    特点：
    - 同时出现在两个结果中的文档得分更高
    - 不同检索方法的排名加权融合
    """
    rrf_scores = {}
    k = 60
    
    # 密集检索贡献
    for rank, doc in enumerate(dense):
        doc_id = doc.metadata["source"]
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank + 1)
    
    # 稀疏检索贡献
    for rank, doc in enumerate(sparse):
        doc_id = doc.metadata["source"]
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0) + 1 / (k + rank + 1)
    
    # 排序并返回
    sorted_docs = sorted(
        set(dense + sparse),
        key=lambda d: rrf_scores.get(d.metadata["source"], 0),
        reverse=True
    )
    
    return sorted_docs
```

### 2️⃣ BM25 稀疏检索 (`src/rag/bm25.py`)

#### BM25 算法原理

```
BM25 得分 = IDF(q_i) * (f(q_i, D) * (k1 + 1)) / (f(q_i, D) + k1 * (1 - b + b * |D| / avgdl))

其中：
- q_i: 查询中的第 i 个词
- f(q_i, D): 词 q_i 在文档 D 中的频率
- |D|: 文档 D 的长度
- avgdl: 平均文档长度
- k1, b: 参数（通常 k1=2.0, b=0.75）
- IDF: 逆文档频率 = log((N - n(q_i) + 0.5) / (n(q_i) + 0.5))
```

#### 实现

```python
class BM25Retiever:
    def __init__(self):
        self.persist_path = Path(settings.bm25_persist_dir)
        self.docs = []
        self.bm25 = None  # BM25Okapi | None
        
    def index_document(self, docs: List[Document]):
        """构建 BM25 索引并持久化"""
        self.docs = docs
        corpus_tokens = [_tokenize(doc.page_content) for doc in docs]
        self.bm25 = BM25Okapi(corpus_tokens)
        with open(self.persist_path, "wb") as f:
            pickle.dump({"docs": self.docs, "bm25": self.bm25}, f)
    
    def load(self):
        """从磁盘加载（不存在则 raise RuntimeError）"""
        if not self.persist_path.exists():
            raise RuntimeError("bm25 索引未建库，请先运行 build_knowledge_base.py")
        with open(self.persist_path, "rb") as f:
            data = pickle.load(f)
            self.bm25 = data["bm25"]
            self.docs = data["docs"]
    
    def search(self, query: str, top_k: int = 5) -> List[Document]:
        """BM25 搜索"""
        query_tokens = _tokenize(query)
        scores = self.bm25.get_scores(query_tokens)
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]
        return [self.docs[i] for i in top_indices]

def _tokenize(text: str) -> List[str]:
    tokens = re.split(r"[^A-Za-z0-9_]+", text)
    return [t for t in tokens if t]
```

### 3️⃣ Query Rewriter (`src/rag/query_rewriter.py`)

#### 设计目标

改写用户的**口语化、模糊查询**为**信息密度高、精确的检索词组合**。

#### 改写策略

```
原始查询：
"妈妈，请帮我找一下切分文本的函数定义def，呜呜呜。。。。。"
  ↓ [降噪]
"找切分文本的函数定义def"
  ↓ [实体保留]
保留：切分、文本、函数、def
  ↓ [术语扩展]
添加：TextSplitter、Document、Chunk 等专业术语
  ↓ [改写后]
"切分文本 TextSplitter Document Chunk 函数定义 def"
```

#### 实现

```python
class Query_rewriter:
    def rewrite(self, raw_query: str) -> Query_rewrite_result:
        """
        使用 LLM 改写查询
        """
        system_prompt = """
        你是一个为代码 RAG 系统设计的 Query 改写专家。
        
        核心策略：
        1. 保留所有实体（文件名、函数名、类名）
        2. 扩展专业术语
        3. 降噪口语废话
        
        输出格式：
        {"dense_query": "改写后的查询"}
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"原始提问：{raw_query}"}
        ]
        
        response = chat_completion(messages)
        result = safe_json_loads(response)
        
        return Query_rewrite_result(
            raw_query=raw_query,
            dense_query=result.get("dense_query", raw_query)
        )
```

---

## Agent 决策引擎

### 工具路由决策流程（Function Calling）

```
LLM 返回 message（含 tool_calls）
  ↓
┌──────────────────────────────────┐
│ 解析 tool_calls                  │
│ - function["name"] → 工具名       │
│ - function["arguments"] → JSON 字符串 │
│ - safe_json_loads(arguments) → 参数字典 │
└──────────────────────────────────┘
  ↓
┌──────────────────────────────────┐
│ 工具名验证                       │
│ - 检查是否在 available_tools 中   │
│ - 处理无效工具（返回错误）        │
└──────────────────────────────────┘
  ↓
┌──────────────────────────────────┐
│ 参数验证                         │
│ - 类型检查                       │
│ - 范围检查                       │
└──────────────────────────────────┘
  ↓
┌──────────────────────────────────┐
│ 工具执行                         │
│ - try/catch 错误处理              │
│ - 结果格式化                     │
└──────────────────────────────────┘
  ↓
反馈给 LLM 进行总结
```

### JSON 解析的鲁棒性处理

```python
def safe_json_loads(s: str) -> dict:
    """
    鲁棒的 JSON 解析，处理常见格式错误
    """
    if not isinstance(s, str):
        return {}
    
    s = s.strip()
    
    # 移除 ```json``` 标记
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    
    # 提取 { ... } 内容
    l = s.find("{")
    r = s.rfind("}")
    if l != -1 and r != -1 and r > l:
        s = s[l:r+1]
    
    try:
        return json.loads(s)
    except Exception as e:
        print(f"⚠️ JSON 解析失败: {e}")
        return {}
```

---

## 数据流与状态管理

### 单轮对话的完整数据流

```
输入: query (用户问题)
  ↓
[1] Query Preprocessing
    - 检查长度
    - 清理特殊字符
  ↓
[2] Context Assembly
    - 从 self.memory 构建对话历史
    - 按 token 限制截断
    - 添加 TOOLS_SCHEMA
  ↓
[3] LLM Call - Tool Selection（循环内）
    LLM 输入:
    - 系统提示词 + 对话历史 + 工具定义 (TOOLS_SCHEMA)
    ↓
    LLM 输出 (message):
    - tool_calls: [{function: {name, arguments}, id}, ...]
    或
    - content: 最终回答（无工具调用时）
  ↓
[4] Tool Execution (if tool_calls)
    - safe_json_loads(arguments) 解析参数
    - available_tools.get(name) 获取工具
    - 执行并追加 role: "tool" 到 memory
  ↓
[5] 继续循环 或 返回
    - 有 tool_calls → 继续下一轮 LLM 调用
    - 无 tool_calls → 提取 content，_prune_memory()，返回
  ↓
[6] Memory Update
    - 添加用户输入到 memory
    - 添加助手回答到 memory
    - 裁剪超长 memory
  ↓
输出: response (最终回答)
```

### 状态管理关键点

```python
class DevAgent:
    def __init__(self):
        self.memory = []              # 对话历史
        self.available_tools = {...}  # 工具映射
        
    def chat(self, query):
        # 状态转移 1: 记录用户输入
        self.memory.append({"role": "user", "content": query})
        
        # 状态转移 2: 获取工具结果（可能无）
        tool_result = ...
        
        # 状态转移 3: 记录 LLM 响应
        self.memory.append({"role": "assistant", "content": response})
        
        # 状态转移 4: 清理过期数据
        if len(self.memory) > MAX_MEMORY:
            self.memory = self.memory[-MAX_MEMORY:]
```

---

## 性能优化策略

### 1️⃣ 向量库预热（核心优化，效果显著）

在 `DevAgent.__init__` 中**提前触发**向量库单例加载，将 Chroma + BM25 的磁盘读取成本前置到 Agent 创建时，避免首次 `search_codebase` 调用时才加载导致的明显延迟。

```python
# src/agent/core.py

class DevAgent:
    def __init__(self, max_history_turns=1):
        self.available_tools = {...}
        self.memory = []
        self.max_history_turns = max_history_turns

        # 🔥 预热数据库：提前触发单例加载
        from src.agent.tools.search_tool import _get_vector_store
        _get_vector_store()  # 首次调用时加载 Chroma + BM25，后续复用
```

**效果对比**（实测）：

| 场景 | 首次 search_codebase 耗时 | 说明 |
|------|---------------------------|------|
| **无预热** | 首次调用时需加载 + 检索，延迟叠加 | 用户首轮对话体验差 |
| **有预热** | 加载在 Agent 创建时完成，检索时直接命中内存 | 首轮对话时向量库已就绪 |

日志输出示例：

**无预热**：先出系统提示词(模型初次被调用)，才加载向量库

加载系统提示词
Agent综合分析中
Agent决策：决定调用工具：search_codebase
[System] 首次加载向量库...
成功从路径./data/Chroma中读取Chroma向量数据库
成功从硬盘持久路径读取到bm25索引引擎！
成功从路径data\bm25_index.pkl中读取bm25向量数据库

⏱️ [耗时监控] 函数 'search_codebase' 执行完毕 | 耗时: 7.452 秒


**有预热**：在被调用前加载向量库
```
[System] 首次加载向量库...
成功从路径./data/Chroma中读取Chroma向量数据库
成功从硬盘持久路径读取到bm25索引引擎！
加载系统提示词
Agent综合分析中

Agent决策：决定调用工具：search_codebase
⏱️ [耗时监控] 函数 'search_codebase' 执行完毕 | 耗时: 3.365 秒
```

### 2️⃣ 向量库单例模式

```python
# src/agent/tools/search_tool.py

_vector_store: Optional[VectorStore] = None

def _get_vector_store() -> VectorStore:
    """
    全局单例，避免重复加载向量库
    优势：
    - 首次初始化一次，后续复用
    - 减少磁盘 I/O
    - 首次调用：加载 Chroma + BM25 到内存
    - 后续调用：直接返回已加载实例
    """
    global _vector_store
    if _vector_store is None:
        print("[System] 首次加载向量库...")
        _vector_store = VectorStore()
        _vector_store.load()
    return _vector_store
```

### 3️⃣ 耗时监控（time_logger）

`search_codebase`、`chat` 等关键函数使用 `@time_logger` 装饰器，自动打印执行耗时，便于定位性能瓶颈：

```python
# 输出示例
⏱️ [耗时监控] 函数 'search_codebase' 执行完毕 | 耗时: 3.365 秒
⏱️ [耗时监控] 函数 'chat' 执行完毕 | 耗时: 42.761 秒
```

### 4️⃣ 网络请求优化

```python
# src/agent/llm.py - 使用 OpenAI 官方 SDK（内置连接池和重试）
client = OpenAI(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url
)

# 参数调优
temperature=0.2   # 低随机性 → 快速收敛
max_tokens=800    # 适度长度 → 平衡质量和速度
```

### 5️⃣ 检索策略

- **Dense-only**：在评估集上 Hit@8=100%、MRR≈0.94，是当前主力检索引擎（见 [README#性能基准](./README.md#-性能基准)）
- **RRF 融合**：Hybrid 模式下 Dense + BM25 采用 Reciprocal Rank Fusion
- **可选重排**：CrossEncoder / Qwen gte-rank-v2 精排

### 6️⃣ 文本处理优化

```python
# src/rag/splitter.py - 使用 LangChain 工业级分割器
self.py_splitter = RecursiveCharacterTextSplitter.from_language(
    language=Language.PYTHON,
    chunk_size=2000,
    chunk_overlap=350
)
```

---

## 扩展与定制

### 1️⃣ 添加新工具

#### 步骤 1: 实现工具函数

```python
# src/agent/tools/my_new_tool.py

from src.agent.core import chat_completion

def analyze_requirements(repo_structure: str) -> str:
    """
    分析项目需求和依赖关系
    """
    SYSTEM_PROMPT = """
    你是一个项目需求分析专家...
    """
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"项目结构：\n{repo_structure}"}
    ]
    
    return chat_completion(messages, max_tokens=1000)
```

#### 步骤 2: 注册到 Agent

```python
# src/agent/core.py
from src.agent.tools.my_new_tool import analyze_requirements

class DevAgent:
    def __init__(self):
        self.available_tools = {
            "analyse_code": analyse_code,
            "search_codebase": search_codebase,
            "complete_code": code_completion,
            "generate_docker_file": gen_docker_file,
            "generate_test": gen_tests,
            "analyse_log": analyse_log,
            "analyze_requirements": analyze_requirements,  # 新工具
        }
```

#### 步骤 3: 添加 Schema 定义

```python
# src/agent/tools/tools_schemas.py

TOOLS_SCHEMA.append({
    "type": "function",
    "function": {
        "name": "analyze_requirements",  # 必须与 available_tools 键一致
        "description": "分析项目的需求和依赖关系",
        "parameters": {
            "type": "object",
            "properties": {
                "repo_structure": {"type": "string", "description": "项目目录结构或源代码"}
            },
            "required": ["repo_structure"]
        }
    }
})
```

### 2️⃣ 更换 LLM

```python
# src/agent/llm.py

# 方案 A：更换 OpenAI 兼容的 base_url（如 Qwen、Claude 等）
# 修改 .env 或 src/config.py
deepseek_base_url = "https://api.openai.com"  # 或其他兼容端点
model_name = "gpt-4"

# 方案 B：使用其他 SDK（如 Anthropic）
# 需适配返回格式，确保 tool_calls 结构兼容
```

### 3️⃣ 支持更多编程语言

```python
# src/rag/splitter.py

class CodeSplitter:
    def __init__(self):
        # Python
        self.py_splitter = RecursiveCharacterTextSplitter.from_language(
            Language.PYTHON, chunk_size=2000, chunk_overlap=350
        )
        # Java
        self.java_splitter = RecursiveCharacterTextSplitter.from_language(
            Language.JAVA, chunk_size=2000, chunk_overlap=350
        )
        # Go
        self.go_splitter = RecursiveCharacterTextSplitter.from_language(
            Language.GO, chunk_size=2000, chunk_overlap=350
        )
        # ... 等等
```

---

## 部署与运维

### Docker 部署

```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# 构建向量库
RUN python scripts/build_knowledge_base.py

# 启动 API（需在项目根目录，或设置 PYTHONPATH）
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 监控与日志

```python
# 时间追踪装饰器
@time_logger
def search_codebase(query: str, top_k: int = 6) -> str:
    """
    自动记录执行时间：
    ⏱️ [耗时监控] 函数 'search_codebase' 执行完毕 | 耗时: 0.234 秒
    """
    ...
```

---

## 参考资源

- **RAG 论文**: [Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks](https://arxiv.org/abs/2005.11401)
- **LoRA 论文**: [LoRA: Low-Rank Adaptation](https://arxiv.org/abs/2106.09685)
- **BM25**: [Okapi BM25](https://en.wikipedia.org/wiki/Okapi_BM25)
- **RRF**: [Reciprocal Rank Fusion](https://citeseerx.ist.psu.edu/viewdoc/summary?doi=10.1.1.36.8814)

---

---

**文档最后更新**: 2026年3月
