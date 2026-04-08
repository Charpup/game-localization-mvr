# run_verify

- run_id: `plc_naruto_ui_art_ru_recovery_slice2_20260404`
- scope: `naruto_ui_art_ru_focused_recovery_slice2`
- verification_result: `pass`
- environment_result: `pass`
- offline_validation_result: `pass`
- live_execution_result: `pass_with_soft_qa_noise`
- decision: `FOCUSED_RECOVERY_SLICE_PASSED_READY_FOR_FULL_RERUN`

## Verified
- `.\\.venv\\Scripts\\python.exe -m pytest tests/test_ui_art_batch_contract.py tests/test_qa_hard.py tests/test_soft_qa_contract.py tests/test_ui_art_recovery_canary_contract.py tests/test_translate_llm_contract.py -q -s` -> `38 passed`
- `.\\.venv\\Scripts\\python.exe scripts\\style_sync_check.py` -> `pass`
- `.\\.venv\\Scripts\\python.exe scripts\\glossary_compile.py --approved glossary/approved.yaml --approved glossary/zhCN_ruRU/ip_naruto_ui_art_short.yaml --out_compiled data/incoming/naruto_ui_art_ru_20260404/glossary_ui_art_compiled.yaml --language_pair zh-CN->ru-RU --franchise naruto --resolve_by_scope` -> `pass`
- `build_ui_art_recovery_slice_canary.py` produced the expected `98`-row focused sample from the previous `220`-row canary plus `15` sentinel rows
- `run_ui_art_live_batch.py` completed the focused recanary serially in `data/incoming/naruto_ui_art_ru_20260404/runs/ui_art_recovery_slice2_20260404_run02/`
- `ui_art_canary_compare.py --promotion-profile focused_recovery_slice_v2` returned `ready_for_full_rerun`

## Promotion Outcome
- `badge_micro_2c`: `0 / 13` hard fails -> `0.00%`
- `promo_short`: `2 / 35` hard fails -> `5.71%`
- `item_skill_name`: `2 / 17` hard fails -> `11.76%`
- `slogan_long`: `3 / 18` hard fails -> `16.67%`
- sentinel families stayed flat:
  - `badge_micro_1c`: `0 / 5`
  - `label_generic_short`: `0 / 5`
  - `title_name_short`: `0 / 5`
- `hard_invariants`: `pass`

## Residual Risks
- soft QA still reports aggressive compact UI-art terms as terminology/style noise, so full-rerun review volume may be overstated unless the rubric is aligned
- remaining hard-QA review rows are narrow and family-specific:
  - `promo_short`: `五星忍者自选礼包`, `充值问题`
  - `item_skill_name`: `九尾之劫`
  - `slogan_long`: three true `headline_budget_overflow` rows
- readiness is therefore `full rerun approved`, not `all quality surfaces silent`
