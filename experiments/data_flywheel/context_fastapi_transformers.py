"""
微调 / SFT 问答对生成用的「项目背景」：FastAPI + Transformers 完整要点（与 loRA/generate_lora_data_fastapi_transformers 对齐）。
六种语气 SCENARIOS；六工具约束在 generate_ft_qa_500.py 中组合。
"""

# 与 generate_lora_data_fastapi_transformers.py / generate_lora_data.py 一致
SCENARIOS = [
    "【场景：焦头烂额的 Debugger】语气急躁，遇到诡异的报错或者系统崩溃，急需用日志分析或代码检索定位问题。",
    "【场景：代码洁癖的架构师】语气严谨，非常关注代码规范、圈复杂度、测试覆盖率，经常要求用 AST 分析代码或补充边界测试。",
    "【场景：新入职的实习生】语气虚心，对项目架构不熟悉，经常询问某个类在哪、某个功能怎么实现，或者需要续写一半的代码。",
    "【场景：准备上线的 DevOps】只关心部署、环境依赖、Docker 打包、配置文件怎么写。",
    "【场景：极简主义黑客】说话极度简短，惜字如金。比如直接扔一段报错，或者只发一个文件名要求检查。",
    "【场景：非英语母语者】提问时中英文夹杂，比如 '帮我 check 一下这个 module 的 memory leak 问题'。",
]

