# run_verify

- run_id: `plc_naruto_ui_art_ru_residual_v2_20260405`
- scope: `naruto_ui_art_ru_residual_v2`
- verification_result: `warn`
- environment_result: `pass`
- offline_validation_result: `pass`
- live_execution_result: `pass_with_manual_review_pending`
- decision: `RESIDUAL_V2_COMPLETED_PENDING_MANUAL_REVIEW`

## Verified
- `.\\.venv\\Scripts\\python.exe -m pytest tests/test_ui_art_residual_v2_contract.py tests/test_ui_art_residual_triage_contract.py tests/test_translate_llm_contract.py tests/test_qa_hard.py tests/test_ui_art_full_rerun_assess_contract.py -q -s` -> `pass`
- `.\\.venv\\Scripts\\python.exe scripts\\style_sync_check.py` -> `pass`
- `run_ui_art_residual_v2.py` completed `residual_v2_20260405_slice02` end-to-end on the residual-triage base slice
- `ui_art_residual_v2_assess.py` wrote both:
  - `ui_art_residual_v2_assessment.json`
  - `ui_art_residual_v2_assessment.md`

## Residual V2 Delta
- hard QA total: `509 -> 510`
- soft hard-gate: `503 -> 500`
- review queue total: `1231 -> 1201`
- `title_name_short` blocking length: `380 -> 378`
- hard invariants: no regression
- delivery rows: `3235 -> 3235`, `row_count_match=true`

## Harness Outcome
- manual queue separation is present:
  - `manual_creative_titles = 10`
  - `manual_ambiguity_terms = 69`
- auto-fixable repeated-title surface is present:
  - `auto_fix_candidate_rows = 156`
  - `auto_fix_blocker_rows = 33`
- family coverage diff is present and lists uncovered repeated residual families for deterministic follow-up

## Conclusion
- this phase succeeded as a harness-first residual visibility slice
- it also completed the last justified narrow automatic repair experiment
- the measured gain from that final auto pass is too small to justify another broad automatic slice
- the remaining route is manual review against the separated queues and family coverage surfaces
