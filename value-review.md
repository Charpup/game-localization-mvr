# Value Review: deep-cleanup-main-batch9

## Decision

GO

## Why this is worth doing

Batch 8 already removed the last obvious low-risk repair-side historical utilities from the
active `scripts/` surface. The only meaningful blocked cleanup surface still left inside
`main_worktree` is the cluster of stress-like shell entrypoints and adjacent helpers.

This is worth doing now because it reduces the final ambiguous operator surface without
opening a new implementation front. One retained stress shell entrypoint is still useful
for side-path pressure validation, but the drifted `acceptance_stress_*` scripts should no
longer sit in an undifferentiated blocked bucket when they are not part of the keep-chain
and are not covered by recent mainline smoke usage.

## Evidence captured

- The active keep chain remains
  `llm_ping -> normalize_guard -> translate_llm -> qa_hard -> rehydrate_export -> smoke_verify`.
- Batch 7 restored the retained production development baselines.
- Batch 8 completed the repair-side physical archive closeout and left stress-like shell
  entrypoints plus the `src/scripts` compatibility mirror as the only meaningful remaining
  cleanup surfaces.
- `scripts/stress_test_3k_run.sh` is the least-drifted retained shell path and already ties
  into retained scripts such as `normalize_tag_llm.py`, `soft_qa_llm.py`, and `repair_loop.py`.
- Several `acceptance_stress_*` scripts still use historical CLI patterns, especially around
  `rehydrate_export.py`, which is evidence for archive-candidate rather than must-keep status.

## Scope guardrails

- Batch 9 does not change keep-chain, M4, authority drift policy, or Metrics optionality.
- Batch 9 does not modify retained repair or validation surfaces.
- Batch 9 does not physically archive stress scripts yet; it only canonicalizes and reclassifies them.
- Repo-root `src/scripts` remains compatibility-only and stays outside this batch.

## Exit condition for this step

This step is complete when:

- `scripts/stress_test_3k_run.sh` is explicitly retained as the canonical stress shell path,
- the `acceptance_stress_*` scripts and adjacent helpers are individually classified,
- the frozen-zone inventory no longer represents the entire stress surface as a single blocked bucket,
- the regression suite and evidence gate remain green,
- and the Batch 9 report states whether the cleanup roadmap has entered final closeout.
