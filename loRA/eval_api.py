#基线模型：不挂载LoRA参数

import json

from tqdm import tqdm 
#单独import tqdm 仅仅是一个模块，我们要直接使用tqdm()，需要从模块中导入函数

#tqdm类：进度条功能
#peft:paramater efficient fine-tuning:LoRA：部分参数微调挂载。

#1.指定好测试集，模型文件，loRA参数的路径
from src.config import settings
from openai import OpenAI

#实例化官方客户端
client = OpenAI(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
)




TEST_DATA_PATH = "/root/LLaMA-Factory/data/devagent_test_data.json"

#===========







#作用于模型层：调整行为模式。典型：layerNorm,BatchNorm,RMSNorm使用全局均值/方差；dropout关闭

print("已载入商业模型")

#4.读取测试数据
with open(TEST_DATA_PATH,"r",encoding="utf-8") as f:
    test_cases = json.load(f)
#初始化评分字典面板

metrics = {
    "total":len(test_cases),
    "format_success":0,#json解析
    "tool_match":0,#工具选择
    "hallucination":0#幻觉
}
            #使用集合而非列表
            #方便O(1)判断是否在内（底层哈希）
            #列表：关注严格顺序
ALLOWED_TOOLS = {"analyse_code","complete_code","generate_tests",
                 "generate_dockerfile","analyse_log","search_codebase"}


#启动测试
print(f"启动total:{len(test_cases)}条测试")
for i,case in enumerate(tqdm(test_cases)):

    #5.提取正确答案
    system_prompt = case["conversations"][0]["value"]
    user_query = case["conversations"][1]["value"]

    expected_output_str = case["conversations"][2]["value"]
    #尝试提取标准json格式
    try:
        #大模型：只认纯文本；python逻辑判断：字典方便
        #将json格式字符串转为字典：
        expected_json = json.loads(expected_output_str)
        expected_tool = expected_json.get("name")
            #标准答案发生问题
    except Exception as e:
        print(f"在读取第{i+1}条测试数据时发现预期json异常:{e}")
        continue

    #构造输入：列表
    message = [
        {"role" : "system","content":system_prompt},
        {"role" : "user","content":user_query},
    ]
    #进行手动tokenize
    



    #获取模型输出：生成的是词表对应索引的数组：不同于词嵌入层的语义向量
    #用到了张量运算，测试阶段关闭梯度：作用于自动求导引擎，节省算力。
   

    #5.打分机制
    #首先尝试解析json字符串成字典数据
    try:
        response = client.chat.completions.create(
            model = settings.model_name,
            temperature=0.1,
            max_tokens=512,
            messages = message

        )

        #取出纯内容

        raw_data = response.choices[0].message.content.strip()

        #清理一下可能残留的md格式

        if raw_data.startswith("```json"):
            raw_data = raw_data[7:-3].strip()
        elif raw_data.startswith("```"):
            raw_data = raw_data[3:-3].strip()
        
        parsed_data = json.loads(raw_data)
        #解析成功直接加分
        metrics["format_success"] += 1

        tool_name = parsed_data.get("name")
        #匹配工具
        if tool_name == expected_tool: 
            metrics["tool_match"] += 1
        elif tool_name not in ALLOWED_TOOLS:
            metrics["hallucination"] += 1

    except json.JSONDecodeError as e:
        #解析不成功直接下一个
        continue


#打印报告
print("======DevAgent deepseek商业api 工具调用测试报告======")
print(f"\n测试总条数  = {len(test_cases)}")

formatted_rate = 100 * metrics["format_success"] / len(test_cases)
tool_match_rate = 100 * metrics["tool_match"] / len(test_cases)
hallucination_rate = 100 * metrics["hallucination"] / len(test_cases)

print(f"Json格式输出正确率：{formatted_rate:.3f}%(越高越好)\n") #.3:三位有效数字 .3f：三位小数
print(f"工具匹配正确率：{tool_match_rate:.3f}%(越高越好)\n")
print(f"工具幻觉率：{hallucination_rate:.3f}%(越低越好)\n")
print("="*50)