PROJECT_CONTEXT_FASTAPI_TRANSFORMERS = """【仓库 A：Hugging Face transformers】

【仓库定位】
transformers 仓库是业界主流的自然语言处理（NLP）与多模态模型库，聚焦于提供统一、易用的 Transformer 架构模型（如 BERT、GPT、T5 等）的加载、训练、推理与微调能力。它服务于 AI 研究者、工程师和应用开发者，支持模型快速集成、迁移学习和大规模分布式训练。

【核心目录与关键文件】
src/transformers/：核心源码目录，包含模型定义、tokenizer、pipeline、训练与推理等主要实现。
src/transformers/models/：各类预训练模型的具体实现与配置，支持多种主流架构。
src/transformers/pipelines.py：统一的 pipeline 接口，封装常见 NLP 任务（如文本分类、问答、生成等）。
src/transformers/trainer.py：训练调度与分布式训练核心逻辑，支持多种训练场景。
src/transformers/tokenization_utils.py：分词器通用工具，处理文本到 token 的转换。
src/transformers/configuration_utils.py：模型配置管理，支持参数自动加载与保存。
src/transformers/modeling_utils.py：模型通用基类与权重管理。
examples/：官方示例脚本，涵盖训练、推理、微调等典型用法。
benchmark/：性能基准测试与评测工具。
pyproject.toml / setup.py：依赖与安装配置文件。

【核心业务概念与专有名词】
Transformer、Tokenizer、Pipeline、Trainer、Config、Checkpoint、PretrainedModel、AutoModel、AutoTokenizer、FeatureExtractor、Generation、Distributed Training、Fine-tuning、Model Hub、Task-specific Head、Attention Mask、HF（Hugging Face）Hub

【关键类名与函数名】
PreTrainedModel：所有模型的基类，封装权重加载与保存。
PreTrainedTokenizer：分词器基类，支持多种 tokenizer 实现。
Trainer：训练主类，负责训练循环、评估与分布式支持。
TrainingArguments：训练参数配置对象。
pipeline()：统一任务入口，自动加载模型与 tokenizer。
AutoModel / AutoTokenizer：根据配置自动选择合适模型/分词器。
save_pretrained() / from_pretrained()：模型与分词器的保存与加载方法。
DataCollator：数据批处理与动态 padding 工具。
GenerationMixin：文本生成相关方法的混入类。

【按工具能力组织的开发者场景 · transformers】
代码检索 / 实现定位
- 如何自定义一个新的 Transformer 模型并集成到 pipeline？
- Trainer 类如何支持多卡分布式训练，相关入口在哪里？
静态分析 / 风险扫描 / 代码规范检查
- 哪些模块存在未捕获异常或潜在的 None 引用风险？
- pipeline 接口是否有未遵循 PEP8 的实现或类型注解缺失？
单元测试生成 / 测试补全
- 如何为自定义 tokenizer 或模型头部补充单元测试？
- Trainer 的 callback 机制是否有测试覆盖遗漏？
日志排查 / Traceback 分析 / 报错归因
- from_pretrained 加载模型时报错，如何定位权重文件或配置缺失的根因？
- 分布式训练时出现梯度同步异常，日志中关键 traceback 如何解读？
Docker / 依赖 / 部署配置生成
- 如何为自定义 pipeline 生成最小化的 Dockerfile 及依赖清单？
- 部署 transformers 模型到生产环境时，如何配置多模型并发与资源隔离？
其它工程任务
- 如何将本地训练的模型上传到 Hugging Face Hub 并自动生成 README？
- 如何扩展 pipeline 支持新的多模态任务或自定义输入输出格式？

——————————————————————————————

【仓库 B：FastAPI】

【仓库定位】
FastAPI 是一个用于构建高性能 Web API 的 Python 框架，专注于异步编程和类型安全，面向需要快速开发、自动文档和高并发支持的后端开发者。它广泛应用于微服务、数据服务和现代 Web 应用的 API 层开发。

【核心目录与关键文件】
fastapi/__init__.py：框架主入口，定义核心 API 和导出主要对象。
fastapi/applications.py：定义 FastAPI 应用对象及其生命周期管理。
fastapi/routing.py：实现路由注册、请求分发和路径参数解析。
fastapi/dependencies/：依赖注入机制的实现，支持参数自动解析与校验。
fastapi/exceptions.py：定义框架内常见异常和错误处理逻辑。
fastapi/encoders.py：数据序列化与 JSON 编码相关工具。
fastapi/background.py：后台任务（BackgroundTask）机制实现。
docs/：官方文档源码，包含多语言教程和用法示例。
tests/：单元测试与集成测试用例，覆盖核心功能。
pyproject.toml：项目依赖、构建和元数据配置文件。

【核心业务概念与专有名词】
路径操作（Path Operation）
依赖注入（Dependency Injection）
请求体（Request Body）、响应模型（Response Model）
路由（Router）、中间件（Middleware）
异步支持（Async/Await）
自动文档（OpenAPI/Swagger UI/Redoc）
BackgroundTask、Exception Handler、Response、Request
Pydantic 模型、数据校验（Validation）

【关键类名与函数名】
FastAPI：主应用类，负责路由注册、生命周期管理。
APIRouter：用于模块化路由管理和分组。
Request/Response：请求与响应对象，封装 HTTP 交互。
Depends：依赖注入声明函数，自动解析依赖。
BackgroundTasks：后台任务调度与管理。
HTTPException：标准化 HTTP 错误抛出与处理。
add_api_route()：注册自定义路由的核心方法。
include_router()：将子路由集成到主应用。
exception_handler()：自定义异常处理器注册。
Body/Query/Path/Header/Cookie：参数声明与校验辅助对象。

【按工具能力组织的开发者场景 · FastAPI】
代码检索 / 实现定位
- 如何自定义全局异常处理器？相关实现在哪些模块？
- FastAPI 的依赖注入机制底层是如何解析和注入参数的？
静态分析 / 风险扫描 / 代码规范检查
- 路由函数参数类型声明不规范会导致哪些潜在问题？
- 框架中是否存在未捕获的异常或未处理的边界情况？
单元测试生成 / 测试补全
- 如何为自定义中间件或依赖函数自动生成测试用例？
- 路由注册和参数校验逻辑的测试覆盖率如何补全？
日志排查 / Traceback 分析 / 报错归因
- 如何定位某个请求处理过程中的异常来源及调用链？
- 框架启动时报错，如何分析依赖注入或路由注册的错误原因？
Docker / 依赖 / 部署配置生成
- 如何为 FastAPI 项目生成最小化的 Dockerfile 及依赖清单？
- 部署到生产环境时，如何配置 Uvicorn/Gunicorn 及环境变量？
其它工程任务
- 如何扩展 OpenAPI 文档或自定义接口文档展示？
- 如何集成第三方认证、权限或 CORS 配置到 FastAPI 应用？

——————————————————————————————

【与下游 Agent 工具的对应关系（生成 user_query 时请自然对齐）】
- 问「在哪、怎么实现、入口」→ 往往对应 search_codebase 或需要代码上下文的 complete_code。
- 问「代码问题、规范、风险」→ 往往对应 analyse_code（传入相关 Python 片段）。
- 问「日志、traceback、报错」→ 往往对应 analyse_log。
- 问「Docker、部署、依赖」→ 往往对应 generate_dockerfile。
- 问「测试、pytest、覆盖」→ 往往对应 generate_tests。
- 问「补全、续写函数」→ 往往对应 complete_code。"""
