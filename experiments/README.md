# Experiments

与主工程（`src/`、线上评测）**物理隔离**的实验区：大仓库基准、数据飞轮、SFT、SFL 等。

## 目录约定

| 路径 | 用途 |
|------|------|
| [`external/`](./external/) | 第三方大仓库克隆（默认不提交 blob，见该目录 README） |
| [`data_flywheel/`](./data_flywheel/) | 数据收集、标注、闭环；含 **FastAPI+Transformers 语境 500 条** FC 问答生成脚本 |
| [`sft/`](./sft/) | 监督微调：数据格式、训练入口、配置 |
| [`sfl/`](./sfl/) | 拆分联邦 / 相关分布式实验（按你方定义落地） |
| [`indices/`](./indices/) | 实验用 Chroma + BM25（与主仓 `data/` 隔离），见该目录 README |

## 原则

- **主仓只提交**：脚本、配置、小样本、版本 pin（commit / tag）、文档。
- **大依赖**：优先 `git submodule`，或克隆到 `external/`（已 ignore），在 README 里写死 commit。

## 默认大仓基准

Python 实验区默认使用 **[🤗 Transformers](https://github.com/huggingface/transformers)** + **[FastAPI](https://github.com/fastapi/fastapi)**，克隆与 **commit pin** 见 [`external/README.md`](./external/README.md)。

## 与 DevAgent 的关系

需要复用主仓代码时，从仓库根目录用 `PYTHONPATH` 或 `pip install -e .`，避免把 `src/` 拷进 `experiments/`。
