# Value Review: deep-cleanup-main-batch8

## Decision

GO

## Why this is worth doing

Batch 7 already restored the retained production development baselines. That makes Batch 8
the right moment to finish the earlier repair-side cleanup and physically remove the two
historical utilities that no longer belong in the active `scripts/` surface.

This is worth doing now because the governance retirement work is already complete:
`repair_loop_v2.py` is no longer a retained repair path, and `repair_checkpoint_gaps.py`
is no longer the supported checkpoint recovery path. Keeping them in `scripts/` after that
creates avoidable operator noise without adding runtime value.

## Evidence captured

- The active keep chain remains
  `llm_ping -> normalize_guard -> translate_llm -> qa_hard -> rehydrate_export -> smoke_verify`.
- Batch 6 retired active governance references and reclassified the two historical
  repair utilities to `archive-candidate`.
- Batch 7 restored `repair_loop.py`, `run_validation.py`, and `build_validation_set.py`
  as tested must-keep surfaces, so Batch 8 can archive the historical pair without
  weakening current production development paths.
- `loc-translate.md` already keeps `scripts/rebuild_checkpoint.py` as the supported
  checkpoint recovery path.
- The remaining work is physical archive closeout, README/reporting, and inventory sync.

## Scope guardrails

- Batch 8 does not change keep-chain, M4, authority drift policy, or Metrics optionality.
- Batch 8 does not modify retained repair or validation surfaces.
- Batch 8 does not add wrappers or compatibility aliases for archived files.
- Repo-root `src/scripts` remains compatibility-only and stays outside physical cleanup.

## Exit condition for this step

This step is complete when:

- `repair_loop_v2.py` and `repair_checkpoint_gaps.py` no longer live under `scripts/`,
- `_obsolete/repair_archive/` contains both files plus an auditable README,
- the frozen-zone inventory marks both as `archive-complete`,
- the regression suite and evidence gate remain green,
- and the Batch 8 report explains why no wrapper was retained.
