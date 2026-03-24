# Task Plan

> Historical ledger note:
> The legacy M4 goal/phases below remain for traceability only.
> The current active scope is `milestone_E_prepare` on branch `codex/milestone-e-prepare`.

## Goal
Run M4 preflight and full on `data/smoke_runs/inputs/test_input_1000_smoke_layered.csv`, then capture run paths, manifests, issues, and blocking points for mainline cleanup.

## Scope
- Use `main_worktree` only.
- Record `run_id`, manifest path, issue report path, verify report path, and any row/placeholder/tag mismatches.
- Focus on `string_id=305833`, translate row counts, and `row_checks`.

## 2026-03-21 PLC + TriadDev Integration Priority

### Goal
Stabilize the C/D milestone branch into one mergeable mainline PR, clear outstanding review feedback, and only then open milestone E from a clean `main`.

### Route
- `plc`: use `docs/project_lifecycle/continuity_protocol.md`, `docs/project_lifecycle/roadmap_index.md`, and dated `run_records` as the governance source of truth.
- `triadev`: stay on the Extended route with the already-passed value gate; this step is implementation hardening and integration cleanup, not new feature expansion.

### Scope
- Treat `codex/plc-c-verify` as the only active integration branch for GitHub.
- Pull only the minimum necessary fixes into that branch:
  - PR #9 code review fixes in `scripts/soft_qa_llm.py` and `scripts/translate_llm.py`
  - PLC ledger/schema corrections needed to keep milestone B/C/D evidence internally consistent
- Do not implement milestone E functionality in this step.
- Do not broaden the cleanup roadmap or reopen archived Batch 1-10 surfaces.

### Integration Phases
- [complete] Phase 0: Reconcile PLC roadmap state vs GitHub PR topology and choose a single mainline PR.
- [complete] Phase 1: Land the minimum code fixes required by PR #9 review.
- [complete] Phase 2: Land the minimum PLC contract fixes required for schema/ledger consistency.
- [complete] Phase 3: Run targeted regression and document merge readiness.
- [complete] Phase 4: Merge/hand off to clean `main`, then open milestone E from updated trunk.

### Exit Criteria
- PR #9 remains the single active mainline PR candidate.
- `soft_qa_llm` no longer drops higher-severity placeholder findings behind lower-severity length findings.
- `translate_llm` and `soft_qa_llm` both surface prohibited alias / banned term constraints from the style profile.
- milestone B run manifest uses a schema-valid run status.
- the stale milestone-B blocker is removed from the active ledger.
- milestone E remains `next_scope` only, with no E implementation mixed into this integration branch.

### Current Result
- Integration branch remains `codex/plc-c-verify`.
- Completed code fixes:
  - `scripts/soft_qa_llm.py`
  - `scripts/translate_llm.py`
- Completed governance fixes:
  - `docs/project_lifecycle/run_records/2026-03/2026-03-21/run_manifest_plc_run_b_202603211300.json`
  - `docs/decisions/ADR-0001-project-continuity-framework.md`
  - `docs/decisions/ADR-0002-skill-governance-framework.md`
  - `docs/decisions/README.md`
  - `docs/decisions/index.md`
- Completed regression:
  - `python -m pytest tests/test_soft_qa_contract.py -q`
  - `python -m pytest tests/test_translate_style_contract.py -q`
  - `python -m pytest tests/test_plc_docs_contract.py -q`
- Remaining action:
  - start `milestone_E_prepare` from refreshed `main`

### Merge Result
- PR #9 merged into `main` as `fdc253f`.
- PR #7 and PR #8 were marked superseded by PR #9 and closed.
- mainline integration phase is complete; the next active scope is `milestone_E_prepare`.

## 2026-03-21 Milestone E Prepare

### Goal
Prepare milestone E from clean post-merge mainline and define the implementation entry for delta tooling plus incremental retranslation task generation.

### Route
- `plc`: start from the latest merged `main` and maintain dated handoff continuity.
- `triadev`: remain on Extended route, reuse the already-passed value gate, and stop at planning/delta/tasks readiness for E.

### Scope
- Work only from `codex/milestone-e-prepare`.
- Define the E planning surface around:
  - delta tool entrypoints and expected artifacts
  - incremental retranslation task generation flow
  - integration points with the C/D style and drift gates
