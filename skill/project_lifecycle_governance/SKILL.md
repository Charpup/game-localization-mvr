# Project Lifecycle Governance

> Short trigger alias: use [`plc`](/D:/Dev_Env/GPT_Codex_Workspace/game-localization-mvr/main_worktree/skill/plc/SKILL.md) as a one-word shortcut.

## Overview

用于任何涉及 `A→S` 路线执行、跨会话交接、run 证据闭环、以及是否 skill 化决策推进的会话。  
该 skill 的目标是：保证每个会话都能从文档恢复，并把里程碑状态、决议、证据、阻塞项保持一致。

## 触发场景

- 需要读取当前里程碑状态与优先级
- 需要执行 `A→S` 的任一里程碑
- 需要会话接续（session_start / session_end）
- 需要新增/更新里程碑 evidence 或 ADR
- 需要确认 skill 化路径（里程碑 S）的执行分支

## 读文件顺序（必须）

1. `docs/HANDOFF_MAINLINE_GUARDRAILS.md`
2. `task_plan.md`
3. `docs/project_lifecycle/roadmap_index.md`
4. `docs/project_lifecycle/continuity_protocol.md`

冲突处理：以 1+2 为准，并在 4 中记录冲突修复动作。

## 里程碑执行工作流（1 小时单位）

1. 在 `docs/project_lifecycle/run_records/<YYYY-MM>/<YYYY-MM-DD>/session_start_<ts>.md` 记录会话入口。
2. 更新本里程碑状态字段（`status/progress_pct/evidence_ready`）。
3. 识别 blocker，并决定是否触发 governance brake。
4. 产出证据三件套（`run_manifest`, `run_issue`, `run_verify`）与对应 ADR 引用。
5. 会话结束前写 `session_end_<ts>.md`，带 `next_owner/next_scope`。
6. 在 `task_plan.md` 记录当次执行结果。
7. 将里程碑快照记录到 `docs/project_lifecycle/milestone_state_<A-S>.md`。

## 质量闸与复盘

- 每 2 个里程碑做一次 mini review。
- 每 4 个里程碑做一次 governance brake。
- 连续 2 次里程碑未通过收口 => 阻塞新增里程碑推进。

## 命令清单（建议）

- 新设备恢复：
  - 读取三源真相与里程碑快照
  - 校验 `session_end` 与里程碑状态映射
  - 验证最近一次 run 的 `run_manifest/run_issue/run_verify`
- 文件同步检查：
  - `task_plan.md` 中里程碑是否有与 `docs/project_lifecycle/roadmap_index.md` 一致状态
  - `decision_ref` 是否指向有效 ADR

## 输出模板索引

- `docs/project_lifecycle/continuity_protocol.md`（会话协议）
- `docs/project_lifecycle/roadmap_index.md`（A→S）
- `docs/project_lifecycle/field_schema.md`（字段标准）
- `docs/project_lifecycle/run_records/README.md`（证据链规范）
- `docs/project_lifecycle/decisions/index.md`（决策索引）
- `docs/project_lifecycle/session_start_template.md`
- `docs/project_lifecycle/session_end_template.md`
- `docs/project_lifecycle/milestone_state_template.md`
