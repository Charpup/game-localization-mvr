# 里程碑 B：normalize 错误码归类字典（v0.1）

- run_id: plc_run_b_202603211300
- scope: `milestone_B_execute`
- owner: Codex
- evidence_ready: false

## 错误码字典（草案）

| 错误码 | 语义 | 触发条件 | 修复动作 | 责任归属 |
|---|---|---|---|---|
| NORM-INPUT-EMPTY | 输入为空/不可解析 | 空行、None、空格串 | 回退占位并记录告警 | normalize_guard |
| NORM-SEGMENT-MISMATCH | 分段边界异常 | 分段前后长度或 token 异常 | 调整分段边界规则并补回归测试 | normalize_tagger |
| NORM-TAG-FORMAT | 标签格式不合法 | 见占位符或标签语法错误 | 标记为可修复失败并补规范约束 | normalize_ingest |
| NORM-UTF8-LOSS | 编码异常 | 非法字符导致编码转换 | 追加清洗并限制非法码点替换 | normalize_tag_llm |
| NORM-TRANSLATE-NULL | 翻译返回空 | LLM 输出空片段 | 重试路由 + 降级文本保持 | translate_llm |
| NORM-SCHEMA-DRIFT | 结构字段漂移 | 目标字段缺失/类型漂移 | 更新 schema 校验并补契约测试 | qa_hard |

## 观察/复测要求

- 每个错误码至少绑定 1 个 normalize 测试场景。
- 复测报告要输出为失败分桶：`错误码 -> 频次 -> 关联 fixture -> 关闭行动`。
- 与 glossary 任务联动时，统一保留字段：
  - error_code
  - normalized_value
  - translator_hint
  - repair_action

## 当前状态

- 本周期为草案阶段，未形成最终可执行闭环（等待 pytest 环境恢复后补齐自动化回归）。
