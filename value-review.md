# Value Review: deep-cleanup-r3

## Decision

GO

## Why this is worth doing

The branch needs a brownfield TriadDev control plane before any deeper cleanup work can be
sequenced safely. The current runtime truth is already concentrated in
`main_worktree/scripts`, while `src/scripts` functions as a compatibility mirror. Writing
that split down reduces accidental edits in the wrong zone and gives later implementation
steps a stable authority model.

## Evidence captured

- Active branch is `codex/deep-cleanup-r3`.
- The stable smoke path is preserved by `scripts/run_smoke_pipeline.py` as
  `llm_ping -> normalize_guard -> translate_llm -> qa_hard -> rehydrate_export -> smoke_verify`.
- Coverage/decision helpers (`scripts/m4_3_collect_coverage.py` and
  `scripts/m4_4_decision.py`) reference the same chain, which reinforces that it is the
  intended keep chain.
- `main_worktree/scripts` and repo-root `src/scripts` both exist, matching the desired
  authority-plus-compat-zone model.

## Scope guardrails

- This bootstrap is artifact-only and does not modify production code.
- First wave remains blocked from `scripts/repair_loop.py`, `scripts/run_validation.py`,
  `gate/**`, `stress/**`, `skill-v1.4.0/**`, and `packaging/**`.
- No existing user changes are reverted.

## Exit condition for this step

TriadDev artifacts exist and describe the current brownfield state accurately enough for
later work to proceed without ambiguity about authority, compat boundaries, or protected
surfaces.
