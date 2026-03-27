# run_issue

- run_id: `plc_phase6_operator_workspace_dashboard_20260327`
- status: `closed`
- blockers: `none`
- env_blockers: `none`
- resolved:
  - `P6-001`: workspace aggregation now uses a pure derivation path and no longer requires write-on-demand summarize behavior inside GET requests.
  - `P6-002`: the local UI now exposes `Runtime Shell` and `Operator Workspace` modes without regressing the accepted Phase 5 runtime lane.
  - `P6-003`: workspace APIs fail closed on invalid `limit`, `status`, `card_type`, `priority`, and unknown `run_id`.
  - `P6-004`: dashboard drilldown routes back through the existing manifest-scoped artifact preview endpoint rather than arbitrary file reads.

