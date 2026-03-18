from src.agent.core import chat_completion

CODE_COMPLETION_SYSTEM = """你是一名资深 Python 工程师。
根据给出的上下文，补全后续代码。
要求：
1. 保持风格和已有代码一致
2. 不要重复已经写过的部分
3. 尽量写出可运行的代码
只输出补全部分，不要解释。
"""

def code_completion(context:str):
    message  = [
        {"role":"system","content":"CODE_COMPLETION_SYSTEM"},
        {"role":"user","content:":f"请依据上下文：\n{context}\n，补全代码"}
    ]
    return chat_completion(message,max_tokens=800,temperature=0.2)