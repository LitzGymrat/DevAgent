#测试混合检索
from src.rag.splitter import CodeSplitter
from src.rag.loader import RePoLoader
from src.rag.vectorstore import VectorStore

if __name__ == "__main__":
    loader = RePoLoader("src")#主目录
    docs = loader.load()
    splitter  = CodeSplitter()

    all_chunks = splitter.split(docs)
    
    hybrid = VectorStore()

    #建库（只进行一次）
    hybrid.index_document(all_chunks)

    hybrid.load()

    query = "请找到vectorstore.py中def index_document的定义"
    print(f"======================当前提问为：{query}=================================\n")
    res = hybrid.search(query)
    i = 0
    for d in res:
        print(f"===============第{i+1}个片段===================\ns从来源{d.metadata["source"]}查找到的文本内容为:{d.page_content}\n")
        i+=1