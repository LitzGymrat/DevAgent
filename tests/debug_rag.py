#RAG排查：把搜索到的切分片段拉出来看看
from src.rag.vectorstore import VectorStore

if __name__ == "__main__":
    query = "请根据vectorstore.py相关代码片段告诉我def index_document是怎么定义的"
    print(f"搜索：{query}")
    print(f"="*50)

    db = VectorStore()
    
    db.load()

    res = db.search(query,top_k = 10)

    for i,doc in enumerate(res):
        print(f"第{i+1}个参考片段：\n")
        print(f"="*50)
        print(f"{doc.page_content}\n")
        print(f"="*50)