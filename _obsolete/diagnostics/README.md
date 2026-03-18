# Round 2 Diagnostics Archive

Date: 2026-03-19

This directory stores the Round 2 mainline cleanup trial artifacts for
`main_worktree/scripts/debug_*` and `main_worktree/scripts/diagnose_*`.

Archive policy:
- Archive first, do not delete
- Keep file contents unchanged
- Do not treat this directory as a runnable mainline location

Round 2 whitelist:
- `debug_auth.py`
- `debug_destructive_failures.py`
- `debug_llm_format.py`
- `debug_translation.py`
- `debug_v4_traces.py`
- `diagnose_direct_api.py`
- `diagnose_sequential_batch.py`
- `diagnose_single_call.py`
- `diagnose_sonnet_retest.py`

Evidence summary:
- The latest M4 core decision still keeps only the six mainline scripts:
  `llm_ping.py`, `normalize_guard.py`, `translate_llm.py`, `qa_hard.py`,
  `rehydrate_export.py`, and `smoke_verify.py`
- The latest obsolete inventory and legacy candidate reports classify these
  diagnostic modules as archive candidates for `_obsolete/diagnostics`
- Direct reference checks for this round found report and inventory mentions
  only; no accepted root entrypoint dependency was found for these files

Out of scope for this archive:
- `src/`
- `skill/v1.4.0`
- `gate/*`
- `stress/*`
- `repair/*`
- `validation/*`
- mainline smoke evidence under `data/smoke_runs/`
