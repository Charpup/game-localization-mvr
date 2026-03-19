# Batch 8 Repair Archive Closeout

## Goal

Physically remove the two historical repair-side utilities from the active `scripts/`
surface now that retained production-development paths are already stable.

## Archived Moves

- `scripts/repair_loop_v2.py` ->
  `_obsolete/repair_archive/repair_loop_v2.py`
- `scripts/repair_checkpoint_gaps.py` ->
  `_obsolete/repair_archive/repair_checkpoint_gaps.py`

## Why This Is Safe

- `repair_loop.py` remains the retained repair authority.
- `rebuild_checkpoint.py` remains the retained checkpoint recovery path.
- Batch 6 already retired active governance references and downgraded both files to
  `archive-candidate`.
- Batch 7 restored production-development baselines first, so Batch 8 does not need to
  keep wrappers or compatibility aliases for these historical utilities.

## Why No Wrapper

Batch 8 intentionally leaves no wrapper or alias inside `scripts/`. Keeping a shell file or
 import trampoline there would preserve operator ambiguity and defeat the point of closing
 the active surface. Historical access now goes through `_obsolete/repair_archive/`.

## Inventory Outcome

- `scripts/repair_loop_v2.py` => `archive-complete`
- `scripts/repair_checkpoint_gaps.py` => `archive-complete`
- `scripts/repair_loop.py` => unchanged `must-keep`
- `scripts/run_validation.py` => unchanged `must-keep`
- `scripts/build_validation_set.py` => unchanged `must-keep`

## Remaining Higher-Risk Surfaces

- stress-like shell entrypoints under `scripts/`
- `../src/scripts/**` compatibility mirror
- any future archive/retirement work beyond the current repair-side historical pair

Batch 9 should evaluate `stress-like shell` entrypoints before any deeper cleanup of the
remaining blocked surfaces.

## Verification Run

Focused archive-closeout suites:

```powershell
& 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\.venv_main\Scripts\python.exe' -m pytest tests/test_batch5_archive_candidates.py tests/test_batch6_repair_metrics_contract.py tests/test_batch8_repair_archive_closeout.py -q
```

Result: `17 passed`

Full regression:

```powershell
& 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\.venv_main\Scripts\python.exe' -m pytest tests/test_smoke_verify.py tests/test_qa_hard.py tests/test_normalize_segmentation.py tests/test_batch_infrastructure.py tests/test_script_authority.py tests/test_runtime_adapter_contract.py tests/test_normalize_auxiliary_contract.py tests/test_soft_qa_contract.py tests/test_batch3_batch4_governance.py tests/test_batch5_archive_candidates.py tests/test_batch6_repair_metrics_contract.py tests/test_validation_contract.py tests/test_repair_loop_contract.py tests/test_batch8_repair_archive_closeout.py -q
```

Result: `81 passed`

## Evidence Gate

Observed results:

- authority: `WARN`
- alert-only drift: `runtime_adapter.py`
- M4 issue hotspots: `0`
- M4 decision summary: `KEEP=6, BLOCK=0, REWORK=0, OBSOLETE=0`
