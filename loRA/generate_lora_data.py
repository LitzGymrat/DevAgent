import json
import random
from openai import OpenAI
from google import genai
import time
from google.genai import types

# 填入你的 DeepSeek 或 OpenAI API Key
client = genai.Client(api_key="AIzaSyDRabIWU4T7EGHhgWAjutp9wvYhjGZvaXc")

# 定义多种不同的开发者场景和情绪，打破大模型的思维定势
SCENARIOS = [
    "【场景：焦头烂额的 Debugger】语气急躁，遇到诡异的报错或者系统崩溃，急需用日志分析或代码检索定位问题。",
    "【场景：代码洁癖的架构师】语气严谨，非常关注代码规范、圈复杂度、测试覆盖率，经常要求用 AST 分析代码或补充边界测试。",
    "【场景：新入职的实习生】语气虚心，对项目架构不熟悉，经常询问某个类在哪、某个功能怎么实现，或者需要续写一半的代码。",
    "【场景：准备上线的 DevOps】只关心部署、环境依赖、Docker 打包、配置文件怎么写。",
    "【场景：极简主义黑客】说话极度简短，惜字如金。比如直接扔一段报错，或者只发一个文件名要求检查。",
    "【场景：非英语母语者】提问时中英文夹杂，比如 '帮我 check 一下这个 module 的 memory leak 问题'。"
]


