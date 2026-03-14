import time
from functools import wraps



from src.rag.vectorstore import VectorStore
from src.agent.llm import chat_completion

#导入工具
import json
import re
from src.agent.tools.tools_schemas import TOOLS_SCHEMA
from src.agent.tools.code_analyser import analyse_code
from src.agent.tools.search_tool import search_codebase
from src.agent.tools.complete_code_llm import code_completion
from src.agent.tools.docker_file_llm import gen_docker_file
from src.agent.tools.generate_tests_llm import gen_tests
from src.agent.tools.log_analyser_llm import analyse_log

def time_logger(func):
    
    @wraps(func) # 保持原函数的元信息（名字、注释等）不变
    def wrapper(*args, **kwargs):
       
        start_time = time.perf_counter() 
        
        # 执行原本的函数逻辑（无论是工具调用还是聊天主循环）
        result = func(*args, **kwargs) 
        
        end_time = time.perf_counter()
        elapsed_time = end_time - start_time
        
        # 打印耗时日志（可以后续存入文件或数据库）
        print(f"\n⏱️ [耗时监控] 函数 '{func.__name__}' 执行完毕 | 耗时: {elapsed_time:.3f} 秒\n")
        
        return result
    return wrapper


def safe_json_loads(s: str) -> dict:
    
    if not isinstance(s, str): return {}
    s = s.strip()
    # 去除可能存在的 ```json 和 ``` 标记
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    # 裁剪出第一个 { 到最后一个 } 的内容
    l, r = s.find("{"), s.rfind("}")
    if l != -1 and r != -1 and r > l:
        s = s[l:r+1]
    try:
        return json.loads(s)
    except Exception as e:
        print(f"⚠️ [JSON 解析失败] 原始字符串: {s} \n错误: {e}")
        return {}
#定义成类而非函数

#创建实例，维护状态变量

