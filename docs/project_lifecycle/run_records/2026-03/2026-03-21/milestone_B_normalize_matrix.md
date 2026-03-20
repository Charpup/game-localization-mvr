# 里程碑 B：normalize 用例矩阵（v0.1）

- run_id: plc_run_b_202603211300
- scope: `milestone_B_execute`
- owner: Codex
- evidence_ready: false

## 一、测试目标

- 覆盖 normalize 主链路的边界、回归、字段漂移与失败码映射场景。
- 为后续 `fixture` 与 `error_code` 归类提供输入依据。

## 二、矩阵（待补齐）

| 类别 | 场景 | 输入示例 | 预期失败码 / 行为 | 对应测试文件 |
|---|---|---|---|---|
| 边界 | 空输入 | `""`、`None` | 输入校验失败/降级规则返回 | tests/test_normalize_segmentation.py |
| 边界 | Unicode / Emoji | 混合表情字符 | unicode 安全归一化且不丢失标点 | tests/test_normalize_auxiliary_contract.py |
| 回归 | 版本化占位符 | 含版本占位符样例 | 保留模板位与占位变量 | tests/test_normalize_auxiliary_contract.py |
| 回归 | 标签噪音 | 非标准标签嵌套 | 归一化失败并产生日志码 | tests/test_normalize_auxiliary_contract.py |
| 失败码 | 错误映射链条 | 输入格式异常 | 落到统一错误码表并标注修复动作 | tests/test_normalize_segmentation.py |
| 失败码 | 边界异常 | 字段缺失/类型不匹配 | fallback 行为+错误码归档 | tests/test_normalize_auxiliary_contract.py |

## 三、下一步待执行（本周期）

- `tests/test_normalize_auxiliary_contract.py::test_normalize_error_code_contract`（新建）
- `tests/test_normalize_segmentation.py` 覆盖新增边界分支
- `tests/test_glossary_review.py`（若可复用）补齐失败码断言

## 四、当前缺口

- 当前测试文件仍需新建/补充失败码断言用例条目
- fixture 样本尚未与该矩阵逐条对齐
- 复测链尚未形成 `coverage + 失败分桶` 的固定报告
