# session_start

- date: `2026-04-04`
- branch: `main`
- current_scope: `naruto_ui_art_ru_live_batch`
- route: `plc + triadev`
- base_branch: `main`

## Context
- read_versions:
  - `task_plan.md @ 20260404T144900+0800`
  - `progress.md @ 20260404T144900+0800`
  - `data/incoming/naruto_ui_art_ru_20260404/README.md @ 20260404T144700+0800`
- blockers:
  - `real source file is GB18030/GBK rather than utf-8-sig`
  - `source contains duplicate original string_id values that must not leak into runtime checkpoint keys`
  - `provider has rate limits, so batch execution must stay single-process and resumable`

## Slice
- bounded implementation target: `execute the real Naruto UI art ru-RU live batch with batch-local prep/orchestration/restore safeguards`
- mini plan:
  - `add a run-dir orchestrator and original-id restore step`
  - `upgrade prep for encoding normalization and working-id generation`
  - `launch one serial live batch and follow it through hard/soft QA plus delivery export`

## Validation Decision
- validation mode: `focused-tests plus live batch`
- smoke run: `replaced by batch-local live execution`
- rationale: `the real source file and provider credentials are now present, so the highest-value validation is the actual bounded live batch rather than another fixture-only smoke`

## Handoff
- next_owner: `Codex`
- next_scope: `naruto_ui_art_ru_live_batch_closeout`
- next_action: `let run ui_art_live_20260404_run01 finish, verify output counts and review queue, then record PLC verify/end artifacts`
