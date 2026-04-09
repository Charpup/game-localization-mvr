# Session End Handoff: Human Delivery PR Split And Real LLM Plan

## Current State
- `workspace board` foundation is implemented as a run-level case projection.
- `task-first human delivery console` is implemented with:
  - `Task Wizard`
  - `Task Inbox`
  - curated `delivery bundle`
  - `Ops Monitor` and `Pro Runtime` handoff
- `LLM setup gate` is implemented with:
  - local `base_url / api_key / model` configuration
  - explicit connection test
  - launch gating for task creation and runtime launch

## Open PR Plan
### PR Train A: Operator UI / Human Delivery
1. `codex/phase6-workspace-board`
   - Title: `Phase 6 workspace board foundation`
   - Base: `main`
   - Scope:
     - `scripts/operator_ui_models.py`
     - `scripts/operator_ui_server.py`
     - `tests/test_operator_ui_workspace_models.py`
     - `tests/test_operator_ui_workspace_server.py`
     - `tests/test_phase6_acceptance_gate.py`

2. `codex/task-first-human-delivery`
   - Title: `Task-first human delivery console`
   - Base: `codex/phase6-workspace-board`
   - Scope:
     - `scripts/operator_ui_tasks.py`
     - `scripts/operator_ui_server.py`
     - `operator_ui/index.html`
     - `operator_ui/app.js`
     - `operator_ui/styles.css`
     - `tests/test_operator_ui_task_models.py`
     - `tests/test_operator_ui_task_server.py`
     - `tests/test_phase6_operator_workspace_dashboard.py`
     - `tests/test_phase5_acceptance_gate.py`

3. `codex/llm-setup-gate`
   - Title: `LLM setup gate for human console`
   - Base: `codex/task-first-human-delivery`
   - Scope:
     - `scripts/operator_ui_llm.py`
     - `scripts/operator_ui_launcher.py`
     - `scripts/operator_ui_server.py`
     - `operator_ui/index.html`
     - `operator_ui/app.js`
     - `operator_ui/styles.css`
     - `tests/test_operator_ui_server.py`
     - `tests/test_operator_ui_task_server.py`
     - `tests/test_phase6_operator_workspace_dashboard.py`
     - this handoff document

### PR Train B: Naruto Workbook Glossary Refresh
4. `codex/naruto-workbook-glossary-refresh`
   - Title: `Naruto workbook glossary refresh pipeline`
   - Base: `main`
   - Scope:
     - `scripts/build_reviewed_workbook_glossary.py`
     - `scripts/run_naruto_ui_art_glossary_refresh.py`
     - `scripts/translate_refresh.py`
     - `scripts/glossary_autopromote.py`
     - `workflow/lifecycle_registry.yaml`
     - `tests/test_build_reviewed_workbook_glossary.py`
     - `tests/test_run_naruto_ui_art_glossary_refresh.py`
     - `tests/test_translate_refresh_contract.py`

5. `codex/naruto-workbook-glossary-artifacts`
   - Title: `Naruto workbook refresh artifacts and run records`
   - Base: `codex/naruto-workbook-glossary-refresh`
   - Scope:
     - `glossary/compiled_naruto_ui_art_workbook_refresh.lock.json`
     - `glossary/compiled_naruto_ui_art_workbook_refresh.yaml`
     - `glossary/zhCN_ruRU/project_naruto_ui_art_workbook_refresh_approved.yaml`
     - `reports/translate_refresh_incremental_failed_batches.json`
     - `reports/translate_failed_batches.json`
     - `reports/soft_qa_failed_batches.json`
     - `docs/project_lifecycle/run_records/2026-04/2026-04-04/`
     - `docs/project_lifecycle/run_records/2026-04/2026-04-05/`
     - `scripts/seed_phase6_manual_uat.py` only if still confirmed as Naruto-line output support

## Repo State
- Current implementation session started from `main`.
- `origin`:
  - `https://github.com/Charpup/game-localization-mvr.git`
- Mixed working tree was intentionally split into stacked worktrees so the dirty local `main` tree would not be rewritten in place.
- Functional files belong to PR train A or B.
- Local process noise should stay out of PRs:
  - `.triadev/*`
  - `task_plan.md`
  - `findings.md`
  - `progress.md`
  - `value-review.md`
  - `.playwright-cli/`
  - transient `output/` validation artifacts
  - any fake LLM credential or fake endpoint config

## Validation Already Done
### Workspace Board Foundation
- `tests/test_operator_ui_workspace_models.py`
- `tests/test_operator_ui_workspace_server.py`
- `tests/test_phase6_acceptance_gate.py`

### Task-First Human Delivery Console
- `tests/test_operator_ui_task_models.py`
- `tests/test_operator_ui_task_server.py`
- `tests/test_phase6_operator_workspace_dashboard.py`
- `tests/test_phase5_acceptance_gate.py`

### LLM Setup Gate
- `tests/test_operator_ui_server.py`
- `tests/test_operator_ui_task_server.py`
- `tests/test_phase6_operator_workspace_dashboard.py`
- Playwright fake-endpoint acceptance was completed in the prior implementation session to verify:
  - locked launch before setup
  - explicit connection test
  - unlock after successful test
  - task/runtime entry handoff after unlock

## Real LLM API Validation Next
1. In shell, export or prepare the real credential values you want to use locally.
2. Run:
   - `.\.venv\Scripts\python.exe scripts\llm_ping.py`
3. Confirm the shell ping succeeds against the real provider.
4. Open the web UI and fill:
   - `base_url`
   - `api_key`
   - optional `model`
5. Click `Test connection`.
6. Confirm the task creation and runtime launch controls unlock.
7. Run one real `Create task and launch`.
8. Verify:
   - task enters expected status progression
   - `Ops Monitor` handoff works
   - `Pro Runtime` shows the linked run
   - delivery bundle appears when the run reaches a releasable stage

## Known Risks
- The real provider may differ subtly from OpenAI-compatible `/chat/completions` expectations.
- The local credential persistence model may need review if the machine/user expectation is session-only rather than stored-on-disk.
- Real failure copy may still need polish once a provider returns non-simulated errors.
- The `cgi` deprecation warning remains non-blocking but should be cleaned up in a later pass.

## First Next Session Tasks
1. Push and open draft PRs for A1, A2, and A3.
2. Push and open draft PRs for B1 and B2.
3. Run real LLM smoke validation after A3 is reviewable.
4. Fold any real-provider compatibility fixes into the top `codex/llm-setup-gate` branch before merge.
5. Resume product/UI iteration only after the PR train and real LLM smoke are stable.
