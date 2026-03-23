# 软熔断 Phase1 Bad Case 报告
- 数据源: `data/soft_fuse/soft_fuse_phase1_raw_promptv2.json`
- 域内距离: min=0.5021 max=1.1832 mean=0.8383
- 参考阈值: **1.12**（distance > 阈值 ⇒ 拦截）

## A. 域内 top1 距离偏高（软熔断易误伤 / 召回看起来「差」）
- **p30** dist=1.1832 src=`agent\core.py`  
  为了防止重复调用和死循环，调用指纹机制是怎么实现的？
- **p31** dist=1.1410 src=`api\routes.py`  
  AST 静态分析器的入口函数在哪，主要检查了哪些反模式？
- **p36** dist=1.1225 src=`rag\vectorstore.py`  
  LoRA 微调模型的加载和动态挂载逻辑是在什么位置实现的？
- **p38** dist=1.0901 src=`evaluation\eva_retrieval.py`  
  上下文过滤和滑动窗口优化是在推理链路的哪个阶段做的？
- **p32** dist=1.0797 src=`rag\loader.py`  
  GitHub Actions CI 流水线里是如何集成 AST 静态分析器的？
- **p13** dist=1.0340 src=`main.py`  
  Streamlit Web UI 的入口文件名是什么？
- **p09** dist=1.0325 src=`agent\core.py`  
  生成单元测试对应哪个工具函数？
- **p15** dist=0.9946 src=`rag\vectorstore.py`  
  RRF 融合里平滑常数 c 取多少？
- **p37** dist=0.9895 src=`evaluation\rag_dataset.py`  
  项目里构造 6 类业务场景 SFT 数据的脚本或流程在哪？
- **p08** dist=0.9831 src=`api\routes.py`  
  analyse_code 工具主要做哪些静态分析？
- **p12** dist=0.9630 src=`agent\core.py`  
  多轮对话记忆裁剪 _prune_memory 会丢掉什么消息？
- **p22** dist=0.9619 src=`api\routes.py`  
  项目中负责接收用户问题并分发工具调用的核心逻辑在哪个模块？

## B. 域外合并但距离 ≤ 域内 max(1.1832) — 与域内分布重叠
共 **28** 条（含远域 / 术语近 / 误导 三桶）。
- **m01** (misleading_edge) dist=0.4975 src=`main.py`  
  DevAgent 这种项目里一般为什么要用 FastAPI？
- **m03** (misleading_edge) dist=0.5821 src=`rag\vectorstore.py`  
  Chroma 和 BM25 哪个更适合做通用知识问答？
- **q08** (term_near_no_rag) dist=0.6381 src=`rag\bm25.py`  
  什么是 BM25？
- **q01** (term_near_no_rag) dist=0.7161 src=`main.py`  
  FastAPI 的路由怎么注册？
- **m02** (misleading_edge) dist=0.7745 src=`main.py`  
  如果要在 FastAPI 里注册一个新路由，通常该怎么写？
- **q07** (term_near_no_rag) dist=0.8277 src=`rag\loader.py`  
  LangChain 是做什么用的？
- **m04** (misleading_edge) dist=0.8533 src=`agent\core.py`  
  LoRA 为什么适合做小模型微调，这和 DevAgent 有什么关系？
- **m05** (misleading_edge) dist=0.8705 src=`agent\core.py`  
  如果一个 Agent 老是死循环调用工具，通常有哪些通用解决思路？
- **m06** (misleading_edge) dist=0.8757 src=`evaluation\eva_retrieval.py`  
  Query Rewrite 一般是怎么提升检索效果的？
- **q09** (term_near_no_rag) dist=0.8980 src=`rag\vectorstore.py`  
  什么是向量数据库？
- **m10** (misleading_edge) dist=0.9197 src=`agent\core.py`  
  Function Calling 和普通 Prompt 问答相比，最大的区别是什么？
- **m09** (misleading_edge) dist=0.9575 src=`evaluation\rag_dataset.py`  
  RAG 系统里为什么会出现幻觉，通常怎么缓解？
- **q17** (term_near_no_rag) dist=0.9751 src=`evaluation\rag_dataset.py`  
  什么是 RAG？
- **d07** (far_general) dist=1.0336 src=`agent\core.py`  
  Docker 构建每次都要重新 pip install，镜像层缓存像没命中，可能哪里出了问题？
- **d10** (far_general) dist=1.0430 src=`main.py`  
  前端 dev 正常，打包上线后静态资源 404，多半是 publicPath、路由模式还是部署路径哪类问题？
