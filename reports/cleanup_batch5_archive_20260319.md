# Batch 5 Archive Cleanup Report

## Summary

Batch 5 started as an archive-candidate cleanup attempt for:

- `repair_loop_v2.py`
- `repair_checkpoint_gaps.py`

Final outcome: fallback-to-blocked. The archive move was rolled back after hidden
dependency review, so both files remain under `scripts/`.

## Why they were considered first

- neither script is part of the smoke keep-chain
- `repair_loop_v2.py` has no active runtime caller in `main_worktree`
- `repair_checkpoint_gaps.py` is a hard-coded one-off recovery utility
- both were already classified as `archive-candidate` in `workflow/batch4_frozen_zone_inventory.json`

## Why archive was rolled back

- `repair_loop_v2.py` still appears in active rules and root-level inventory, so the
  surrounding contract surface is not yet retired.
- `repair_checkpoint_gaps.py` still participates in the documented
  `translate_checkpoint.json` recovery contract through `scripts/rebuild_checkpoint.py`
  and `.agent/workflows/loc-translate.md`.
- Batch 5 policy requires fallback to inventory-only when hidden dependencies appear.

## Remaining frozen surfaces

- `repair_loop_v2.py`
- `repair_checkpoint_gaps.py`
- `repair_loop.py`
- `run_validation.py`
- `build_validation_set.py`
- stress-like shell entrypoints under `scripts/`
- `src/scripts` compatibility mirror

## Verification

- `pytest tests/test_smoke_verify.py tests/test_qa_hard.py tests/test_normalize_segmentation.py tests/test_batch_infrastructure.py tests/test_script_authority.py tests/test_runtime_adapter_contract.py tests/test_normalize_auxiliary_contract.py tests/test_soft_qa_contract.py tests/test_batch3_batch4_governance.py tests/test_batch5_archive_candidates.py -vv`
  - result: `56 passed`
- `python scripts/check_script_authority.py --out reports/script_authority_report_20260319.json`
  - result: `WARN`, alert-only drift is `runtime_adapter.py` only
- `python scripts/m4_3_collect_coverage.py`
  - result: coverage refreshed, hotspot count remains `0`
- `python scripts/m4_4_decision.py`
  - result: `KEEP=6, BLOCK=0, REWORK=0, OBSOLETE=0`
