- id: D
- status: in_progress
- owner: Codex
- next_owner: Codex
- progress_pct: 12
- evidence_ready: false
- blockers:
  - 基线样本漂移 checksum 与术语回顾脚本尚待首次运行
- dependencies: [C]
- decision_ref: null
- eta_hours: 16
- notes: >
  里程碑 D 目标是为“复核漂移”建立可复用底线：先建立 checksum 对账脚本与
  翻译漂移复测机制，再把复测动作嵌入 glossary 复核与 soft QA 的后置检查；
  下一步重点输出首次基线 run_id 与 D 里程碑验证手册。
- evidence:
  - run_id: plc_run_d_prepare
  - run_manifest: docs/project_lifecycle/run_records/2026-03/2026-03-21/run_manifest_plc_run_d_prepare.md
  - run_issue: docs/project_lifecycle/run_records/2026-03/2026-03-21/run_issue_plc_run_d_prepare.md
  - run_verify: docs/project_lifecycle/run_records/2026-03/2026-03-21/run_verify_plc_run_d_prepare.md
- handoff:
  - next_owner: Codex
  - next_scope: milestone_D_prepare
