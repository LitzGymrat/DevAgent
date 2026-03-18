from src.agent.core import chat_completion

def gen_tests(code:str,description:str)->str:

    
    TEST_GEN_SYSTEM = """你是一名资深 Python 测试工程师。
    根据给定的函数代码和说明，生成 pytest 样式的单元测试。
    要求：
    1. 覆盖正常情况和常见边界情况
    2. 使用 pytest 风格的测试函数 (test_xxx)
    3. 必要时使用 fixture 或参数化
    4. 测试代码要可运行，不要省略 import
    只输出测试代码，不要解释。
    """
    user_prompt = "下面是一段函数的代码，请为其生成单元测试"
    user_prompt += f"\ncode\n"

    if description.strip():
        user_prompt += f"\n函数说明：{description}\n"

    message = [
        {"role":"system","content":TEST_GEN_SYSTEM},
        {"role":"user","content":f"{user_prompt}"},
    ]

    return chat_completion(message,max_tokens=800,temperature=0.2)