# Findings

## Current task
- Planning files were missing and have been created.
- Core scripts are present: `scripts/run_smoke_pipeline.py`, `scripts/smoke_verify.py`, `scripts/llm_ping.py`.
- Exact-input preflight/full runs were attempted in `data/smoke_runs/manual_1000_preflight_20260318_124314`, `data/smoke_runs/manual_1000_preflight_20260318_124327`, `data/smoke_runs/manual_1000_preflight_20260318_124433`, and `data/smoke_runs/manual_1000_full_20260318_124415`.
- Pipeline connectivity is failing inside `run_smoke_pipeline.py` even when direct `scripts/llm_ping.py` succeeds in the shell.
- Older full run `data/smoke_runs/manual_1000_full_20260318_122459` reached translation and QA Hard, then failed on QA Hard with `85` errors.

## To record
- Preflight and full run IDs.
- Manifest paths.
- Any issue JSON/JSONL files written by the pipeline.
- Any mismatch involving `string_id=305833`, translate row counts, or row checks.

## 2026-03-19 Deep Cleanup R3
- Checkpoint branch `codex/checkpoint-mainline-20260319` was created, split into three commits, and pushed to origin.
- Brownfield control artifacts now exist for `codex/deep-cleanup-r3`: `.triadev/state.json`, `.triadev/workflow.json`, `SPEC.yaml`, `SPEC-delta.yaml`, and `value-review.md`.
- Batch 1 authority governance artifacts now exist: `workflow/script_authority_manifest.json`, `scripts/check_script_authority.py`, and `reports/script_authority_report_20260319.json`.
- Batch 1 regression coverage was expanded in `tests/test_batch_infrastructure.py` and `tests/test_script_authority.py`.
- Current authority check result is `WARN`, not `FAIL`: only `runtime_adapter.py` remains in `alert_only_drift`; required mirror files are not drifting.
- Current regression/evidence state is green:
  - `pytest tests/test_smoke_verify.py tests/test_qa_hard.py tests/test_normalize_segmentation.py tests/test_batch_infrastructure.py tests/test_script_authority.py -vv`
  - `scripts/check_script_authority.py --out reports/script_authority_report_20260319.json`
  - `scripts/m4_3_collect_coverage.py`
  - `scripts/m4_4_decision.py`
- `M4_4_decision.jsonl` remains `KEEP=6, BLOCK=0, REWORK=0, OBSOLETE=0`.

## 2026-03-19 Deep Cleanup R3 Batch 2
- The minimal irreversible center is now explicitly treated as:
  `run_smoke_pipeline + keep chain + runtime_adapter + smoke_issue_logger + governance/tests`.
- `src/scripts` remains blocked from physical cleanup and stays in drift-governance mode only.
- `runtime_adapter.py` was found to contain a real router injection bug:
  passing an explicit router into `LLMClient(...)` still got overwritten by the shared
  class router. Batch 2 fixes and tests now pin that behavior.
- `normalize_tagger.py`, `normalize_tag_llm.py`, `translate_llm.py`, and `soft_qa_llm.py`
  all had import-time stdout/stderr behavior that could destabilize test capture.
  Batch 2 moves those stream adjustments to CLI execution time.
- `soft_qa_llm.py --dry-run` had a concrete contract break:
  it called `split_into_batches()` without importing it and instantiated the wrong
  `BatchConfig` type. Batch 2 fixes and tests now pin the correct `batch_utils` path.
- Current audit statuses are:
  - `runtime_adapter.py`: `must-keep core`
  - `normalize_ingest.py`: `frozen audit candidate`
  - `normalize_tagger.py`: `must-keep candidate`
  - `normalize_tag_llm.py`: `frozen duplicate / compat-keep`
  - `qa_soft.py`: `compat-keep wrapper`
  - `soft_qa_llm.py`: `compat-keep canonical`
- New Batch 2 test surfaces now exist:
  - `tests/test_runtime_adapter_contract.py`
  - `tests/test_normalize_auxiliary_contract.py`
  - `tests/test_soft_qa_contract.py`

## 2026-03-19 Deep Cleanup R3 Phase 1 Batch 3/4
- `normalize_tagger.py` is still the best-supported canonical normalize classifier:
  it has live workflow references plus fixture coverage for heuristic/LLM fallback behavior.
- `normalize_tag_llm.py` is not a pure duplicate: it still owns the `--length-rules`
  variant and appears in stress-like shell entrypoints, so it is now classified as a
  stress-only compatibility entrypoint rather than a frozen duplicate.
- `qa_soft.py` is intentionally tiny, but it still represents a compatibility contract:
  callers expect it to forward CLI arguments into `soft_qa_llm.py`.
- `normalize_ingest.py` is still a documented ingest path and now stays classified as a
  compat-keep documented ingest surface rather than an audit-only candidate.
- `repair_loop.py`, `repair_loop_v2.py`, `repair_checkpoint_gaps.py`, `run_validation.py`,
  and `build_validation_set.py` all remain blocked because they lack deterministic test
  coverage in `main_worktree/tests` and still have doc/config/runbook references.
