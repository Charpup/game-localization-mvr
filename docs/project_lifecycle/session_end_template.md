# session_end 模板

- ended_at: 2026-03-20T10:00:00+08:00
- owner: <owner_id>
- completed:
  - [x] <milestone_or_task>
  - [ ] <milestone_or_task>
- run_records:
  - run_id: <run_id>
  - run_manifest: <path>
  - issue_report: <path>
  - verify_report: <path>
- blockers:
  - id: <B-001>
    description: <描述>
    next_action: <动作>
- evidence_ready: <true|false>
- decision_ref: <ADR path or null>
- next_owner: <user_or_agent>
- next_scope: <下次会话目标>
- handoff_check:
  - task_plan 更新: [done]
  - session_end 与下次 session_start 对齐: [done]

