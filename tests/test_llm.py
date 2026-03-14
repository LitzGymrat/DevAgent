#写一个小的测试文件
#把需要的类导入进来
from src.agent.llm import chat_completion

if __name__ == "__main__":
    #字典列表。
    msgs = [
        {"role" : "system","content" : "你是一个人类"},
        {"role" : "user","content" : "introduce yourself"},
    ]
    ans = chat_completion(msgs)
    print("模型回答：",ans)