# run_issue

- run_id: `plc_naruto_ui_art_ru_full_rerun_20260404`
- scope: `naruto_ui_art_ru_full_rerun`
- severity: `warn`
- issue_summary: `the full rerun completed successfully, but residual triage is still required because soft-QA hard-gate findings remain dominated by true residual length and ambiguity issues`

## Resolved By Rerun
- row integrity is restored at full scale:
  - `3235 prepared`
  - `3235 delivered`
  - `1 skipped_empty`
- hard-QA and review pressure are materially lower than the original failed run
- `badge_micro_2c` remained stable at `0` review rows after scaling up from the focused slice

## Remaining Issues
- soft-QA hard-gate still fails with `874` violations
- the dominant hard-gate type is still `length`:
  - `780` of `874` hard-gate violations
- the remaining targeted-family review load is still material:
  - `promo_short`: `44`
  - `item_skill_name`: `175`
  - `slogan_long`: `112`
- top true-residual source clusters from assessment include:
  - `守卫木叶`
  - `反伤试炼`
  - `快速扫荡`
  - `真伤试炼`
  - `全能试炼`
  - `满级预览`

## Operational Read
- the rerun itself is trustworthy and reusable
- the next bounded task should be residual triage, not another blind full rerun
