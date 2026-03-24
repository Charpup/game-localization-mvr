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
decision_ref: string | null
eta_hours: integer | null
notes: string
```

## 2. Run 清单字段（最小集）

```yaml
run_id: string
run_scope: string
status: enum[pass, warn, blocked]
started_at: datetime_iso8601
finished_at: datetime_iso8601
owner: string
input_manifest: string (path)
issue_report_path: string (path)
verify_report_path: string (path)
artifacts: array[path]
blockers: array[object(id, description, next_action)]
decision_refs: array[path]
next_step_owner: string
next_step_scope: string
```

## 3. 会话交接字段

```yaml
date: date_iso8601
branch: string
current_scope: string
next_owner: string
next_scope: string
open_issues: array[string]
next_action: string
validation_mode: string
smoke_required: boolean
```

## 4. markdown 工件约定

### session_start

- 顶层必填字段：
  - `date`
  - `branch`
  - `current_scope`
  - `route`
- 必填 section：
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
  - `Handoff`

### milestone_state

- 顶层必填字段：
  - `id`
  - `status`
  - `owner`
  - `next_owner`
  - `progress_pct`
  - `evidence_ready`
  - `decision_ref`
- 必填 section：
  - `evidence`
  - `handoff`

