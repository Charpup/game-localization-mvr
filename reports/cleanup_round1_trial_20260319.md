# Cleanup Round 1 Trial

Date: 2026-03-19

## Summary

This report records the first small-scope mainline cleanup trial for
`main_worktree`. The trial is intentionally limited to three P0 temporary
residues identified in `reports/m4_core_obsolete_inventory.md`.

Archive strategy:
- Archive first, do not delete
- Do not touch the smoke pipeline core chain
- Do not move `src`, `data/smoke_runs`, `reports`, `workflow`, `glossary`, or `config`

Archive destination:
- `main_worktree/_obsolete/round1_tmp/`

## Round 1 Whitelist

Archived objects:
- `main_worktree/tmp_run200.ps1`
- `main_worktree/tmp_single_run.ps1`
- `main_worktree/tmp_single_305833.csv`

Selection evidence:
- Listed as P0 in `reports/m4_core_obsolete_inventory.md`
- Not referenced by `main_worktree/scripts/run_smoke_pipeline.py`
- Not referenced by `scripts/validate_v130.py`
- Not referenced by `package_v1.3.0.sh`
- Not referenced by `skill/v1.3.0/package.sh`

## Exclusions

Explicitly excluded from Round 1:
- Core chain scripts kept by latest M4 decision:
  `scripts/llm_ping.py`, `scripts/normalize_guard.py`,
  `scripts/translate_llm.py`, `scripts/qa_hard.py`,
  `scripts/rehydrate_export.py`, `scripts/smoke_verify.py`,
  `scripts/run_smoke_pipeline.py`, `scripts/smoke_issue_logger.py`
- `src/` compatibility area
- `main_worktree/data/smoke_runs` and historical evidence files
- `main_worktree/reports` existing M4 outputs
- `scripts/debug_*` and `scripts/diagnose_*`
- stress, gate, repair, and soft-QA related scripts

Reason for exclusion:
- Either still part of the validated mainline
- Or not sufficiently proven obsolete within the latest cleanup evidence window

## Round 2 Preview

Candidates to evaluate next, but not execute in this round:
- `scripts/debug_auth.py`
- `scripts/debug_destructive_failures.py`
- `scripts/debug_llm_format.py`
- `scripts/debug_translation.py`
- `scripts/debug_v4_traces.py`
- `scripts/diagnose_direct_api.py`
- `scripts/diagnose_sequential_batch.py`
- `scripts/diagnose_single_call.py`
- `scripts/diagnose_sonnet_retest.py`

Planned Round 2 action shape:
- Archive to `_obsolete/diagnostics/`
- Keep source content intact
- Re-verify no root-level references before moving

## Required Verification

Post-archive checks for this round:
- Smoke-focused tests continue to pass
- Current mainline verification command set remains usable
- M4 decision summary still shows the six core scripts as `KEEP`
- Historical smoke evidence remains unchanged except for this new cleanup record
