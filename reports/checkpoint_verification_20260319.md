# Checkpoint Verification

Date: 2026-03-19

## Scope

This report records the verification run used before creating the remote
checkpoint branch for the current `main_worktree` mainline state.

## Commands

Executed on `codex/checkpoint-mainline-20260319`:

```powershell
& 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\.venv_main\Scripts\python.exe' -m pytest tests/test_smoke_verify.py tests/test_qa_hard.py tests/test_normalize_segmentation.py -vv
& 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\.venv_main\Scripts\python.exe' 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\scripts\m4_3_collect_coverage.py'
& 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\.venv_main\Scripts\python.exe' 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\scripts\m4_4_decision.py'
```

## Results

Pytest window:
- Start: 2026-03-19T01:33:50.5257768+08:00
- End: 2026-03-19T01:33:51.8758167+08:00
- Exit: `0`
- Summary: `12 passed in 0.93s`

Coverage decision scripts:
- `m4_3_collect_coverage.py`: start `2026-03-19T01:34:28.5884370+08:00`, end `2026-03-19T01:34:28.7064660+08:00`, exit `0`, analyzed 3 runs, wrote 6 stage entries, hotspot count `0`
- `m4_4_decision.py`: start `2026-03-19T01:34:28.5741065+08:00`, end `2026-03-19T01:34:28.6895042+08:00`, exit `0`, rewrote decision summary

M4 state after verification:
- `KEEP=6`
- `BLOCK=0`
- `REWORK=0`
- `OBSOLETE=0`
- `M4_3_issue_hotspots.jsonl` contains an explicit summary-only record with `hotspot_count = 0`

## Stabilization Notes

The verification run includes two checkpoint hardening fixes applied before
branch freeze:
- `scripts/normalize_guard.py` no longer rewires `sys.stdout/sys.stderr` at
  import time; UTF-8 console setup now happens only in CLI entrypoints
- `scripts/qa_hard.py` no longer rewires `sys.stdout/sys.stderr` at import
  time; UTF-8 console setup now happens only in CLI entrypoints
- `scripts/normalize_guard.py` now segments Chinese text around placeholders
  instead of disabling segmentation for the whole row when a placeholder exists
- `scripts/smoke_verify.py` now prefers text writes before raw buffer fallback,
  which avoids pytest output-stream instability
