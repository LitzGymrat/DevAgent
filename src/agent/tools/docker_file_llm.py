from src.agent.core import chat_completion

def gen_docker_file(project_description:str)->str:

    DOCKER_FILE_SYSTEM = """你是一名 DevOps 专家。
    根据用户提供的项目描述，生成一个合理的 Dockerfile。
    要求：
    1. 选择合适的基础镜像（尽量小，例如 python:3.11-slim）
    2. 正确安装依赖（pip/poetry/pnpm 等，根据描述判断）
    3. 设置工作目录、复制代码、安装依赖
    4. 使用非 root 用户运行服务（如果合适）
    5. 设置健康的启动命令（CMD/ENTRYPOINT）
    6. 关键步骤加上简短注释
    只输出 Dockerfile 内容，不要多余解释。
    """
    
    message = {
        {"role":"system","content":DOCKER_FILE_SYSTEM},
        {"role":"user","content":f"请根据以下项目描述生成Dockerfile:\n'''{project_description}'''\n"},
    }

    return chat_completion(message,max_tokens=800,temperature=0.2)