from src.rag.loader import RePoLoader

if __name__ == "__main__":
    loader = RePoLoader(".")#当前目录
    docs = loader.load()
    print("调试")
    print("文件个数：",len(docs))
    #查看前5个文件情况
    for d in docs[:5]:
        print("来源:       ",d.metadata["source"])
        print("文件名称：     ",d.metadata["file_name"]) #键是字符串，需要带引号！
        print("文件类型：     ",d.metadata["suffix"])
        print("内容前100个词：         ",d.page_content[:100])
