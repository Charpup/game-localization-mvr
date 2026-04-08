# run_verify

- run_id: `plc_naruto_ui_art_ru_residual_triage_20260405`
- scope: `naruto_ui_art_ru_residual_triage`
- verification_result: `warn`
- environment_result: `pass`
- offline_validation_result: `pass`
- live_execution_result: `pass_with_manual_review_pending`
- decision: `RESIDUAL_TRIAGE_COMPLETED_PENDING_MANUAL_REVIEW`

## Verified
- `.\\.venv\\Scripts\\python.exe -m pytest tests/test_ui_art_residual_triage_contract.py tests/test_translate_llm_contract.py tests/test_qa_hard.py tests/test_ui_art_full_rerun_assess_contract.py -q -s` -> `pass`
- `.\\.venv\\Scripts\\python.exe scripts\\style_sync_check.py` -> `pass`
- `.\\.venv\\Scripts\\python.exe scripts\\glossary_compile.py --approved glossary/approved.yaml --approved glossary/zhCN_ruRU/ip_naruto_ui_art_short.yaml --out_compiled data/incoming/naruto_ui_art_ru_20260404/glossary_ui_art_compiled.yaml --language_pair zh-CN->ru-RU --franchise naruto --resolve_by_scope` -> `pass`
- `run_ui_art_residual_triage.py` completed `residual_triage_20260405_slice01` end-to-end on the derived full-rerun slice
- `ui_art_residual_assess.py` wrote both:
  - `ui_art_residual_assessment.json`
  - `ui_art_residual_assessment.md`

## Residual Delta
- hard QA total: `1058 -> 509`
- soft hard-gate: `874 -> 503`
- review queue total: `1641 -> 1231`
- hard invariants: no regression
- delivery rows: `3235 -> 3235`, `row_count_match=true`

## Acceptance Snapshot
- `hard_total_lte_650`: `pass`
- `soft_hard_gate_lte_500`: `fail`
- `badge_micro_1c_compact_mapping_missing_zero`: `fail`
- `promo_short_review_rows_lte_15`: `fail`
- `item_skill_name_review_rows_lte_90`: `fail`
- `slogan_long_review_rows_lte_60`: `fail`

## Conclusion
- this phase succeeded as a derived repair-and-assess slice
- it materially improved the current delivery without another full rerun
- it did not clear the batch for silent release
- the next bounded slice, if pursued, should target title/headline leakage and the residual manual queue rather than reopening generic compaction work
