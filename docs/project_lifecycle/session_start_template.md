# session_start 模板

- started_at: 2026-03-20T10:00:00+08:00
- owner: <owner_id>
- next_owner: <next_owner>
- scope: <A-S / 子任务>
- source_docs:
  - docs/HANDOFF_MAINLINE_GUARDRAILS.md (mtime: <ts>)
  - task_plan.md (mtime: <ts>)
  - docs/project_lifecycle/roadmap_index.md (mtime: <ts>)
  - docs/project_lifecycle/continuity_protocol.md (mtime: <ts>)
- milestone:
  - id: <A>
  - status: <todo|in_progress|blocked>
  - progress_pct: <0-100>
  - blockers: [<id>, <id>]
- plan_1h_chunks:
  - [<chunk_1>, <chunk_2>, <chunk_3>]
- verification_floor: [tests, checks, run scope]
- next_step_scope: <scope for next session>

