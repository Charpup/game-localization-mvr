# 里程碑 B：normalize 用例矩阵（v0.2）

- run_id: plc_run_b_202603211300
- scope: `milestone_B_execute`
- owner: Codex
- evidence_ready: true
- status: pass

## 一、覆盖目标

- 覆盖 normalize 主链路边界、回归、字段漂移与失败码映射。
- 与 `fixture_report` / `error_taxonomy` 做闭环映射，确保每类失败码有至少一条对应场景。

## 二、覆盖矩阵（当前执行结果）

| 类别 | 场景 | 输入示例 | 预期失败码 / 行为 | 对应测试文件 | 执行结果 |
|---|---|---|---|---|---|
| 边界 | 空输入 | `""`、`None` | 输入校验失败或降级规则返回 | tests/test_normalize_segmentation.py | pass |
| 边界 | Unicode / Emoji | 混合表情字符 | unicode 安全归一化且不丢失标点 | tests/test_normalize_auxiliary_contract.py | pass |
| 回归 | 版本化占位符 | 含版本占位符样例 | 保留模板位与占位变量 | tests/test_normalize_auxiliary_contract.py | pass |
| 回归 | 标签噪音 | 非标准标签嵌套 | 归一化失败并产生日志码 | tests/test_normalize_auxiliary_contract.py | pass |
| 失败码 | 错误映射链条 | 输入格式异常 | 落到统一错误码表并标注修复动作 | tests/test_normalize_segmentation.py | pass |
| 失败码 | 边界异常 | 字段缺失/类型不匹配 | fallback 行为+错误码归档 | tests/test_normalize_auxiliary_contract.py | pass |

## 三、统计与交付

- 目标场景：6
- 已执行场景：6
- 通过率：100%
- 复测命令：`python -m pytest tests/test_normalize_auxiliary_contract.py tests/test_normalize_segmentation.py -q`
- 关键结果：`8 passed`

## 四、与错误码字典映射

- NORM-INPUT-EMPTY：边界空输入场景命中
- NORM-SEGMENT-MISMATCH：分段边界异常场景命中
- NORM-TAG-FORMAT：标签格式异常场景命中
- NORM-SCHEMA-DRIFT：字段缺失场景命中
