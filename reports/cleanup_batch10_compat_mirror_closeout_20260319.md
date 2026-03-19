# Batch 10 Compat Mirror Closeout

## Goal

Close the current `main_worktree` cleanup roadmap by giving `src/scripts` a final
governance decision without physically deleting or migrating it in this batch.

## Final Decision

- `../src/scripts/**` remains operationally present
- status stays `compat-keep`
- closeout decision is fixed to `separate-exit-program`

This means:

- the current cleanup roadmap is finished after Batch 10
- `src/scripts` is no longer counted as an unfinished cleanup item
- any future physical retirement of the mirror must be handled as a separate migration effort

## Why It Cannot Exit Now

`src/scripts` is not the runtime authority, but it is still operationally bound by:

- `package_v1.3.0.sh`, which still packages `src/scripts`
- authority/governance tests that still expect `../src/scripts`
- root inventory and project docs that still describe `src/scripts` compatibility flows

The authority manifest already encodes the correct reduction gate:

- detach packaging/tests/docs first
- keep `mirror_required_missing=0`
- keep `mirror_required_drift=0`

## Why Cleanup Can Still Close

By Batch 10, the active `main_worktree` surface has already been reduced to:

- retained authority scripts in `main_worktree/scripts`
- explicit archive-complete historical utilities
- explicit archive-candidate or compat-keep helper surfaces
- one managed compatibility mirror with a written exit plan

There are no longer any real blocked cleanup surfaces inside `main_worktree`.

## Roadmap Closure Criteria

Batch 10 closes the cleanup roadmap only when all of the following remain true:

- keep-chain still resolves to `KEEP=6`
- authority remains at most `WARN(runtime_adapter only)`
- the inventory has no real `blocked` surface
- `src/scripts` has a written closeout decision and exit blockers
- future mirror retirement is explicitly treated as a separate migration project

## Verification Run

Focused Batch 10 governance:

```powershell
& 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\.venv_main\Scripts\python.exe' -m pytest tests/test_script_authority.py tests/test_batch3_batch4_governance.py tests/test_batch10_closeout_decision.py -q
```

Result: `15 passed`

Retained regression suite:

```powershell
& 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\.venv_main\Scripts\python.exe' -m pytest tests/test_smoke_verify.py tests/test_qa_hard.py tests/test_normalize_segmentation.py tests/test_batch_infrastructure.py tests/test_script_authority.py tests/test_runtime_adapter_contract.py tests/test_normalize_auxiliary_contract.py tests/test_soft_qa_contract.py tests/test_batch3_batch4_governance.py tests/test_batch5_archive_candidates.py tests/test_batch6_repair_metrics_contract.py tests/test_validation_contract.py tests/test_repair_loop_contract.py tests/test_batch8_repair_archive_closeout.py tests/test_batch9_stress_surface_governance.py tests/test_batch10_closeout_decision.py -q
```

Result: `92 passed`

Evidence gate:

- authority: `WARN`
- alert-only drift: `runtime_adapter.py`
- M4 issue hotspots: `0`
- M4 decision summary: `KEEP=6, BLOCK=0, REWORK=0, OBSOLETE=0`

## Next Step After Closure

If the team decides to retire `src/scripts`, open a separate compat-mirror migration
program focused on:

- packaging detachment
- authority/governance test updates
- root inventory and docs detachment
- mirror-required list shrinkage
