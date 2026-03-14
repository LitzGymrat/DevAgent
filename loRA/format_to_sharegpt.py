#将Json转换用于微调训练的sharegpt格式

#微调训练所用的system-prompt应与实际推理时一致。否则导致“分布偏差”，实际运行的微调效果不好

import json
import random
# 1. 真实业务 System Prompt (保持一字不差)
USER_RUNTIME_PROMPT = """你是一个拥有多智能体协作能力的研发助手。
你有多个的辅助工具（如静态代码分析、源码检索、日志分析等）。
请严格遵守以下指令：
1. 分析用户问题，如果需要查阅代码、分析 Bug 或生成配置，必须毫不犹豫地调用对应工具。
2. 除非明显缺少信息，否则不要重复调用工具。每个问题最多调用 1 次 search_codebase。
3. 必须用中文回答。"""

# 2. 模拟底层 SDK 拼接的“工具描述与格式要求”
# 这样不仅维持了你的人设，还给了模型明确的输出规范
TOOL_SCHEMA_INSTRUCTION = """
【可用工具集合】
1. `analyse_code`: 静态分析Python代码规范。参数: {"code": "<Python代码>"}
2. `search_codebase`: 检索相关代码。参数: {"query": "<检索关键词>", "top_k": <整数>}
3. `analyse_log`: 分析报错日志。参数: {"log": "<报错日志/Traceback>"}
4. `generate_dockerfile`: 生成Docker配置。参数: {"project_description": "<环境要求>"}
5. `generate_tests`: 生成单元测试。参数: {"code": "<目标代码>", "description": "<额外说明>"}
6. `complete_code`: 补全残缺代码。参数: {"context": "<残缺代码片段>"}

【工具调用格式】
如果你需要调用工具，请务必直接输出如下纯 JSON 格式（不要附带任何解释性文本或 markdown 标记）：
{"name": "工具名称", "arguments": {"参数名": "参数值"}}
"""

FINAL_SYSTEM_PROMPT = f"{USER_RUNTIME_PROMPT}\n{TOOL_SCHEMA_INSTRUCTION}"


def convert_to_sharegpt(raw_data):
    formatted_data = []
    for item in raw_data:
        #把相应的需要输出的内容打包成字典，再转为标准json字符串格式

        #openai接口要求的function call协议返回工具名和参数
        tool_call_dict = {
            "name":item["tool_name"],
            "arguments":item["arguments"]
        }
                            #dumps:存到字符串；dump:存到文件中
        tool_call_json_str = json.dumps(tool_call_dict,ensure_ascii=False) #否则中文会被转义成ASCII码

        #组装sharegpt格式
        formatted_case = {
            "conversations":[
                {
                    "from":"system",
                    "value":FINAL_SYSTEM_PROMPT,
                },
                {
                    "from":"user",
                    "value":item["user_query"],
                },
                {
                    "from":"assistant",
                    "value":tool_call_json_str,
                }
            ]
        }
        formatted_data.append(formatted_case)

    return formatted_data


if __name__ == "__main__":
    #读取数据
    #with open:上下文管理，离开自动关闭文件，释放资源
    with open("loRA\devagent_raw_data.json","r",encoding="utf-8") as f:
        raw_data = json.load(f)
    #设置种子
    random.seed(42)
    random.shuffle(raw_data)

    total = len(raw_data)
    split_idx = int(total * 0.9) #切分数据集

    train_data = convert_to_sharegpt(raw_data[:split_idx])
    test_data = convert_to_sharegpt(raw_data[split_idx:])

    #将数据集保存                w写入
                        #生成文件也加上.json后缀
    with open("devagent_train_data.json","w",encoding="utf-8") as f:
        json.dump(train_data,f,ensure_ascii=False,indent=2)#缩进 = 2
    with open("devagent_test_data.json","w",encoding="utf-8") as f:
        json.dump(test_data,f,ensure_ascii=False,indent=2)#缩进 = 2

    print(f"格式转换完成！完全对齐实际运行 Prompt！")
    print(f"训练集: {len(train_data)} 条 -> devagent_train.json")
    print(f"测试集: {len(test_data)} 条 -> devagent_eval.json")
    