# run_issue

- run_id: `plc_phase5_frontend_runtime_shell_acceptance_20260327`
- status: `closed_with_env_blocker`
- blockers: `none`
- env_blockers:
  - `ACC-ENV-001`: `python scripts/llm_ping.py` failed because `LLM_BASE_URL` and `LLM_API_KEY` are not set in the current environment.
- resolved:
  - `ACC-REAL-001`: `python scripts/operator_ui_server.py --host 127.0.0.1 --port 8765` originally failed with `ModuleNotFoundError: scripts`; the server entrypoint now bootstraps repo-root imports and is covered by `tests/test_operator_ui_server.py`.
  - `ACC-REAL-002`: real HTTP acceptance coverage now exists in `tests/test_phase5_acceptance_gate.py`, including `/`, `/app.js`, all four API contracts, negative cases, and pending launch visibility.
  - `ACC-REAL-003`: retained offline regression floor is green after the acceptance hardening changes.
