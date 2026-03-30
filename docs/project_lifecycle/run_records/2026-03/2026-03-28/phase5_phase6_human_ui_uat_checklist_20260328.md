# Phase 5 + 6 Human UI UAT Checklist

- target_worktree: `D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\phase6_dashboard_worktree`
- server_url: `http://127.0.0.1:8765/`
- live_dataset: `D:\Dev_Env\loc-mvr 测试文档\test_input_200-row.csv`
- seed_runs:
  - `phase6_manual_uat_derived`
  - `phase6_manual_uat_persisted`

## Wave A

- Open `/` and confirm default mode is `Operator Workspace`.
- Confirm these sections render:
  - `Overview Ribbon`
  - `Cross-Run Cards`
  - `Decision Context`
  - `Review Workload`
  - `KPI Snapshot`
  - `Governance Drift`
- With `status=open`, confirm `phase6_manual_uat_derived` is visible.
- Open `phase6_manual_uat_derived` and confirm:
  - decision context populated
  - review workload shows pending review
  - KPI snapshot populated
  - governance drift non-empty
- Switch filter to `status=all` and confirm `phase6_manual_uat_persisted` appears.
- Open `phase6_manual_uat_persisted` and confirm:
  - persisted data is visible
  - cards are closed
  - runtime drilldown is still possible
- Use `Open Runtime Lane` and confirm:
  - mode switches to `Runtime Shell`
  - selected run appears in recent runs
  - timeline is visible
  - verify summary matches run status
  - issue summary matches issue artifact
- Preview:
  - `run_manifest`
  - `smoke_verify_log`

## Wave B

- In `Runtime Shell`, launch one run with:
  - `input = D:\Dev_Env\loc-mvr 测试文档\test_input_200-row.csv`
  - `target_lang = en-US`
  - `verify_mode = preflight`
- Confirm:
  - pending row appears immediately
  - run shows `running`
  - pending detail is visible before final manifest is ready
- Refresh until the launched run becomes manifest-backed or completes.
- Confirm new run detail shows:
  - run id
  - stages/timeline
  - verify summary
  - artifact list
  - previewable manifest/log artifacts
- Return to `Operator Workspace` and confirm:
  - page remains stable
  - `recent_runs` reflects the launched run
  - inbox/card updates are only required if operator-context artifacts exist

## Screenshots

- default `Operator Workspace`
- selected derived card with detail panels
- persisted run visible under `status=all`
- `Runtime Shell` selected run timeline
- artifact preview for `run_manifest`
- launch form filled for live run
- pending live run
- completed or manifest-backed live run detail

## Failure Classification

- `P0`: crash, blank page, impossible launch flow, unsafe artifact access
- `P1`: wrong selection/binding, broken mode switch, missing required content
- `P2`: non-blocking copy/layout/refresh friction
