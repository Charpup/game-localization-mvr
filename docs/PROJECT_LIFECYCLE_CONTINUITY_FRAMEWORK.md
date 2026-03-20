# Project Lifecycle Continuity Framework

> 目标：把项目执行从“当前会话记忆”升级为“跨会话/跨上下文可追踪的项目知识系统”。

## 统一主干（新入口）

核心文档集中到：

- `D:/Dev_Env/GPT_Codex_Workspace/game-localization-mvr/main_worktree/docs/project_lifecycle/roadmap_index.md`
- `D:/Dev_Env/GPT_Codex_Workspace/game-localization-mvr/main_worktree/docs/project_lifecycle/continuity_protocol.md`
- `D:/Dev_Env/GPT_Codex_Workspace/game-localization-mvr/main_worktree/docs/project_lifecycle/field_schema.md`
- `D:/Dev_Env/GPT_Codex_Workspace/game-localization-mvr/main_worktree/docs/project_lifecycle/run_records/README.md`
- `D:/Dev_Env/GPT_Codex_Workspace/game-localization-mvr/main_worktree/docs/project_lifecycle/decisions/index.md`

## 三层职责（兼容旧入口）

1. `task_plan.md`：历史执行账本（执行记录、run 对齐）。
2. `ROADMAP_A_TO_S.md`：兼容入口（保持最小可读摘要）。
3. `docs/decisions/` 与 `docs/decisions/ADR-*.md`：决策治理（Proposed/Accepted）。
4. 上述 1~3 的统一索引：`docs/project_lifecycle/*`。

## 运行一致性规则

1. 每次会话开始必须先读：
   - `docs/HANDOFF_MAINLINE_GUARDRAILS.md`
   - `task_plan.md`
   - `docs/project_lifecycle/roadmap_index.md`
   - `docs/project_lifecycle/continuity_protocol.md`
2. 所有关键变更必须有 ADR（先 Proposed，后 Accepted + 证据）。
3. 里程碑收口必须有 `run_manifest`、`run_issue`、`run_verify` 与 ADR 锚点。
4. 时间使用 ISO8601 时区格式（如 `2026-03-20T14:00:00+08:00`）。

## 质量与恢复性

- 可发现性：固定入口 + 字段标准 + 标准模板。
- 可追溯性：每次行动可回溯到 run + ADR + task_plan 状态。
- 可控性：阻塞项、governance brake、回退路径必须记录。
- 可恢复性：会话交接严格按 `session_start`/`session_end` 文件化。

