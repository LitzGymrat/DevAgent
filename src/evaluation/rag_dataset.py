# src/evaluation/eval_dataset.py
"""
检索评估数据集

每条数据包含：
  - query: 用户问题
  - expected_files: 期望检索到的文件（可能多个）
  - query_type: 查询类型（用于分类统计）
"""

EVAL_QUERIES = [
    # === 精确关键词查询（BM25 应该强）===
    {
        "query": "def index_document",
        "expected_files": ["rag/vectorstore.py", "rag/bm25.py"],
        "query_type": "exact_keyword"
    },
    {
        "query": "def search",
        "expected_files": ["rag/vectorstore.py", "rag/bm25.py"],
        "query_type": "exact_keyword"
    },
    {
        "query": "class VectorStore",
        "expected_files": ["rag/vectorstore.py"],
        "query_type": "exact_keyword"
    },
    {
        "query": "class BM25Retiever",
        "expected_files": ["rag/bm25.py"],
        "query_type": "exact_keyword"
    },
    {
        "query": "def load",
        "expected_files": ["rag/vectorstore.py", "rag/bm25.py", "rag/loader.py"],
        "query_type": "exact_keyword"
    },
    
    # === 中文语义查询（Dense 应该强）===
    {
        "query": "如何建立向量数据库",
        "expected_files": ["rag/vectorstore.py"],
        "query_type": "chinese_semantic"
    },
    {
        "query": "怎么加载代码文件",
        "expected_files": ["rag/loader.py"],
        "query_type": "chinese_semantic"
    },
    {
        "query": "代码切分是怎么实现的",
        "expected_files": ["rag/splitter.py"],
        "query_type": "chinese_semantic"
    },
    {
        "query": "如何调用大模型",
        "expected_files": ["agent/llm.py"],
        "query_type": "chinese_semantic"
    },
    {
        "query": "混合检索怎么做的",
        "expected_files": ["rag/vectorstore.py"],
        "query_type": "chinese_semantic"
    },
    
    # === 英文语义查询 ===
    {
        "query": "how to call LLM API",
        "expected_files": ["agent/llm.py"],
        "query_type": "english_semantic"
    },
    {
        "query": "embedding model initialization",
        "expected_files": ["rag/vectorstore.py"],
        "query_type": "english_semantic"
    },
    {
        "query": "code splitting strategy",
        "expected_files": ["rag/splitter.py"],
        "query_type": "english_semantic"
    },
    
    # === 中英混合查询 ===
    {
        "query": "BM25检索实现",
        "expected_files": ["rag/bm25.py"],
        "query_type": "mixed"
    },
    {
        "query": "Chroma数据库怎么用",
        "expected_files": ["rag/vectorstore.py"],
        "query_type": "mixed"
    },
    {
        "query": "RRF融合算法",
        "expected_files": ["rag/vectorstore.py"],
        "query_type": "mixed"
    },
    {
        "query": "FastAPI路由定义",
        "expected_files": ["api/routes.py"],
        "query_type": "mixed"
    },
    {
        "query": "Agent核心逻辑",
        "expected_files": ["agent/core.py"],
        "query_type": "mixed"
    },
]