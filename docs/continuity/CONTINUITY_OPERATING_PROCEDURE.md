# 跨会话/跨上下文作业手册（历史路径兼容）

> 该文件保持路径兼容性。正式治理口径统一到：
> `docs/project_lifecycle/continuity_protocol.md`

## 1. 启动前读取

按顺序读取并记录版本：

1. `docs/HANDOFF_MAINLINE_GUARDRAILS.md`
2. `task_plan.md`
3. `docs/project_lifecycle/roadmap_index.md`
4. `docs/project_lifecycle/continuity_protocol.md`

## 2. 会话文件（建议）

- `docs/project_lifecycle/run_records/<YYYY-MM>/<YYYY-MM-DD>/session_start_<ts>.md`
- `docs/project_lifecycle/run_records/<YYYY-MM>/<YYYY-MM-DD>/session_end_<ts>.md`
- `docs/project_lifecycle/run_records/<YYYY-MM>/<YYYY-MM-DD>/milestone_state_<A-S>.md`

## 3. 收口规则（里程碑）

- 每个里程碑至少一套：`run_manifest/run_issue/run_verify`
- `decision_ref` 必须可追溯到 `docs/decisions` 的 ADR
- 交接字段必须在下一次启动文件中复用

