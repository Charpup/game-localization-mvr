# session_start

- date: `2026-03-28`
- owner: `Codex`
- scope: `phase5_phase6_human_ui_acceptance`
- branch: `codex/phase6-operator-workspace-dashboard`
- route: `plc + triadev`
- objective:
  - prepare deterministic data and a live server for human UI acceptance
  - verify the current merged Phase 5 + 6 surface in `phase6_dashboard_worktree`
  - hand off a concrete Wave A + Wave B checklist to the human operator
- preparation_steps:
  - `python -m pytest tests/test_phase5_acceptance_gate.py -q`
  - `python -m pytest tests/test_phase6_acceptance_gate.py -q`
  - `python -m pytest tests/test_seed_phase6_manual_uat.py -q`
  - `python scripts/seed_phase6_manual_uat.py`
  - `python scripts/llm_ping.py`
  - `python scripts/operator_ui_server.py --host 127.0.0.1 --port 8765`
