# 检索评估：Pool Size 对比实验

## 实验设置

- top_k = 8
- 对比池子大小：20 vs 10

## 第二组：池子 = 20

### 按提问类型

| 提问类型 | 引擎 | Hit_Rate | MRR |
|----------|------|----------|-----|
| exact_keyword | hybrid | 100.0% | 0.750 |
| exact_keyword | bm25 | 100.0% | 0.690 |
| exact_keyword | dense | 100.0% | 0.900 |
| chinese_semantic | hybrid | 40.0% | 0.080 |
| chinese_semantic | bm25 | 20.0% | 0.033 |
| chinese_semantic | dense | 80.0% | 0.467 |
| english_semantic | hybrid | 66.7% | 0.389 |
| english_semantic | bm25 | 66.7% | 0.381 |
| english_semantic | dense | 100.0% | 0.733 |
| mixed | hybrid | 80.0% | 0.700 |
| mixed | bm25 | 80.0% | 0.392 |
| mixed | dense | 100.0% | 0.617 |

### 全局结果

| 引擎 | Hit_Rate | MRR |
|------|----------|-----|
| hybrid | 72.2% | 0.490 |
| bm25 | 66.7% | 0.373 |
| dense | **94.4%** | **0.673** |

## 第三组：池子 = 10

### 按提问类型

| 提问类型 | 引擎 | Hit_Rate | MRR |
|----------|------|----------|-----|
| exact_keyword | bm25 | 100.0% | 0.690 |
| exact_keyword | dense | 100.0% | 0.900 |
| exact_keyword | hybrid | 100.0% | 0.750 |
| chinese_semantic | bm25 | 20.0% | 0.033 |
| chinese_semantic | dense | 80.0% | 0.467 |
| chinese_semantic | hybrid | 80.0% | 0.197 |
| english_semantic | bm25 | 66.7% | 0.381 |
| english_semantic | dense | 100.0% | 0.733 |
| english_semantic | hybrid | 100.0% | 0.456 |
| mixed | bm25 | 80.0% | 0.392 |
| mixed | dense | 100.0% | 0.617 |
| mixed | hybrid | 100.0% | 0.740 |

### 全局结果

| 引擎 | Hit_Rate | MRR |
|------|----------|-----|
| bm25 | 66.7% | 0.373 |
| dense | **94.4%** | **0.673** |
| hybrid | **94.4%** | 0.544 |

## 结论

- **池子=10** 时 Hybrid 与 Dense 全局 Hit 持平（94.4%），在 mixed 类型上 Hybrid MRR 甚至略优（0.740）。
- **池子=20** 时 Hybrid 只有 72% 命中，比 Dense 差一截。
- **调参发现**：
  - pool_size 太小：Hybrid 几乎变成 Dense-only
  - pool_size 太大：BM25 噪声太多，拉垮 Dense
  - 在当前语料 & query 分布下，**pool_size ≈ 10** 是 Hybrid 比较平衡的点

**选型建议**：Dense 主力，Hybrid 在调到合适配置后「至少不拉跨」，可作为 mixed 类型 query 的增强选项。