# 💡 这就是你刚才 IDE 生成的完美 Context！
PROJECT_CONTEXT = """DevAgent 项目背景信息（详细版）
【核心目录与关键文件】
Agent 核心模块
agent/core.py - DevAgent 核心执行引擎，实现 Function Calling 工作流、工具调度、消息处理、JSON 安全解析（safe_json_loads）
agent/llm.py - LLM 接口封装，支持 DeepSeek/OpenAI/Qwen API，管理 API Key、temperature、max_tokens 等参数
工具链模块
agent/tools/code_analyser.py - AST 静态分析器，包含 5 个检测模块：可变默认参数、裸 except、函数过长（超 50 行）、圈复杂度、未使用导入
agent/tools/complete_code_llm.py - 代码补全工具，基于上下文生成后续代码
agent/tools/generate_tests_llm.py - 测试生成工具，输出 pytest 风格的单元测试
agent/tools/docker_file_llm.py - Dockerfile 生成工具，选择合适基础镜像、非 root 用户、健康检查
agent/tools/log_analyser_llm.py - 日志分析工具，分析错误类型、关键位置、修复方案、预防策略
agent/tools/search_tool.py - 代码库搜索工具，支持查询改写、Dense/BM25 混合检索，返回 JSON 格式结果
agent/tools/tools_schemas.py - 工具菜单定义，为 LLM 提供 Function Calling 的 JSON Schema
RAG 检索模块
rag/vectorstore.py - 混合向量数据库，支持三种检索模式：Dense（OpenAI/Qwen Embedding）、BM25（稀疏）、Hybrid（RRF 融合）
rag/bm25.py - BM25 稀疏检索实现，包含私有分词器 _tokenize（正则表达式过滤非字母数字下划线），支持 Pickle 序列化持久化
rag/query_rewriter.py - 查询改写引擎，将口语化提问（如"妈妈，请帮我找一下切分文本的函数定义"）转换为高密度检索词，返回 Query_rewrite_result 对象
rag/loader.py - RePoLoader 类，递归加载指定目录所有代码文件，支持的格式：.py .js .txt .java .go .cpp .md .rs .yml .yaml .json，忽略：.git .idea .venv pycache node_modules 等
rag/splitter.py - CodeSplitter 类，使用 LangChain 的 RecursiveCharacterTextSplitter，分别处理 Python 代码（chunk_size=2000, overlap=350）和文本（1500, 350）
API 层
api/routes.py - FastAPI 路由，定义 POST /chat、/analyse-code、/generate-dockerfile、/log-analyse、/clear-memory，GET /health
main.py - FastAPI 应用入口，CORS 中间件允许所有源，uvicorn 运行于 0.0.0.0:8000
config.py - Settings 配置类，管理 LLM（DeepSeek、OpenAI、Qwen）、向量库（Chroma、BM25）、RAG 参数
评估模块
evaluation/eva_retrieval.py - 基准评估脚本，计算检索的 Hit@K 和 MRR（Mean Reciprocal Rank）
evaluation/eva_rewriter.py - 查询改写评估，测试噪声数据集上的改写效果
evaluation/rag_dataset.py - 清洁评估数据集，包含 query、expected_files、query_type
evaluation/rewriter_noisy_dataset.py - 噪声评估数据集，极度口语化、中英文混杂的真实用户提问
数据构建脚本
build_knowledge_base.py - 知识库构建入口：加载 src 目录 → 切分 → 向量化 → 持久化
【核心业务概念与专有名词】
AI 与 RAG 相关
Function Calling / Tool Calling - LLM 调用外部工具的机制，通过 JSON Schema 定义工具接口
RAG（检索增强生成） - 混合检索模式，结合 Dense（语义）和 BM25（精确词匹配）两种方式
Query Rewriter - 查询改写器，将模糊口语转换为高信息密度的检索关键词（特别针对代码搜索）
Embedding - 词嵌入，将文本转换为高维向量，支持 OpenAI Ada 002、Qwen v4、HuggingFace 本地模型
Dense Retrieval - 密集检索，基于语义相似度的向量相似度搜索
Sparse Retrieval - 稀疏检索，基于关键词匹配的 BM25 算法
RRF（Reciprocal Rank Fusion） - 倒数排名融合，将多种检索结果融合为单一排序
代码分析相关
AST（Abstract Syntax Tree） - 抽象语法树，用于静态代码分析
可变默认参数 - Python 反模式，如 def func(items=[]) 导致跨调用共享状态
裸 except - 不指定异常类型的 except，会捕获 KeyboardInterrupt、SystemExit 等系统异常
圈复杂度（Cyclomatic Complexity） - 代码分支数量，反映代码复杂度和可测试性
函数过长 - 超过 50 行的函数被标记为需要重构
检索评估指标
Hit@K - Top-K 结果中是否包含预期文档的命中率
MRR（Mean Reciprocal Rank） - 倒数排名均值，反映预期结果的排名位置
Precision / Recall - 精准率和召回率
技术栈与库
Chroma - 开源向量数据库，支持持久化和快速语义搜索
rank_bm25 - Python BM25 实现库
LangChain - RAG 框架，提供 Document、TextSplitter、Embeddings 等标准接口
FastAPI - 高性能 Web 框架，支持自动 API 文档生成
Pydantic - 数据验证库，BaseModel 用于请求/响应模型定义
pytest - Python 测试框架
RecursiveCharacterTextSplitter - LangChain 的递归文本切分器，支持多种语言
HuggingFaceEmbeddings - 本地 Embedding 模型（all-MiniLM-L6-v2）
OpenAIEmbeddings - OpenAI 官方 Embedding API 集成
部署与工程
Dockerfile LLM - 根据项目描述自动生成优化的容器镜像配置
非 root 用户 - Docker 安全最佳实践
CORS（跨域资源共享） - FastAPI 中间件配置，允许跨域请求
单例模式 - _agent 全局变量，实现懒加载和状态维护
Pickle 序列化 - BM25 索引的二进制序列化格式
【关键类名与函数名】
核心类
DevAgent - 主智能体类，维护对话记忆、工具调用循环、消息历史
VectorStore - 向量数据库管理类，包含 index_document()、load()、search_dense()、search_bm25()、search_hybrid()
BM25Retiever - BM25 检索器，包含 index_document()、load()、search(query, top_k=5)
CodeSplitter - 代码切分器，包含 split(docs: List[Document]) -> List[Document]
RePoLoader - 仓库加载器，包含 iter_file()、load() -> List[Document]
Query_rewriter - 查询改写器，包含 rewrite(raw_query) -> Query_rewrite_result
code_analyser - 代码分析器，包含 analyse(code) -> List[code_issue]、5 个私有检测方法
Query_rewrite_result - 数据类，包含 raw_query、dense_query
API 模型类
ChatRequest - 聊天请求模型
ChatResponse - 聊天响应模型
CodeAnalyseRequest - 代码分析请求
DockerfileRequest - Dockerfile 生成请求
LogAnalyseRequest - 日志分析请求
核心函数
safe_json_loads(s: str) -> dict - 安全的 JSON 解析，处理 ```json 标记、空值、异常
analyse_code(code: str) - 执行完整的代码分析，返回问题报告
search_codebase(query: str, top_k: int = 6) -> str - 搜索代码库，返回 JSON 格式结果
code_completion(context: str) - 代码补全工具函数
gen_tests(code: str, description: str) -> str - 生成单元测试
gen_docker_file(project_description: str) -> str - 生成 Dockerfile
analyse_log(log: str) -> str - 分析错误日志
_tokenize(text: str) -> List[str] - 私有分词器，使用正则表达式 r"[^A-Za-z0-9_]+" 切分
检测方法（AST 分析）
_check_mutable_default_args(tree: ast.AST) - 检测可变默认参数
_check_bare_except(tree: ast.AST) - 检测裸 except
_check_function_length(tree: ast.AST) - 检测函数过长（>50 行）
_check_complexity(tree: ast.AST) - 检测圈复杂度过高
_check_unused_imports(code: str, tree: ast.AST) - 检测未使用的导入
_calc_complexity(node: ast.AST) -> int - 计算单个节点的圈复杂度
评估函数
hit_and_rr(docs: List[Document], expected_source) -> tuple - 计算 Hit 和 RR 指标
【常见开发者场景】
场景 1：代码质量审查与规范检查
用户需求 - "帮我检查这段代码有什么问题"、"这个函数圈复杂度太高吗？"
触发工具 - code_analyser（AST 分析）
返回内容 - 可变默认参数、裸 except、过长函数、高复杂度、未使用导入的清单
典型对话 - 严谨的架构师或代码审查官
场景 2：源码定位与知识库检索
用户需求 - "def index_document 是怎么定义的"、"混合检索怎么实现"、"BM25 分词用的什么算法"
触发工具 - search_codebase（RAG 混合检索 + Query Rewriter）
返回内容 - 相关代码片段、文件位置、上下文
典型对话 - 新手实习生、快速学习者
场景 3：错误堆栈与日志分析
用户需求 - 贴上 Traceback 或错误日志，要求根本原因分析
触发工具 - log_analyser_llm
返回内容 - 错误类型、关键位置、修复方案、预防建议
典型对话 - 焦头烂额的 Debugger，遇到诡异报错
场景 4：代码补全与续写
用户需求 - 提供函数上下文，要求补全剩余代码
触发工具 - complete_code_llm
返回内容 - 可运行的代码补全部分（不重复已有内容）
典型对话 - 新人快速开发、Pair Programming
场景 5：单元测试生成
用户需求 - "为这个函数生成 pytest 测试"、"覆盖边界情况"
触发工具 - generate_tests_llm
返回内容 - pytest 风格的测试代码、覆盖正常/边界情况、使用 fixture 或参数化
典型对话 - 代码洁癖的架构师
场景 6：容器化与部署配置
用户需求 - "根据项目描述生成 Dockerfile"、"如何打包这个 Python 项目"
触发工具 - docker_file_llm
返回内容 - 优化的 Dockerfile、合适的基础镜像、非 root 用户、健康检查命令
典型对话 - 准备上线的 DevOps
场景 7：噪声数据处理与查询改写测试
用户需求 - "妈妈，请帮我找一下切分文本的函数定义 def，呜呜呜......"（极度口语化、中英混杂）
触发工具 - query_rewriter（改写为"切分文本 TextSplitter Document Chunk split"）→ search_codebase
返回内容 - 对应的代码片段
典型对话 - 非英语母语者、极简主义黑客、真实用户场景
【系统架构设计细节】
工作流程
用户提问 → DevAgent.chat() 接收
LLM 根据 Tool Schema 判断是否需要调用工具
若需要检索 → Query Rewriter 改写 → VectorStore（Dense + BM25） 混合搜索
若需要分析代码 → AST 分析器执行
若需要生成内容 → 相应的 LLM 工具函数
结果汇总 → LLM 生成最终回复 → 返回给用户
向量库三层架构
第一层 - Document 加载：RePoLoader 递归加载所有支持的文件
第二层 - 切分处理：CodeSplitter 针对不同文件类型（Python vs 文本）进行不同策略的分块
第三层 - 索引存储：VectorStore 同时维护 Chroma（Dense）和 BM25（Sparse）两个索引，支持 RRF 融合
配置管理
.env 文件管理敏感信息（API Key）
config.py 统一配置入口，支持多个 LLM 提供商（DeepSeek、OpenAI、Qwen）
支持本地 Embedding（HuggingFace）和云端 Embedding（OpenAI、Qwen）切换"""

