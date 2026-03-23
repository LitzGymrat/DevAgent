# Badcase × Chroma `chroma.sqlite3` 直接审计

说明：读取 SQLite 表 `embedding_metadata` 中 `key='chroma:document'` 的**已入库全文**，判断题面中的代码型符号是否**字面出现在任意 chunk 里**（与向量检索是否召回到无关）。

- **配置中的持久化目录**：`Chroma_persist_dir` = `./data/chorma`
- **本报告主库**：`C:\Users\MilesZhu\DevAgent\data\chorma\chroma.sqlite3`（embeddings 行数 **26**，可解析文档块 **26**）

- **对照库**：`C:\Users\MilesZhu\DevAgent\data\Chroma\chroma.sqlite3`（embeddings **0**，块 **0**）

## 结论怎么用

| 符号在 **当前 src** | 符号在 **chroma.sqlite3 文本** | 含义 |
|---|---|---|
| 有 | 无 | 建库后源码已改 / 从未索引到该段 → **先重建索引**再评 E2E |
| 有 | 有 | 索引里有字，但检索仍差 → 查 query/嵌入/阈值，而非「库里没有」 |
| 无 | 无 | 题面超出仓库或 gold 过严 |

## 逐条 badcase（第二轮）

### p02

- **题干**：DevAgent 的 DevAgent.chat 里工具调用是怎么解析 JSON 的？
- **E2E**：`top1_distance=0.7353863716125488`，`soft_fallback_triggered=False`

| 符号 | 在主库 chunk 中出现？ | 命中的 source（若有） |
|------|----------------------|------------------------|
| `DevAgent` | 是 | agent\core.py, api\routes.py, main.py |

对照库 `C:\Users\MilesZhu\DevAgent\data\Chroma\chroma.sqlite3`：
- `DevAgent` → 无

### p08

- **题干**：analyse_code 工具主要做哪些静态分析？
- **E2E**：`top1_distance=None`，`soft_fallback_triggered=None`

| 符号 | 在主库 chunk 中出现？ | 命中的 source（若有） |
|------|----------------------|------------------------|
| `analyse_code` | 是 | api\routes.py |

对照库 `C:\Users\MilesZhu\DevAgent\data\Chroma\chroma.sqlite3`：
- `analyse_code` → 无

### p12

- **题干**：多轮对话记忆裁剪 _prune_memory 会丢掉什么消息？
- **E2E**：`top1_distance=1.0121188163757324`，`soft_fallback_triggered=False`

| 符号 | 在主库 chunk 中出现？ | 命中的 source（若有） |
|------|----------------------|------------------------|
| `_prune_memory` | **否** |  |

对照库 `C:\Users\MilesZhu\DevAgent\data\Chroma\chroma.sqlite3`：
- `_prune_memory` → 无

### p17

- **题干**：Query Rewriter 在检索里什么时候会改写 query？
- **E2E**：`top1_distance=0.8983399868011475`，`soft_fallback_triggered=False`

| 符号 | 在主库 chunk 中出现？ | 命中的 source（若有） |
|------|----------------------|------------------------|
| `Rewriter` | **否** |  |

对照库 `C:\Users\MilesZhu\DevAgent\data\Chroma\chroma.sqlite3`：
- `Rewriter` → 无

### p19

- **题干**：构建本地知识库的脚本一般在 scripts 目录叫什么？
- **E2E**：`top1_distance=1.1018381118774414`，`soft_fallback_triggered=False`

| 符号 | 在主库 chunk 中出现？ | 命中的 source（若有） |
|------|----------------------|------------------------|
| `scripts` | **否** |  （提示：`build_knowledge_base` 只索引 `src/`，**`scripts/` 不在向量库范围**） |

对照库 `C:\Users\MilesZhu\DevAgent\data\Chroma\chroma.sqlite3`：
- `scripts` → 无

### p27

- **题干**：Query Rewrite 的处理是在检索前哪个阶段执行的？
- **E2E**：`top1_distance=0.8289085030555725`，`soft_fallback_triggered=False`

| 符号 | 在主库 chunk 中出现？ | 命中的 source（若有） |
|------|----------------------|------------------------|
| `Rewrite` | **否** |  |

对照库 `C:\Users\MilesZhu\DevAgent\data\Chroma\chroma.sqlite3`：
- `Rewrite` → 无

### p29

- **题干**：DevAgent 的工具路由结果是如何组织成 JSON 输出的？
- **E2E**：`top1_distance=0.7950540781021118`，`soft_fallback_triggered=False`

| 符号 | 在主库 chunk 中出现？ | 命中的 source（若有） |
|------|----------------------|------------------------|
| `DevAgent` | 是 | agent\core.py, api\routes.py, main.py |

对照库 `C:\Users\MilesZhu\DevAgent\data\Chroma\chroma.sqlite3`：
- `DevAgent` → 无

### p30

- **题干**：为了防止重复调用和死循环，调用指纹机制是怎么实现的？
- **E2E**：`top1_distance=1.1770275831222534`，`soft_fallback_triggered=True`

- **题面可抽取符号**：无（多为中文题或短词）→ 需人工看 SQLite 全文或改题库关键词。

### p31

- **题干**：AST 静态分析器的入口函数在哪，主要检查了哪些反模式？
- **E2E**：`top1_distance=1.1572178602218628`，`soft_fallback_triggered=True`

- **题面可抽取符号**：无（多为中文题或短词）→ 需人工看 SQLite 全文或改题库关键词。

### p32

- **题干**：GitHub Actions CI 流水线里是如何集成 AST 静态分析器的？
- **E2E**：`top1_distance=1.1290849447250366`，`soft_fallback_triggered=True`

- **题面可抽取符号**：无（多为中文题或短词）→ 需人工看 SQLite 全文或改题库关键词。

### p34

- **题干**：Docker 配置生成工具的 prompt 或逻辑定义写在哪个文件里？
- **E2E**：`top1_distance=0.8942810297012329`，`soft_fallback_triggered=False`

| 符号 | 在主库 chunk 中出现？ | 命中的 source（若有） |
|------|----------------------|------------------------|
| `prompt` | 是 | agent\core.py, agent\llm.py |

对照库 `C:\Users\MilesZhu\DevAgent\data\Chroma\chroma.sqlite3`：
- `prompt` → 无

### p36

- **题干**：LoRA 微调模型的加载和动态挂载逻辑是在什么位置实现的？
- **E2E**：`top1_distance=1.1167607307434082`，`soft_fallback_triggered=False`

- **题面可抽取符号**：无（多为中文题或短词）→ 需人工看 SQLite 全文或改题库关键词。

### p37

- **题干**：项目里构造 6 类业务场景 SFT 数据的脚本或流程在哪？
- **E2E**：`top1_distance=1.050250768661499`，`soft_fallback_triggered=False`

- **题面可抽取符号**：无（多为中文题或短词）→ 需人工看 SQLite 全文或改题库关键词。

### p40

- **题干**：项目中如果检索结果质量较差，是否有相应的降级或熔断处理逻辑？
- **E2E**：`top1_distance=1.2037427425384521`，`soft_fallback_triggered=True`

- **题面可抽取符号**：无（多为中文题或短词）→ 需人工看 SQLite 全文或改题库关键词。

---

生成：`python scripts/analyze_badcase_chroma_sqlite.py`