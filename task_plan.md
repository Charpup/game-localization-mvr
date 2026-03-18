# Task Plan

## Goal
Run M4 preflight and full on `data/smoke_runs/inputs/test_input_1000_smoke_layered.csv`, then capture run paths, manifests, issues, and blocking points for mainline cleanup.

## Scope
- Use `main_worktree` only.
- Record `run_id`, manifest path, issue report path, verify report path, and any row/placeholder/tag mismatches.
- Focus on `string_id=305833`, translate row counts, and `row_checks`.

## Phases
- [complete] Phase 1: Initialize plan files and inspect run entrypoints.
- [complete] Phase 2: Run `llm_ping` and preflight.
- [complete] Phase 3: Run full.
- [in_progress] Phase 4: Summarize outputs and block points.

## Notes
- Do not change implementation unless a blocking issue requires it.
- Keep the report anchored to absolute local paths.

## Run IDs collected
- `smoke_run_20260318_044314`
- `smoke_run_20260318_044327`
- `smoke_run_20260318_044415`

## 2026-03-19 Deep Cleanup R3

### Goal
Bootstrap the TriadDev brownfield control plane for `codex/deep-cleanup-r3`, add Batch 1 TDD coverage for authority drift and runtime adapter recovery, and keep the M4 evidence chain intact.

### Scope
- Treat `main_worktree/scripts` as the runtime authority.
- Keep repo-root `src/scripts` as a compatibility mirror only.
- Add alerting for drift without deleting compat-zone files.
- Preserve the keep chain: `llm_ping -> normalize_guard -> translate_llm -> qa_hard -> rehydrate_export -> smoke_verify`.

### Phases
- [complete] Phase 0: Freeze and push the checkpoint branch `codex/checkpoint-mainline-20260319`.
- [complete] Phase 1: Materialize `.triadev/*`, `SPEC.yaml`, `SPEC-delta.yaml`, and `value-review.md`.
- [complete] Phase 2: Add/update Batch 1 tests for `runtime_adapter` and script authority drift.
- [complete] Phase 3: Run Batch 1 regression suite plus M4 evidence gate.
- [in_progress] Phase 4: Stage and commit `codex/deep-cleanup-r3` Batch 1 changes.