DATA_GENERATOR_PROMPT = f"""
你是一个AI 数据集构建者。我正在训练一个私有化的代码 Agent (DevAgent)，需要你生成 20 条多样的高质量的 Function Calling 训练数据。

【项目真实背景与黑话】
{PROJECT_CONTEXT}
请在生成用户提问时，大量，有多样性，随机且自然地使用上述文件和专有名词，模拟真实的开发者语气。

【Agent 当前严格的工具列表与参数要求（务必遵守）】
1. 工具名: `analyse_code`
   - 触发场景: 静态代码问题分析。
   - 参数: {{"code": "<必填，一段存在潜在问题的 Python 源代码>"}}
2. 工具名: `search_codebase`
   - 触发场景: 询问某个模块、逻辑在哪，或者查询配置。
   - 参数: {{"query": "<必填，已做扩展的检索关键词/短句>", "top_k": <选填整数，默认6>}}
3. 工具名: `analyse_log`
   - 触发场景: 报错信息、异常堆栈分析。
   - 参数: {{"log": "<必填，一段包含 traceback 的报错文本>"}}
4. 工具名: `generate_dockerfile`
   - 触发场景: 容器化配置、Docker 打包需求。
   - 参数: {{"project_description": "<必填，项目运行环境或依赖描述>"}}
5. 工具名: `generate_tests`
   - 触发场景: 要求写单元测试（pytest）或边界覆盖。
   - 参数: {{"code": "<必填，需要被测试的函数代码>", "description": "<选填，额外补充说明>"}}
6. 工具名: `complete_code`
   - 触发场景: 续写残缺代码。
   - 参数: {{"context": "<必填，用户已有的残缺代码>"}}

【任务要求】
请在这 6 个工具中**随机分配**生成 20 条数据。
返回格式必须是严格的 JSON 数组，格式如下：
[
  {{
    "user_query": "结合背景信息生成的逼真的提问",
    "tool_name": "必须是上述 6 个工具名之一",
    "arguments": {{"严格按照对应工具的参数要求填入真实的 mock 数据，例如参数需要代码就填入真实 Python 代码，需要日志就填入日志段"}}
  }}
]
"""


