# session_start

- date: `2026-04-05`
- branch: `main`
- route: `plc + triadev`
- current_scope: `naruto_ui_art_ru_full_rerun`
- objective: `rerun the full 3235-row Naruto UI-art batch on the focused recovery slice baseline, then assess soft-QA residuals`

## Continuity Note
- this execution resumed the `20260404` change slice, so the PLC record stays under `2026-04-04/` even though the local execution date is `2026-04-05`

## Input Basis
- authoritative raw input: `data/incoming/naruto_ui_art_ru_20260404/source_ui_art.csv`
- failed full baseline: `data/incoming/naruto_ui_art_ru_20260404/runs/ui_art_live_20260404_run01/`
- focused strategy anchor: `data/incoming/naruto_ui_art_ru_20260404/runs/ui_art_recovery_slice2_20260404_run02/`

## Guardrails
- single-process only
- process-scoped credentials only
- no concurrent live LLM workers
- do not change the focused slice runtime policy before the rerun
- treat `soft_qa` hard-gate as assessment input, not as a delivery blocker
