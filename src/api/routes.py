from typing import Optional#类型标注
from fastapi import HTTPException,APIRouter#分发网址
from pydantic import BaseModel
from src.agent.core import DevAgent
#pydantic:数据校验库：字典里面的数据对不对（检查格式等等）



#在routes.py建立一个API分流挂载器
router = APIRouter()

#初始化模型
#全局变量：单例模式，只生成一次
#懒加载：只有调用的时候才加载(网页顺畅打开)，而且检查是否为空

#_全局变量   Optional：可选，为空或者DevAgent，否则的话为空会报错
_agent : Optional[DevAgent] = None


#设定获取函数懒加载：只有调用的时候才加载(网页顺畅打开)，而且检查是否为空
def get_agent():
    #声明是全局变量
    global _agent
    if _agent == None:
        _agent = DevAgent()
    return _agent

#==========数据模型============
#全部都封装起来
class ChatRequest(BaseModel):
    #BaseModel:方便尤其是字典数据传输
    #类型注解：工程化常用。保证类型合理
    #请求JSON格式标注。
    question :str

class ChatResponse(BaseModel):
    answer :str

class CodeAnalyseRequest(BaseModel):
    code :str
class DockerfileRequest(BaseModel):
    project_description : str
class LogAnalyseRequest(BaseModel):
    log_content :str


#=============路由=============



#聊天 :
#.post表示被发送的操作
@router.post("/chat",response_model = ChatResponse) #表明返回的一定包含ChatResponse里面的answer字段
            #表明输入的一定是从ChatRequest来的字段
async def chat_endpoint(request : ChatRequest):
    """ 和 DevAgent 对话（当前版本：返回占位字符串）。 后面会接入 RAG + LLM。 """
    try:
        agent = get_agent()
        answer = agent.chat(request.question)
        #返回值也封装成类
        return ChatResponse(answer=answer) #指定参数传值
    #工程中的try-except：如果运行主体出问题，不能直接崩溃报错吧，得切到except
        #将错误信息存到e中
    except Exception as e:
        raise HTTPException(status_code=500,detail=str(e)) #返回错误码和错误信息(转成字符串)


#代码检查
@router.post("/analyse-code")
#路由web代码用endpoint区分。可能调用里面不带endpoint的函数
#工程习惯问题
async def analyse_code_endpoint(request : CodeAnalyseRequest):
    """代码分析，现在先返回代码占位
    后续接入LLM做真实分析"""
            #标注清楚
            #一般都是返回字典？键+值清晰
            #相应的JSON格式。
    return {"analyse" : f"[TODO:分析代码]\n\n {request.code}"}

#docker-file生成接口
@router.post("/generate-dockerfile")
async def generate_dockerfile_endpoint(request : DockerfileRequest):
    """先返回占位"""
    return {"docker-file": f"[TODO:根据描述生成dockerfile]\n\n 描述：{request.project_description}"}



#日志分析接口
@router.post("/log-analyse")
async def log_analyse_endpoint(request : LogAnalyseRequest):
    """日志分析接口，现在先占位"""
    return {"log-analyse" : f"[TODO:生成日志分析]\n\n 日志：{request.log_content}"}

#清空记忆接口
@router.post("/clear-memory")
async def clear_memory_endpoint():
    #get_agent会返回已有。
    get_agent().clear_memory()
    return {"status" : "OK"}

#检查健康接口：运维会不断发送信息检查运行状态

@router.get("/health")
async def health():
    """API层健康检查"""
    return {"status" : "healthy"}