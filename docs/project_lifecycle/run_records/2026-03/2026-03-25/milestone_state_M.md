- id: M
- status: in_progress
- owner: Codex
- next_owner: Codex
- progress_pct: 15
- evidence_ready: false
- blockers: []
- dependencies: [E]
- decision_ref: docs/decisions/ADR-0002-skill-governance-framework.md
- eta_hours: 10
- notes: >
  Phase 2 governance substrate first package is active. The current slice freezes a
  machine-checkable governance contract for run/session/milestone artifacts and adds a
  validator plus focused regression over representative PLC records.
- evidence:
  - run_id: phase2_governance_20260325
  - run_manifest: null
  - run_issue: null
  - run_verify: null
- handoff:
  - next_owner: Codex
  - next_scope: phase2_governance_contract_validator
