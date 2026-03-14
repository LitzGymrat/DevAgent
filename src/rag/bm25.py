from __future__ import annotations #必须在最前面
#bm25稀疏向量库
#  词袋模型：正则表达式过滤，处理代码精细搜索

import pickle #序列存储和读写

from typing import List
from pathlib import Path

import re   #正则表达式和模式匹配

from rank_bm25 import BM25Okapi
from langchain_core.documents import Document
from src.config import settings


#1.暴力分词器：利用正则表达式去掉非字母数字下划线
#私有内部辅助函数，私有变量：标注_
def _tokenize(text : str)->List[str]:
    tokens = re.split(r"[^A-Za-z0-9_]+",text) #r:表示原生字符串，不需要转义；+表示一个或多个字符；^表示取反，把非那些的切掉

    #返回切好的字符串列表(去空)，工整
    return [t for t in tokens if t]

class BM25Retiever:
    """基于BM25的稀疏检索器
    带文件存储和读写，search功能"""
    def __init__(self):
                    #把配置里面的str地址转成Path地址方便处理
                    #chorma可以直接接受字符串去处理，但是自己搭建的bm25需要转成Path类方便遍历
        self.persist_path = Path(settings.bm25_persist_dir)
        self.docs : List[Document] = []
        #可能是None或者BM250kapi类
        self.bm25 : BM25Okapi | None = None



#2.写库存储:传入文件列表
    def index_document(self,docs:List[Document]):
        self.docs = docs
        print("正在计算bm25稀疏词频矩阵")
        #先把数据切分好 :列表表示式
        corpus_tokens = [_tokenize(doc.page_content) for doc in docs]
        #然后给bm25
        #计算稀疏索引矩阵
        self.bm25 = BM25Okapi(corpus_tokens)

        #在上一层目录创建相应文件夹
        self.persist_path.parent.mkdir(parents=True,exist_ok=True) #parents = True:上一层文件夹都建立好，exist_ok:如果存在就静默
        with open(self.persist_path,"wb") as f:  #"wb"：写入二进制模式
            #存入文本和稀疏索引（这里不如chorma智能，需要手动传入字典）
            pickle.dump({"docs" : self.docs,"bm25": self.bm25},f)
        print(f"稀疏索引已持久化保存至{self.persist_path}")

#3.load加载数据库
    def load(self):
        #先看路径在不在
        if not self.persist_path.exists():

            #工程：使用raise RuntimeError报错终止！
            raise RuntimeError(f"bm25索引未建库！\n请先建库于{self.persist_path}")
        
        
        
        
        
        with open(self.persist_path,"rb") as f:#读取二进制模式
            #使用pikcle存储的序列需要先用pickle.load读取
            data = pickle.load(f)
            self.bm25 = data["bm25"]
            self.docs = data["docs"]
        print("成功从硬盘持久路径读取到bm25索引引擎！")




#4.search根据索引查找 传入查询和top_k
    def search(self,query:str,top_k = 5)->List[Document]:
        #先看bm25数据库有没有初始化
        if self.bm25 is None:
            raise RuntimeError(f"bm25数据库未初始化！\n请先调用index_document或者load函数")

        #将query也暴力切分
        query = _tokenize(query)
        #计算和bm25中各个文档的匹配分数
        scores = self.bm25.get_scores(query)

        
        #进行排序，计算排序后的序号
        #1.传入需要排序的对象
            #按照文件的序号
        sorted_indices = sorted(
            
            range(len(self.docs)),
            
            key = lambda i : scores[i],#2.传入比较的依据，一般用匿名函数去做映射，和索引序号相对应
            reverse=True #要降序排列，默认升序

        )[:top_k]
        #按照新的序号顺序返回文档列表
        return [self.docs[i] for i in sorted_indices]