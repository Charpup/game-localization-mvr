# 里程碑与 run 记录字段规范

> 机器可校验的单一合同源见 `workflow/plc_governance_contract.yaml`。
> 本文件保留为人读规范，与合同文件保持同语义。

## 1. 里程碑状态字段

```yaml
id: string (A-Z)
status: enum[todo, in_progress, blocked, done, shelved]
owner: string
next_owner: string
progress_pct: integer(0-100)
evidence_ready: boolean
blockers: array[string]
dependencies: array[string]
decision_ref: path | null
eta_hours: integer | null
notes: string
changed_files: array[path]
evidence_refs: array[path | command:<shell command>]
adr_refs: array[path in docs/decisions | none]
evidence:
  run_id: string
  run_manifest: path
  run_issue: path
  run_verify: path
handoff:
  next_owner: string
  next_scope: string
  next_action: string
```

## 2. Run 清单字段（最小集）

```yaml
manifest_version: string
run_id: string
run_scope: string
status: enum[pass, warn, blocked]
started_at: datetime_iso8601
finished_at: datetime_iso8601
owner: string
input_manifest: path
issue_report_path: path
verify_report_path: path
artifacts: array[path]
blockers: array[object | string]
changed_files: array[path]
evidence_refs: array[path | command:<shell command>]
adr_refs: array[path in docs/decisions | none]
decision_refs: array[string]
evidence_ready: boolean
next_step_owner: string
next_step_scope: string
gate_result: enum[pass, warn, blocked] | optional
```

## 3. 会话交接字段

```yaml
date: date_iso8601
branch: string
current_scope: string
route: string
base_branch: string
Context:
  read_versions: array[object(file, mtime)]
  blockers: array[string | none]
Slice:
  bounded_implementation_target: string
  mini_plan: array[string]
Validation_Decision:
  validation_mode: string
  smoke_run: enum[required, not required for this slice, skipped by design]
  rationale: string
Governance:
  changed_files: array[path]
  evidence_refs: array[path | command:<shell command>]
  adr_refs: array[path in docs/decisions | none]
  blocker_list: array[string | none]
Handoff:
  next_owner: string
  next_scope: string
  open_issues: array[string | none]
  next_hour_task: string
  next_action: string
```

## 4. markdown 工件约定

### session_start

- 顶层必填字段：
  - `date`
  - `branch`
  - `current_scope`
  - `route`
  - `base_branch`
- 必填 section：
  - `Context`
  - `Slice`
  - `Validation Decision`
  - `Handoff`

### session_end

- 顶层必填字段：
  - `date`
  - `branch`
  - `current_scope`
  - `slice_status`
- 必填 section：
  - `Delivered Surface`
  - `Acceptance`
  - `Outcome`
  - `Governance`
  - `Handoff`

### milestone_state

- 顶层必填字段：
  - `id`
  - `status`
  - `owner`
  - `next_owner`
  - `progress_pct`
  - `evidence_ready`
  - `blockers`
  - `dependencies`
  - `decision_ref`
  - `eta_hours`
  - `notes`
  - `changed_files`
  - `evidence_refs`
  - `adr_refs`
  - `evidence`
  - `handoff`

## 5. 三点校验定义（Phase 2 Closeout）

- `changed_files`：本次交付实际变更或明确受影响的文件路径，必须存在于仓库中。
- `evidence_refs`：测试命令、验证报告、run artifact 的可追溯引用。
  - 文件路径必须存在。
  - 命令引用统一使用 `command:<shell command>` 形式。
- `adr_refs`：与本次交付相关的 ADR 路径。
  - 若当前无新增 ADR 但需要显式说明，可写 `none`。
  - 非 `none` 值必须落在 `docs/decisions/` 下。
