# run_issue

- run_id: `plc_phase5_frontend_runtime_shell_pr_closeout_20260327`
- status: `closed`
- blockers: `none`
- resolved:
  - `PR19-001`: server entrypoint now boots with repo-root import fallback and static asset fallback.
  - `PR19-002`: frontend timeline now renders from `run.stages`.
  - `PR19-003`: frontend verify card now renders from `run.verify`.
  - `PR19-004`: launcher run IDs now carry microseconds plus a short suffix to prevent same-second collisions.
  - `PR19-005`: branch conflict with `origin/main` was reconciled locally and the post-merge regression floor stayed green.
  - `PR19-006`: acceptance gate now creates a repo-local launch input fixture instead of depending on a workstation-specific external CSV path.
  - `PR19-007`: `/api/runs?limit=` now returns a structured `400` on malformed input instead of raising `ValueError` inside the handler thread.
