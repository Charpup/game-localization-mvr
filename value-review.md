# Value Review: deep-cleanup-main-batch5

## Decision

GO

## Why this is worth doing

The repo is already past the governance-heavy Phase 1 work, so the next highest-value
cleanup step is to test whether the safest historical utilities can leave the active
`scripts/` surface without touching blocked repair or validation flows. Batch 5 still
has value even though the final outcome is fallback-to-blocked:

- `repair_loop_v2.py` was already classified as an `archive-candidate` rather than a
  blocked surface, because no active runtime caller was found in `main_worktree`.
- `repair_checkpoint_gaps.py` is a hard-coded one-off recovery tool, not part of the
  smoke-chain or the currently supported repair authority surface.
- The audit exposed hidden dependencies before an unsafe cleanup landed:
  `repair_loop_v2.py` is still referenced by active rules and inventory, while
  `repair_checkpoint_gaps.py` still hangs off the documented `translate_checkpoint`
  recovery contract.

## Evidence captured

- The active keep chain remains
  `llm_ping -> normalize_guard -> translate_llm -> qa_hard -> rehydrate_export -> smoke_verify`.
- Batch 4 inventory already separated `archive-candidate` from `blocked`, so Batch 5 is
  acting on pre-classified low-risk targets rather than discovering new cleanup scope.
- Batch 5 adds characterization coverage for:
  the current `repair_loop_v2.py` CLI shape and the hard-coded recovery behavior of
  `repair_checkpoint_gaps.py`.
- Local reference recheck shows no active runtime caller for either file; remaining
  mentions are governance docs, rules, inventory, and recovery-contract records.
- Hooke's independent audit found enough residual contract surface to block physical
  archive in this round, so the batch now records a safe fallback rather than a false clean win.

## Scope guardrails

- Batch 5 does not touch `repair_loop.py`, `run_validation.py`, `build_validation_set.py`,
  stress-like shell entrypoints, or repo-root `src/scripts`.
- Batch 5 does not change `run_smoke_pipeline.py` orchestration or M4 decision logic.
- Any archive move must be rolled back if hidden dependencies are found.
- No wrapper, alias, or new CLI is introduced.

## Exit condition for this step

This step is complete when:

- the characterization tests are green,
- the smoke-focused regression suite and M4 evidence gate stay green,
- `workflow/batch4_frozen_zone_inventory.json` records both targets with their final
  Batch 5 fallback status,
- and the repo has an auditable explanation for why archive was not yet safe.