- Do not implement E runtime behavior in this kickoff step.

### Mini Plan
- [complete] Read merged PLC/TriadDev state from `main` and open milestone E session records.
- [complete] Identify the minimum E planning interfaces: delta inputs, outputs, and handoff artifacts.
- [complete] Prepare the next implementation-ready task slice for E without entering code changes beyond planning docs/state.

## 2026-03-24 Milestone E Implementation Gate

### Goal
Lock the milestone E contract and execution order, then execute the first two implementation packages with subagent-first ownership boundaries.

### Route
- `plc`: keep dated run records, `task_plan.md`, and `progress.md` aligned to the active E package.
- `triadev`: remain on Extended route; use `workflow/milestone_e_contract.yaml` as the E gate artifact and update `.triadev/workflow.json` to the E change id before downstream implementation.

### Package Order
- [complete] E-contract: freeze locale-generic contracts, compat-layer rules, and hard-gate enums.
- [complete] E-repro: make glossary/style inputs explicit, restore clean-worktree reproducibility, and align docs plus CLI behavior.
- [complete] E-delta-engine: replace narrow glossary-only impact logic with typed delta propagation and operator-facing reports.
- [complete] E-task-executor: generate incremental tasks from row impacts, execute bounded actions, and enforce post-run gates.
- [complete] E-regression: close reviewer blockers, rerun milestone E regression, and record evidence.

### Worker Ownership
- Main thread owns `E-contract`, PLC ledger updates, and `.triadev/workflow.json` gate alignment.
- Worker A owns `E-repro`:
  - CLI/input authority
  - clean-worktree reproducibility
  - doc/arg parity
  - soft-QA contract drift
- Worker B owns `E-delta-engine`:
  - typed delta logic
  - delta artifact schemas
  - impact classification
- Worker C opens only after A/B integrate:
  - incremental task generation
  - executor split
  - post-run manifest and gates

### Exit Criteria
- `workflow/milestone_e_contract.yaml` is the single E contract source of truth.
- `.triadev/workflow.json` no longer points at Batch 10 and reflects `milestone-e-prepare-20260324`.
- clean-worktree execution no longer assumes residual `data/style_profile.yaml` or `data/glossary.yaml`.
- typed delta output explains impact by locale, content class, and rule reason rather than a bare `impact_set`.
- incremental task artifacts exist before any executor writes candidate output.

### Current Active Slice
- Main thread completed the E gate and integrated the first parallel wave.
- Worker A completed `E-repro`:
  - explicit glossary/style authority resolution
  - clean-worktree bootstrap behavior
  - README and workflow CLI parity
  - soft-QA contract reconciliation
- Worker B completed `E-delta-engine`:
  - typed delta propagation across glossary, style profile, rubric, placeholder, and rule changes
  - locale-generic row-impact artifacts and aggregate reports
- Worker C is now responsible for `E-task-executor`:
  - `delta_rows.jsonl` -> `incremental_tasks.jsonl`
  - review queue generation
  - bounded execution and `qa_hard` post-gates
- Reviewer blockers are now closed:
  - executor writes to a staged candidate file before post-gates
  - mixed-locale execution groups tasks by `target_locale`
  - glossary loading is fail-closed for non-`ru-RU` locales
  - E contract no longer promises an unimplemented `soft_qa` task type

### Final Result
- `E-task-executor` now stages candidate CSV output, writes an explicit `incremental_failure_breakdown.json`, and only promotes the final `--out-csv` after row-count, placeholder, and `qa_hard` gates pass.
- `translate_refresh.py` now executes refresh / retranslate by locale group instead of one global target locale, so mixed-market tasks update the correct target columns.
- `translate_llm.py` and `glossary_delta.py` now treat locale lookup as fail-closed:
  - `targets.<locale>` must match the requested locale
  - legacy `term_ru` / `target_ru` compatibility is retained only for `ru-RU`
- Milestone E focused regression is green:
  - `python -m pytest tests/test_translate_refresh_contract.py tests/test_milestone_e_e2e.py tests/test_soft_qa_contract.py tests/test_milestone_e_repro_contract.py tests/test_glossary_delta_contract.py tests/test_milestone_e_delta_contract.py tests/test_translate_style_contract.py tests/test_plc_docs_contract.py -q`
  - result: `27 passed`

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
- [complete] Phase 4: Prepare commit, push branch, and open the Batch 8 PR.

