# Value Review: deep-cleanup-main-batch7

## Decision

GO

## Why this is worth doing

The cleanup roadmap is already good enough to keep the smoke chain stable, but not yet good
enough to support normal production development. The next highest-value step is therefore
to recover the retained development baselines rather than to keep chasing deletion count.

`run_validation.py` and `build_validation_set.py` are still required for deterministic
regression work, but they were previously frozen because their sampling, scoring, and
artifact contracts were not pinned. Turning them into a tested must-keep surface reduces
future breakage and gives the team a reproducible development baseline again.

`repair_loop.py` is likewise still the active repair authority, but docs and rules had
drifted away from the real flags-only CLI and were overselling resume behavior. Aligning
the runbooks to the actual script contract is high value because it removes operational
ambiguity without broadening runtime scope.

## Evidence captured

- The active keep chain remains
  `llm_ping -> normalize_guard -> translate_llm -> qa_hard -> rehydrate_export -> smoke_verify`.
- Batch 6 already restored Metrics as an optional stage and downgraded the two historical
  repair utilities to `archive-candidate`, so Batch 7 does not need to touch that logic.
- Validation fixture coverage now exists for deterministic sampling, metadata schema,
  report schema, scoring, parse fallback, and explicit I/O paths.
- Repair fixture coverage now exists for the flags-only CLI, supported task input formats,
  passthrough behavior, artifact directories, and the `repair_soft_major` routing step.
- The remaining drift lives in documentation and surface classification, not in the
  keep-chain or M4 decision code.

## Scope guardrails

- Batch 7 does not physically archive `repair_loop_v2.py` or `repair_checkpoint_gaps.py`.
- Batch 7 does not implement true repair resume.
- Batch 7 does not change keep-chain, M4, authority drift policy, or Metrics optionality.
- Repo-root `src/scripts` remains compatibility-only and stays outside physical cleanup.

## Exit condition for this step

This step is complete when:

- `run_validation.py` and `build_validation_set.py` are promoted from `blocked` to
  `must-keep`,
- `repair_loop.py` is promoted from `blocked` to `must-keep`,
- the runbooks publish only the real flags and path contracts,
- the regression suite and evidence gate remain green,
- and the Batch 7 report explains the production-dev recovery position in an auditable way.
