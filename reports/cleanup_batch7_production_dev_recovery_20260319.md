# Batch 7 Production Dev Recovery

## Goal

Recover the retained validation baseline and repair authority surfaces so development can
resume on top of a tested, documented mainline without changing keep-chain, M4,
authority-drift policy, or optional Metrics behavior.

## Scope

- `scripts/build_validation_set.py`
- `scripts/run_validation.py`
- `scripts/repair_loop.py`
- Validation and repair runbooks/rules
- `workflow/batch4_frozen_zone_inventory.json`
- Batch 7 contract tests

## Decisions

- `scripts/run_validation.py` => `must-keep`
- `scripts/build_validation_set.py` => `must-keep`
- `scripts/repair_loop.py` => `must-keep`
- `scripts/repair_loop_v2.py` => stays `archive-candidate`
- `scripts/repair_checkpoint_gaps.py` => stays `archive-candidate`

## What Changed

- Validation commands are now documented with explicit `--input`, `--output-dir`,
  `--report-dir`, and `--api-key-path` contracts in `docs/repro_baseline.md`.
- The retained API-key example now uses `data/attachment/api_key.txt`, matching the live
  script default instead of the drifted `config/api_key.txt` path.
- Workspace and repair workflow docs now describe `repair_checkpoint.json` as a checkpoint
  snapshot / observability artifact rather than true resume support.
- `docs/WORKSPACE_RULES.md` now aligns repair routing names with runtime reality:
  `repair_hard` and `repair_soft_major`.
- Frozen-zone inventory now treats validation and retained repair authority surfaces as
  `must-keep`, not `blocked`.

## Test Surface

- `tests/test_validation_contract.py`
- `tests/test_repair_loop_contract.py`
- `tests/test_batch3_batch4_governance.py`

## Verification Run

Focused contract suites:

```powershell
& 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\.venv_main\Scripts\python.exe' -m pytest tests/test_validation_contract.py -q
& 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\.venv_main\Scripts\python.exe' -m pytest tests/test_repair_loop_contract.py tests/test_batch3_batch4_governance.py -q
```

Full regression:

```powershell
& 'D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\.venv_main\Scripts\python.exe' -m pytest tests/test_smoke_verify.py tests/test_qa_hard.py tests/test_normalize_segmentation.py tests/test_batch_infrastructure.py tests/test_script_authority.py tests/test_runtime_adapter_contract.py tests/test_normalize_auxiliary_contract.py tests/test_soft_qa_contract.py tests/test_batch3_batch4_governance.py tests/test_batch5_archive_candidates.py tests/test_batch6_repair_metrics_contract.py tests/test_validation_contract.py tests/test_repair_loop_contract.py -q
```

Result: `77 passed`

## Evidence Gate Run

- `scripts/check_script_authority.py --out reports/script_authority_report_20260319.json`
- `scripts/m4_3_collect_coverage.py`
- `scripts/m4_4_decision.py`

Observed results:

- authority: `WARN`
- alert-only drift: `runtime_adapter.py`
- M4 issue hotspots: `0`
- M4 decision summary: `KEEP=6, BLOCK=0, REWORK=0, OBSOLETE=0`

## Expected Acceptance

- `KEEP=6` remains unchanged
- authority remains at most `WARN(runtime_adapter only)`
- Metrics remains optional and non-blocking
- current validation and repair runbook commands are executable against the retained CLI

## Batch 7 Outcome

Acceptance criteria met. Batch 7 restores the retained validation pair and retained repair
authority as documented, tested must-keep surfaces and leaves physical archive closeout for
`repair_loop_v2.py` and `repair_checkpoint_gaps.py` to Batch 8.
