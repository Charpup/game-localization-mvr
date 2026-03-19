# Value Review: deep-cleanup-r3 Phase 1 Batch 3/4

## Decision

GO

## Why this is worth doing

The repo is no longer blocked by obvious P0/P2 drift in the smoke chain, so the next
highest-value cleanup work is to turn the remaining near-core ambiguity into explicit,
test-backed governance. Batch 3/4 does that without deleting uncertain code:

- `normalize_*` and `soft QA` are now the smallest near-core surfaces still needing
  canonical/frozen/compat decisions before any deeper cleanup can proceed safely.
- `repair`, `validation`, stress-like shell flows, and `src/scripts` are too loosely
  specified to clean yet; freezing them behind an explicit inventory reduces accidental
  deletion risk and makes later work testable.
- A branch audit checklist has value now because it prevents remote cleanup from becoming
  an ad hoc decision after code cleanup finishes.

## Evidence captured

- The active keep chain remains
  `llm_ping -> normalize_guard -> translate_llm -> qa_hard -> rehydrate_export -> smoke_verify`.
- Batch 2 already established fixture coverage for `normalize_ingest.py`,
  `normalize_tagger.py`, `normalize_tag_llm.py`, and `soft_qa_llm.py`.
- Batch 3 adds explicit governance coverage for:
  wrapper compatibility (`qa_soft.py`), CLI failure boundaries (`normalize_ingest.py`),
  and canonical/frozen relationship artifacts.
- Batch 3 also tightens the actual status model:
  `normalize_ingest.py` remains a documented compat-keep ingest surface, while
  `normalize_tag_llm.py` is treated as a stress-only compatibility entrypoint rather than
  a pure duplicate.
- Batch 4 adds a blocked-surface inventory that records direct references, I/O expectations,
  and missing tests for `repair`, `validation`, stress-like shell flows, and the compat mirror.
- Remote branch evidence already shows that several branches are fully contained in `main`,
  while `reorg/v1.3.0-structure` remains the only audit-first outlier.

## Scope guardrails

- Batch 3/4 does not remove files from `main_worktree/scripts`.
- Batch 3/4 does not change `run_smoke_pipeline.py` orchestration or M4 decision logic.
- Batch 3/4 does not enter `repair`, `validation`, `gate`, `stress`, or repo-root
  `src/scripts` implementation surfaces.
- Compatibility wrappers such as `qa_soft.py` remain in place.
- Remote branch actions remain planning-only in this step.

## Exit condition for this step

This step is complete when:

- the new governance/CLI tests are green,
- the smoke-focused regression suite and M4 evidence gate stay green,
- near-core statuses are written down clearly enough that later cleanup can distinguish
  `must-keep`, `compat-keep`, `frozen`, and `blocked` without re-discovery,
- and the GitHub branch audit checklist exists before any merge/delete step is attempted.
