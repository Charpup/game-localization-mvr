# run_issue

- run_id: `plc_naruto_ui_art_ru_residual_triage_20260405`
- scope: `naruto_ui_art_ru_residual_triage`
- severity: `warn`
- issue_summary: `the residual triage slice improved the batch materially, but title/headline leakage and creative-name residuals still leave a non-trivial manual review queue`

## Resolved By Residual Triage
- the derived repair slice completed end-to-end without spawning a duplicate live process
- repaired delivery integrity remained intact:
  - `3235 prepared`
  - `3235 delivered`
  - `row_count_match = true`
- headline quality movement versus the base full rerun:
  - hard QA: `1058 -> 509`
  - soft hard-gate: `874 -> 503`
  - review queue: `1641 -> 1231`
- strongest family win:
  - `badge_micro_1c`: `107 -> 4`

## Remaining Issues
- the slice narrowly missed the soft hard-gate target:
  - `503` remaining vs target `<= 500`
- family thresholds still missed:
  - `promo_short`: `30`
  - `item_skill_name`: `171`
  - `slogan_long`: `72`
- the remaining queue is now dominated more by title/headline leakage and creative naming than by mechanical compact-policy misses
- top remaining source clusters include:
  - `熙晨归客`
  - `风再归时`
  - `翠岚之门`
  - `八十神空击`
  - `自然一体化`

## Operational Read
- the repaired delivery is trustworthy as the new working baseline
- the next bounded step should be manual queue separation plus selected title/headline leakage triage, not another full rerun
