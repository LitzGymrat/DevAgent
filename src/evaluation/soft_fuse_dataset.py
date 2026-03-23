"""
软熔断 / 工具路由评测用 Query 集。

规模：
  - 40 道域内（本仓库可定位答案）
  - 域外拆为三桶（共 50 条）：
      · 明显通用远域 — 排障/基础语法与算法，与仓库术语弱相关
      · 术语接近但不该查库 — 概念与仓库技术栈重叠，但答案应来自通识而非翻本仓库
      · 误导边界 — 诱导「像要查库」或项目名挂钩，但与本仓库弱相关

Phase 1：可分桶看 top-1 距离；合并域外 50 条可做整体阈值标定。
"""

# --- 域内 40：应被主链路当作「有效召回」---
DOMAIN_IN_PROJECT: list[dict] = [
    {"id": "p01", "query": "FastAPI 里路由是怎么注册到应用上的？"},
    {"id": "p02", "query": "DevAgent 的 DevAgent.chat 里工具调用是怎么解析 JSON 的？"},
    {"id": "p03", "query": "VectorStore 里 dense 检索和 RRF 混合检索分别在哪几个方法？"},
    {"id": "p04", "query": "search_codebase 工具返回给模型的 JSON 结构是什么？"},
    {"id": "p05", "query": "BM25 索引默认持久化到哪个文件路径？"},
    {"id": "p06", "query": "代码切块 Chunk 是在哪个模块里做的？"},
    {"id": "p07", "query": "如何用 Qwen 的 text-embedding-v4 做嵌入？"},
    {"id": "p08", "query": "analyse_code 工具主要做哪些静态分析？"},
    {"id": "p09", "query": "生成单元测试对应哪个工具函数？"},
    {"id": "p10", "query": "Dockerfile 自动生成走哪个 Python 模块？"},
    {"id": "p11", "query": "settings 里 embedding_provider 可以填哪些值？"},
    {"id": "p12", "query": "多轮对话记忆裁剪 _prune_memory 会丢掉什么消息？"},
    {"id": "p13", "query": "Streamlit Web UI 的入口文件名是什么？"},
    {"id": "p14", "query": "FastAPI 聊天接口挂载在哪个路由下面？"},
    {"id": "p15", "query": "RRF 融合里平滑常数 c 取多少？"},
    {"id": "p16", "query": "Chroma 向量库从磁盘 load 时在 VectorStore 哪个方法？"},
    {"id": "p17", "query": "Query Rewriter 在检索里什么时候会改写 query？"},
    {"id": "p18", "query": "日志诊断 analyse_log 工具怎么接到 Agent 里的？"},
    {"id": "p19", "query": "构建本地知识库的脚本一般在 scripts 目录叫什么？"},
    {"id": "p20", "query": "向量持久化目录 Chroma_persist_dir 在配置里怎么配？"},
    {"id": "p21", "query": "DevAgent 里 FastAPI 的接口路由是怎么组织和注册的？"},
    {"id": "p22", "query": "项目中负责接收用户问题并分发工具调用的核心逻辑在哪个模块？"},
    {"id": "p23", "query": "DevAgent 是如何封装 Function Calling 工具列表的？"},
    {"id": "p24", "query": "项目里 search_codebase 工具的实现流程是怎样的？"},
    {"id": "p25", "query": "Chroma 向量库是在什么位置初始化的，是否做了单例预热？"},
    {"id": "p26", "query": "代码仓库文档切分的逻辑写在哪，使用了什么 chunk 策略？"},
    {"id": "p27", "query": "Query Rewrite 的处理是在检索前哪个阶段执行的？"},
    {"id": "p28", "query": "项目中 Dense 检索的 embedding 模型调用逻辑在哪？"},
    {"id": "p29", "query": "DevAgent 的工具路由结果是如何组织成 JSON 输出的？"},
    {"id": "p30", "query": "为了防止重复调用和死循环，调用指纹机制是怎么实现的？"},
    {"id": "p31", "query": "AST 静态分析器的入口函数在哪，主要检查了哪些反模式？"},
    {"id": "p32", "query": "GitHub Actions CI 流水线里是如何集成 AST 静态分析器的？"},
    {"id": "p33", "query": "日志分析工具在项目里是如何解析输入日志并生成结果的？"},
    {"id": "p34", "query": "Docker 配置生成工具的 prompt 或逻辑定义写在哪个文件里？"},
    {"id": "p35", "query": "项目中的 RAG 检索评测脚本是如何计算 MRR 的？"},
    {"id": "p36", "query": "LoRA 微调模型的加载和动态挂载逻辑是在什么位置实现的？"},
    {"id": "p37", "query": "项目里构造 6 类业务场景 SFT 数据的脚本或流程在哪？"},
    {"id": "p38", "query": "上下文过滤和滑动窗口优化是在推理链路的哪个阶段做的？"},
    {"id": "p39", "query": "Streamlit 前端是如何把用户提问、工具返回和模型回答串起来的？"},
    {"id": "p40", "query": "项目中如果检索结果质量较差，是否有相应的降级或熔断处理逻辑？"},
]

