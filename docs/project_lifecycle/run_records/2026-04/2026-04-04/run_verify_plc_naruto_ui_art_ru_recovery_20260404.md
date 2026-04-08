# run_verify

- run_id: `plc_naruto_ui_art_ru_recovery_20260404`
- scope: `naruto_ui_art_ru_recovery`
- verification_result: `pass`
- environment_result: `pass`
- offline_validation_result: `pass`
- live_execution_result: `deferred_pending_canary`
- decision: `RECOVERY_READY_FOR_STRATIFIED_CANARY`
- verified:
  - `.\\.venv\\Scripts\\python.exe -m pytest tests/test_glossary_compile_contract.py tests/test_ui_art_batch_contract.py tests/test_soft_qa_contract.py -q -s` -> `20 passed`
  - `.\\.venv\\Scripts\\python.exe scripts/style_sync_check.py` -> `pass`
  - `.\\.venv\\Scripts\\python.exe scripts/glossary_compile.py --approved glossary/approved.yaml --approved glossary/zhCN_ruRU/ip_naruto_ui_art_short.yaml --out_compiled data/incoming/naruto_ui_art_ru_20260404/glossary_ui_art_compiled.yaml --language_pair zh-CN->ru-RU --franchise naruto --resolve_by_scope` -> `pass`
  - `prepare_ui_art_batch.py` now emits `ui_art_category` across the batch-prep contract
  - `translate_llm.py` and `soft_qa_llm.py` now prefer compact glossary metadata for UI-art rows
  - `qa_hard.py` now distinguishes badge compact-only failures, target-vs-review overflow bands, and slogan line-budget risk
  - `ui_art_length_review.py` now emits category-aware reasons for the manual review queue
- residual_risks:
  - no canary rerun has been executed yet, so family-level fail-rate improvement is still unproven on live rows
  - some compact Russian forms remain intentionally aggressive and may still require manual approval on a subset of art labels
