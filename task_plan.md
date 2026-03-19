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
- [complete] Phase 4: Stage and commit `codex/deep-cleanup-r3` Batch 1 changes.

## 2026-03-19 Deep Cleanup R3 Batch 2

### Goal
Stabilize the shared runtime contract, audit `normalize_*` and `soft QA` surfaces using
fixture tests, and keep cleanup aligned to the smallest system needed for continued
development.

### Scope
- Keep `main_worktree/scripts` as the runtime authority.
- Treat `src/scripts` as drift-governed compatibility only.
- Work only in `runtime_adapter.py`, `normalize_ingest.py`,
  `normalize_tagger.py`, `normalize_tag_llm.py`, `qa_soft.py`, `soft_qa_llm.py`,
  and supporting `tests/`.
- Freeze `repair`, `validation`, `gate`, `stress`, and repo-root `src/scripts`.

### Phases
- [complete] Phase 0: Re-confirm first-principles core, compat zone, and blocked surfaces.
- [complete] Phase 1: Add RED contract tests for runtime adapter routing/error handling.
- [complete] Phase 2: Add fixture tests for normalize ingest/tagger and soft QA behavior.
- [complete] Phase 3: Apply minimal fixes for router injection, dry-run batching, and import-time stream side effects.
- [complete] Phase 4: Run Batch 2 regression + evidence gate and prepare commit scope.

## 2026-03-19 Deep Cleanup R3 Phase 1 Batch 3/4

### Goal
Finish Phase 1 of the cleanup roadmap by freezing near-core surface decisions, adding
minimal CLI governance tests, and producing the blocked-zone and branch-audit artifacts
needed before any later PR merge or remote branch cleanup.

### Scope
- Keep `main_worktree/scripts` as the authority zone.
- Do not physically delete `normalize_*`, `soft QA`, or compat-mirror files.
- Do not implement inside `repair`, `validation`, stress-like shell flows, or repo-root `src/scripts`.
- Produce a GitHub branch audit checklist, but do not merge or delete remote branches yet.

### Phases
- [complete] Phase 0: Re-collect Batch 3/4 evidence from tests, docs, and branch topology.
- [complete] Phase 1: Materialize Batch 3 surface-status and Batch 4 blocked-surface inventories.
- [complete] Phase 2: Add governance tests for wrapper forwarding and CLI failure boundaries.
- [complete] Phase 3: Run smoke-focused regression, authority gate, and M4 evidence gate.
- [complete] Phase 4: Prepare commit scope for roadmap Phase 1 artifacts and branch audit checklist.

## 2026-03-19 Deep Cleanup Batch 5

### Goal
Archive the two lowest-risk repair-side historical utilities out of `main_worktree/scripts`
after characterization tests and reference rechecks confirm they are not part of the
active runtime or current repair authority path.

### Scope
- Work only on `repair_loop_v2.py`, `repair_checkpoint_gaps.py`, Batch 5 tests, and
  supporting TriadDev/governance artifacts.
- Attempt archive only if reference and recovery-contract checks stay clean.
- Keep `repair_loop.py`, `run_validation.py`, `build_validation_set.py`, stress-like shell
  entrypoints, and repo-root `src/scripts` frozen.
- Preserve the keep chain:
  `llm_ping -> normalize_guard -> translate_llm -> qa_hard -> rehydrate_export -> smoke_verify`.

### Phases
- [complete] Phase 0: Recheck references and confirm both targets remain archive-candidates.
- [complete] Phase 1: Add Batch 5 characterization tests for archived CLI/recovery contracts.
- [complete] Phase 2: Roll back archive action after hidden dependency review; keep both targets in `scripts/` and reclassify them as blocked for now.
- [complete] Phase 3: Run Batch 5 regression suite, authority gate, and M4 evidence gate.
- [complete] Phase 4: Prepare commit scope and report the new roadmap position.

