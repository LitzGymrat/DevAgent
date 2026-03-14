#测试bm25数据库
from src.rag.bm25 import BM25Retiever
from src.rag.loader import RePoLoader
from src.rag.splitter import CodeSplitter
if __name__ == "__main__":
    loader = RePoLoader("src") #只读src目录，滤掉测试脚本:精细化匹配容易受到脏语料影响
    docs = loader.load()
    splitter  = CodeSplitter()

    all_chunks = splitter.split(docs)
    bm25 = BM25Retiever()
    #索引标注，只运行一次！

    #试试用切分后颗粒度更细的块，而非整个文档？
    #bm25.index_document(all_chunks)
    bm25.load()

    query = "请找到vectorstore.py中def index_document的定义"
    print(f"======================当前提问为：{query}=================================\n")
    res = bm25.search(query)
    i = 0
    for d in res:
        print(f"===============第{i+1}个片段===================\n从来源{d.metadata["source"]}查找到的文本内容为:{d.page_content}\n")
        i+=1