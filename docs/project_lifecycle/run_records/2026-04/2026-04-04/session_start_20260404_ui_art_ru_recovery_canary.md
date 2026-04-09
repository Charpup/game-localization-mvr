# session_start

- date: `2026-04-04`
- branch: `main`
- route: `plc + triadev`
- current_scope: `naruto_ui_art_ru_recovery_canary`
- objective: `run a live 220-row stratified recovery canary and decide whether the category-aware policy is strong enough for a full rerun`

## Input Basis
- authoritative source: `data/incoming/naruto_ui_art_ru_20260404/source_ui_art.csv`
- fresh prepared full source: `data/incoming/naruto_ui_art_ru_20260404/source_ui_art_fresh_prepared.csv`
- canary input: `data/incoming/naruto_ui_art_ru_20260404/runs/ui_art_recovery_canary_20260404_run01/source_ui_art_canary_prepared.csv`
- baseline comparator: `data/incoming/naruto_ui_art_ru_20260404/runs/ui_art_live_20260404_run01/`

## Guardrails
- single-process only
- process-scoped credentials only
- no concurrent live LLM workers
- no full rerun promotion unless the explicit canary thresholds pass

## Known Sampling Constraint
- planned `badge_micro_2c=30` is infeasible on the real prepared source; only `13` live-ready rows exist in that family
- the canary must keep total rows at `220` and record the `17`-row shortfall explicitly in the sample manifest
