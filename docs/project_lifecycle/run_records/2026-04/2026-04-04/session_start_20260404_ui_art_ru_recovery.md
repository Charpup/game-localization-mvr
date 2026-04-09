# session_start

- date: `2026-04-04`
- branch: `main`
- current_scope: `naruto_ui_art_ru_recovery`
- route: `plc + triadev`
- base_branch: `main`

## Context
- read_versions:
  - `task_plan.md @ 20260404T161000+0800`
  - `progress.md @ 20260404T161000+0800`
  - `findings.md @ 20260404T161000+0800`
  - `data/incoming/naruto_ui_art_ru_20260404/runs/ui_art_live_20260404_run01/ui_art_qa_hard_report_recheck_v2.json @ 20260404T155000+0800`
- blockers:
  - `the live batch ended with 3002 length failures, proving the current UI-art policy is systematically wrong`
  - `soft_qa_llm.py and qa_hard.py still apply category-blind logic`
  - `compiled glossary artifacts currently drop compact metadata needed for runtime precedence`

## Slice
- bounded implementation target: `convert the Naruto UI-art recovery plan into category-aware prep, compact-term precedence, and profile-aware QA without changing global hard invariants or keep-chain order`
- mini plan:
  - `update triadev/value gate for the recovery scope`
  - `implement category-aware prep / translate / qa_hard / soft_qa / review logic`
  - `expand compact glossary and sync governed style assets`
  - `run focused tests plus style/profile/glossary verification`

## Validation Decision
- validation mode: `focused recovery tests plus governed asset checks`
- smoke run: `deferred`
- rationale: `the immediate question is whether the new category-aware policy is wired correctly; a full rerun is too expensive until the recovery contract is proven on tests first`

## Handoff
- next_owner: `Codex`
- next_scope: `naruto_ui_art_ru_recovery_verify`
- next_action: `finish the recovery implementation, verify the focused test floor, then stage a stratified canary as the next execution boundary`
