# run_issue

- run_id: `plc_naruto_ui_art_ru_recovery_canary_20260404`
- scope: `naruto_ui_art_ru_recovery_canary`
- route: `plc + triadev`

## Runtime Issues Closed During Execution
- `run_ui_art_live_batch.py` originally treated `compact_mapping_missing` / `compact_term_miss` as blocking post-repair hard errors, which prevented the canary from reaching soft QA and comparison even though these are deferred UI-art review issues.
- `run_ui_art_live_batch.py` originally mixed `soft_qa_llm.py --input` with positional asset arguments, which shifted CLI parsing and caused a false lifecycle governance failure on `workflow/soft_qa_rubric.yaml`.
- `run_ui_art_live_batch.py` also treated `soft_qa_llm.py` exit code `2` as a transport/runtime failure instead of the intended “report written, hard gate triggered” content-state return code.

## Residual Blocking Content Families
- `badge_micro_2c`: still blocked by missing approved compact mappings
- `slogan_long`: still fails the promotion rule because residual failures are dominated by `length`, not `line_budget_overflow`
- `promo_short` and `item_skill_name`: materially improved or stabilized, but still too overflow-heavy for immediate full rerun approval
