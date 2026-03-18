# Issue 账本

## 当前高优先
- QA_HARD_WARNINGS (P2)
  - source_tag_unbalanced / empty_source_translation
  - 影响：决议保持 REWORK
- VERIFY_QA_WARNING (P2)
  - 与 qa_hard 串联
  - 影响：未形成 green gate

## 历史已处理
- LLM_CONNECTIVITY_FAIL (P0，历史窗口)：已通过 key/ping 验证恢复

## 风险
- 主脚本源漂移：存在 `main_worktree/scripts` 与 `src/scripts` 版本不一致风险