- **q20** (far_general) dist=1.0495 src=`rag\bm25.py`  
  heapq 在 Python 里怎么用？
- **d05** (far_general) dist=1.0718 src=`agent\core.py`  
  requirements 里写了包名，运行却报 No module named，先检查虚拟环境、路径还是安装方式？
- **q16** (term_near_no_rag) dist=1.0837 src=`rag\vectorstore.py`  
  什么是余弦相似度？
- **d09** (far_general) dist=1.1031 src=`api\routes.py`  
  接口返回 401 和 403，排障时一般怎么判断是 token 无效还是权限不足？
- **q02** (far_general) dist=1.1206 src=`main.py`  
  Python 的装饰器怎么写？
- **d02** (far_general) dist=1.1231 src=`main.py`  
  浏览器里前端请求后端报 CORS 被拦截，后端侧通常要动哪些配置？
- **m07** (misleading_edge) dist=1.1239 src=`agent\core.py`  
  GitHub Actions 里为什么常常要做代码质量检查？
- **d16** (far_general) dist=1.1494 src=`evaluation\eva_retrieval.py`  
  接口变慢怀疑 ORM 打出 N+1，日志或 profiling 上怎么快速验证？
- **d01** (far_general) dist=1.1535 src=`api\routes.py`  
  线上接口偶发 502，从网关、负载均衡到上游服务一般按什么顺序排查？

… 其余 4 条略。

## C. 术语接近不该查库 — top1 距离最低（易与仓库片段撞语义）
- **q08** dist=0.6381 src=`rag\bm25.py`  
  什么是 BM25？
- **q01** dist=0.7161 src=`main.py`  
  FastAPI 的路由怎么注册？
- **q07** dist=0.8277 src=`rag\loader.py`  
  LangChain 是做什么用的？
- **q09** dist=0.8980 src=`rag\vectorstore.py`  
  什么是向量数据库？
- **q17** dist=0.9751 src=`evaluation\rag_dataset.py`  
  什么是 RAG？
- **q16** dist=1.0837 src=`rag\vectorstore.py`  
  什么是余弦相似度？
- **q13** dist=1.1832 src=`agent\core.py`  
  Dockerfile 和 docker-compose 有什么区别？
- **q12** dist=1.1917 src=`agent\core.py`  
  GitHub Actions 的基本作用是什么？
- **q10** dist=1.2252 src=`agent\llm.py`  
  LoRA 微调的原理是什么？
- **q06** dist=1.2751 src=`rag\bm25.py`  
  什么是 Transformer？
- **q11** dist=1.3143 src=`api\routes.py`  
  什么是 JSON Schema？
- **q14** dist=1.3340 src=`rag\loader.py`  
  什么是 AST（抽象语法树）？

## D. 明显通用远域 — top1 距离最低（远域桶内仍「像库内」的条目）
- **d07** dist=1.0336 src=`agent\core.py`  
  Docker 构建每次都要重新 pip install，镜像层缓存像没命中，可能哪里出了问题？
- **d10** dist=1.0430 src=`main.py`  
  前端 dev 正常，打包上线后静态资源 404，多半是 publicPath、路由模式还是部署路径哪类问题？
- **q20** dist=1.0495 src=`rag\bm25.py`  
  heapq 在 Python 里怎么用？
- **d05** dist=1.0718 src=`agent\core.py`  
  requirements 里写了包名，运行却报 No module named，先检查虚拟环境、路径还是安装方式？
- **d09** dist=1.1031 src=`api\routes.py`  
  接口返回 401 和 403，排障时一般怎么判断是 token 无效还是权限不足？
- **q02** dist=1.1206 src=`main.py`  
  Python 的装饰器怎么写？
- **d02** dist=1.1231 src=`main.py`  
  浏览器里前端请求后端报 CORS 被拦截，后端侧通常要动哪些配置？
- **d16** dist=1.1494 src=`evaluation\eva_retrieval.py`  
  接口变慢怀疑 ORM 打出 N+1，日志或 profiling 上怎么快速验证？
- **d01** dist=1.1535 src=`api\routes.py`  
  线上接口偶发 502，从网关、负载均衡到上游服务一般按什么顺序排查？
- **q15** dist=1.1545 src=`agent\core.py`  
  Python 中 try/except 的作用是什么？
- **q18** dist=1.1573 src=`rag\loader.py`  
  如何在 Python 中读取一个 txt 文件？
