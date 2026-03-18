#项目配置文件：核心参数，重要配置数据。
#配置与代码分离
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    #每个变量都对应一个配置参数
    #继承父类BaseSettings:每个变量会自动到关键的.env文件里面去找

    #LLM配置
    deepseek_api_key : str#不设置默认值,.env里面必须有
    deepseek_base_url : str = "https://api.deepseek.com" #有默认值
    model_name : str = "deepseek-chat"
    embedding_model : str = "text-embedding-ada-002"

    #向量数据库配置

    Chroma_persist_dir : str = "./data/Chroma"    #Chroma需要一个文件夹

    #软编码。在config中指定配置
    bm25_persist_dir : str = "./data/bm25_index.pkl"  #bm25只需要一个具体文件
    
    #模型选择
    embedding_provider : str = "qwen"
    #embedding_provider : str = "local"
    #模型名称
    local_embedding_name : str = "all-MiniLM-L6-v2" #经典轻量级模型。

    qwen_api_key : str
    qwen_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_embedding_name : str =  "text-embedding-v4"


    #rerank模型选择
    reranking_provider:str = "qwen"
    #reranking_provider:str = "local"
    #RAG配置
    #每个片段最大字符数
    code_chunk_size:int = 2000,
    code_chunk_overlap:int = 350,
    text_chunk_size : int = 1500,
    text_chunk_overlap : int = 350,
    #每个片段重叠字符数
      
    top_k : int = 8
    #是否启用rewriter模型调用      显式声明类型！
    enable_query_rewrite_in_tool : bool = False
    #隐藏文件指定 (BaseSettings会去找Config)
    #嵌套类
    class Config:
        #根目录找.env的隐藏文件。
        env_file = ".env"

#创建全局唯一的Settings实例：单例模式
settings = Settings()