# 检索评估：Query Rewrite 消融实验

## 实验设置

- 数据集：18 条口语化评估 query
- 改写方式：LLM Query Expansion

## 改写示例

| 改写前 | 改写后 |
|--------|--------|
| 妈妈，请帮我找一找一下切分文本的函数定义def，呜呜呜。。。。。 | 切分文本 TextSplitter Document Chunk 函数定义 def |
| 那个叫啥 index_document 的函数具体在哪儿定义的来着？ | index_document 函数 定义 位置 |
| 兄弟帮我找一下搜索代码 search 那个 def，急用 | search 代码 def 搜索函数 |
| 咱存数据的那个大管家 class VectorStore 写在哪个文件里了？ | VectorStore class 存储 数据 文件 |

## 结果对比

| 引擎 | 改写前 MRR | 改写后 MRR | 变化 |
|------|------------|------------|------|
| Dense | 0.810 | **0.944** | **+16.5%** |
| Hybrid | 0.709 | 0.747 | +5.4% |
| BM25 | 0.444 | 0.426 | -4% |

## 结论

Query Rewrite 对 Dense 检索效果提升显著，口语化问题转换为技术关键词后 MRR 提升 16%。
