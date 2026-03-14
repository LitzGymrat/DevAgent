from src.rag.splitter import CodeSplitter
from src.rag.loader import RePoLoader

if __name__ == "__main__":
    loader = RePoLoader("src")#只读src目录，滤掉测试脚本
    docs = loader.load()
    splitter  = CodeSplitter()

    all_chunks = splitter.split(docs)
    print("打印切分结果:     ",all_chunks[:100])


