# Value Review: deep-cleanup-main-batch10

## Decision

GO

## Why this is worth doing

Batch 9 already reduced the remaining active cleanup surface to a final governance decision
around `src/scripts`. That makes Batch 10 worth doing because it finishes the roadmap
without pretending the compatibility mirror can be removed before packaging, tests, and
docs are detached from it.

This batch creates closure by turning `src/scripts` from a vague long-tail concern into an
explicitly managed compatibility liability with a fixed exit program. That lets the cleanup
roadmap end cleanly while still preserving the current packaging and governance truth.

## Evidence captured

- The active keep chain remains
  `llm_ping -> normalize_guard -> translate_llm -> qa_hard -> rehydrate_export -> smoke_verify`.
- Batch 9 moved the roadmap into closeout readiness and left `src/scripts` as the only
  meaningful unresolved governance decision.
- `src/scripts` is still operationally bound by packaging (`package_v1.3.0.sh`), authority
  tests, and legacy inventory/docs.
- The authority manifest already encodes the correct reduction gate: no physical reduction
  until packaging/tests/docs are detached and required mirror gaps remain zero.
- Current authority evidence remains stable at `WARN(runtime_adapter only)`.

## Scope guardrails

- Batch 10 does not change keep-chain, M4, authority drift policy, or Metrics optionality.
- Batch 10 does not modify retained repair, validation, or stress authority surfaces.
- Batch 10 does not physically remove or migrate `src/scripts`.
- Batch 10 does not change packaging behavior.

## Exit condition for this step

This step is complete when:

- `../src/scripts/**` remains present but is explicitly marked as `closeout_decision: separate-exit-program`,
- the frozen-zone inventory no longer contains any real blocked surface,
- the authority manifest records the exit blockers and frozen mirror policy,
- the regression suite and evidence gate remain green,
- and the Batch 10 report states that the current cleanup roadmap is complete.
