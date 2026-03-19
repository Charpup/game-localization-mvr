# Batch 9 Stress Surface Canonicalization

## Goal

Reduce the remaining stress-like shell surface to one retained canonical path plus explicit
historical candidates, without changing keep-chain semantics, M4 decision logic, authority
drift policy, or optional Metrics behavior.

## Canonical Retained Path

- `scripts/stress_test_3k_run.sh` -> retained canonical stress shell authority

Why retained:

- It is the only stress shell entrypoint already aligned with the current `repair_loop.py`
  and `soft_qa_llm.py` contracts.
- It still binds the retained `normalize_tag_llm.py` stress-only compatibility entrypoint.
- Batch 9 corrected its remaining export drift by switching `rehydrate_export.py` to the
  current positional contract.

## Historical Candidates

- `scripts/acceptance_stress_final.sh` -> `archive-candidate`
- `scripts/acceptance_stress_resume.sh` -> `archive-candidate`
- `scripts/acceptance_stress_resume_fix.sh` -> `archive-candidate`
- `scripts/acceptance_stress_run.sh` -> `archive-candidate`
- `scripts/acceptance_stress_phase3.sh` -> `archive-candidate`
- `scripts/finalize_stress_report.py` -> `archive-candidate`
- `scripts/run_long_text_gate_v1.py` -> `archive-candidate`
- `scripts/verify_3k_test.py` -> `compat-keep`

## Why These Are Not Retained Stress Paths

- No active docs or runbooks inside `main_worktree` bind the `acceptance_stress_*` shell
  scripts as current operational paths.
- `acceptance_stress_final.sh` and `acceptance_stress_resume.sh` still use drifted
  `rehydrate_export.py --input --placeholder-map --output` syntax.
- `acceptance_stress_resume_fix.sh` is a one-off fixed variant, not a stable retained
  operator path.
- `acceptance_stress_run.sh` and `acceptance_stress_phase3.sh` are split 5k helpers rather
  than the current canonical stress orchestration path.
- `finalize_stress_report.py` only serves the historical 5k acceptance flow.

## Inventory Outcome

- `stress/**` -> `compat-keep` umbrella only; no longer the active blocked surface
- `scripts/stress_test_3k_run.sh` -> `must-keep`
- historical 5k stress shells -> `archive-candidate`
- `scripts/verify_3k_test.py` -> `compat-keep`

## Closeout Readiness

Batch 9 moves the roadmap into closeout territory.

If the retained stress path remains stable after regression and evidence gate, only one
meaningful cleanup decision should remain:

- Batch 10 should decide whether `src/scripts` compat mirror becomes a documented
  long-term retained surface or gets an explicit exit plan.

No further broad script-surface cleanup should be opened unless new evidence appears.
