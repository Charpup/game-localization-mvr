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
