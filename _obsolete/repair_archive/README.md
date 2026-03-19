# Repair Archive

This directory stores historical repair-side utilities that no longer belong to the active
`main_worktree/scripts` surface.

## Batch 8 Archived Files

- `repair_loop_v2.py`
- `repair_checkpoint_gaps.py`

## Why They Left `scripts/`

- `repair_loop_v2.py` is no longer the retained repair path. The current mainline
  retained repair authority is `scripts/repair_loop.py`.
- `repair_checkpoint_gaps.py` is no longer the retained checkpoint recovery path. The
  current mainline retained checkpoint recovery path is `scripts/rebuild_checkpoint.py`.
- Both files were downgraded to historical-only utilities in Batch 6 and kept out of
  physical cleanup during Batch 7 so production development could be restored first.
- Batch 8 completes that plan by removing them from the active scripts surface without
  adding wrappers or compatibility aliases.

## Restore Basis

If one of these archived utilities ever needs to be revived, use all of the following as
the recovery basis:

- the archived file in this directory
- `reports/cleanup_batch5_archive_20260319.md`
- `reports/cleanup_batch6_contract_metrics_20260319.md`
- `reports/cleanup_batch7_production_dev_recovery_20260319.md`
- `reports/cleanup_batch8_repair_archive_closeout_20260319.md`

Do not treat these files as default mainline tools unless a later batch explicitly
re-promotes them.
