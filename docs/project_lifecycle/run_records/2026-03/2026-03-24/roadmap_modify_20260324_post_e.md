# Post-E Roadmap Modify Proposal

- date: `2026-03-24`
- branch: `codex/milestone-e-prepare`
- scope: `post_e_roadmap_modify`
- route: `plc + triadev`

## Summary
- Rewrote the post-E roadmap view from a flat `F → S` sequence into four execution phases.
- Preserved the original milestone letters and their strategic ownership.
- Synced the new phase view into:
  - `docs/project_lifecycle/roadmap_index.md`
  - `task_plan.md`
  - `progress.md`
  - `.triadev/workflow.json`
  - `.triadev/state.json`

## Four-Phase View
- Phase 1: `F/G/H`
  - runtime quality closure and routing
- Phase 2: `M/N/O/P`
  - governance substrate and continuity schema
- Phase 3: `I/J/K/L`
  - language governance, feedback loop, lifecycle, and KPI operations
- Phase 4: `Q/R/S`
  - agent-first operator control plane and final operating-model decision

## Recommended Next Scope
- main: `milestone_F_execute`
- sidecar planning: `milestone_M_prepare`

## Rationale
- `milestone E` introduced new delta/task/run artifacts; governance schemas should not lag behind later runtime expansion.
- GUI-heavy work remains explicitly downstream of agent-first operator flow stabilization.
- Language governance is treated as a first-class operational layer, not only prompt or style-guide documentation.
