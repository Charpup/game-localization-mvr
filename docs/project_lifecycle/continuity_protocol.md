# 项目生命周期连续性协议（统一文档主干）

> 目的：把跨会话、跨上下文、跨设备的连续性，变成可执行、可验证、可恢复的“固定流程”。

## 1. 入口与单一真相源（SST，Single Source Trio）

每次会话开始必须按顺序读取：

1. `docs/HANDOFF_MAINLINE_GUARDRAILS.md`
2. `task_plan.md`
3. `docs/project_lifecycle/roadmap_index.md`

若三者冲突，以 `HANDOFF_MAINLINE_GUARDRAILS.md` + 最新 `task_plan.md` 的执行记录为准，并在
`docs/decisions/README.md` 与 `task_plan.md` 中补齐冲突说明。

## 2. 会话启动协议（session_start）

每次会话开始写：
`docs/project_lifecycle/run_records/YYYY-MM/YYYY-MM-DD/session_start_<YYYYMMDDHHMM>.md`

可复制 [session_start_template.md](D:/Dev_Env/GPT_Codex_Workspace/game-localization-mvr/main_worktree/docs/project_lifecycle/session_start_template.md)。

若你偏好短触发词，可直接约定使用 `plc`。

必须记录：

- 启动时间（ISO8601 + 时区）
- 读取版本（文件路径 + 文件 mtime）
- 当前 scope
- 本次最小交付目标
- `mini plan`（1-3 个 1h 子任务）
- 阻塞项（如果有）
- 下一步交接人（`next_owner`）

### 交接校验

- 必须确认 `docs/project_lifecycle/run_records/<YYYY-MM>/<YYYY-MM-DD>/milestone_state_<A-S>.md` 中至少一个可落地项的 `status=todo|in_progress`。
- 若里程碑依赖未满足，说明阻塞并打标 `blocked`。

## 3. 会话结束协议（session_end）

每次会话结束写：
`docs/project_lifecycle/run_records/YYYY-MM/YYYY-MM-DD/session_end_<YYYYMMDDHHMM>.md`

可复制 [session_end_template.md](D:/Dev_Env/GPT_Codex_Workspace/game-localization-mvr/main_worktree/docs/project_lifecycle/session_end_template.md)。

必须记录：

- 完成项（含文件路径）
- 未完成项 + 原因
- blocker list（JSON array）
- 证据清单（run_id、manifest、issue、verify）
- 资源建议：下一步 1h 子任务（含 owner/owner 备份）
- `next_owner` 与 `next_scope`

结束文件中的 `next_owner/next_scope` 与下次 `session_start` 强制一致校验。

## 4. 里程碑级收口标准

每个里程碑结束必须产生：

- `run_manifest`（字段见 `field_schema.md`）
- `issue_report`（问题分级与复现路径）
- `verify_report`（DoD 与再现命令）
- blocker list（含预期恢复动作、责任人、优先级）
- 里程碑状态更新（`task_plan.md` + 本文件）

任何缺失字段或证据项，视为未通过里程碑收口。

## 5. 证据链目录规范

推荐目录：

`docs/project_lifecycle/run_records/<YYYY-MM>/<YYYY-MM-DD>/`

文件命名建议：

- `run_manifest_<run_id>.json`
- `run_issue_<run_id>.md`
- `run_verify_<run_id>.md`
- `session_start_<timestamp>.md`
- `session_end_<timestamp>.md`
- `milestone_state_<A-S>.md`

可复制 [milestone_state_template.md](D:/Dev_Env/GPT_Codex_Workspace/game-localization-mvr/main_worktree/docs/project_lifecycle/milestone_state_template.md)。

## 6. 决策与 ADR 锚定

涉及以下内容的变更必须先有 ADR（至少 Proposed）后续 Accepted：

- 运行主链/脚本权威边界
- `src/scripts` 策略
- `task_plan` / 里程碑优先级重排
- 门禁、质量指标和验收标准变化
- 是否封装 skill 的决策（里程碑 S）

ADR 锚点规则：`decision_ref` 字段必须可逆向从里程碑状态映射到 `docs/decisions` 文件。

## 7. 质量闸与复审节奏

- 2 里程碑一次 mini review（看 `progress`, `evidence_ready`, `blockers`）
- 4 里程碑一次 governance brake（必要时暂停新增范围）
- 连续 2 次里程碑未通过 -> 冻结新增里程碑并补充回退路径
