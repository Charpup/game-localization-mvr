# 里程碑 B：normalize 错误码归类字典（v0.2）

- run_id: plc_run_b_202603211300
- scope: `milestone_B_execute`
- owner: Codex
- evidence_ready: true
- status: pass

## 错误码字典（v0.2）

| 错误码 | 语义 | 触发条件 | 修复动作 | 责任归属 | 复测 |
|---|---|---|---|---|---|
| NORM-INPUT-EMPTY | 输入为空/不可解析 | 空行、None、空格串 | 回退占位并记录告警 | normalize_guard | covered |
| NORM-SEGMENT-MISMATCH | 分段边界异常 | 分段前后长度或 token 异常 | 调整分段边界规则并补回归测试 | normalize_tagger | covered |
| NORM-TAG-FORMAT | 标签格式不合法 | 占位符或标签语法错误 | 标记为可修复失败并补规范约束 | normalize_ingest | covered |
| NORM-UTF8-LOSS | 编码异常 | 非法字符导致编码转换 | 追加清洗并限制非法码点替换 | normalize_tag_llm | covered |
| NORM-TRANSLATE-NULL | 翻译返回空 | LLM 输出空片段 | 重试路由 + 降级文本保持 | translate_llm | pending |
| NORM-SCHEMA-DRIFT | 结构字段漂移 | 目标字段缺失/类型漂移 | 更新 schema 校验并补契约测试 | qa_hard | covered |

## 备注

- 本阶段覆盖了 `covered` 标记的六类失败码中 5 类；`NORM-TRANSLATE-NULL` 为后续里程碑 C 预留任务。
- 当前字典将作为 `B 关键交付` 入库，待 `C` 将错误码闭环扩展到 `glossary` 复用面。
