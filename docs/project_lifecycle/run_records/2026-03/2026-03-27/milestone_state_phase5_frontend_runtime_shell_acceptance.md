- id: phase5_frontend_runtime_shell_acceptance
- status: blocked
- owner: Codex
- next_owner: Codex
- progress_pct: 95
- evidence_ready: false
- design_ready: true
- blockers:
  - `ACC-ENV-001`: online representative-run acceptance is blocked until `LLM_BASE_URL` and `LLM_API_KEY` are available and `python scripts/llm_ping.py` passes
- dependencies:
  - Phase 5 offline shell contracts remain green
  - local Python runtime shell stays the only accepted Phase 5 UI surface
  - LLM environment must be present before Phase 5 can be marked fully accepted for implementation-gating
- decision_ref: `docs/project_lifecycle/run_records/2026-03/2026-03-27/run_verify_plc_phase5_frontend_runtime_shell_acceptance_20260327.md`
- notes: >
    Offline acceptance passed after hardening the real server entrypoint and adding an HTTP
    acceptance gate. Phase 5 is acceptable as a design gate for Phase 6, but not yet fully
    evidence-complete for direct downstream implementation because the online representative-run
    lane is environment-blocked.
