# run_issue

- run_id: `plc_naruto_ui_art_ru_recovery_slice2_20260404`
- scope: `naruto_ui_art_ru_focused_recovery_slice2`
- severity: `warn`
- issue_summary: `focused recanary passed promotion, but soft-QA still reports compact-term/style noise that should be aligned before or during the full rerun`

## Resolved In Slice
- `badge_micro_2c` moved from approval-gap failures to exact approved mappings with deterministic bypass
- `promo_short` repeated failure clusters for `奖励预览` and `充值返利` were collapsed out of the hard-fail set
- `item_skill_name` compact glossary coverage and structure rules reduced the family hard-fail rate to acceptable levels
- `slogan_long` residuals are now subtype-specific `headline_budget_overflow`, not generic prose expansion

## Remaining Non-Blocking Issues
- `soft_qa_llm.py` still flags some approved compact UI-art terms as terminology/style violations:
  - `Топ`
  - `Донат+`
  - `Сэн-тест`
- focused run `ui_art_recovery_slice2_20260404_run01` surfaced missing exact-bypass coverage for `badge_micro_1c`, `首充`, `今日充值`, and `人间道·灵魂吞噬`; those gaps were fixed before `run02`
- focused run `ui_art_recovery_slice2_20260404_run02` still leaves a small review queue in:
  - `promo_short`
  - `item_skill_name`
  - `slogan_long`

## Operational Read
- this issue set does not block the focused promotion decision
- it does justify treating soft-QA compact-policy alignment as a near-term follow-up before or alongside the next full rerun
