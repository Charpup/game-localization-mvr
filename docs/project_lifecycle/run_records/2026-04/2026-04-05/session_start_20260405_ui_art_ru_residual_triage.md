# session_start

- date: `2026-04-05`
- branch: `main`
- route: `plc + triadev`
- current_scope: `naruto_ui_art_ru_residual_triage`
- objective: `repair the existing full-rerun delivery in a derived residual slice, then reassess whether the remaining queue is mostly manual-review material`

## Input Basis
- immutable base run:
  - `data/incoming/naruto_ui_art_ru_20260404/runs/ui_art_full_rerun_20260404_run01/`
- residual assessment anchor:
  - `data/incoming/naruto_ui_art_ru_20260404/runs/ui_art_full_rerun_20260404_run01/ui_art_full_rerun_assessment.json`
- derived repair slice:
  - `data/incoming/naruto_ui_art_ru_20260404/runs/ui_art_full_rerun_20260404_run01/residual_triage_20260405_slice01/`

## Guardrails
- do not rerun the full batch
- do not overwrite the base full-rerun delivery
- single-process only
- process-scoped credentials only
- if a matching residual slice process is already active, allow it to finish; do not start a second live job
- treat repaired delivery plus residual assessment as the outcome surface, not “zero queue”
