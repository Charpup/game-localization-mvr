# 里程碑 B：fixture 报表（v0.2）

- run_id: plc_run_b_202603211300
- scope: `milestone_B_execute`
- owner: Codex
- evidence_ready: true
- status: pass

## 一、运行摘要

- 运行命令：`python -m pytest tests/`
- 执行结果：`104 passed, 8 skipped`
- 采样源：`tests/test_normalize_auxiliary_contract.py`、`tests/test_normalize_segmentation.py`、`tests/test_glossary_review.py`（当前无新增用例）、`tests/test_qa_hard.py`
- normalize 专项复测：`python -m pytest tests/test_normalize_auxiliary_contract.py tests/test_normalize_segmentation.py -q`
- normalize 专项复测：`8 passed`

## 二、失败分桶（基于当前 run）

- 0 / pass=112（含 skipped）
- 0 / NORM-INPUT-EMPTY
- 0 / NORM-SEGMENT-MISMATCH
- 0 / NORM-TAG-FORMAT
- 0 / NORM-SCHEMA-DRIFT

## 三、fixture 覆盖映射（示例）

| fixture_id | test_file | scenario | fail_count | fail_bucket | root_cause | action |
|---|---|---|---:|---|---|---|
| normalize-empty-001 | tests/test_normalize_segmentation.py | 空输入防御 | 0 | NORM-INPUT-EMPTY | 输入校验返回降级结果 | 保持现有 fallback |
| normalize-unicode-001 | tests/test_normalize_auxiliary_contract.py | Unicode 输入 | 0 | NORM-UTF8-LOSS | 合法字符编码链路稳定 | 保持现有清洗策略 |
| normalize-placeholder-001 | tests/test_normalize_auxiliary_contract.py | 占位符保留 | 0 | NORM-TAG-FORMAT | 标签/占位映射链路正常 | 规则保持 |
| normalize-schema-001 | tests/test_normalize_auxiliary_contract.py | 缺失字段 | 0 | NORM-SCHEMA-DRIFT | schema 缺失校验通过 fail-fast | 继续沿用校验器 |

## 四、趋势与下一步

- 本周期未发现 normalize 归一化失败回归。
- 下一步建议：里程碑 C 将新增 `NORM-TRANSLATE-NULL` fixture 与 glossary 归类联动场景。
