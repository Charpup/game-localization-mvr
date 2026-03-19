# Batch 6 Cleanup Report

## Scope

Batch 6 focused on two non-destructive cleanup goals:

- retire external contracts that still described `repair_loop_v2.py` and
  `repair_checkpoint_gaps.py` as current tooling
- restore Metrics as an optional smoke-pipeline observability stage

This batch does **not** physically archive repair-side scripts and does **not** modify the
keep-chain semantics.

## Repair-side contract retirement

Updated files:

- `main_worktree/.agent/rules/localization-mvr-rules.md`
- `SCRIPTS_INVENTORY.md`
- `main_worktree/.agent/workflows/loc-translate.md`
- `main_worktree/scripts/repair_checkpoint_gaps.py`
- `main_worktree/workflow/batch4_frozen_zone_inventory.json`

Result:

- `repair_loop.py` remains the retained repair authority
- `repair_loop_v2.py` is now documented as a historical candidate pending archive
- `rebuild_checkpoint.py` is the retained checkpoint recovery entrypoint
- `repair_checkpoint_gaps.py` is now documented as historical tooling rather than a current recovery path
- both repair-side targets moved from `blocked` to `archive-candidate` in the frozen-zone inventory

## Metrics rewiring

Updated files:

- `main_worktree/scripts/run_smoke_pipeline.py`
- `main_worktree/scripts/metrics_aggregator.py`

Result:

- smoke runs now attempt a Metrics stage before verify when progress logs are present
- Metrics writes:
  - `smoke_metrics_report.md`
  - `smoke_metrics_report.json`
- manifest wiring now records:
  - `artifacts.metrics_report`
  - `artifacts.metrics_report_json`
  - `stage_artifacts.metrics_log`
  - `stage_artifacts.metrics_report_md`
  - `stage_artifacts.metrics_report_json`
- metrics failure is warning-only (`P2`) and does not block smoke success
- token totals now fall back to trace token fields or char-count estimation when `usage` is absent

## Batch 6 tests

Primary new test file:

- `main_worktree/tests/test_batch6_repair_metrics_contract.py`

This covers:

- repair-side governance retirement
- inventory downgrade to `archive-candidate`
- metrics token fallback
- non-blocking metrics failure behavior
- manifest-visible metrics artifacts
- verify compatibility with manifest-based metrics reports

## Verification

Executed:

- `python -m pytest tests/test_smoke_verify.py tests/test_qa_hard.py tests/test_normalize_segmentation.py tests/test_batch_infrastructure.py tests/test_script_authority.py tests/test_runtime_adapter_contract.py tests/test_normalize_auxiliary_contract.py tests/test_soft_qa_contract.py tests/test_batch3_batch4_governance.py tests/test_batch5_archive_candidates.py tests/test_batch6_repair_metrics_contract.py -vv`
- `python scripts/check_script_authority.py --out reports/script_authority_report_20260319.json`
- `python scripts/m4_3_collect_coverage.py`
- `python scripts/m4_4_decision.py`

Result:

- regression suite: `63 passed`
- authority: `WARN` with `runtime_adapter.py` as the only alert-only drift
- M4 summary: `KEEP=6, BLOCK=0, REWORK=0, OBSOLETE=0`
- issue hotspots: `0`

## Current roadmap position

Batch 6 is the first batch after GitHub governance closure that resumes deep cleanup on
code and contracts. The next logical step is Batch 7:

- reassess whether the two repair-side candidates are now safe to archive
- or pivot into `run_validation.py` / `build_validation_set.py` contract characterization if
  archive is still premature
