# Phase 5 + 6 Human UI Acceptance Handoff

- scope: `phase5_phase6_human_ui_acceptance`
- worktree: `D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\phase6_dashboard_worktree`
- ui_url: `http://127.0.0.1:8765/`
- server_entrypoint: `python scripts/operator_ui_server.py --host 127.0.0.1 --port 8765`
- seed_entrypoint: `python scripts/seed_phase6_manual_uat.py`
- live_launch_dataset: `D:\Dev_Env\loc-mvr 测试文档\test_input_200-row.csv`

## Prepared Seed Runs

- `phase6_manual_uat_derived`
  - expected in `Operator Workspace` with default `status=open`
  - expected to show non-empty `Decision Context`, `Review Workload`, `KPI Snapshot`, and `Governance Drift`
  - expected to have no persisted operator artifacts on disk
- `phase6_manual_uat_persisted`
  - expected to appear when workspace filter changes to `status=all`
  - expected to read persisted operator cards and summary
  - expected to show closed cards and still allow runtime drilldown

## Human UAT Waves

- `Wave A`
  - workspace mode render, filters, card selection, persisted vs derived run behavior
  - runtime mode switch, recent runs, timeline, verify/issue summaries, artifact preview
- `Wave B`
  - live `preflight` launch with the representative dataset
  - pending run visibility, refresh to manifest-backed detail, post-launch workspace stability

## Required Evidence

- screenshot: default `Operator Workspace`
- screenshot: selected derived card with populated detail panels
- screenshot: persisted run visible under `status=all`
- screenshot: runtime timeline for a selected run
- screenshot: `run_manifest` artifact preview
- screenshot: live launch form filled
- screenshot: pending live run
- screenshot: completed or manifest-backed live run detail

## Decision Rules

- `ACCEPTED`
  - Wave A passes
  - Wave B passes
- `ACCEPTED_WITH_ENV_BLOCKER`
  - Wave A passes
  - Wave B is blocked only by environment or external runtime dependency
- `REJECTED`
  - any `P0` or `P1`

## Failure Severity

- `P0`
  - blank page
  - server crash
  - broken launch flow
  - artifact preview escapes manifest-scoped allow-list
- `P1`
  - wrong run or card selected
  - broken workspace/runtime mode switch
  - wrong verify or issue binding
  - missing required detail panel content
- `P2`
  - copy/layout confusion
  - awkward refresh behavior
  - non-blocking visual rough edges
