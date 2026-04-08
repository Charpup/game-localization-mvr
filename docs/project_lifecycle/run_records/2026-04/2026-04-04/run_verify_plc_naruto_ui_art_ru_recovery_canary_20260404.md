# run_verify

- run_id: `plc_naruto_ui_art_ru_recovery_canary_20260404`
- scope: `naruto_ui_art_ru_recovery_canary`
- verification_result: `warn`
- environment_result: `pass`
- offline_validation_result: `pass`
- live_execution_result: `pass_with_content_hold`
- decision: `RECOVERY_CANARY_FAILED_HOLD_FULL_RERUN`

## Verified
- `.\\.venv\\Scripts\\python.exe -m pytest tests/test_ui_art_recovery_canary_contract.py tests/test_qa_hard.py tests/test_soft_qa_contract.py -q -s` -> `22 passed`
- `build_ui_art_recovery_canary.py` produced an exact `220`-row sample and recorded the real `badge_micro_2c` shortfall (`13 available`, `17 backfilled`)
- `run_ui_art_live_batch.py` completed the canary serially in `data/incoming/naruto_ui_art_ru_20260404/runs/ui_art_recovery_canary_20260404_run01/`
- `ui_art_canary_compare.py` compared the canary against `ui_art_live_20260404_run01` on the same sampled row ids
- promotion thresholds:
  - `badge_micro_combined`: `pass` (`30.23%`)
  - `label_generic_short`: `pass` (`0.00%`)
  - `title_name_short`: `pass` (`35.85%`)
  - `slogan_long`: `fail`
  - `hard_invariants`: `pass`

## Key Deltas
- hard-QA fail-rate movement:
  - `badge_micro_1c`: `100.00% -> 0.00%`
  - `badge_micro_2c`: `100.00% -> 100.00%`
  - `label_generic_short`: `18.52% -> 0.00%`
  - `title_name_short`: `47.17% -> 35.85%`
  - `promo_short`: `83.33% -> 50.00%`
  - `slogan_long`: `65.00% -> 15.00%`
  - `item_skill_name`: `80.00% -> 80.00%`
- review queue movement:
  - `label_generic_short`: `54 -> 0`
  - `promo_short`: `30 -> 16`
  - `title_name_short`: `36 -> 26`
  - `badge_micro_1c`: `30 -> 30`, but downgraded from `critical` to `warning`
- soft-QA canary mix now exposes the true residual issues:
  - `length`: `53`
  - `compact_mapping_missing`: `23`
  - `compact_term_miss`: `8`
  - `line_budget_overflow`: `5`

## Residual Risks
- `badge_micro_2c` still cannot pass without approved compact mappings
- `slogan_long` remains blocked by residual generic length expansion, not just banner line pressure
- `promo_short` and `item_skill_name` still need another compacting pass before a full rerun is worth the API spend
