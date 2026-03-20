# 里程碑 B：fixture 报表（草案 v0.1）

- run_id: plc_run_b_202603211300
- scope: `milestone_B_execute`
- owner: Codex
- evidence_ready: false

## 运行态说明

- 当前 pytest 基础设施异常，无法稳定执行完整回归。先以“采集模板 + 已知缺口”方式沉淀，待环境恢复后补充真实数据。

## 报表字段（预期）

- fixture_id
- test_file
- scenario
- fail_count
- fail_bucket（错误码）
- root_cause
- action
- owner

## 目录与文件（本周期）

- `tests/test_normalize_auxiliary_contract.py`
- `tests/test_normalize_segmentation.py`
- `tests/test_glossary_review.py`（预期新增）
- `tests/test_qa_hard.py`（复用健康检查）

## 初始覆盖情况（当前）

- 样本覆盖：`20`（计划）
- 已覆盖：`4`（已对齐现有 normalize 核心文件）
- 缺口：`16`（待补齐 normalize 边界与错误码场景）

## 下一步输出（恢复后）

- 用命令形成覆盖表：`python -m pytest --collect-only -q` 与关键用例逐条执行结果
- 输出失败分桶统计并映射到 `milestone_B_error_taxonomy.md`
- 与 triadev run 验证串联：在 `run_verify` 写入“coverage -> fail bucket -> trend”
