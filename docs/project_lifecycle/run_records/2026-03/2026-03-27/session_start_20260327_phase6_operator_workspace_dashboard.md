# session_start

- date: `2026-03-27`
- owner: `Codex`
- scope: `phase6_operator_workspace_dashboard`
- branch: `codex/phase6-operator-workspace-dashboard`
- route: `plc + triadev`
- objective:
  - freeze the Phase 6 dashboard contract on fresh `main`
  - implement read-only workspace models and APIs over existing operator artifacts
  - preserve the accepted Phase 5 runtime shell while adding workspace mode and drilldown
- acceptance_floor:
  - `python -m pytest tests/test_operator_ui_workspace_models.py tests/test_operator_ui_workspace_server.py tests/test_phase6_operator_workspace_dashboard.py -q`
  - `python -m pytest tests/test_phase4_operator_control_plane.py tests/test_operator_ui_models.py tests/test_operator_ui_workspace_models.py tests/test_operator_ui_launcher.py tests/test_operator_ui_server.py tests/test_operator_ui_workspace_server.py tests/test_phase5_frontend_runtime_shell.py tests/test_phase6_operator_workspace_dashboard.py tests/test_phase5_acceptance_gate.py tests/test_smoke_verify.py tests/test_runtime_adapter_contract.py tests/test_batch6_repair_metrics_contract.py tests/test_validation_contract.py tests/test_qa_hard.py tests/test_script_authority.py tests/test_batch3_batch4_governance.py tests/test_plc_docs_contract.py -q`
  - `python scripts/plc_validate_records.py --preset representative --preset templates`
- server_entrypoint: `python scripts/operator_ui_server.py --host 127.0.0.1 --port 8765`
- api_under_test:
  - `GET /api/runs?limit=N`
  - `GET /api/runs/{run_id}`
  - `GET /api/runs/{run_id}/artifacts/{artifact_key}`
  - `GET /api/workspace/overview?limit_runs=N`
  - `GET /api/workspace/cards?...`
  - `GET /api/workspace/runs/{run_id}`

