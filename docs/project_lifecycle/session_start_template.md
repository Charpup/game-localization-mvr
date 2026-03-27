# session_start 模板

- date: `2026-03-25`
- branch: `codex/<branch-name>`
- current_scope: `<milestone / slice>`
- route: `plc + triadev`
- base_branch: `main`

## Context
- read_versions:
  - `docs/HANDOFF_MAINLINE_GUARDRAILS.md @ <YYYYMMDDTHHMMSS+ZZZZ>`
  - `task_plan.md @ <YYYYMMDDTHHMMSS+ZZZZ>`
  - `docs/project_lifecycle/roadmap_index.md @ <YYYYMMDDTHHMMSS+ZZZZ>`
- blockers:
  - `none`

## Slice
- bounded implementation target: `<one bounded package>`
- mini plan:
  - `<1h task 1>`
  - `<1h task 2>`

## Validation Decision
- validation mode: `<focused-governance-tests|focused-runtime-tests|smoke>`
- smoke run: `<required|not required for this slice>`
- rationale: `<why this validation floor is enough>`

## Handoff
- next_owner: `<owner_id>`
- next_scope: `<next bounded scope>`
- next_action: `<one concrete next step>`
