# run_verify

- run_id: `plc_naruto_ui_art_ru_preparation_20260404`
- scope: `naruto_ui_art_ru_preparation`
- verification_result: `pass_with_external_blockers`
- environment_result: `pass`
- offline_validation_result: `pass`
- live_smoke_result: `not_run_by_design`
- decision: `READY_FOR_SOURCE_AND_CREDENTIAL_HANDOFF`
- verified:
  - `.\\.venv\\Scripts\\python.exe -m pytest tests/test_glossary_compile_contract.py tests/test_ui_art_batch_contract.py -q -s` -> `4 passed`
  - `.\\.venv\\Scripts\\python.exe scripts/style_sync_check.py` -> `pass`
  - `.\\.venv\\Scripts\\python.exe scripts/glossary_compile.py --approved glossary/approved.yaml --approved glossary/zhCN_ruRU/ip_naruto_ui_art_short.yaml --out_compiled data/incoming/naruto_ui_art_ru_20260404/glossary_ui_art_compiled.yaml --language_pair zh-CN->ru-RU --franchise naruto --resolve_by_scope` -> `compiled glossary_ui_art_compiled.yaml`
  - `.\\.venv\\Scripts\\python.exe scripts/prepare_ui_art_batch.py --input data/incoming/naruto_ui_art_ru_20260404/source_ui_art.csv --output data/incoming/naruto_ui_art_ru_20260404/source_ui_art_prepared.csv --report data/incoming/naruto_ui_art_ru_20260404/source_ui_art_prepare_report.json` -> `0 rows prepared`
  - `.\\.venv\\Scripts\\python.exe scripts/ui_art_length_review.py --input data/incoming/naruto_ui_art_ru_20260404/source_ui_art_prepared.csv --output data/incoming/naruto_ui_art_ru_20260404/ui_art_review_queue.csv --report data/incoming/naruto_ui_art_ru_20260404/ui_art_review_queue.json` -> `0 review rows`
  - `.\\.venv\\Scripts\\python.exe scripts/plc_validate_records.py --preset representative --preset templates` -> `Validated 11 PLC governance artifact(s).`
- residual_risks:
  - the real batch has not been supplied yet, so there is still no row-level live translation evidence
  - `llm_ping` and the live translation chain remain blocked until credentials are provided
  - controversial compact forms remain intentionally outside the approved extension until human confirmation
