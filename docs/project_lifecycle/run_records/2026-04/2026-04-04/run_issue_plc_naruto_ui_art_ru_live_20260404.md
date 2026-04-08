# run_issue

- run_id: `plc_naruto_ui_art_ru_live_20260404`
- scope: `naruto_ui_art_ru_live_batch`
- severity: `warn`

## Active blockers

- `soft_qa` finished but its hard gate failed on `length / terminology / style_contract / placeholder` findings
- `ui_art_review_queue.csv` contains `3189` rows requiring human follow-up, including `2839` critical rows
- `ui_art_qa_hard_report_recheck_v2.json` still contains `3002` `length_overflow` findings, so the batch is not release-clean

## Non-blocking notes

- final delivery export exists and row counts are aligned: `3235 prepared -> 3235 delivery`
- `reports/soft_qa_failed_batches.json` records `1` failed soft-QA batch parse; the overall report still completed
- the batch required two manual hard-QA fallback fixes:
  - `UIART_000397` -> `Пробуждение!!!`
  - `UIART_002934` -> `Пом.`
