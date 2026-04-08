# session_start

- date: `2026-04-04`
- branch: `main`
- route: `plc + triadev`
- current_scope: `naruto_ui_art_ru_focused_recovery_slice2`
- objective: `tighten badge_micro_2c, slogan_long, promo_short, and item_skill_name handling on a 98-row focused recanary and reassess full-rerun readiness`

## Input Basis
- authoritative source: `data/incoming/naruto_ui_art_ru_20260404/source_ui_art.csv`
- focused prepared full source: `data/incoming/naruto_ui_art_ru_20260404/runs/ui_art_recovery_slice2_20260404_run02/source_ui_art_full_prepared.csv`
- prior canary sample: `data/incoming/naruto_ui_art_ru_20260404/runs/ui_art_recovery_canary_20260404_run01/source_ui_art_canary_prepared.csv`
- focused recanary input: `data/incoming/naruto_ui_art_ru_20260404/runs/ui_art_recovery_slice2_20260404_run02/source_ui_art_recovery_slice_canary_prepared.csv`
- baseline comparator: `data/incoming/naruto_ui_art_ru_20260404/runs/ui_art_recovery_canary_20260404_run01/`

## Guardrails
- single-process only
- process-scoped credentials only
- no concurrent live LLM workers
- limit runtime changes to the four failing families plus sentinel stability checks
- do not approve a full rerun unless the focused promotion profile passes explicitly

## Focused Sample Shape
- target families:
  - `badge_micro_2c`: `13`
  - `promo_short`: `30`
  - `item_skill_name`: `20`
  - `slogan_long`: `20`
- sentinel families:
  - `badge_micro_1c`: `5`
  - `label_generic_short`: `5`
  - `title_name_short`: `5`