## 2026-03-19 Deep Cleanup Batch 6

### Goal
Retire the remaining governance contracts around `repair_loop_v2.py` and
`repair_checkpoint_gaps.py`, restore Metrics as a visible but non-blocking smoke stage,
and keep the keep-chain and M4 evidence logic unchanged.

### Scope
- Work in rules, workflow docs, root inventory, metrics wiring, Batch 6 tests, and
  TriadDev control files only.
- Reclassify `repair_loop_v2.py` and `repair_checkpoint_gaps.py` from `blocked` back to
  `archive-candidate` without physically archiving them in this batch.
- Reconnect `scripts/metrics_aggregator.py` to `scripts/run_smoke_pipeline.py` as an
  optional observability stage.
- Keep `repair_loop.py`, `run_validation.py`, `build_validation_set.py`, and repo-root
  `src/scripts` frozen.

### Phases
- [complete] Phase 0: Collect Batch 6 evidence from repair contracts, metrics workflow, and existing smoke wiring.
- [complete] Phase 1: Add RED tests for repair-side governance retirement and optional metrics behavior.
- [complete] Phase 2: Retire repair-side rules/inventory/workflow references and downgrade both scripts to `archive-candidate`.
- [complete] Phase 3: Rewire Metrics into the smoke manifest as a warning-only optional stage and add token fallback support.
- [complete] Phase 4: Run Batch 6 full regression + evidence gate and prepare commit scope.

## 2026-03-19 Deep Cleanup Batch 7

### Goal
Recover the retained validation baseline and repair authority surfaces so normal production
development can continue on top of a tested, documented mainline.

### Scope
- Promote `run_validation.py` and `build_validation_set.py` from `blocked` to `must-keep`
  by pinning their deterministic sampling, scoring, report-schema, and explicit I/O
  contracts.
- Promote `repair_loop.py` from `blocked` to `must-keep` by pinning its flags-only CLI,
  supported task formats, artifact outputs, and routing metadata.
- Keep `repair_loop_v2.py` and `repair_checkpoint_gaps.py` as `archive-candidate`; do not
  physically archive them in this batch.
- Preserve keep-chain, M4, authority drift policy, and optional Metrics semantics.

### Phases
- [complete] Phase 0: Reconfirm Batch 7 route and guardrails from `task_plan.md`.
- [complete] Phase 1: Land deterministic validation and repair contract tests.
- [complete] Phase 2: Align docs, rules, and frozen-zone inventory to the retained validation and repair authority contracts.
- [complete] Phase 3: Run Batch 7 regression suite plus evidence gate.
- [complete] Phase 4: Prepare commit, push branch, and write the Batch 7 report.

## 2026-03-19 Deep Cleanup Batch 8

### Goal
Complete the physical archive closeout for the two historical repair-side utilities so
they leave the active `scripts/` surface without changing retained development baselines
or smoke-chain semantics.

### Scope
- Move `repair_loop_v2.py` and `repair_checkpoint_gaps.py` from `scripts/` into
  `_obsolete/repair_archive/`.
- Add a repair-archive README plus a Batch 8 closeout report.
- Promote both surfaces from `archive-candidate` to `archive-complete` in
  `workflow/batch4_frozen_zone_inventory.json`.
- Preserve `repair_loop.py`, `run_validation.py`, `build_validation_set.py`,
  `rebuild_checkpoint.py`, keep-chain, M4, authority drift policy, and optional Metrics.

### Phases
- [complete] Phase 0: Reconfirm that both repair-side targets have no retained active caller and only historical references remain.
- [complete] Phase 1: Add/archive-adjust characterization tests for physical closeout.
- [complete] Phase 2: Move both files into `_obsolete/repair_archive/` and sync README/inventory/reporting.
- [complete] Phase 3: Run Batch 8 regression suite plus evidence gate.
- [in_progress] Phase 4: Prepare commit, push branch, and open the Batch 8 PR.