#而且函数需要每次调用重新初始化，类一次初始化构建。
class DevAgent:
    #核心DevAgent
    #先打桩占位
    #整个模型可以跑通，后续再填东西


    
                #加入多轮记忆
    def __init__(self,max_history_turns = 1):
        #构建工具映射字典：
        self.available_tools = {
            "analyse_code":analyse_code,
            "complete_code":code_completion,
            "generate_docker_file":gen_docker_file,
            "search_codebase":search_codebase,
            "generate_test":gen_tests,
            "analyse_log":analyse_log,
        }
        #初始化对话记忆数组
        self.memory = []
        self.max_history_turns = max_history_turns
    
        #初始化向量库
        #self.db = VectorStore()
        #尝试拉取本地向量库

        #提前触发单例加载
        from src.agent.tools.search_tool import _get_vector_store
        _get_vector_store()



        #读写分离：前面Vectorstore是没有建库的，test的时候建立了

        """建库都集成到了search_tool里面"""

        #专门再写个建库脚本

        #预热数据库
        #try:
            #self.db.load()
            #拉取成功打印信息
            #print(f"成功预热本地代码仓库！\n")
        #except Exception as e:
            #print(f"读取本地数据库失败，请先运行测试脚本建库！\n错误信息:{e}")



    #多轮记忆去粗取精滑动窗口
    def _prune_memory(self):
        if not self.memory:
            return
        
        pruned_chat_history = []
        #1.留下system prompt
        #传入的是字典格式
        system_prompt = self.memory[0] if self.memory[0].get("role") == "system" else None

        #2.过滤中间的tool calls and observations
        for msg in self.memory:
            role = msg.get("role")

            if role == "tool" or(role == "assistant" and msg.get("tool_calls")):
                continue #这条不要
            elif role == "system":
                continue
            pruned_chat_history.append(msg)

        #3.去掉旧记忆
        max_len = 2*self.max_history_turns
        if len(pruned_chat_history) > max_len:
            print(f"目前已达设定上下文上限{self.max_history_turns}轮，正在裁剪记忆\n")
            pruned_chat_history = pruned_chat_history[-max_len:]
            


        #4.重新组装
        new_memory = []
        if system_prompt:
            new_memory.append(system_prompt)
        new_memory.extend(pruned_chat_history) #字典列表：先解包再放进去
        
        self.memory = new_memory
        print(f"[Memory] 修剪完毕，过滤掉工具调用残余，当前保留 {len(self.memory)} 条核心消息。")
        
    @time_logger              #类型声明清楚:str
    def chat(self,question:str)->str:
        #先返回一个固定字符串占位
        #后续会根据上下文检索返回
        #Mock模拟返回值，让模型可以先跑通

        #如果是第一轮对话，放入system prompt
        if not self.memory:
            print("加载系统提示词")
            system_prompt = """你是一个拥有多智能体协作能力的研发助手。
            你有多个的辅助工具（如静态代码分析、源码检索、日志分析等）。
            请严格遵守以下指令：
            1. 分析用户问题，如果需要查阅代码、分析 Bug 或生成配置，必须毫不犹豫地调用对应工具。
            2. 除非明显缺少信息，否则不要重复调用工具。每个问题最多调用 1 次 search_codebase。
            3. 必须用中文回答。
            """
            self.memory.append({"role":"system","content":system_prompt})
        #放入用户提问
        self.memory.append({"role":"user","content":question})

        #引入调用指纹：防止相同参数循环
        call_signatures = set()

        for _ in range(5):
            print(f"Agent综合分析中\n")

            #1.呼出大模型
            response_obj = chat_completion(self.memory,tools=TOOLS_SCHEMA)
            #返回的是SDK对象,转换为纯字典

            try:
                resp_dict = response_obj.model_dump(exclude_unset = True) #去掉None内容
            except AttributeError:
                #如果前面已经转为了字典
                resp_dict = response_obj
            #把这一步关于工具调用的分析记录下来

            #已经加入记忆
            self.memory.append(resp_dict)

            #2.判断是否需要调用工具

            tool_calls = resp_dict.get("tool_calls",None)

            if tool_calls:
                #遍历所有要的工具
                for tool_call in tool_calls:
                    #获取名字
                    function_name = tool_call["function"]["name"]
                    #获取参数
                    argument_str = tool_call["function"]["arguments"]
                    call_fingerprint = f"{function_name}_"


                    
                    
                    if call_fingerprint in call_signatures:
                        #发现大模型在原地踏步（用完全一样的参数调同一个工具）！
                        print(f"检测到重复调用: {function_name}")
                        
                        # 
                        error_msg = "系统拦截：你刚刚已经调用过该工具了！请不要原地踏步。如果你已经收集到足够信息，请立刻输出最终回答；如果信息不够，请更换检索关键词！"
                        
                        self.memory.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": error_msg
                        })
                        continue # 让它带着指令，进入下一次循环重新思考！
                    #如果不在，加入集合
                    
                    call_signatures.add(call_fingerprint)

                    print(f"Agent决策：决定调用工具：{function_name}")
                    #解析参数
                    args = safe_json_loads(tool_call["function"]["arguments"])

                    #从字典中取出需要的函数

                    function_to_call = self.available_tools.get(function_name,None)

                    if function_to_call:
                        try:
                            #执行代码'
                            function_resp = function_to_call(**args) #解包
                        except Exception as e:
                            #给function_resp一个可用值
                            function_resp = f"工具'{function_name}'内部执行出错\n错误信息：{str(e)}"
                            print(f"工具'{function_name}'内部执行出错\n错误信息：{str(e)}")
                    else:
                        function_resp = f"未找到工具{function_name}\n"
                        print(f"未找到工具{function_name}\n")

                    #
                    #调用完工具，将observation放回去
                    tool_msg = {
                        "role":"tool",
                        "tool_call_id" : tool_call["id"],
                        "content":str(function_resp),#保证转回字符串
                    }
                    self.memory.append(tool_msg)
                #一轮跑完继续循环，让模型可以对着结果再思考
                continue
            else:
                #没有tool_calls，模型觉得不用调用工具，
                #直接提取回复的人话
                final_resp = resp_dict.get("content","大模型未返回内容")

                #记忆修剪
                self._prune_memory()
                return final_resp


        return "Agent思考超过最大迭代次数（5次）已停止思考....."



        """核心链路：1.用户提问 2.数据库检索 3.拼接prompt 4. LLM生成"""
        #尝试！！！！排错关键
        try:
            #1.根据提问查找
            #执行关键操作的打印！
            print("正在检索相关代码")

            #Document列表类型

            #通过self.db。。。实例调用而非VectorStore类名调用。。
                                #经过测试，先拥抱dense_only
            retrieved_docs = self.db.search_dense(question,top_k=8)


            #2.组装:把检索到的代码拼接成长字符串
            context_str = ""
            for i,doc in enumerate(retrieved_docs):
                source = doc.metadata.get("source","未知来源") #使用get查找source键，没有就是未知来源
                context_str += f"----第{i+1}个参考代码片段(来源:{source})----\n"
                context_str += f"{doc.page_content}\n"
                


        #上下文注入：提示词工程
            system_prompt  = {
                f"你是 DevAgent，一个熟知当前项目代码，帮助开发者解决问题的智能代码助手。\n",
                f"请你严格依照被提供的【参考代码片段】来回答用户的问题\n",
                f"严格规定：\n",
                f"- 1.必须且只能根据我为你提供的代码片段回答\n",
                f"- 2.如果当前代码片段找不到很好的依据，请诚实回答“未当前项目代码仓库中找到相关片段”\n",
                f"- 3.回答时候必须注明来源，比如“根据src/main.py显示”\n",
                f"- 4.用中文回答\n",
                f"- 5.尽量给出清晰、可执行的建议\n",
                f"- 6.不确定的地方要说明自己不确定\n",
                    #加入代码片段
                f"参考代码片段:\n{context_str}"
        }





        #调用时的try except

    


                #列表字典！unhashable![{}]
            messages = [
                {"role" : "system","content" : f"{system_prompt}"}, #单独在外，也可以不加格式化。
                {"role" : "user","content" : f"{question}"},
                ]
            answer = chat_completion(messages)
        except Exception as e:
                return f"大模型开小差了，错误信息:{str(e)}"

        return answer
    
    def clear_memory(self):
        #清楚对话历史,(上下文上限)
        #现在先什么都不做
        pass

    """
    列表（List，[]）：就是一个排队的长龙，谁排第一、谁排第二清清楚楚。你往里面塞什么字典它都不管。

集合（Set，{}）：如果你在 Python 里用 {} 包裹一堆没有冒号的数据（比如 {1, 2, 3}），
这就叫集合。集合的底层是一个哈希表（Hash Table），
它要求里面的每一个元素都必须是**绝对固定、不可改变（Immutable）**的。

灾难发生： 字典 {"role": "..."} 
在 Python 里是可以随意增删改的（Mutable）。
当你试图把一个字典塞进集合 {} 时，
Python 发现它算不出固定的哈希值，当场急眼，直接把桌子掀了
，大喊：“字典这玩意儿不可哈希（unhashable type: 'dict'）！老子不存"""