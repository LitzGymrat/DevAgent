from src.evaluation.rewriter_noisy_dataset import NOISY_EVAL_QUERIES
from src.rag.vectorstore import VectorStore

from typing import List,Dict
from langchain_core.documents import Document
from src.rag.query_rewriter import Query_rewriter
rewriter = Query_rewriter()
#量化评估脚本

#计算top_k命中率以及RR

def hit_and_rr(docs:List[Document],expected_source):
    for idx,doc in enumerate(docs):
        #如果预期文件源中包含给定文件的源，就算数
        #Langchain中Document的底层源码，值可以是任意类型。显式再强制转成str形式，告诉编译器是字符串
        src = str(doc.metadata.get("source","")).replace("\\","/")   #对路径在win上替换
        if any(exp in src for exp in expected_source):
            return 1,1.0 / (idx + 1)    #加括号！
        
    #全部没有才返回0.。
    return 0,0.0
    
#main准备：构建向量数据库，不同模式的量化指标字典推导式
if __name__ == "__main__":


    vs = VectorStore()
    vs.load()

    modes = {"dense","bm25","hybrid"}

    #为每种场景分别计分
    from collections import defaultdict
    #自动初始化字典数据结构：使用匿名函数接受传入的键。如果字典中没有，新构建一个
    stats = defaultdict(lambda : {m:{"hit":0,"rr":0.0,"count":0} for m in modes})



    #全局的计分
    global_stats = {m:{"hit":0,"rr":0.0} for m in modes} #每种模式构建一个存值字典。

    top_k = 8
    #基准测试

    #提取问题，提取答案，算出预期，进行量化

    for case in NOISY_EVAL_QUERIES:
        q = case["query"]
        clean_query = rewriter.rewrite(q).dense_query
        q = clean_query
        exp = case["expected_files"]
        #获取问题类型
        q_type = case["query_type"]

        result = {
            "dense" : vs.search_dense(q,top_k = top_k),
            "bm25" : vs.search_bm25(q,top_k = top_k),
            "hybrid" : vs.search_hybrid(q,top_k = top_k)
        }


        #for key,values in dict.items() :返回每个键值对的元组。如果不加items()，遍历字典只返回键
        for mode,docs in result.items():
            hit,rr = hit_and_rr(docs,exp)
            #把量化数据加进去
            stats[q_type][mode]["hit"] += hit 
            stats[q_type][mode]["rr"] += rr
            #更新数量
            stats[q_type][mode]["count"] += 1

        for mode,docs in result.items():
            hit,rr = hit_and_rr(docs,exp)
            #把量化数据加进去
            global_stats[mode]["hit"] += hit 
            global_stats[mode]["rr"] += rr

    #不同提问类型的结果
    for q_type,type_stats in stats.items():
        count = type_stats["dense"]["count"]

        print(f"======================== 提问类型:{q_type} =======================\n")
        print(f"======================== 问题数量:{count} =======================\n")

        for mode in modes:          #字符串键：加双引号。
            hit_rate = type_stats[mode]["hit"] / count
            mrr = type_stats[mode]["rr"] / count
        
            print(f"{q_type}类型提问：引擎：{mode} | Hit_Rate：{hit_rate*100:.1f}% | MRR:{mrr:.3f}") 





    #计算最终平均结果

    n = len(NOISY_EVAL_QUERIES) #总题数

    print("="*100)
    print("=="*25,f"最终全局评测结果(top_k = {top_k})","=="*25)

    for mode in modes:          #字符串键：加双引号。
        hit_rate = global_stats[mode]["hit"] / n
        mrr = global_stats[mode]["rr"] / n
        
        print(f"引擎：{mode} | Hit_Rate：{hit_rate*100:.1f}% | MRR:{mrr:.3f}") 