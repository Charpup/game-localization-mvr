# session_start

- date: `2026-04-04`
- branch: `main`
- current_scope: `naruto_ui_art_ru_preparation`
- route: `plc + triadev`
- base_branch: `main`

## Context
- read_versions:
  - `docs/HANDOFF_MAINLINE_GUARDRAILS.md @ 20260401T021117+0800`
  - `task_plan.md @ 20260404T132500+0800`
  - `workflow/style_guide.md @ 20260404T133200+0800`
- blockers:
  - `real source_ui_art.csv rows are not available yet`
  - `live LLM credentials are still required before llm_ping and translation`

## Slice
- bounded implementation target: `research-backed UI art ru-RU batch preparation with strict length metadata`
- mini plan:
  - `write compact-term research and glossary/style addendum`
  - `add prep/review helpers that feed existing row-level max_len_target contracts`
  - `prepare the incoming batch path and stop before live translation`

## Validation Decision
- validation mode: `focused-governance-tests`
- smoke run: `not required for this slice`
- rationale: `the slice adds assets and prep/review tooling only; the retained translation keep-chain remains unchanged`

## Handoff
- next_owner: `Codex`
- next_scope: `naruto_ui_art_ru_live_batch`
- next_action: `collect source_ui_art.csv plus live credentials, then run llm_ping and the prepared batch commands`
