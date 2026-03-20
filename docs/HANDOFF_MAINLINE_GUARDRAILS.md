# Mainline Handoff Guardrails

This document is the operational handoff for future agents working in
`main_worktree`.

Use it together with
[D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\task_plan.md](D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\task_plan.md):

- `task_plan.md` is the historical cleanup ledger
- this file is the forward-looking development guardrail
- governance execution protocols are centralized at `docs/project_lifecycle/*`
- for session handoff and milestone continuity, use `skill/plc` (alias: `plc`, full alias: `skill/project_lifecycle_governance`)

If the two ever drift, treat current scripts plus contract tests as authoritative, then
update the docs in the same change.

## 1. Working Baseline

- Work from `main` only unless a short-lived feature branch is required.
- The only runtime authority root is `main_worktree/scripts`.
- The repo-root `src/scripts` tree is **not** a runtime authority. It is an
  operationally retained compatibility mirror with
  `closeout_decision: separate-exit-program`.
- The cleanup roadmap is closed after Batch 10. Future retirement of `src/scripts`
  is a separate migration project, not an extension of the old cleanup work.

## 2. Protected Mainline

The retained keep-chain is fixed to:

`llm_ping -> normalize_guard -> translate_llm -> qa_hard -> rehydrate_export -> smoke_verify`

Treat the following as protected retained surfaces:

- `scripts/run_smoke_pipeline.py`
- `scripts/llm_ping.py`
- `scripts/normalize_guard.py`
- `scripts/translate_llm.py`
- `scripts/qa_hard.py`
- `scripts/rehydrate_export.py`
- `scripts/smoke_verify.py`
- `scripts/runtime_adapter.py`
- `scripts/smoke_issue_logger.py`
- `scripts/repair_loop.py`
- `scripts/run_validation.py`
- `scripts/build_validation_set.py`
- `scripts/stress_test_3k_run.sh`

Rules:

- Do not change keep-chain order or semantics casually.
- Do not bypass `runtime_adapter.py` for LLM calls.
- Do not turn Metrics into a blocking gate.
- Do not treat stress tooling as part of the keep-chain.

## 3. Surface Status Model

Current governance status lives in
[D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\workflow\batch4_frozen_zone_inventory.json](D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\workflow\batch4_frozen_zone_inventory.json)
and
[D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\workflow\script_authority_manifest.json](D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\workflow\script_authority_manifest.json).

Read those files before changing script ownership.

Practical interpretation:

- `must-keep`
  - active retained surfaces
  - any change needs tests plus doc sync
- `compat-keep`
  - still present for compatibility or tooling, but not the preferred runtime path
  - do not silently promote these back to authority
- `archive-candidate`
  - historical surfaces that may be retired later
  - do not revive them without an explicit decision record
- `archive-complete`
  - already moved out of the active mainline
  - do not move them back into `scripts/` without a dedicated restoration change

Important current classifications:

- `../src/scripts/**` = `compat-keep`, exit-planned, not authority
- `scripts/repair_loop_v2.py` = `archive-complete`
- `scripts/repair_checkpoint_gaps.py` = `archive-complete`
- `scripts/acceptance_stress_*.sh` = historical `archive-candidate`
- `scripts/stress_test_3k_run.sh` = the only retained canonical stress shell path

## 4. Development Rules

Before changing code:

- Read
  [D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\docs\WORKSPACE_RULES.md](D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\docs\WORKSPACE_RULES.md)
- Read the relevant runbook:
  - pipeline work:
    [D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\docs\localization_pipeline_workflow.md](D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\docs\localization_pipeline_workflow.md)
  - validation work:
    [D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\docs\repro_baseline.md](D:\Dev_Env\GPT_Codex_Workspace\game-localization-mvr\main_worktree\docs\repro_baseline.md)

Non-negotiable rules:

- All LLM calls go through `runtime_adapter.py`.
- Every `llm.chat()` call must carry `metadata.step`.
- Placeholder/tag handling must stay behind `normalize_guard.py`.
- `qa_hard.py` remains a blocking gate before final export.
- `repair_loop.py` remains the retained repair authority.
- `run_validation.py` and `build_validation_set.py` remain the retained validation baseline.
- Checkpoint files are evidence/snapshots unless a future change explicitly implements
  resume semantics.

If you touch docs or rules for a retained script, make them match the real CLI contract.
Do not keep old flags alive only to preserve stale docs.

## 5. Compat Mirror Policy

`src/scripts` is still present because it is bound by:

- packaging
- authority/governance tests
- legacy inventory/docs

Do not physically delete or shrink `src/scripts` as part of routine feature work.

If the team wants to retire it, open a separate compat-mirror migration program with at
least these explicit goals:

- detach packaging from `src/scripts`
- detach authority/governance tests from `src/scripts`
- detach legacy docs and inventory references
- reduce required mirror entries without introducing required drift or missing mirrors

Until then:

- `main_worktree/scripts` stays the authority root
- `src/scripts` stays compatibility-only
- new required mirror growth should be treated as exceptional and deliberate, not casual

## 6. Minimum Verification Floor

When touching retained authority or governance surfaces, run the focused regression floor:

- `tests/test_smoke_verify.py`
- `tests/test_qa_hard.py`
- `tests/test_script_authority.py`
- `tests/test_batch3_batch4_governance.py`

Add these when relevant:

- validation changes:
  `tests/test_validation_contract.py`
- repair changes:
  `tests/test_repair_loop_contract.py`
- runtime/metrics changes:
  `tests/test_runtime_adapter_contract.py`
  `tests/test_batch6_repair_metrics_contract.py`

Evidence gate remains:

- `scripts/check_script_authority.py`
- `scripts/m4_3_collect_coverage.py`
- `scripts/m4_4_decision.py`

Expected steady-state after normal safe changes:

- authority at most `WARN(runtime_adapter only)`
- `M4_4` remains `KEEP=6`

## 7. Branch And Repo Hygiene

The repository has already been cleaned back to one long-lived branch: `main`.

Future branch rules:

- Use `codex/*` only for short-lived implementation branches.
- Open one authoritative PR per change line.
- Merge, then delete the branch locally and remotely.
- Do not rebuild stacked cleanup chains unless the work truly requires it.
- Preserve history with tags, not with abandoned long-lived side branches.

If a branch is merged, delete it promptly. Do not let cleanup, experiment, or checkpoint
branches accumulate again.

## 8. Handoff Checklist For The Next Agent

Before starting non-trivial work:

1. Confirm you are on `main`.
2. Read `task_plan.md` for cleanup history and decision boundaries.
3. Read `HANDOFF_MAINLINE_GUARDRAILS.md` for current operational rules.
4. Read `script_authority_manifest.json` and `batch4_frozen_zone_inventory.json` if your
   work touches script ownership, packaging, stress tooling, or compat behavior.
5. If your change would alter authority root, keep-chain, compat mirror policy, or archive
   status, treat it as governance work and update tests and docs together.

If you follow these rules, the repo should stay on a clean mainline instead of sliding back
into mixed authority, stale branches, and undocumented script drift.