def generate_batch(batch_index,max_retries=3):
    # 每次随机挑一个场景注入到 Prompt 里
    current_scenario = random.choice(SCENARIOS)
    print(f"批次 {batch_index} 随机场景注入: {current_scenario[:15]}...")
    
    dynamic_prompt = DATA_GENERATOR_PROMPT + f"\n\n【本批次特殊场景限制（极其重要）】\n请基于以下场景和语气来生成这 20 条数据，确保与之前生成的风格截然不同：\n{current_scenario}"

    config = types.GenerateContentConfig(
        system_instruction=dynamic_prompt,
        response_mime_type="application/json", # Gemini 特性：强制输出纯 JSON
        temperature=1
    )
    

    print("正在请求大模型生成数据...")
     
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3-flash-preview", 
                config=config,
                contents=["请生成 20 条高质量、Json格式正确的数据。"],
            )
            
             # 2. 获取文本内容（Gemini 是直接 .text，没有 choices）
            raw_text = response.text
            
            # 3. 清理可能残留的 markdown 标记
            raw_text = raw_text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:]
            if raw_text.endswith("```"):
                raw_text = raw_text[:-3]
            raw_text = raw_text.strip()

            # 4. 解析为 JSON
            data = json.loads(raw_text)
            
            # 兼容大模型有时包一层 {"data": [...]} 的情况
            if isinstance(data, dict):
                for key in data:
                    if isinstance(data[key], list):
                        return data[key]
            return data if isinstance(data, list) else []
            
        except Exception as e:
            # 捕获网络断开、JSON 解析失败等所有异常
            print(f"[批次 {batch_index}] 第 {attempt + 1} 次请求失败: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 4 # 递增等待：3秒, 6秒...
                print(f" 等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                print(f"[批次 {batch_index}] 连续 {max_retries} 次失败，跳过本批次。")
                return [] # 重试 3 次都不行，直接放弃这一批，防止死循环


if __name__ == "__main__":
    all_data = []
    BATCH_COUNT = 25 # 直接跑 25 批，生成 500 条
    
    for i in range(BATCH_COUNT):
        batch = generate_batch(i + 1)
        if batch:
            all_data.extend(batch)
            print(f" [批次 {i+1}] 成功，新增 {len(batch)} 条。当前总计: {len(all_data)} 条。")
            
            # 为了防止触发Rate Limit，每次请求后强制睡 4 秒
            time.sleep(4) 
        
    with open("devagent_raw_data.json", "w", encoding="utf-8") as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    
    print(f"\成功生成 {len(all_data)} 条带有项目特征的数据，已保存到 devagent_raw_data.json！")
