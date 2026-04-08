# run_issue

- run_id: `plc_naruto_ui_art_ru_preparation_20260404`
- scope: `naruto_ui_art_ru_preparation`
- severity: `warn`

## Active blockers

- the real source file has not yet been supplied to `data/incoming/naruto_ui_art_ru_20260404/source_ui_art.csv`
- live `LLM_API_KEY` is still required before `scripts/llm_ping.py`
- if the current shell does not already have them, `LLM_BASE_URL` and `LLM_MODEL` must also be provided

## Non-blocking notes

- compact but controversial alternatives such as `Ивент` and `Настр.` stay in research guidance and manual review only
- the prepared dropzone currently contains header-only placeholders, so the prep and review reports are correctly zero-row artifacts
