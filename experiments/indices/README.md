# 实验用索引（Chroma + BM25）

与主工程 `data/chorma`、`data/bm25_index.pkl` **隔离**，用于 `experiments/external/` 下的基准仓库。

## 布局

| 语料 | 源码目录（默认） | Chroma | BM25 |
|------|------------------|--------|------|
| transformers | `external/transformers/src/transformers` | `transformers/chroma/` | `transformers/bm25_index.pkl` |
| fastapi | `external/fastapi/fastapi` | `fastapi/chroma/` | `fastapi/bm25_index.pkl` |

## 构建

### 如何一直看到进度条（推荐）

在 **Cursor / VS Code 集成终端**里**前台**运行下面命令（不要用后台任务跑），才能实时看到 **tqdm** 进度条：

- 打开终端：按 **Ctrl+反引号**（键盘左上角，`Esc` 下方、数字 `1` 左侧）或菜单 **查看 → 终端**
- 在仓库根目录执行 `python scripts/build_experiment_indices.py ...`

由 AI/脚本在后台执行时，进度条往往不会出现在你当前窗口里；需要盯进度时请自己在终端里跑。

若仍几乎无输出：用无缓冲模式运行，并注意进度会打到 **stderr**（与 tqdm 一致）：

```bash
python -u scripts/build_experiment_indices.py --corpus transformers
```

---

在仓库根目录执行。**默认使用 Qwen 嵌入**（与主工程 `src/config.py` 一致），需在 `.env` 中配置 `qwen_api_key`、`qwen_base_url` 等。

```bash
# 两套都打（Qwen 嵌入）
python scripts/build_experiment_indices.py --corpus all

# 仅 transformers / 仅 fastapi
python scripts/build_experiment_indices.py --corpus transformers
```

离线或节省 API 时，显式加 `--local` 使用本地 HuggingFace 嵌入：

```bash
python scripts/build_experiment_indices.py --corpus all --local
```

脚本会显示 **tqdm 进度条**：加载文件、切分 chunk、Chroma 分批嵌入、BM25；长时间无输出时请看是否卡在「Chroma 嵌入」某一批。默认 **`--batch-size` 为 256**；若 API 限流或报错，可改为 `128`。

本目录下二进制与 sqlite **不提交**（见根目录 `.gitignore`）。

### 嵌入维度报错（Chroma）

若出现 `Collection expecting embedding with dimension of 384, got 1024` 之类错误，说明磁盘上**旧 Chroma** 是用另一种嵌入模型建的（例如先 `--local` 再改 Qwen）。**每次运行** `build_experiment_indices.py` 会先清理该语料下的旧 `chroma/` 与 `bm25_index.pkl` 再重建；若仍报错，请手动删掉 `experiments/indices/<语料>/chroma` 后重跑。
