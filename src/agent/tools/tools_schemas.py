"""
Agent 工具链菜单 (Tool Schemas)
这里定义了所有对大模型开放的工具。大模型会根据这里的 description 决定调用哪个工具。
"""

TOOLS_SCHEMA  = [
    #1.AST函数分析
    {
        "type":"function",
        "function":{
            "name":"analyse_code",
            "description":"这是一个python静态代码问题分析器，当用户发来一段python代码需要分析问题时，路由至此工具",
            "parameters":{
                "type":"object",
                "properties":{
                    "code":{
                        "type":"string",
                        "description":"需要被静态分析的python源代码",
                    }
                },
                "required":["code"]#参数字典必须包含"code"键。否则报错.
            }
        }
    },
    

    # 2. 核心大眼：RAG 代码库检索 
    {
        "type": "function",
        "function": {
            "name": "search_codebase",
            "description": "在本地代码库中检索相关代码片段并返回来源文件与片段内容。"
                "当用户询问：函数/类定义在哪、某个模块如何实现、某段逻辑源码是什么、RAG/向量库/索引/配置在哪里等，需要先调用该工具。"
                "调用时请将用户口语化问题改写/扩展为适合检索的关键词（可中英混合，尽量包含可能的函数名/类名/变量名/库名）。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "检索关键词/短句（建议已做扩展）"
                    
                    },
                    "top_k": {"type": "integer", 
                              "description": "返回片段数量", 
                              "default": 6},
                },
                "required": ["query"]
            }
        }
    },

    # 日志分析
    {
        "type": "function",
        "function": {
            "name": "analyse_log",
            "description": "当用户发来一串报错信息(Error)、异常堆栈(Traceback)或系统日志时，路由至此工具。它能一针见血指出根本原因并给出修复方案。",
            "parameters": {
                "type": "object",
                "properties": {
                    "log": {
                        "type": "string",
                        "description": "原始的报错日志或异常堆栈文本"
                    }
                },
                "required": ["log"]
            }
        }
    },

    # 4.Dockerfile 配置生成
    {
        "type": "function",
        "function": {
            "name": "generate_dockerfile",
            "description": "当用户要求为项目编写 Dockerfile、docker-compose 或询问如何打包容器镜像时，路由至此工具。它将输出高标准的容器化配置。",
            "parameters": {
                "type": "object",
                "properties": {
                    "project_description": {
                        "type": "string",
                        "description": "项目的运行环境描述、依赖需求或启动方式"
                    }
                },
                "required": ["project_description"]
            }
        }
    },

    # 5. 单元测试生成
    {
        "type": "function",
        "function": {
            "name": "generate_tests",
            "description": "当用户提供一段代码，要求为其编写单元测试（如 pytest）或覆盖边界情况时，路由至此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "需要编写测试用例的目标函数或类代码"
                    },
                    "description": {
                        "type": "string",
                        "description": "可选参数：关于这个函数功能的额外补充说明"
                    }
                },
                "required": ["code"]
            }
        }
    },

    # 6. 代码补全
    {
        "type": "function",
        "function": {
            "name": "complete_code",
            "description": "代码生成助手。当用户提供一半的代码片段，要求续写代码、补全逻辑时，路由至此工具。",
            "parameters": {
                "type": "object",
                "properties": {
                    "context": {
                        "type": "string",
                        "description": "用户已有的残缺代码上下文"
                    }
                },
                "required": ["context"]
            }
        }
    }



]






