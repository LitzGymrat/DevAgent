## E2E Bad case（首轮 baseline）
- **文件**：`data/e2e_eval_log.jsonl`
- **样本数**：90
- **软熔断阈值（文档/默认）**：T = 1.12（与 `eval_e2e_pipeline --soft-fuse-threshold` 一致时 Chroma distance > T 记为触发）

### L1 False Positive（不应检索却检索）
共 **33** 条（紧凑表）。

| sample_id | bucket | top1_distance | soft_fallback | vs T |
|-----------|--------|---------------|---------------|------|
| `p01` | domain | 0.8197611570358276 | False | ≤ 1.12 |
| `d01` | far_general | 1.2205226421356201 | True | > 1.12 |
| `d02` | far_general | 0.8592137694358826 | False | ≤ 1.12 |
| `d04` | far_general | 1.3560473918914795 | True | > 1.12 |
| `d05` | far_general | 1.002838373184204 | False | ≤ 1.12 |
| `d06` | far_general | 1.2228138446807861 | True | > 1.12 |
| `d07` | far_general | 1.1268192529678345 | True | > 1.12 |
| `d08` | far_general | 1.309748649597168 | True | > 1.12 |
| `d09` | far_general | 1.1761362552642822 | True | > 1.12 |
| `d10` | far_general | 1.0919067859649658 | False | ≤ 1.12 |
| `d11` | far_general | 1.2428724765777588 | True | > 1.12 |
| `d12` | far_general | 1.1786577701568604 | True | > 1.12 |
| `d13` | far_general | 1.2893445491790771 | True | > 1.12 |
| `d14` | far_general | 1.2606326341629028 | True | > 1.12 |
| `d15` | far_general | 1.3010362386703491 | True | > 1.12 |
| `d16` | far_general | 1.1677165031433105 | True | > 1.12 |
| `d17` | far_general | 1.3602519035339355 | True | > 1.12 |
| `d18` | far_general | 1.2289659976959229 | True | > 1.12 |
| `d19` | far_general | 1.1746248006820679 | True | > 1.12 |
| `d20` | far_general | 1.3679906129837036 | True | > 1.12 |
| `q18` | far_general | 1.02961266040802 | False | ≤ 1.12 |
| `q20` | far_general | 1.0698280334472656 | False | ≤ 1.12 |
| `q01` | term_near_no_rag | 0.7858739495277405 | False | ≤ 1.12 |
| `q09` | term_near_no_rag | 0.736729085445404 | False | ≤ 1.12 |
| `q10` | term_near_no_rag | 1.213059663772583 | True | > 1.12 |
| `q17` | term_near_no_rag | 0.6804316639900208 | False | ≤ 1.12 |
| `m01` | misleading_edge | 0.676812469959259 | False | ≤ 1.12 |
| `m02` | misleading_edge | 0.6448119878768921 | False | ≤ 1.12 |
| `m03` | misleading_edge | 0.46772176027297974 | False | ≤ 1.12 |
| `m04` | misleading_edge | 0.7862778306007385 | False | ≤ 1.12 |
| `m05` | misleading_edge | 0.8784002065658569 | False | ≤ 1.12 |
| `m06` | misleading_edge | 0.7910059094429016 | False | ≤ 1.12 |
| `m09` | misleading_edge | 0.8891786336898804 | False | ≤ 1.12 |


### L1 False Negative（应检索却未检索，`should_call_tool=yes`）
*（无）*

### L2 软熔断子集（实际检索 + gold 要求误调应熔断）
| sample_id | bucket | top1_distance | soft_fallback_triggered | 同时是 L1 FP |
|-----------|--------|---------------|-------------------------|-------------|
| `d01` | far_general | 1.2205226421356201 | True | True |
| `d02` | far_general | 0.8592137694358826 | False | True |
| `d04` | far_general | 1.3560473918914795 | True | True |
| `d05` | far_general | 1.002838373184204 | False | True |
| `d06` | far_general | 1.2228138446807861 | True | True |
| `d07` | far_general | 1.1268192529678345 | True | True |
| `d08` | far_general | 1.309748649597168 | True | True |
| `d09` | far_general | 1.1761362552642822 | True | True |
| `d10` | far_general | 1.0919067859649658 | False | True |
| `d11` | far_general | 1.2428724765777588 | True | True |
| `d12` | far_general | 1.1786577701568604 | True | True |
| `d13` | far_general | 1.2893445491790771 | True | True |
| `d14` | far_general | 1.2606326341629028 | True | True |
| `d15` | far_general | 1.3010362386703491 | True | True |
| `d16` | far_general | 1.1677165031433105 | True | True |
| `d17` | far_general | 1.3602519035339355 | True | True |
| `d18` | far_general | 1.2289659976959229 | True | True |
| `d19` | far_general | 1.1746248006820679 | True | True |
| `d20` | far_general | 1.3679906129837036 | True | True |
| `q18` | far_general | 1.02961266040802 | False | True |
| `q20` | far_general | 1.0698280334472656 | False | True |
| `q01` | term_near_no_rag | 0.7858739495277405 | False | True |
| `q09` | term_near_no_rag | 0.736729085445404 | False | True |
| `q10` | term_near_no_rag | 1.213059663772583 | True | True |
| `q17` | term_near_no_rag | 0.6804316639900208 | False | True |
| `m01` | misleading_edge | 0.676812469959259 | False | True |
| `m02` | misleading_edge | 0.6448119878768921 | False | True |
| `m03` | misleading_edge | 0.46772176027297974 | False | True |
| `m04` | misleading_edge | 0.7862778306007385 | False | True |
| `m05` | misleading_edge | 0.8784002065658569 | False | True |
| `m06` | misleading_edge | 0.7910059094429016 | False | True |
| `m09` | misleading_edge | 0.8891786336898804 | False | True |

子集内已熔断 **17/32**。
