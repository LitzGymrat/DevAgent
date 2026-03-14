from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.routes import router as api_router

#app声明
app = FastAPI(
    title = "DevAgeng API",
    description = "智能编程助手API",
    version = "0.1.0",
)

app.add_middleware(
    #跨域共享问题
    CORSMiddleware,
    allow_origins = ["*"],
    allow_methods = ["*"],
    allow_credentials = True,
    allow_headers = ["*"],

)

#把api挂载到v1
app.include_router(api_router,prefix="/api/v1")

#装饰器，把函数和网址绑定起来
@app.get("/health")
#健康检查
#异步编程:服务器可以同时服务多个用户
async def health():
    return {"status" : "OK"}

@app.get("/")
async def root():
    #返回字典信息                                           /docs:fastapi生成的信息文档
    return {"name" : "DevAgent","version" : "0.1.0","docs" : "/docs"}

#带下划线：py维护的魔法变量
#意思就是py文件名为main才执行，防止其他执行文件读main.py的时候异常启动服务器
if __name__ == "__main__":
    import uvicorn
                #监听所有网卡（局域网均可以访问）  
    uvicorn.run(app,host = "0.0.0.0",port = 8000)#在我的8000端口执行
