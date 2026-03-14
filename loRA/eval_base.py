#基线模型：不挂载LoRA参数

import json
import torch #Huggingface底层框架依赖pytorch，后续操作用到          引入基类进行标注，否则只有读取到之后才能显示
from transformers import AutoTokenizer,AutoModelForCausalLM,PreTrainedTokenizer,PreTrainedModel #auto工厂模式：方便切换不同的模型;causal:因果推断

from tqdm import tqdm 
#单独import tqdm 仅仅是一个模块，我们要直接使用tqdm()，需要从模块中导入函数

#tqdm类：进度条功能
#peft:paramater efficient fine-tuning:LoRA：部分参数微调挂载。

#1.指定好测试集，模型文件，loRA参数的路径

BASE_MODEL_PATH = "/root/autodl-tmp/models/qwen/Qwen2.5-7B-Instruct"



TEST_DATA_PATH = "/root/LLaMA-Factory/data/devagent_test_data.json"

#===========

print("正在加载分词器和基座模型\n")
#2.加载分词器，基座模型：从训练好的本地模型读取
tokenizer:PreTrainedTokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_PATH,trust_remote_code = True) #信任客制化模型的代码

model:PreTrainedModel = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL_PATH,
    #自动切片分配到不同的显卡上（否则默认分配到CPU上，需要手动，而单卡存在爆显存风险）
    device_map = "auto",
    trust_remote_code = True,
    #指定数据类型:特殊的torch数据2类型bfloat16:比普通的float32省显存，又比普通的float16精度高(牺牲了小数部分位数，扩大整数范围)，不容易出现溢出，梯度消失。
    torch_dtype = torch.bfloat16,
)





#作用于模型层：调整行为模式。典型：layerNorm,BatchNorm,RMSNorm使用全局均值/方差；dropout关闭
model.eval()
print("已载入基座模型并开启测试模式")

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

    #1.先将字典转为一串对话模板字符串               先不分词，方便检查中间模板 ;下一步生成的提示词
    text = tokenizer.apply_chat_template(message,tokenize = False,add_generation_prompt = True)
    #2.调用tokenizer正式分词：向量化 ：返回pytorch_tensor类型(类字典)，方便给GPU计算
    #ids:转为词表对应索引
    #model_input是一个类字典对象！{'input_ids':...,'attention_mask':.....}
    model_input = tokenizer([text],return_tensors = "pt").to(model.device)#输入要进行计算了，挂载到GPU上


    #获取模型输出：生成的是词表对应索引的数组：不同于词嵌入层的语义向量
    #用到了张量运算，测试阶段关闭梯度：作用于自动求导引擎，节省算力。
    with torch.no_grad():
        #自回归模型默认返回inputs_ids和output_ids的拼接
        generated_ids = model.generate(
            #解包tensor张量(类字典)传入：
            #input_ids包含输入的索引数组和掩码注意力矩阵
            #解包成关键字参数传入
            **model_input,
            max_new_tokens = 512,
            #测试:调低温度：确定性，容易复现，更加稳定。
            temperature = 0.1,
            #关闭随机发散取样
            do_sample = False,

        )

    #自回归模型:generated_ids包含了输入和输出的索引数组，需要做个提取。
                                                                            #打包起来做列表推导式:提取出input_ids张量
    output_ids = [output_ids[len(input_ids):] for input_ids,output_ids in zip(model_input.input_ids,generated_ids)]

    #根据词表解码得到raw_data

    #输出数据第零维度为batch，batch_decode可以接受二维张量
    #decode则需要特别取出来。                       跳过特殊词元
    #这里我们每次读一句，batch_size=  1。所以直接取出第一个元素。
    raw_data = tokenizer.batch_decode(output_ids,skip_special_tokens=True)[0]

    #5.打分机制
    #首先尝试解析json字符串成字典数据
    try:
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
print("======DevAgent 基座模型工具调用测试报告======")
print(f"\n测试总条数  = {len(test_cases)}")

formatted_rate = 100 * metrics["format_success"] / len(test_cases)
tool_match_rate = 100 * metrics["tool_match"] / len(test_cases)
hallucination_rate = 100 * metrics["hallucination"] / len(test_cases)

print(f"Json格式输出正确率：{formatted_rate:.3f}%(越高越好)\n") #.3:三位有效数字 .3f：三位小数
print(f"工具匹配正确率：{tool_match_rate:.3f}%(越高越好)\n")
print(f"工具幻觉率：{hallucination_rate:.3f}%(越低越好)\n")
print("="*50)