- There is no concrete `gate/` or `stress/` directory inside `main_worktree`; the real
  stress-like surface currently lives in shell entrypoints under `scripts/`.
- `stress_test_3k_run.sh` had live CLI drift against `soft_qa_llm.py`; it now points to
  `--out_report`/`--out_tasks` and feeds repair loop the actual tasks JSONL instead of the report JSON.
- Remote branch topology now supports the planned end-state:
  - fully contained in `origin/main`: `backup-before-cleanup`, `feat/apiyi-metrics-integration`,
    `feature/batch-llm-runtime`, `feature/omni-test-cost-monitoring`, `sync/local-baseline-20260122`
  - same tip as `origin/main`: `release/production-go-complete`
  - audit-first outlier: `reorg/v1.3.0-structure`

## 2026-03-19 Deep Cleanup Batch 5
- `repair_loop_v2.py` and `repair_checkpoint_gaps.py` were already the lowest-risk cleanup
  targets in the frozen-zone inventory because they were classified as `archive-candidate`
  rather than `blocked`.
- Local reference recheck still finds no active runtime caller for either file; remaining
  mentions are limited to rules, legacy reports, inventory, and the new Batch 5 artifacts.
- `repair_loop_v2.py` still exposes a real CLI contract (`--input`, `--tasks`, `--output`,
  `--output-dir`, `--qa-type`, `--config`), so Batch 5 characterizes that contract before archive.
- `repair_checkpoint_gaps.py` is confirmed to be a one-off hard-coded recovery tool that
  reconstructs `data/translate_checkpoint.json` from specific checkpoint and CSV inputs.
- Independent audit found hidden blockers:
  `repair_loop_v2.py` still appears in active rules and root-level inventory, and
  `repair_checkpoint_gaps.py` is still tied to the documented `translate_checkpoint.json`
  recovery contract via `scripts/rebuild_checkpoint.py` and `.agent/workflows/loc-translate.md`.
- Batch 5 therefore falls back to inventory-only: both files stay in `scripts/` and are
  reclassified as `blocked` until the rule/inventory/recovery contracts are explicitly retired.
- `repair_loop.py`, `run_validation.py`, and `build_validation_set.py` remain frozen:
  this batch does not change their status or interfaces.

## 2026-03-19 Deep Cleanup Batch 6
- `repair_loop_v2.py` is no longer described as an active repair path in the rules or the
  root inventory. It is now explicitly documented as a historical candidate pending archive.
- `repair_checkpoint_gaps.py` no longer owns the supported `translate_checkpoint.json`
  recovery story. The retained recovery entrypoint is `scripts/rebuild_checkpoint.py`;
  `repair_checkpoint_gaps.py` now survives only as a historical helper.
- `workflow/batch4_frozen_zone_inventory.json` now classifies both
  `repair_loop_v2.py` and `repair_checkpoint_gaps.py` as `archive-candidate`, not `blocked`.
- The Metrics subsystem still existed in code before Batch 6, but it had become detached
  from smoke orchestration. `scripts/run_smoke_pipeline.py` now runs
  `scripts/metrics_aggregator.py` as a non-blocking stage before verify.
- Metrics writes are now attached to the run manifest through
  `artifacts.metrics_report`, `artifacts.metrics_report_json`, and stage artifacts for the
  log and two report files.
- `scripts/metrics_aggregator.py` now supports token fallback from trace char counts when
  usage blocks are missing, which restores a stable metrics summary for mixed trace quality.
- Batch 6 keeps the smoke gate unchanged:
  metrics failures are warning-only (`P2`) and must not flip an otherwise healthy smoke run to failed.
- New Batch 6 test surface lives in `tests/test_batch6_repair_metrics_contract.py`.
- Full Batch 6 regression is green at `63 passed`.
- Authority drift remains at the accepted level:
  only `runtime_adapter.py` is alert-only drift after re-syncing the required
  `src/scripts/run_smoke_pipeline.py` mirror.

## 2026-03-19 Deep Cleanup Batch 7
- `run_validation.py` and `build_validation_set.py` are not cleanup noise; they are the
  retained development validation baseline and now have deterministic contract coverage for
  sampling, metadata, scoring, parse fallback, and explicit I/O paths.
- `docs/repro_baseline.md` had real drift before Batch 7:
  it favored implicit defaults and still referenced `config/api_key.txt` even though the
  current retained contract uses `--api-key-path` and defaults to `data/attachment/api_key.txt`.
- `repair_loop.py` remains the active repair authority, not a historical side surface.
  The real CLI is flags-only, and the script already supports both hard-report JSON and
  soft-task JSONL through `--tasks`.
- `docs/WORKSPACE_RULES.md` was still overstating checkpoint behavior and still listed a
  generic `repair` step. Batch 7 aligns that policy surface to the real runtime steps:
  `repair_hard` and `repair_soft_major`, with snapshot-only checkpoint semantics.
