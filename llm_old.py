#我们有很多不同请求，都是要给LLM发送信息，接收信息
#把发送请求的逻辑全部封装起来
from typing import List,Dict #类型标注：List,Dict
from src.config import settings #配置文件
import requests #握手库

#函数输入 
#对话补全
def chat_completion(
        #需要传入的参数
        #上下文对话
        
        #大模型本身没有记忆，记忆由后端代码维护
        messages : List[Dict[str,str]],#一个字典列表：system:.....user:....：完整对话/
        #冒号就是标注类型，等价于int max_tokens = 800。一般的传参就是(messages,max_tokens = 800,temperature = 0.2)
        max_tokens: int = 800,
        temperature : float = 0.2


)->str :
    """
    调用deepseek api接口
    messages诸如：{"role" : "user","content" : "......"}
                    {"role" : "system","content" : "......"}
    """

    #三要素

    #1.地址url
    url = f"{settings.deepseek_base_url}/chat/comletions" #comletion "s"修改完记得保存才行！

    #2.快递单
    #授权证明和备注
    headers = {
        #定死的名称字典键。通用规则
        "Authorization" : f"Bearer{settings.deepseek_api_key}",
        #打包数据类型：JSON
        "Content-type" : "application/json",
    }

    #3.订单内容流水：模型，输入信息，最大输出token，温度
    payload = {
        #同样有规定的名称
        #传入的是字典！--->Json格式
        "model" : settings.model_name,
        "messages" : messages,
        "max_tokens" : max_tokens, 
        "temperature" : temperature,
        

    }

    #发送请求:post。 无等号的url:位置参数：按照位置确认参数。 headers,json：关键字参数，按照名字确认参数。方便。
    resp = requests.post(url,headers=headers,json=payload,timeout=60)#最长请求时间
    #先查状态码，如果你欠费了，或者模型有问题。会立即报错
    resp.raise_for_status()

    #获得返回数据
    data = resp.json()#多层JSON数据字典，用.json()将。纯文本转为字典
    return data["choices"][0]["message"]["content"]
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
