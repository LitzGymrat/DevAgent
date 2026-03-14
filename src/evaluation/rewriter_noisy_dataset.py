# src/evaluation/noisy_eval_dataset.py
"""
极其口语化的“脏数据”评估集，专门用来测试 Query Rewriter 的抗压能力！
"""

NOISY_EVAL_QUERIES = [
    # === 精确关键词查询（加上各种无意义的废话和主观情绪）===
    {
        "query": "那个叫啥 index_document 的函数具体在哪儿定义的来着？",
        "expected_files": ["rag/vectorstore.py", "rag/bm25.py"],
        "query_type": "exact_keyword"
    },
    {
        "query": "兄弟帮我找一下搜索代码 search 那个 def，急用",
        "expected_files": ["rag/vectorstore.py", "rag/bm25.py"],
        "query_type": "exact_keyword"
    },
    {
        "query": "咱存数据的那个大管家 class VectorStore 写在哪个文件里了？",
        "expected_files": ["rag/vectorstore.py"],
        "query_type": "exact_keyword"
    },
    {
        "query": "理科生那个类！就那个 class BM25Retiever 是怎么写的？",
        "expected_files": ["rag/bm25.py"],
        "query_type": "exact_keyword"
    },
    {
        "query": "启动的时候加载数据的那个 def load 放哪了，找半天没看到",
        "expected_files": ["rag/vectorstore.py", "rag/bm25.py", "rag/loader.py"],
        "query_type": "exact_keyword"
    },
    
    # === 中文语义查询（极其模糊的口语表达）===
    {
        "query": "咱这个项目到底是怎么把 Chroma 向量数据库给搞起来的啊？",
        "expected_files": ["rag/vectorstore.py"],
        "query_type": "chinese_semantic"
    },
    {
        "query": "怎么把本地硬盘上的那些 py 代码文件给读进来的？",
        "expected_files": ["rag/loader.py"],
        "query_type": "chinese_semantic"
    },
    {
        "query": "那个...负责把代码切成一小块一小块的功能是在哪实现的？",
        "expected_files": ["rag/splitter.py"],
        "query_type": "chinese_semantic"
    },
    {
        "query": "和外部的 DeepSeek 大模型对话的接口代码在哪里？",
        "expected_files": ["agent/llm.py"],
        "query_type": "chinese_semantic"
    },
    {
        "query": "咱们那个又用向量又用字面量的混合检索是怎么写出来的？",
        "expected_files": ["rag/vectorstore.py"],
        "query_type": "chinese_semantic"
    },
    
    # === 英文语义查询（带点 Chinglish 和情绪）===
    {
        "query": "how do we actually call the damn LLM API in our code??",
        "expected_files": ["agent/llm.py"],
        "query_type": "english_semantic"
    },
    {
        "query": "where is the embedding model initialization part?",
        "expected_files": ["rag/vectorstore.py"],
        "query_type": "english_semantic"
    },
    {
        "query": "I need to check our code splitting strategy, which file?",
        "expected_files": ["rag/splitter.py"],
        "query_type": "english_semantic"
    },
    
    # === 中英混合查询（真实的程序员日常提问）===
    {
        "query": "我想看看咱们那个 BM25 稀疏检索的具体实现，是在哪个模块？",
        "expected_files": ["rag/bm25.py"],
        "query_type": "mixed"
    },
    {
        "query": "那个啥，Chroma数据库怎么用代码去实例化的？",
        "expected_files": ["rag/vectorstore.py"],
        "query_type": "mixed"
    },
    {
        "query": "算分数的那个 RRF 融合算法逻辑在哪儿？",
        "expected_files": ["rag/vectorstore.py"],
        "query_type": "mixed"
    },
    {
        "query": "给前端提供接口的 FastAPI 路由定义在哪看？",
        "expected_files": ["api/routes.py"],
        "query_type": "mixed"
    },
    {
        "query": "大脑总控！就是那个 Agent 核心的对话逻辑在哪个文件？",
        "expected_files": ["agent/core.py"],
        "query_type": "mixed"
    },
]