- After Batch 6, `repair_loop_v2.py` and `repair_checkpoint_gaps.py` are already in the
  right place for now: `archive-candidate`. Batch 7 should not mix physical archive work
  into production-dev recovery.
- Batch 7 focused validation and repair contract suites are green, and the full regression
  suite now passes at `77 passed`.
- Authority remains at the accepted level (`WARN`) with `runtime_adapter.py` as the only
  alert-only drift, and `M4_4_decision.jsonl` still reports `KEEP=6`.

## 2026-03-19 Deep Cleanup Batch 8
- `repair_loop_v2.py` and `repair_checkpoint_gaps.py` no longer have retained active-path
- status after Batch 6/7; their remaining references are historical evidence, cleanup
  reports, inventory state, and translate-recovery documentation that already points to
  `scripts/rebuild_checkpoint.py` as the retained path.
- `_obsolete/repair_archive/` exists but is not yet a real archive surface; before Batch 8
  it only contains stray `__pycache__` output and no audit README.
- Root inventory still describes `repair_loop_v2.py` as pending archive, so Batch 8 needs
  to convert that wording to archived historical utility rather than current candidate.
- Batch 8 archive closeout is now in place: both historical repair-side utilities live
  under `_obsolete/repair_archive/` and no longer occupy the active `scripts/` surface.
- Batch 8 focused archive tests and full regression are green; total suite is now
  `81 passed`.
- Authority remains at the accepted level (`WARN`) with `runtime_adapter.py` as the only
  alert-only drift, and `M4_4_decision.jsonl` still reports `KEEP=6`.

## 2026-03-19 Deep Cleanup Batch 9
- The only real blocked surface left in `main_worktree/scripts` after Batch 8 is the
  stress-like shell layer; `gate/**` is only a placeholder entry, not a real directory.
- `scripts/stress_test_3k_run.sh` is the best retained stress shell candidate because it
  already matches the current `repair_loop.py` and `soft_qa_llm.py` contracts, but before
  Batch 9 it still had a live export drift against `rehydrate_export.py`.
- `acceptance_stress_final.sh` and `acceptance_stress_resume.sh` still use drifted
  `rehydrate_export.py --input --placeholder-map --output` syntax and have no active
  `main_worktree` doc/runbook bindings, so they should not remain implied must-keep.
- `acceptance_stress_resume_fix.sh` uses a less-drifted export form, but it is still a
  one-off fix variant rather than a retained operator path.
- `acceptance_stress_run.sh` and `acceptance_stress_phase3.sh` are historical split-phase
  5k helpers, not the retained stress authority path.
- `finalize_stress_report.py` belongs to the historical 5k acceptance flow,
  `verify_3k_test.py` is only a read-only 3k verification helper adjacent to the retained
  path, and `run_long_text_gate_v1.py` is best treated as a gate experiment candidate.
- Batch 9 should move the roadmap into closeout territory: after stress canonicalization,
  the only meaningful remaining cleanup decision should be `src/scripts` compat mirror.

## 2026-03-19 Deep Cleanup Batch 10
- `src/scripts` is not the runtime authority and should not remain framed as a healthy
  long-term keep surface; authority already lives in `main_worktree/scripts`.
- `src/scripts` still cannot be physically removed in the same batch because it remains
  bound by `package_v1.3.0.sh`, authority/governance tests, and legacy inventory/docs.
- The correct Batch 10 decision is therefore governance closeout, not mirror deletion:
  keep `src/scripts` operationally, but mark it as `separate-exit-program`.
- Removing the non-real `gate/**` placeholder from the frozen-zone inventory is part of
  honest closure; after Batch 10 there should be no real blocked cleanup surface left.
- If the team later wants to retire `src/scripts`, that work should be tracked as a new
  compat-mirror migration project, not as unfinished cleanup debt from the current roadmap.
- Batch 10 meets the closure bar when treated as a governance decision batch:
  the inventory can now reach zero real blocked surfaces while authority stays at
  `WARN(runtime_adapter only)` and M4 remains `KEEP=6`.
- Batch 9 regression/evidence state is green: focused governance regression passed, the
  explicit full test-file run passed at `98 passed, 8 skipped`, authority remains `WARN`
  only on `runtime_adapter.py`, and `M4_4_decision.jsonl` still reports `KEEP=6`.

## 2026-03-27 Phase 5 Closeout
- The original Phase 5 acceptance blocker was environmental, not code-level:
  `llm_ping.py` passed immediately once `LLM_BASE_URL` and `LLM_API_KEY` were injected for the process.
- PR #19 still had real merge blockers after the first acceptance pass:
  unresolved frontend timeline and verify field mismatches,
  unresolved run-id collision risk in `operator_ui_launcher.py`,
  and an unpushed local fix for `operator_ui_server.py` script entrypoint / asset fallback.
- The frontend regressions survived the first implementation pass because API tests were green while no test pinned the JavaScript field names against the backend contract.
- A real online representative run through the local UI shell now proves the Phase 5 surface is end-to-end viable:
  launch, run discovery, run detail, stage timeline, verify summary, issue summary, and allow-list artifact preview all work over live HTTP.
