# Value Review: deep-cleanup-main-batch6

## Decision

GO

## Why this is worth doing

Batch 5 proved the next cleanup bottleneck is no longer file deletion risk, but contract
retirement risk. `repair_loop_v2.py` and `repair_checkpoint_gaps.py` could not safely
leave the active `scripts/` surface because operator rules, root inventory, and recovery
workflow docs still described them as current tooling. Retiring those contracts first is
high-value because it reduces false operational surface without touching runtime behavior.

Metrics rewiring is also worth doing now because the functionality still exists but has
been disconnected from the smoke pipeline. Restoring it as an optional observability stage
improves traceability after each smoke run while preserving the current keep-chain gate.

## Evidence captured

- The active keep chain remains
  `llm_ping -> normalize_guard -> translate_llm -> qa_hard -> rehydrate_export -> smoke_verify`.
- `repair_loop_v2.py` no longer appears as a live execution path in active rules or root
  inventory; it is now documented as a historical candidate pending archive.
- `repair_checkpoint_gaps.py` no longer owns the supported checkpoint recovery workflow;
  `scripts/rebuild_checkpoint.py` is now the retained recovery entrypoint.
- `smoke_verify.py` already supports Metrics as an optional stage, so the safest change is
  to reconnect `run_smoke_pipeline.py` to existing Metrics reporting rather than inventing
  a new gate.
- Deterministic Batch 6 tests now cover:
  repair-side governance retirement, metrics token fallback, manifest artifact wiring, and
  non-blocking metrics failure behavior.

## Scope guardrails

- Batch 6 does not modify `repair_loop.py`, `run_validation.py`, or `build_validation_set.py`.
- Batch 6 does not physically archive `repair_loop_v2.py` or `repair_checkpoint_gaps.py`.
- Batch 6 does not make Metrics a required stage.
- Repo-root `src/scripts` remains compatibility-only and stays outside physical cleanup.

## Exit condition for this step

This step is complete when:

- repair-side governance references are retired and both scripts are downgraded from
  `blocked` to `archive-candidate`,
- Metrics artifacts are once again written into smoke manifests and run directories,
- metrics failure remains warning-only,
- the regression suite and evidence gate remain green,
- and the Batch 6 report explains the new roadmap position in an auditable way.
