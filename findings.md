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
