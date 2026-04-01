# run_issue

- run_id: `plc_local_smoke_baseline_readiness_20260401`
- status: `open`
- blockers:
  - `missing live credentials: LLM_BASE_URL / LLM_API_KEY / LLM_MODEL`
  - `llm_ping, smoke preflight, and full smoke are blocked until those values are supplied`
- env_blockers:
  - `live LLM configuration not loaded into the current shell`
- resolved:
  - `B01`: installed managed Python tooling with `uv` and confirmed a repo-local Python 3.11 environment.
  - `B02`: generated `workflow/style_profile.generated.yaml` successfully on Windows after removing emoji-only console output from `style_guide_bootstrap.py`.
  - `B03`: fixed placeholder preservation for printf-style placeholders in `normalize_guard.py` so `%d` no longer drifts to `% d`.
  - `B04`: hardened `test_normalize.py`, `test_qa_hard.py`, `test_rehydrate.py`, and `test_e2e_workflow.py` for fresh-clone Windows execution.
  - `B05`: completed the offline validation floor successfully.
