# src/agent/tools/search_tool.py
import json
from typing import Optional

import time
from functools import wraps

from src.rag.vectorstore import VectorStore
from src.rag.query_rewriter import Query_rewriter
from src.config import settings

_vector_store: Optional[VectorStore] = None
_rewriter: Optional[Query_rewriter] = None

def time_logger(func):
    """
    极简且强大的耗时统计装饰器
    """
    @wraps(func) # 保持原函数的元信息（名字、注释等）不变
    def wrapper(*args, **kwargs):
        # 👑 核心细节：用 perf_counter 而不是 time()！
        # perf_counter 是专门为了测算极短时间间隔设计的，精度极高，且不受系统时钟回拨影响。
        start_time = time.perf_counter() 
        
        # 执行原本的函数逻辑（无论是工具调用还是聊天主循环）
        result = func(*args, **kwargs) 
        
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        
        # 打印极其炫酷的耗时日志（可以后续存入文件或数据库）
        print(f"\n⏱️ [耗时监控] 函数 '{func.__name__}' 执行完毕 | 耗时: {elapsed_time:.3f} 秒\n")
        
        return result
    return wrapper

def _get_vector_store() -> VectorStore:
    global _vector_store
    if _vector_store is None:
        print("[System] 首次加载向量库...")
        _vector_store = VectorStore()
        _vector_store.load()
    return _vector_store


def _get_rewriter() -> Query_rewriter:
    global _rewriter
    if _rewriter is None:
        print("[System] 首次加载 Query Rewriter...")
        _rewriter = Query_rewriter()
    return _rewriter

@time_logger
def search_codebase(query: str, top_k: int = 6) -> str:
    """
    Tool: 在本地代码库检索，返回 JSON 字符串：
    [
      {"source": "...", "content": "..."},
      ...
    ]
    """
    vs = _get_vector_store()

    clean_query = query
    if getattr(settings, "enable_query_rewrite_in_tool", False):
        try:
            rewriter = _get_rewriter()
            clean_query = rewriter.rewrite(query).dense_query or query
            print(f"[Rewrite] '{query}' -> '{clean_query}'")
        except Exception as e:
            print(f"[Rewrite Failed] fallback. err={e}")
            clean_query = query

    docs = vs.search_dense(clean_query, top_k=top_k)

    results = []
    for d in docs:
        results.append({
            "source": str(d.metadata.get("source", "")),
            # 截断，防止 tool 输出过长
            "content": d.page_content[:900],
        })

    return json.dumps(
        {"query": query, "rewritten_query": clean_query, "results": results},
        ensure_ascii=False
    )