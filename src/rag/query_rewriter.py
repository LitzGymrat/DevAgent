#提示词改写：封装到RAG中。因为core职责是黑盒，全部检索过程封装到RAG

import json
import re
from dataclasses import dataclass #类的自动初始化函数标签
from src.agent.llm import chat_completion   #引入对话补全，用于llm的改写

@dataclass
class Query_rewrite_result:
    raw_query:str
    dense_query:str

class Query_rewriter:
    def rewrite(self,raw_query:str)->Query_rewrite_result:
        #.strip除去多余排版字符
        q = raw_query.strip()
        system_prompt = """你是一个专门为代码 RAG（检索增强生成）系统设计的 Query 改写专家。
你的任务是将用户口语化、模糊的提问，改写成信息密度极高、最适合向量数据库（Dense Retrieval）匹配的查询词组合。

【核心策略】：
1. 实体绝对保留：必须保留问题中的所有文件名（如 .py）、函数名（如 def index_document）、类名和特定变量名。
2. 术语自动扩展（极其重要）：根据用户的口语描述，自动预测并补充底层的计算机专业术语。比如用户问“怎么切文本”，你要扩展为“切分文本 TextSplitter Document Chunk”。
3. 极限降噪：彻底去除“请问”、“帮我找一下”、“那个叫什么”等无意义的口语废话。

【输出格式】：
必须严格输出合法的 JSON 格式，绝不能有任何多余的解释性文字！格式如下：
{"dense_query": "改写和扩展后的核心检索词组合"}"""
        user_prompt = f"原始提问:\n{q}"
        #字典列表
        messages = [{"role" : "system","content" : system_prompt},
                    {"role" : "user","content" : user_prompt},]
        
        resp = chat_completion(messages,temperature=0.1)#温度调低，要求更稳定的输出。

        #尝试对返回的json进行处理和提取
        try:
            clean_resp = resp.strip()
            clean_resp = re.sub(r"^```(?:json)?\n?(.*?)\n?```$", r"\1", clean_resp, flags=re.DOTALL)
            #读取json格式:load读本地文件。loads读字符串。
            data = json.loads(clean_resp)
            dense_query = data.get("dense_query","")

            print(f"[Rewrite]:'{q}' -> '{dense_query}'")
        except Exception as e:
            print(f"Rewriter 解析失败。错误原因 {e}\n降级为原问题")
            dense_query = q
        return Query_rewrite_result(
            raw_query= q,
            dense_query= dense_query
        )