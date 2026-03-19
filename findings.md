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
