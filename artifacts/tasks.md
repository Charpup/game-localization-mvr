# Phase 6 Tasks

- [x] Realign TriadDev brownfield state and change id to `phase6-operator-workspace-dashboard`.
- [x] Freeze Phase 6 delta spec, design, and task artifacts.
- [x] Add RED tests for workspace read models and derived-vs-persisted parity.
- [x] Add RED tests for `/api/workspace/overview`, `/api/workspace/cards`, and `/api/workspace/runs/{run_id}`.
- [x] Add frontend contract coverage for runtime/workspace mode switching and workspace drilldown.
- [x] Split `operator_control_plane` into pure derivation plus write-on-demand summarize behavior.
- [x] Implement workspace read models in `operator_ui_models.py`.
- [x] Implement workspace APIs in `operator_ui_server.py`.
- [x] Implement workspace mode and dashboard panels in `operator_ui/*`.
- [x] Run focused regression plus PLC validator.
- [x] Record Phase 6 PLC/TriadDev lifecycle artifacts.
- [x] Add a live Phase 6 acceptance gate for the documented server entrypoint.
- [x] Record Phase 6 acceptance closeout artifacts and move the slice to accepted.

## Verification

- `python -m pytest tests/test_operator_ui_workspace_models.py tests/test_operator_ui_workspace_server.py tests/test_phase6_operator_workspace_dashboard.py -q`
- `python -m pytest tests/test_phase6_acceptance_gate.py -q`
- `python -m pytest tests/test_phase4_operator_control_plane.py tests/test_operator_ui_models.py tests/test_operator_ui_workspace_models.py tests/test_operator_ui_launcher.py tests/test_operator_ui_server.py tests/test_operator_ui_workspace_server.py tests/test_phase5_frontend_runtime_shell.py tests/test_phase5_acceptance_gate.py tests/test_phase6_operator_workspace_dashboard.py tests/test_phase6_acceptance_gate.py tests/test_smoke_verify.py tests/test_runtime_adapter_contract.py tests/test_batch6_repair_metrics_contract.py tests/test_validation_contract.py tests/test_qa_hard.py tests/test_script_authority.py tests/test_batch3_batch4_governance.py tests/test_plc_docs_contract.py -q`
- `python scripts/plc_validate_records.py --preset representative --preset templates`
