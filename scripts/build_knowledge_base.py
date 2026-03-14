#建库

from src.rag.splitter import CodeSplitter
from src.rag.loader import RePoLoader
from src.rag.vectorstore import VectorStore

if __name__ == "__main__":
    
    try:
        address = "src"
        loader = RePoLoader(address)#src目录
        print(f"正在从{address}建立本地知识库\n")
        
        docs = loader.load()
        splitter  = CodeSplitter()

        all_chunks = splitter.split(docs)

    

        db = VectorStore()
        #切分好的词块给向量数据库导入
        db.index_document(all_chunks)
        print(f"本地知识库建立完成！\n")
    except Exception as e:
        print(f"本地知识库建立失败...\n错误信息：{e}")
    



