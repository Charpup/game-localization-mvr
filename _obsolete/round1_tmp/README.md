# Round 1 Tmp Archive

Archived on: 2026-03-19

This directory stores the Round 1 cleanup trial artifacts moved out of the
`main_worktree` root. The move is archival, not destructive deletion.

Scope:
- `tmp_run200.ps1`
- `tmp_single_run.ps1`
- `tmp_single_305833.csv`

Selection rules:
- Not part of the `scripts/run_smoke_pipeline.py` core chain
- Not referenced by root tests, `scripts/validate_v130.py`, or packaging scripts
- Classified as P0 temporary residue in `reports/m4_core_obsolete_inventory.md`
- Not part of `src`, `data/smoke_runs`, `reports`, `workflow`, `glossary`, or `config`

Why archived:
- Keep the repo root cleaner without deleting historical one-off recovery inputs
- Establish an auditable cleanup pattern before expanding to Round 2 candidates

Round 2 candidates remain out of scope for this directory:
- `scripts/debug_*`
- `scripts/diagnose_*`

Authoritative trial record:
- `reports/cleanup_round1_trial_20260319.md`
