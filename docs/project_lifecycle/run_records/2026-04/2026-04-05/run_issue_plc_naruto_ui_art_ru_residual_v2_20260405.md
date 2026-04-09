# run_issue

- run_id: `plc_naruto_ui_art_ru_residual_v2_20260405`
- scope: `naruto_ui_art_ru_residual_v2`
- severity: `warn`
- issue_summary: `the harness layer succeeded, but the final narrow auto slice produced only marginal quality gains and confirms that the remaining path should be manual review rather than another broad automatic repair`

## Resolved By Residual V2
- added queue separation and leakage visibility on top of the repaired residual slice:
  - blocker rows vs warning-only rows
  - manual creative titles
  - manual ambiguity terms
  - auto-fixable repeated titles
  - title/headline provenance via enriched review surfaces
- built a family coverage diff for repeated residual sources and uncovered repeated-family gaps
- ran one final narrow automatic slice only on `156` safe repeated-family rows

## Remaining Issues
- the narrow automatic pass did not produce a new quality step-change:
  - hard QA: `509 -> 510`
  - soft hard-gate: `503 -> 500`
  - review queue: `1231 -> 1201`
- acceptance still missed:
  - `soft_hard_gate_below_500`
  - `badge_micro_1c_compact_mapping_missing_zero`
- remaining top source clusters still skew toward lore-heavy or creative title work:
  - `苍泉之门`
  - `翠岚之门`
  - `耀华之门`
  - `熙晨归客`
  - `风再归时`
  - `天梯排位赛`
  - `八十神空击`

## Operational Read
- the harness outputs are now strong enough to support a disciplined manual-review phase
- further broad automatic slicing is no longer justified by the measured delta
- any future automation should be limited to tiny deterministic family cleanups discovered through the family coverage diff
