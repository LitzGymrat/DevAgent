#我们有很多不同请求，都是要给LLM发送信息，接收信息
#把发送请求的逻辑全部封装起来
from typing import List,Dict #类型标注：List,Dict
from src.config import settings #配置文件

#工业界标准openai接口
from openai import OpenAI

#实例化官方客户端
client = OpenAI(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
)



#函数输入 
#对话补全
def chat_completion(
        #需要传入的参数
        #上下文对话
        
        #大模型本身没有记忆，记忆由后端代码维护
        messages : List[Dict[str,str]],#一个字典列表：system:.....user:....：完整对话/
        #冒号就是标注类型，等价于int max_tokens = 800。一般的传参就是(messages,max_tokens = 800,temperature = 0.2)
        max_tokens: int = 800,
        temperature : float = 0.2,
        tools = None

)->str :
    """
    调用deepseek api接口
    messages诸如：{"role" : "user","content" : "......"}
                    {"role" : "system","content" : "......"}
    """

    
    response = client.chat.completions.create(
        model=settings.model_name,
        messages=messages,
        max_tokens=max_tokens,
        temperature=temperature,
        tools= tools
    )
    return response.choices[0].message
"""{
  "id": "chatcmpl-123",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "死锁是指两个以上的进程..."  <--- 我们真正想要的在这！
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {"prompt_tokens": 10, "completion_tokens": 20}
}"""
