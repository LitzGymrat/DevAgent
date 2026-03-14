#代码切分器：调用langchain工业级解决方案
from typing import List
#要用到langchain数据封装类
from langchain_core.documents import Document
from langchain_text_splitters import Language,RecursiveCharacterTextSplitter



class CodeSplitter:     #指定默认值
    def __init__(self,code_chunk_size:int = 2000,code_chunk_overlap:int = 350, #修改之后要重新建库
                 text_chunk_size:int = 1500,text_chunk_overlap:int = 350,):
        
#1.初始化，构建专门的py代码分割。和一般的text分割           #指定from_language
        self.py_splitter = RecursiveCharacterTextSplitter.from_language(
            #2.规定超参数，进行分割
        language = Language.PYTHON,
        chunk_overlap = code_chunk_overlap,
        chunk_size = code_chunk_size


    )
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_overlap = text_chunk_overlap,
            chunk_size = text_chunk_size
        )
        
    #3.构建最后的列表，分割的结果一一放进去
    #分割函数：接受文档列表，返回切分好块的列表
    #docs : List[Document] docs是传入的数据，List[Document]注明类型
    def split(self,docs : List[Document])->List[Document]:
        all_chunks = []
        for doc in docs:
            suffix = doc.metadata.get("suffix","")  #使用.get查询字典值：比较温和，否则如果查不到就会报错
            if suffix == ".py":
                            #py_splitter是对象：not callable不可调用，需要调用方法
                chunk = self.py_splitter.split_documents([doc])   #切分引擎接受列表
            else:
                chunk = self.text_splitter.split_documents([doc])
            #最后填入最终列表：.append()和.extend()的差别：前者整块放入，后者先解包再放入
            all_chunks.extend(chunk)

        return all_chunks