# --- 域外 ① 明显通用远域：线上排障 + 语言/算法基础，不宜与「本仓库专属实现」绑定 ---
OUTDOMAIN_FAR_GENERAL: list[dict] = [
    {"id": "d01", "query": "线上接口偶发 502，从网关、负载均衡到上游服务一般按什么顺序排查？"},
    {"id": "d02", "query": "浏览器里前端请求后端报 CORS 被拦截，后端侧通常要动哪些配置？"},
    {"id": "d03", "query": "容器里 curl 本机端口正常，宿主机映射端口却访问不通，常见原因有哪些？"},
    {"id": "d04", "query": "Git push 提示 non-fast-forward，本地还有未推送提交，想先同步远端再推上去，常规怎么做？"},
    {"id": "d05", "query": "requirements 里写了包名，运行却报 No module named，先检查虚拟环境、路径还是安装方式？"},
    {"id": "d06", "query": "表数据量没怎么涨，但某条 SQL 突然变慢，先看执行计划、索引还是锁等待比较划算？"},
    {"id": "d07", "query": "Docker 构建每次都要重新 pip install，镜像层缓存像没命中，可能哪里出了问题？"},
    {"id": "d08", "query": "数据库报 Too many connections，更像是连接池配小了还是连接没释放？"},
    {"id": "d09", "query": "接口返回 401 和 403，排障时一般怎么判断是 token 无效还是权限不足？"},
    {"id": "d10", "query": "前端 dev 正常，打包上线后静态资源 404，多半是 publicPath、路由模式还是部署路径哪类问题？"},
    {"id": "d11", "query": "Linux 磁盘写满导致服务起不来，先找大文件、清日志还是扩盘，一般什么顺序？"},
    {"id": "d12", "query": "同一条流水线同一分支有时过有时挂，代码没变，先怀疑依赖锁版本、网络还是 runner 环境？"},
    {"id": "d13", "query": "移动端或 H5 访问 HTTPS 报证书错误，除了过期还经常碰到证书链不完整吗？"},
    {"id": "d14", "query": "微服务 A 调 B 超时，B 的 CPU 不高，先查 B 的线程池、下游依赖还是 A 的重试退避？"},
    {"id": "d15", "query": "本地能连 Redis，线上同密码同端口连不上，除了白名单还要核对 bind、TLS、集群地址吗？"},
    {"id": "d16", "query": "接口变慢怀疑 ORM 打出 N+1，日志或 profiling 上怎么快速验证？"},
    {"id": "d17", "query": "主从同步延迟突然变大，大事务、网络抖动、从库负载，一般先查哪类指标？"},
    {"id": "d18", "query": "接口做了幂等键还是偶尔重复扣款，除了幂等表还要查消息重投、超时重试吗？"},
    {"id": "d19", "query": "线上堆栈里的行号和本地对不上，通常说明构建产物、source map 还是部署版本哪边不一致？"},
    {"id": "d20", "query": "K8s 里 Pod 一直 Pending，节点资源够的话，先看调度事件、亲和性还是 PVC 绑定？"},
    {"id": "q02", "query": "Python 的装饰器怎么写？"},
    {"id": "q03", "query": "什么是快速排序？"},
    {"id": "q04", "query": "二分查找的时间复杂度是多少？"},
    {"id": "q05", "query": "Python 里 list 和 tuple 有什么区别？"},
    {"id": "q15", "query": "Python 中 try/except 的作用是什么？"},
    {"id": "q18", "query": "如何在 Python 中读取一个 txt 文件？"},
    {"id": "q19", "query": "什么是 BFS 和 DFS？"},
    {"id": "q20", "query": "heapq 在 Python 里怎么用？"},
]