## 2026-03-19 Deep Cleanup Batch 9

### Goal
Canonicalize the remaining stress-like shell surface so the active `main_worktree`
cleanup roadmap can enter final closeout with one retained stress entrypoint, clear
archive-candidate scripts, and auditable helper classifications.

### Scope
- Keep `scripts/stress_test_3k_run.sh` as the retained canonical stress shell path.
- Reclassify `acceptance_stress_*.sh` and adjacent stress helpers using evidence from
  live CLI drift, runbook bindings, and recent mainline coverage.
- Keep `repair_loop.py`, `run_validation.py`, `build_validation_set.py`,
  `rebuild_checkpoint.py`, keep-chain, M4, authority drift policy, and optional Metrics unchanged.
- Do not physically archive any stress shell in this batch; this batch is status
  canonicalization plus the minimum CLI alignment needed for the retained path.

### Phases
- [complete] Phase 0: Reconfirm Batch 9 target scope from the frozen-zone inventory and Batch 8 closeout report.
- [complete] Phase 1: Add Batch 9 governance tests for stress-shell canonicalization and helper status assertions.
- [complete] Phase 2: Reclassify the stress shell and helper surfaces in inventory, update TriadDev control files, and align the retained shell path to current CLI contracts.
- [complete] Phase 3: Run Batch 9 regression suite plus evidence gate.
- [complete] Phase 4: Prepare commit scope, push the branch, and record the closeout-readiness decision for Batch 10.

## 2026-03-19 Deep Cleanup Batch 10

### Goal
Close the current cleanup roadmap by fixing a final governance decision for `src/scripts`
as an operationally retained but exit-planned compatibility mirror, without treating its
physical removal as part of this batch's final roadmap closeout.

### Scope
- Keep `../src/scripts/**` present and `compat-keep`, but add explicit closeout decision
  metadata and exit blockers.
- Remove non-real blocked placeholders from the frozen-zone inventory so the closeout
  criteria only reflect real surfaces.
- Keep keep-chain, M4, authority semantics, retained production-dev baselines, retained
  stress authority, and packaging behavior unchanged.
- Treat any future `src/scripts` retirement as a separate migration program rather than an
  unfinished part of this cleanup roadmap.

### Phases
- [complete] Phase 0: Reconfirm from Batch 9 report and authority/packaging evidence that `src/scripts` is the only remaining governance decision.
- [complete] Phase 1: Add Batch 10 closeout governance tests for compat mirror decision and no-real-blocked-surface criteria.
- [complete] Phase 2: Update authority manifest, frozen-zone inventory, root inventory, and closeout report with the fixed compat mirror decision.
- [complete] Phase 3: Run Batch 10 regression suite plus authority/M4 evidence gate.
- [complete] Phase 4: Prepare stacked closeout branch output and declare the cleanup roadmap closed after Batch 10, with any future compat mirror retirement handled as a separate migration program.

## 2026-03-21 Milestone D 收口与里程碑 E 续接

### Goal
Complete milestone D baseline/d drift-control hard-gate closure and register evidence for the next milestone.

### Scope
- Run `baseline_drift_control` preset for `plc_run_d_prepare` / `plc_run_d_full` / `plc_run_d_verify` with可复现参数.
- 补齐并校验 `run_manifest` / `run_issue` / `run_verify` 与 `milestone_state_D`、`roadmap_index` 闭环。
- 触发 `milestone_E_prepare` 的 handoff 准备。

### Results
- `plc_run_d_prepare` / `plc_run_d_full` / `plc_run_d_verify` 均 pass，`evidence_ready=true`，`run_id=plc_run_d_verify`。
- evidence:
  - `docs/project_lifecycle/run_records/2026-03/2026-03-21/run_manifest_plc_run_d_verify.json`
  - `docs/project_lifecycle/run_records/2026-03/2026-03-21/run_issue_plc_run_d_verify.md`
  - `docs/project_lifecycle/run_records/2026-03/2026-03-21/run_verify_plc_run_d_verify.md`

### Next Owner
- `Codex`，`next_scope=milestone_E_prepare`
