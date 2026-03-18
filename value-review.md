# Value Review: deep-cleanup-r3 Batch 2

## Decision

GO

## Why this is worth doing

The repo is no longer blocked by obvious P0/P2 drift in the smoke chain, so the next
highest-value cleanup work is to make the shared runtime and side surfaces safer to keep
or later retire. Batch 2 does that without deleting uncertain code:

- `runtime_adapter.py` is the highest-connectivity shared dependency and needed stronger
  contract tests before any future cleanup.
- `normalize_*` and `soft_qa_llm.py` are not current smoke-core steps, but they still have
  live references in docs, stress flows, or compatibility entrypoints, so they need
  evidence-first status marking instead of removal.
- `src/scripts` remains a compatibility mirror, so the right move is to keep drift
  governance visible rather than force a premature migration.

## Evidence captured

- The active keep chain is still
  `llm_ping -> normalize_guard -> translate_llm -> qa_hard -> rehydrate_export -> smoke_verify`.
- `runtime_adapter.py` now has explicit Batch 2 contract coverage for:
  router chain selection, batch enforcement, error classification, tracing, retry, and
  partial batch handling.
- `normalize_ingest.py` now has fixture coverage for header aliases, required-column
  enforcement, and output-schema stabilization.
- `normalize_tagger.py` and `normalize_tag_llm.py` now have fixture coverage for row
  preservation, fallback tagging, and rules-driven length limits.
- `soft_qa_llm.py` now has fixture coverage for dry-run, resume, optional dependency
  degradation, and non-blocking repair-task emission.

## Scope guardrails

- Batch 2 does not remove files from `main_worktree/scripts`.
- Batch 2 does not change `run_smoke_pipeline.py` orchestration.
- Batch 2 does not enter `repair`, `validation`, `gate`, `stress`, or repo-root
  `src/scripts` implementation surfaces.
- Compatibility wrappers such as `qa_soft.py` remain in place.

## Exit condition for this step

Batch 2 is complete when:

- the new contract/fixture tests are green,
- the smoke-focused regression suite and M4 evidence gate stay green,
- module statuses are written down clearly enough that later cleanup can distinguish
  `must-keep`, `compat-keep`, `frozen duplicate`, and `blocked` without re-discovery.