# --- 域外 ② 术语接近但不该查库：与 RAG/嵌入/工程栈词面重叠，答案应以通识为主 ---
OUTDOMAIN_TERM_NEAR_NO_RAG: list[dict] = [
    {"id": "q01", "query": "FastAPI 的路由怎么注册？"},
    {"id": "q06", "query": "什么是 Transformer？"},
    {"id": "q07", "query": "LangChain 是做什么用的？"},
    {"id": "q08", "query": "什么是 BM25？"},
    {"id": "q09", "query": "什么是向量数据库？"},
    {"id": "q10", "query": "LoRA 微调的原理是什么？"},
    {"id": "q11", "query": "什么是 JSON Schema？"},
    {"id": "q12", "query": "GitHub Actions 的基本作用是什么？"},
    {"id": "q13", "query": "Dockerfile 和 docker-compose 有什么区别？"},
    {"id": "q14", "query": "什么是 AST（抽象语法树）？"},
    {"id": "q16", "query": "什么是余弦相似度？"},
    {"id": "q17", "query": "什么是 RAG？"},
]

# --- 域外 ③ 误导边界：带项目名或强诱导「像要翻代码」，但与本仓库实现弱相关 ---
OUTDOMAIN_MISLEADING_EDGE: list[dict] = [
    {"id": "m01", "query": "DevAgent 这种项目里一般为什么要用 FastAPI？"},
    {"id": "m02", "query": "如果要在 FastAPI 里注册一个新路由，通常该怎么写？"},
    {"id": "m03", "query": "Chroma 和 BM25 哪个更适合做通用知识问答？"},
    {"id": "m04", "query": "LoRA 为什么适合做小模型微调，这和 DevAgent 有什么关系？"},
    {"id": "m05", "query": "如果一个 Agent 老是死循环调用工具，通常有哪些通用解决思路？"},
    {"id": "m06", "query": "Query Rewrite 一般是怎么提升检索效果的？"},
    {"id": "m07", "query": "GitHub Actions 里为什么常常要做代码质量检查？"},
    {"id": "m08", "query": "AST 静态分析一般能发现哪些类型的问题？"},
    {"id": "m09", "query": "RAG 系统里为什么会出现幻觉，通常怎么缓解？"},
    {"id": "m10", "query": "Function Calling 和普通 Prompt 问答相比，最大的区别是什么？"},
]

# 全部域外（50）
PHASE1_OUTDOMAIN_ALL: list[dict] = (
    OUTDOMAIN_FAR_GENERAL + OUTDOMAIN_TERM_NEAR_NO_RAG + OUTDOMAIN_MISLEADING_EDGE
)

# 兼容旧导入名（结构已变，仅避免静默 import 失败）
PHASE1_PRIVATE_IN_DOMAIN = DOMAIN_IN_PROJECT
PHASE1_DEV_SCENARIO = OUTDOMAIN_FAR_GENERAL[:20]
PHASE1_GENERAL = OUTDOMAIN_TERM_NEAR_NO_RAG
PHASE1_MISLEADING = OUTDOMAIN_MISLEADING_EDGE
PHASE1_GENERIC = OUTDOMAIN_FAR_GENERAL
