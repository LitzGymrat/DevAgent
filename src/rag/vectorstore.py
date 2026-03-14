#载入权威开源向量数据库模型pip install langchain-huggingface sentence-transformers


#阿里云SDK
import dashscope
from http import HTTPStatus
from typing import List,Dict
from langchain_core.documents import Document
from langchain_chroma import Chroma       #载入向量数据库:用于存储调用高维语义向量
#线上模型
from langchain_openai import OpenAIEmbeddings        #Embeddings词嵌入模型，转为高维向量

#线下模型                huggingface本地引擎
from langchain_huggingface import HuggingFaceEmbeddings   #Embeddings词嵌入模型，转为高维向量

#模型调用的配置文件
from src.config import settings
from src.rag.bm25 import BM25Retiever

from sentence_transformers import CrossEncoder #引入精排模型

class VectorStore:
    """
    使用chroma构建向量数据库引擎
    """
    #1.初始化，策略模型选择，构建好embedding模型，构建self._db = None


    #2.写入库：传入切分好的词块列表，需要的持久地址，嵌入模型传入Chroma.from_documents()自动建库


    #3.读库，服务器重启，直接.load()从原来的持久地址读取到self._db
    #建立向量数据库
    #也要指定embedding，因为要基于向量数据库把用户提问转化为向量


    #4.接受疑问和搜索

    #需要排错一下None的情况
    #接受疑问，设定top_K，会自动计算余弦相似度返回需要的值列表
                        #热插拔的rerank:默认为纯Dense.
    def __init__(self,use_reranker:bool = False):
        """混合检索算法"""
        #持久化地址
        self.persist_dir = settings.chorma_persist_dir
        if settings.embedding_provider == "local":
            self.embeddings = HuggingFaceEmbeddings(
                #本地模型传入模型名即可
                model = settings.local_embedding_name
            )
        elif settings.embedding_provider == "qwen":
            self.embeddings = OpenAIEmbeddings(
                #区分聊天模型model_name  和embedding模型
                model = settings.qwen_embedding_name,
                #先把框架搭出来：可扩展性。 
                #没打都好导致的自动补全问题。。。
                openai_api_key = settings.qwen_api_key,
                openai_api_base = settings.qwen_base_url, 
                check_embedding_ctx_length=False,
                tiktoken_enabled=False,
                chunk_size=10,
                
            )
        else:
            self.embeddings = OpenAIEmbeddings(
                #区分聊天模型model_name  和embedding模型
                model = settings.embedding_model,
                #先把框架搭出来：可扩展性。 
                #没打都好导致的自动补全问题。。。
                openai_api_key = settings.deepseek_api_key,
                openai_api_base = settings.deepseek_base_url, 
                
            )
            #加下划线：关键私有变量：人为协定
        self._db = None
        #bm25实例
        self.bm25_retriever = BM25Retiever()


        #独立初始化reranker模型
        self.use_reranker = use_reranker
        self.reranker = None

        self.reranker_name = ""

        if self.use_reranker:
            if settings.reranking_provider == "local":
                try:
                    self.reranker = CrossEncoder('BAAI/bge-reranker-base')
                    self.reranker_name = "BAAI/bge-reranker-base"
                    print(f"本地reranker模型加载成功\n")
                except Exception as e:
                    print(f"本地reranker模型加载失败:{e}，降级为普通检索\n")
                    self.use_reranker = False
            #qwen rerank
            elif settings.reranking_provider == "qwen":
                #挂载云端api
                dashscope.api_key=settings.qwen_api_key
                self.reranker_name = "gte-rerank-v2"
                if not dashscope.api_key:
                    #未检测到qwen api_key，降级为普通检索
                    print("未检测到qwen api_key，降级为普通检索")
                    self.use_reranker = False
                else:
                    print("挂载云端qwen api成功")

    
    def index_document(self,all_chunks : List[Document]) -> None:

        #构建向量数据库 .from_documents读库
        self._db = Chroma.from_documents(
            embedding=self.embeddings,
            persist_directory=self.persist_dir,
            documents=all_chunks,
        )
        #完成之后打印调试信息
        print(f"DenseChroma建库成功将{len(all_chunks)}个代码块转化为了向量,存储到路径{self.persist_dir}")

        #bm25建库
        self.bm25_retriever.index_document(all_chunks)
        print(f"bm25建库成功！储存到路径{settings.bm25_persist_dir}!")

    #从硬盘中读取数据库，不是返回，就是重新根据已有数据再建一个Chroma数据库实例
    def load(self)->None:

        #使用raise处理错误：立刻终止运行，爆出错误情况
        #return就返回一个值，不易排错
        #必须使用is None判断：安全性。比较物理地址
        # 不需要判断数据库是否为空

        #因为在core中实例化的就是空的，但是是从原来setting中设定的恒久路径读取数据库，就只需要初始化一次！
        # if self._db is None:
        #     raise RuntimeError("向量数据库未初始化，读取失败")


        
        self._db = Chroma(
            #不再是embedding了，而是embeddingfunction，作用于查询
            embedding_function=self.embeddings,
            persist_directory=self.persist_dir,
            )
        print(f"成功从路径{self.persist_dir}中读取Chroma向量数据库")
        
        self.bm25_retriever.load()
        print(f"成功从路径{self.bm25_retriever.persist_path}中读取bm25向量数据库")










    
    #将用户提问转为向量，找到库中最接近的k个代码块。返回List[Document]
    def search(self,query:str,top_k = 4)->List[Document]:
        #看向量数据库有没有
        if self._db is None:
            raise RuntimeError("chroma向量数据库未初始化，查询失败")
        if self.bm25_retriever is None:
            raise RuntimeError("bm25向量数据库未初始化，查询失败")


        #1.分别搜索得到前10个，大池子
        #相似度查询！
        chroma_results = self._db.similarity_search(query,k=10)#此处为k而非top_k
        bm25_results = self.bm25_retriever.search(query,top_k=10)

        #2.构建计分板，以content字符串为键(ID)doc_map : Dict[str:Document]={} rrf_scores = Dict[str:float] = {}
        doc_map : Dict[str:Document] = {}
        rrf_scores : Dict[str:float] = {}

        c = 60 #平滑常数c = 60
        #3.先对chroma的接过去计算rrf

        #需要排名，使用枚举
        for rank,doc in enumerate(chroma_results):
            content = doc.page_content#用内容做身份标注
            doc_map[content] = doc
                                                #浮点数留意
                                                #如果算过了就累加（所以如果两个都出现，加权会高
                                                #否则就是0.0算
            rrf_scores[content] = rrf_scores.get(content,0.0) + 1.0/(rank+c+1)  #rrf算法，排名+平滑常数+1取倒数。rank小得分高
        
        #3.再对bm25的接过去计算rrf
        for rank,doc in enumerate(bm25_results):
            content = doc.page_content#用内容做身份标注
            doc_map[content] = doc
                                                #浮点数留意
                                                #如果算过了就累加（所以如果两个都出现，加权会高
                                                #否则就是0.0算
            rrf_scores[content] = rrf_scores.get(content,0.0) + 1.0/(rank+c+1)  #rrf算法，排名+平滑常数+1取倒数


        #算完了进行排序
        sorted_contents = sorted(
            rrf_scores.keys(),#排序对象：可迭代对象：rrf_scores.keys()键列表
            #指定Key,大哥
            key = lambda x : rrf_scores[x],  #依据：content对应的值
            reverse=True
        )

        #根据内容取出top_k个原文档（包含元数据等等—）
        final_docs = [doc_map[content] for content in sorted_contents[0:top_k]]
        return final_docs
    


    #qwen接口的精排
    def _rerank_documents_qwen(self,query:str,docs:List[Document],top_k:int)->List[Document]:
        if docs is None:
            return[]
        print(f"正在调用{self.reranker_name}模型对{len(docs)}个文档进行精排\n")
        #1.提取纯文字列表

        docs_text = [doc.page_content for doc in docs]

        #2.获取结果

        try:
            resp = dashscope.TextReRank.call(
                model=self.reranker_name,
                query=query,
                top_n=top_k,
                documents=docs_text,
                return_documents=False#返回前top_k排名索引，方便处理
            )

            #云端调用状态
            if resp.status_code == HTTPStatus.OK:
                return [docs[item.index] for item in resp.output.results]
            else:
                print(f"云端api报错：{resp.message}\n返回粗排结果")
                return docs[:top_k]
        except Exception as e:
            print(f"云端api调用失败：{e}\n返回粗排结果")
            return docs[:top_k]




    #新增一个独立的rerank打分方法
    def _rerank_documents(self,query:str,docs:List[Document],top_k:int)->List[Document]:
        #if docs is None:
            #return[]

        #覆盖空列表情况
        if not docs:
            return []
        
        #0.组装query,document文本对
        sentence_pairs = [[query,doc.page_content] for doc in docs]
        
        print(f"正在调用{self.reranker_name}模型对{len(docs)}个文档进行精排\n")
        #1.交叉编码器打分   
        scores = self.reranker.predict(sentence_pairs)


        #2.将分数和文件绑定

        scored_docs = list(zip(docs,scores))  #大写List:类型注解；小写list:类型转换


        #3.排序

        scored_docs.sort(key = lambda x:x[1],reverse=True)

        #4.剥离分数，输出前top_k个document对象
        
        return [doc for doc,score in scored_docs[:top_k]]



    #为构建评估实验：构建专门的分支

    #直接构建接口
    def search_dense(self,query:str,top_k:int = 5)->List[Document]:
        if self._db is None:
            raise RuntimeError("chroma向量数据库未初始化，查询失败")
        

        #如果使用精排，粗排阶段扩大召回倍数

        if self.use_reranker:
            recall_k = top_k * 3
        else:
            recall_k = top_k
        
        #1.粗排
        candidate_docs = self._db.similarity_search(query,k=recall_k)

        #2.精排
        if self.reranker_name == "BAAI/bge-reranker-base":
            return self._rerank_documents(query,candidate_docs,top_k)
        elif self.reranker_name == "gte-rerank-v2":
            return self._rerank_documents_qwen(query,candidate_docs,top_k)





        else:
            return candidate_docs[:top_k]
    
    
    
    
    
    
    def search_bm25(self,query:str,top_k:int = 5)->List[Document]:
        recall_k = top_k * 3 if self.use_reranker else top_k
        candidate_docs = self.bm25_retriever.search(query, top_k=recall_k)

        if self.reranker_name == "BAAI/bge-reranker-base":
            return self._rerank_documents(query, candidate_docs, top_k)
        elif self.reranker_name == "gte-rerank-v2": 
            return self._rerank_documents_qwen(query, candidate_docs, top_k)
        else:
            return candidate_docs[:top_k]
    def search_hybrid(self,query:str,top_k:int = 5)->List[Document]:

        if self.use_reranker:
            recall_k = top_k * 3
        else:
            recall_k = top_k
        
        #1.粗排
        candidate_docs = self.search(query,top_k=recall_k)

        #2.精排
        if self.reranker_name == "BAAI/bge-reranker-base":
            return self._rerank_documents(query,candidate_docs,top_k)
        elif self.reranker_name == "gte-rerank-v2":
            return self._rerank_documents_qwen(query,candidate_docs,top_k)





        else:
            return candidate_docs[:top_k]



        