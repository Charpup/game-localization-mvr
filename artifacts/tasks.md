# Phase 5 Tasks

- [x] Update TriadDev brownfield state for `phase5-frontend-runtime-shell`.
- [x] Add RED tests for run models and artifact allow-list behavior.
- [x] Add RED tests for launcher command shape and in-flight run tracking.
- [x] Add RED tests for local HTTP API behavior and artifact preview safety.
- [x] Add acceptance coverage for the runtime shell entry page plus run inspection flow.
- [x] Implement `operator_ui_models.py`.
- [x] Implement `operator_ui_launcher.py`.
- [x] Implement `operator_ui_server.py`.
- [x] Implement static assets under `operator_ui/`.
- [x] Run targeted tests and the retained regression floor.
- [x] Record PLC/TriadDev Phase 5 lifecycle artifacts.

## Verification

- `python -m pytest tests/test_operator_ui_models.py tests/test_operator_ui_launcher.py tests/test_operator_ui_server.py tests/test_phase5_frontend_runtime_shell.py -q`
- `python -m pytest tests/test_operator_ui_models.py tests/test_operator_ui_launcher.py tests/test_operator_ui_server.py tests/test_phase5_frontend_runtime_shell.py tests/test_smoke_verify.py tests/test_runtime_adapter_contract.py tests/test_batch6_repair_metrics_contract.py tests/test_validation_contract.py -q`
- `python -m pytest tests/test_qa_hard.py tests/test_script_authority.py tests/test_batch3_batch4_governance.py -q`
