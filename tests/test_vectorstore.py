#测试向量数据库

from src.rag.splitter import CodeSplitter
from src.rag.loader import RePoLoader
from src.rag.vectorstore import VectorStore

if __name__ == "__main__":
    loader = RePoLoader("src")
    docs = loader.load()
    splitter  = CodeSplitter()

    all_chunks = splitter.split(docs)
    #
    query = "如何调用大模型API"

    db = VectorStore()
    #切分好的词块给向量数据库导入
    db.index_document(all_chunks)
    #得到搜索结果
    search_res_docs = db.search(query)
    for doc in search_res_docs:
        print("搜索结果来源：",doc.metadata["source"],"\n")
        print("搜索结果内容：",doc.page_content,"\n")