- **d06** dist=1.1619 src=`evaluation\eva_retrieval.py`  
  表数据量没怎么涨，但某条 SQL 突然变慢，先看执行计划、索引还是锁等待比较划算？

## E. 误导边界 — top1 距离最低（诱导查库时向量仍很近）
- **m01** dist=0.4975 src=`main.py`  
  DevAgent 这种项目里一般为什么要用 FastAPI？
- **m03** dist=0.5821 src=`rag\vectorstore.py`  
  Chroma 和 BM25 哪个更适合做通用知识问答？
- **m02** dist=0.7745 src=`main.py`  
  如果要在 FastAPI 里注册一个新路由，通常该怎么写？
- **m04** dist=0.8533 src=`agent\core.py`  
  LoRA 为什么适合做小模型微调，这和 DevAgent 有什么关系？
- **m05** dist=0.8705 src=`agent\core.py`  
  如果一个 Agent 老是死循环调用工具，通常有哪些通用解决思路？
- **m06** dist=0.8757 src=`evaluation\eva_retrieval.py`  
  Query Rewrite 一般是怎么提升检索效果的？
- **m10** dist=0.9197 src=`agent\core.py`  
  Function Calling 和普通 Prompt 问答相比，最大的区别是什么？
- **m09** dist=0.9575 src=`evaluation\rag_dataset.py`  
  RAG 系统里为什么会出现幻觉，通常怎么缓解？
- **m07** dist=1.1239 src=`agent\core.py`  
  GitHub Actions 里为什么常常要做代码质量检查？
- **m08** dist=1.1932 src=`api\routes.py`  
  AST 静态分析一般能发现哪些类型的问题？

## F. 阈值 T=1.12 下的明细（域内 vs 域外合并）
- 域内被拦 (**误伤**): 3/40
  - p30 dist=1.1832 — 为了防止重复调用和死循环，调用指纹机制是怎么实现的？…
  - p31 dist=1.1410 — AST 静态分析器的入口函数在哪，主要检查了哪些反模式？…
  - p36 dist=1.1225 — LoRA 微调模型的加载和动态挂载逻辑是在什么位置实现的？…
- 域外未拦 (**漏拦**): 19/50
  - d05 (far_general) dist=1.0718 — requirements 里写了包名，运行却报 No module named，先检查虚拟环境、路径还是安装方式？…
  - d07 (far_general) dist=1.0336 — Docker 构建每次都要重新 pip install，镜像层缓存像没命中，可能哪里出了问题？…
  - d09 (far_general) dist=1.1031 — 接口返回 401 和 403，排障时一般怎么判断是 token 无效还是权限不足？…
  - d10 (far_general) dist=1.0430 — 前端 dev 正常，打包上线后静态资源 404，多半是 publicPath、路由模式还是部署路径哪类问题？…
  - q20 (far_general) dist=1.0495 — heapq 在 Python 里怎么用？…
  - q01 (term_near_no_rag) dist=0.7161 — FastAPI 的路由怎么注册？…
  - q07 (term_near_no_rag) dist=0.8277 — LangChain 是做什么用的？…
  - q08 (term_near_no_rag) dist=0.6381 — 什么是 BM25？…
  - q09 (term_near_no_rag) dist=0.8980 — 什么是向量数据库？…
  - q16 (term_near_no_rag) dist=1.0837 — 什么是余弦相似度？…
  - q17 (term_near_no_rag) dist=0.9751 — 什么是 RAG？…
  - m01 (misleading_edge) dist=0.4975 — DevAgent 这种项目里一般为什么要用 FastAPI？…
  - m02 (misleading_edge) dist=0.7745 — 如果要在 FastAPI 里注册一个新路由，通常该怎么写？…
  - m03 (misleading_edge) dist=0.5821 — Chroma 和 BM25 哪个更适合做通用知识问答？…
  - m04 (misleading_edge) dist=0.8533 — LoRA 为什么适合做小模型微调，这和 DevAgent 有什么关系？…
  - m05 (misleading_edge) dist=0.8705 — 如果一个 Agent 老是死循环调用工具，通常有哪些通用解决思路？…
  - m06 (misleading_edge) dist=0.8757 — Query Rewrite 一般是怎么提升检索效果的？…
  - m09 (misleading_edge) dist=0.9575 — RAG 系统里为什么会出现幻觉，通常怎么缓解？…
  - m10 (misleading_edge) dist=0.9197 — Function Calling 和普通 Prompt 问答相比，最大的区别是什么？…
