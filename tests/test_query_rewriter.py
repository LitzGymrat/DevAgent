#测试提示词改写
from src.rag.query_rewriter import Query_rewriter
from src.rag.vectorstore import VectorStore

if __name__ == "__main__":
    
    rewriter = Query_rewriter()
    raw_query = "妈妈，请帮我找一找一下切分文本的函数定义def，呜呜呜。。。。。"
    rewrite_result = rewriter.rewrite(raw_query).dense_query #提出来！结果包含原来的和改写后的
    db = VectorStore()
    db.load()
    #得到搜索结果
    search_res_docs = db.search_dense(rewrite_result.dense_query)
    for doc in search_res_docs:
        print("搜索结果来源：",doc.metadata["source"],"\n")
        print("搜索结果内容：",doc.page_content,"\n")
