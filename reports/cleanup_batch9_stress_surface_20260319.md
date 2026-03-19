# Batch 9 Stress Surface Canonicalization

## Goal

Reduce the remaining stress-like shell surface from a generic blocked placeholder into one
retained canonical path plus explicit historical/helper statuses, without changing
keep-chain behavior, retained production-development baselines, authority drift policy, or
optional Metrics semantics.

## Canonical Retained Path

- `scripts/stress_test_3k_run.sh`

Why this path stays:

- It is the only stress shell entrypoint that still connects directly to retained scripts
  such as `repair_loop.py` and `soft_qa_llm.py`.
- Batch 9 aligns its export step to the current positional `rehydrate_export.py` contract.
- It remains the reason `normalize_tag_llm.py` still has a justified stress-only role.

## Reclassified Historical Stress Shells

- `scripts/acceptance_stress_final.sh` -> `archive-candidate`
- `scripts/acceptance_stress_resume.sh` -> `archive-candidate`
- `scripts/acceptance_stress_resume_fix.sh` -> `archive-candidate`
- `scripts/acceptance_stress_run.sh` -> `archive-candidate`
- `scripts/acceptance_stress_phase3.sh` -> `archive-candidate`

Why they are not retained as canonical paths:

- They are 5k split-flow helpers rather than the retained stress authority.
- The mainline runbooks do not bind them as current operator defaults.
- At least the original `acceptance_stress_final.sh` and `acceptance_stress_resume.sh`
  still use drifted `rehydrate_export.py --input --placeholder-map --output` flags.
- Batch 9 intentionally avoids wrappers or aliases because that would preserve ambiguity
  instead of shrinking the active surface.

## Helper Statuses

- `scripts/finalize_stress_report.py` -> `archive-candidate`
- `scripts/verify_3k_test.py` -> `compat-keep`
- `scripts/run_long_text_gate_v1.py` -> `archive-candidate`

These helpers are not part of the keep-chain. Batch 9 only makes their status explicit so
the roadmap can stop treating the whole stress surface as an undifferentiated blocked zone.

## Closeout Readiness

Batch 9 moves the cleanup roadmap into near-closeout mode:

- retained stress shell surface: `1`
- historical stress shell variants: explicit `archive-candidate`
- helper surfaces: explicit helper/archive status

If regression and evidence remain green, Batch 10 should focus only on the long-tail
`src/scripts` compatibility mirror decision:

- either document it as a long-term compat layer and end the cleanup roadmap
- or define a separate exit path if packaging/tests/docs are ready to detach
