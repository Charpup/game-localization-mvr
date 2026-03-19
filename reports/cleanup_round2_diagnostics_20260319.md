# Cleanup Round 2 Diagnostics Trial

Date: 2026-03-19

## Summary

This report records the second small-scope mainline cleanup trial for
`main_worktree`. Round 2 is limited to diagnostic scripts under
`main_worktree/scripts` that are outside the current smoke mainline.

Archive strategy:
- Archive first, do not delete
- Do not modify the archived file contents
- Do not touch the smoke pipeline core chain
- Do not move `src`, `skill/v1.4.0`, `data/smoke_runs`, packaging files, or
  repair/validation/gate/stress modules

Archive destination:
- `main_worktree/_obsolete/diagnostics/`

## Round 2 Whitelist

Archived objects:
- `main_worktree/scripts/debug_auth.py`
- `main_worktree/scripts/debug_destructive_failures.py`
- `main_worktree/scripts/debug_llm_format.py`
- `main_worktree/scripts/debug_translation.py`
- `main_worktree/scripts/debug_v4_traces.py`
- `main_worktree/scripts/diagnose_direct_api.py`
- `main_worktree/scripts/diagnose_sequential_batch.py`
- `main_worktree/scripts/diagnose_single_call.py`
- `main_worktree/scripts/diagnose_sonnet_retest.py`

Selection evidence:
- Latest 3-run M4 decision keeps only the six core mainline scripts
- `reports/legacy_candidates.jsonl` marks all nine targets as archive
  candidates for `_obsolete/diagnostics`
- `reports/m4_core_obsolete_inventory.md` classifies all nine targets as
  archive candidates
- Direct reference checks for this round found report/inventory mentions only
  and no accepted root-entry mainline dependency

## Exclusions

Explicitly excluded from Round 2:
- `scripts/llm_ping.py`
- `scripts/normalize_guard.py`
- `scripts/translate_llm.py`
- `scripts/qa_hard.py`
- `scripts/rehydrate_export.py`
- `scripts/smoke_verify.py`
- `scripts/run_smoke_pipeline.py`
- `scripts/smoke_issue_logger.py`
- `scripts/repair_loop.py`
- `scripts/run_validation.py`
- `src/`
- `skill/v1.4.0/`
- packaging scripts
- `gate/*`, `stress/*`, `repair/*`, `validation/*`

Reason for exclusion:
- Either still part of the validated mainline
- Or part of compatibility, packaging, or repair/validation surfaces that are
  not proven safe to archive in this round

## Execution Record

Execution window:
- Start: 2026-03-19T00:39:06.9752032+08:00
- End: 2026-03-19T00:39:08.0162687+08:00

Path changes:
- Before: `main_worktree/scripts/<debug_*|diagnose_*>`
- After: `main_worktree/_obsolete/diagnostics/<same filename>`

Executed commands:
- `& 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\.venv_main\Scripts\python.exe' -m pytest -s tests/test_smoke_verify.py tests/test_qa_hard.py`
- `& 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\.venv_main\Scripts\python.exe' 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\scripts\m4_3_collect_coverage.py'`
- `& 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\.venv_main\Scripts\python.exe' 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\scripts\m4_4_decision.py'`

Results summary:
- Archive move completed for all 9 whitelist files with original filenames kept
- `pytest` passed: 9 tests collected, 9 passed, exit code `0`
- `m4_3_collect_coverage.py` passed, analyzed 3 runs, wrote 6 stage entries, found `0` issue hotspots
- `m4_4_decision.py` passed, rewrote `M4_4_decision.jsonl` with decision counts `KEEP=6`, `BLOCK=0`, `REWORK=0`, `OBSOLETE=0`
- `M4_3_issue_hotspots.jsonl` is now non-empty and contains a summary-only record with `hotspot_count = 0`
- No new hotspot entries were produced for this round

Output artifacts:
- `main_worktree/data/smoke_runs/M4_3_coverage_report.jsonl`
- `main_worktree/data/smoke_runs/M4_3_issue_hotspots.jsonl`
- `main_worktree/data/smoke_runs/M4_4_decision.jsonl`

M4 evidence note:
- `M4_3_issue_hotspots.jsonl` must be non-empty after this round. A summary-only
  record is acceptable and means the collector executed successfully with
  `hotspot_count = 0`.

## Next-Round Candidates

Candidates to evaluate next, but not execute in this round:
- `scripts/repair_loop_v2.py`
- `scripts/build_validation_set.py`
- `scripts/repair_checkpoint_gaps.py`
- `scripts/gate_*`
- `scripts/stress_*`
