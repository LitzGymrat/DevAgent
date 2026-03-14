#日志分析

from src.agent.core import chat_completion

def analyse_log(log:str)->str:

    LOG_ANALYSE_SYSTEM = """你是一名资深后端工程师。
    下面是一段错误日志/traceback，请你分析：
    1. 错误的大致类型和根本原因
    2. 关键出错位置（文件/行号/函数）
    3. 可能的修复方案（可给出多种备选）
    4. 如何防止类似问题再次发生（例如增加检查、处理边界情况）
    回答用中文，分点列出，结构清晰。
    """
    
    message = [
        {"role":"system","content":LOG_ANALYSE_SYSTEM},
        {"role":"user","content":f"请分析以下日志:\n'''{log}'''\n"},
    ]

    return chat_completion(message,max_tokens=800,temperature=0.2)