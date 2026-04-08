# run_verify

- run_id: `plc_naruto_ui_art_ru_full_rerun_20260404`
- scope: `naruto_ui_art_ru_full_rerun`
- verification_result: `warn`
- environment_result: `pass`
- offline_validation_result: `pass`
- live_execution_result: `pass_with_residual_triage_pending`
- decision: `FULL_RERUN_COMPLETED_PENDING_RESIDUAL_TRIAGE`

## Verified
- `.\\.venv\\Scripts\\python.exe -m pytest tests/test_ui_art_batch_contract.py tests/test_qa_hard.py tests/test_soft_qa_contract.py tests/test_ui_art_recovery_canary_contract.py tests/test_translate_llm_contract.py tests/test_ui_art_full_rerun_assess_contract.py -q -s` -> `41 passed`
- `.\\.venv\\Scripts\\python.exe scripts\\style_sync_check.py` -> `pass`
- `.\\.venv\\Scripts\\python.exe scripts\\glossary_compile.py --approved glossary/approved.yaml --approved glossary/zhCN_ruRU/ip_naruto_ui_art_short.yaml --out_compiled data/incoming/naruto_ui_art_ru_20260404/glossary_ui_art_compiled.yaml --language_pair zh-CN->ru-RU --franchise naruto --resolve_by_scope` -> `pass`
- `run_ui_art_live_batch.py` completed `ui_art_full_rerun_20260404_run01` end-to-end on the raw source CSV
- `ui_art_full_rerun_assess.py` wrote both:
  - `ui_art_full_rerun_assessment.json`
  - `ui_art_full_rerun_assessment.md`

## Full-Run Delta
- hard QA total: `3002 -> 1058`
- review queue total: `3189 -> 1641`
- soft-QA major findings: `2713 -> 1135`
- hard invariants: no regression
- delivery rows: `3235 -> 3235`, `row_count_match=true`

## Residual Assessment
- remaining soft-QA hard-gate violations: `874`
- hard-gate type mix:
  - `length`: `780`
  - `placeholder`: `2`
  - `style_contract`: `24`
  - `terminology`: `34`
  - `ambiguity_high_risk`: `34`
- bucket split:
  - `true_residual`: `816`
  - `mixed_review`: `57`
  - `compact_policy_noise`: `1`

## Conclusion
- this phase succeeded as a rerun-and-assess slice
- it did not clear the batch for silent release
- the next bounded slice should triage true residual clusters first, then handle mixed terminology/style leftovers
