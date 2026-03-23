# External clones

第三方大仓库克隆目录；内容默认 **不提交**（见仓库根 `.gitignore`），仅本 README 纳入版本控制。

## 当前基准（Transformers + FastAPI）

| 仓库 | 路径 | 上游 | 版本 pin（`main`/`master` 浅克隆） |
|------|------|------|-------------------------------------|
| 🤗 Transformers | `transformers/` | [huggingface/transformers](https://github.com/huggingface/transformers) | `3a3b59cb1a7c0238c8d1072e35d3879c5faff48e` |
| FastAPI | `fastapi/` | [fastapi/fastapi](https://github.com/fastapi/fastapi) | `64feaec80244578bbdabe51e866bcfad1df8b708` |

克隆方式（在 `experiments/external/` 下执行；默认 **浅克隆** 以节省时间与磁盘）：

```bash
git clone --depth 1 --single-branch https://github.com/huggingface/transformers.git transformers
git clone --depth 1 --single-branch https://github.com/fastapi/fastapi.git fastapi
```

需要完整历史时在各自目录内执行：`git fetch --unshallow`。

更新基准后请运行 `git rev-parse HEAD` 将新 **commit** 填回上表。

## 其他示例（OpenClaw 等）

```bash
git clone <REPO_URL> <dirname>
cd <dirname> && git rev-parse HEAD
```
