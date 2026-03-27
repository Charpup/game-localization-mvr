# Phase 6 Design

## Objective

Add a read-mostly operator workspace dashboard on top of the accepted Phase 5 runtime shell so
operators can see what requires action, why it requires action, and which run/artifact/ADR backs
that decision without leaving the local UI shell.

## Architecture

- `scripts/operator_control_plane.py`
  - now owns both a pure derivation path and the existing write-on-demand summarize path
  - pure derivation returns normalized operator cards and operator summary without writing files
- `scripts/operator_ui_models.py`
  - keeps the Phase 5 run models
  - adds workspace read models that prefer persisted `operator_cards/operator_summary` when present
  - falls back to pure derivation from run-level truth sources when persisted artifacts are absent
- `scripts/operator_ui_server.py`
  - preserves the four Phase 5 `/api/runs*` endpoints
  - adds read-only `/api/workspace/overview`, `/api/workspace/cards`, and `/api/workspace/runs/{run_id}`
- `operator_ui/*`
  - preserves the runtime shell
  - adds a top-level mode switch and six workspace panels:
    - overview ribbon
    - operator inbox
    - decision context
    - review workload
    - KPI snapshot
    - governance drift

## Data Flow

1. Runtime mode keeps using `/api/runs`, `/api/runs/{run_id}`, and `/api/runs/{run_id}/artifacts/{artifact_key}`.
2. Workspace mode loads `/api/workspace/overview?limit_runs=N` for ribbon counters and recent runs.
3. Workspace mode loads `/api/workspace/cards?...` for the inbox list and filters.
4. Selecting a card loads `/api/workspace/runs/{run_id}` for run-level workspace detail.
5. Artifact drilldown routes back through the existing Phase 5 artifact preview endpoint.

## Error Handling

- Invalid workspace `limit`, `status`, `card_type`, or `priority` fail closed with `400`.
- Unknown workspace `run_id` fails closed with `404`.
- Missing `operator_cards`, `operator_summary`, `feedback_log`, or `kpi_report` degrade to derived or empty summaries.
- Pending runs stay visible in the runtime lane but do not appear in workspace inbox aggregation.

## Implemented Notes

- Workspace reads are side-effect free: GET paths never write `data/operator_cards/` or `data/operator_reports/`.
- Persisted operator artifacts still win when present, which keeps CLI/report outputs authoritative.
- The frontend stays framework-free and reuses the Phase 5 shell instead of introducing a second UI stack.
