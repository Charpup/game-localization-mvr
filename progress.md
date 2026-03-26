# Progress Log

## 2026-03-21
- Started PLC + TriadDev integration-priority pass before milestone E.
- Confirmed the real GitHub integration branch is `codex/plc-c-verify` in `D:\Dev_Env\GPT_Codex_Workspace`, while `game-localization-mvr/main_worktree` is a nested reference worktree with half-applied fixes.
- Confirmed PLC governance state already marks milestones C and D as `done` with `evidence_ready=true`, but GitHub `main` has not yet absorbed that state.
- Audited open PRs and selected PR #9 as the only viable mainline integration branch; PR #7 and PR #8 are superseded in scope.
- Extracted the current blocking review set:
  - `soft_qa_llm.py` severity loss in `merge_tasks()`
  - missing `prohibited_aliases` / `banned_terms` propagation in translation and soft-QA contracts
  - PLC ledger/schema inconsistencies in milestone-B evidence
- Chose a minimum validation plan: targeted `soft_qa` contract tests, a small translation style-contract test, and file-level PLC contract checks.
- Updated the execution ledger with an explicit `PLC + TriadDev Integration Priority` section so this pass stays bounded to integration hardening rather than milestone E feature work.
- Fixed PR #9 code-review gaps in the outer integration repo:
  - `soft_qa_llm` now prioritizes higher-severity placeholder findings and surfaces `prohibited_aliases` / `banned_terms`
  - `translate_llm` now serializes `prohibited_aliases` / `banned_terms` in the style contract output
- Fixed PLC governance gaps in the outer integration repo:
  - milestone B run manifest now uses schema-valid status `pass`
  - referenced ADR files now exist under `docs/decisions/`
  - added a PLC docs contract test to keep run-manifest schema and ADR references honest
- Ran the targeted regression suite successfully:
  - `tests/test_soft_qa_contract.py`: `7 passed`
  - `tests/test_translate_style_contract.py`: `1 passed`
  - `tests/test_plc_docs_contract.py`: `2 passed`
- Merged PR #9 into `main` as `fdc253f`.
- Closed PR #7 and PR #8 as superseded by PR #9.
- Current state: mainline integration phase is complete; milestone E can now start from clean `main`.
- Opened clean worktree `D:\Dev_Env\GPT_Codex_Workspace_milestone_e` on branch `codex/milestone-e-prepare`.
- Fast-forwarded the E worktree to include the post-merge PLC handoff commit.
- Shifted the active planning scope to `milestone_E_prepare`; next step is E planning/delta/tasks preparation rather than more PR cleanup.

## 2026-03-24
- Started milestone E implementation from `codex/milestone-e-prepare` using the package order `E-contract -> E-repro + E-delta-engine -> E-task-executor`.
- Confirmed the E worktree is clean, but the control plane is stale:
  - `.triadev/state.json` already says `milestone_e_prepare`
  - `.triadev/workflow.json` still points at the old Batch 10 closeout change
- Confirmed the current clean worktree does not contain `data/style_profile.yaml` or `data/glossary.yaml`; this is now a first-class `E-repro` blocker rather than an implicit local-state assumption.
- Confirmed `scripts/glossary_delta.py` and `scripts/translate_refresh.py` are present but still implement a narrow glossary-only refresh path that does not satisfy milestone E.
- Confirmed current regression status before E implementation:
  - `tests/test_translate_style_contract.py`: pass
  - `tests/test_plc_docs_contract.py`: pass
  - `tests/test_soft_qa_contract.py`: 1 failing test due to style-profile drift semantics
- Locked the E gate artifact in `workflow/milestone_e_contract.yaml` and moved the active ledger from planning-only E to implementation-gated E.
- Completed the first parallel implementation wave after the gate:
  - `E-repro` now resolves glossary/style authority explicitly, supports clean-worktree bootstrap, and aligns README/workflow examples with live CLI flags.
  - `E-delta-engine` now emits locale-generic typed delta artifacts and operator-facing aggregate reports instead of a glossary-only impact set.
- Moved the active package to `E-task-executor`; the remaining work is to generate incremental tasks from `delta_rows.jsonl`, split execution from planning, and enforce post-run `qa_hard` gates.
- Closed the reviewer blocker pass before phase-2 closeout:
  - executor now stages candidate output before gates and writes an explicit failure-breakdown artifact
  - executor now groups refresh/retranslate work by `target_locale`, so mixed-market rows update the correct locale columns
  - glossary/style loaders now fail closed for locale mismatches instead of silently borrowing another market's term
- Updated the E contract to match the implemented surface:
  - removed the unimplemented `soft_qa` task type from the E task enum
  - pinned the executor failure artifact as `incremental_failure_breakdown.json`
- Milestone E focused regression is green again:
  - `27 passed` across refresh/executor, repro, typed delta, soft-QA compatibility, translate style contract, and PLC docs contract tests
- Added a post-E roadmap modify proposal to PLC/TriadDev docs:
  - `F → S` now has an explicit four-phase interpretation while preserving the original milestone letters
  - recommended next main scope is `milestone_F_execute`
  - recommended governance sidecar is `milestone_M_prepare`
- Switched to stacked branch `codex/phase1-quality-closure` to start the first Phase 1 implementation slice.
- Locked the Phase 1 slice to `translate_refresh` unified execution-status contracts only:
  - no `run_smoke_pipeline` orchestration changes in this round
  - no `soft_qa` / `repair_loop` runtime wiring in this round
- Current validation plan is focused tests, not smoke:
  - rationale: this slice changes executor artifact semantics but intentionally leaves the smoke entrypoint untouched
- Implemented the Phase 1 status-contract slice in `translate_refresh`:
  - task artifacts now persist `execution_status`, `final_status`, and `status_reason`
  - manifest artifacts now persist `overall_status`, `task_outcomes`, and `gate_summary`
  - review queue rows now persist `review_source`
- Closed the last Phase 1 contract gap in the main thread:
  - execution failures now keep the staged candidate artifact and return a non-zero exit code instead of silently promoting final output
- Phase 1 focused acceptance is green:
  - `python -m pytest tests/test_translate_refresh_contract.py tests/test_milestone_e_e2e.py tests/test_plc_docs_contract.py -q`
  - result: `10 passed`
- Smoke remains intentionally skipped for this slice because `scripts/run_smoke_pipeline.py` is unchanged and orchestration behavior is out of scope for this PR.

## 2026-03-25
- Confirmed PR #10 and PR #11 are merged and `origin/main` now contains both the milestone E baseline and Phase 1 quality-closure follow-up.
- Shifted the active roadmap scope from the merged `milestone_F_execute` slice to `milestone_M_prepare` on branch `codex/phase2-governance-substrate`.
- Chose a bounded Phase 2 first package instead of trying to execute all of `M/N/O/P` at once:
  - freeze a machine-checkable governance contract for `run_manifest`, `session_start`, `session_end`, and `milestone_state`
  - add a validator utility for those artifacts
  - extend PLC docs regression to lock representative records and templates to the same contract
- Validation plan for this slice is focused governance tests only:
  - rationale: Phase 2 first package changes documentation contracts and validator code, not runtime translation orchestration
- Completed the first Phase 2 governance substrate package:
  - added `workflow/plc_governance_contract.yaml` as the machine-checkable contract source
  - added `scripts/plc_validate_records.py` as the repo-local validator
  - expanded `tests/test_plc_docs_contract.py` to validate templates, representative records, and preset-based validator runs
- Synced the human-facing governance docs to the same contract language:
  - `field_schema.md`
  - `session_start_template.md`
  - `session_end_template.md`
  - `milestone_state_template.md`
  - `continuity_protocol.md`
- Focused Phase 2 acceptance is green:
  - `python -m pytest tests/test_plc_docs_contract.py -q` -> `7 passed`
  - `python scripts/plc_validate_records.py --preset representative --preset templates` -> `Validated 7 PLC governance artifact(s).`
- Smoke remains intentionally skipped for this slice because the runtime pipeline and orchestrator are untouched.
- Started the Phase 2 closeout package on `codex/phase2-governance-closeout` to finish the remaining `O + P` substrate work.
- Expanded the governance target from “first bounded package” to “phase-complete closeout”:
  - machine-checkable three-point validation for `changed_files`, `evidence_refs`, and `adr_refs`
  - closeout-grade representative records for session, run manifest, and milestone state
  - Phase 3 stays planning-ready only until a later implementation-start decision
- Completed the Phase 2 closeout package:
  - aligned `workflow/plc_governance_contract.yaml`, `field_schema.md`, `continuity_protocol.md`, and the PLC templates to the same three-point governance semantics
  - upgraded representative PLC records so run/session/milestone artifacts all carry `changed_files`, `evidence_refs`, and `adr_refs`
  - closed `milestone_state_M.md` with `status=done` and `evidence_ready=true`
- Focused closeout acceptance is green:
  - `python -m pytest tests/test_plc_docs_contract.py -q` -> `9 passed`
  - `python scripts/plc_validate_records.py --preset representative --preset templates` -> `Validated 7 PLC governance artifact(s).`
- TriadDev control plane is now aligned to `phase3_planning_ready`; Phase 3 remains planning-only, not implementation-started.
- Confirmed PR #13 is merged and moved the active branch to `codex/milestone-i-prepare` from clean `main`.
- Started `milestone_I_prepare` as a planning-only Phase 3 slice:
  - active target is a bounded style-governance contract package
  - runtime implementation remains gated until `H` completes
- Recorded a fresh set of Phase 3 PLC artifacts:
  - `phase3_milestone_i_prepare_note.md`
  - `run_manifest_phase3_milestone_i_prepare.json`
  - `session_start_20260325_phase3_milestone_i_prepare.md`
  - `session_end_20260325_phase3_milestone_i_prepare.md`
  - `milestone_state_I.md`
- Focused Phase 3 planning acceptance is green:
  - `python -m pytest tests/test_plc_docs_contract.py -q`
  - record-level validation of the new run manifest, session start, session end, and milestone state under `scripts/plc_validate_records.py`
- Merged PR #14 into `main` and reopened Phase 3 from clean trunk on `codex/milestone-i-contract-package`.
- Completed the first milestone-I implementation package:
  - added `workflow/style_governance_contract.yaml`
  - added style-governance metadata and lineage to `data/style_profile.yaml`
  - updated `scripts/style_guide_bootstrap.py` and `scripts/style_sync_check.py` to emit and validate the governance header
  - synced the version/governance header into `workflow/style_guide.generated.md`, `workflow/style_guide.md`, and `.agent/workflows/style-guide.md`
  - added `tests/test_style_governance_contract.py`
- Focused milestone-I contract acceptance is green:
  - `python -m pytest tests/test_style_governance_contract.py tests/test_translate_style_contract.py tests/test_soft_qa_contract.py -q` -> `12 passed`
  - `python scripts/style_sync_check.py` -> `pass`
- Treated merged PR #15 as a bridge foundation only and returned the active execution lane to Phase 1 on fresh `main`.
- Opened `codex/phase1-quality-runtime-closeout` as the single active implementation branch under the phase-sized merge-window policy.
- Completed the remaining Phase 1 runtime closure in `scripts/run_smoke_pipeline.py`:
  - hard QA now routes through `repair_loop` with explicit recheck and blocked-state handling
  - soft QA now routes through bounded repair, fail-closed hard-gate review handoff, and rollback-safe promotion
  - smoke manifests now persist `repair_cycles`, `review_handoff`, `gate_summary`, and `delivery_decision`
- Added focused Phase 1 runtime contract coverage:
  - `tests/test_phase1_quality_runtime_contract.py` now locks hard-repair completion, soft rollback, and soft hard-gate-without-tasks handoff
  - `tests/test_batch6_repair_metrics_contract.py` now carries explicit style-profile and soft-QA rubric inputs for smoke orchestration tests
  - `tests/test_repair_loop_contract.py` keeps CLI doc authority focused on the repair workflow itself
- Phase 1 runtime acceptance is green again:
  - `python -m py_compile scripts/run_smoke_pipeline.py`
  - `python -m pytest tests/test_batch6_repair_metrics_contract.py tests/test_phase1_quality_runtime_contract.py tests/test_repair_loop_contract.py tests/test_soft_qa_contract.py tests/test_smoke_verify.py -q` -> `29 passed`
  - `python -m pytest tests/test_translate_refresh_contract.py tests/test_milestone_e_e2e.py -q` -> `10 passed`
- PLC/TriadDev phase-boundary records now validate for the new Phase 1 run/session/milestone artifacts.
- Merged PR #16 into `main` as `3a84f55`, closing the full Phase 1 large-batch runtime scope.
- Phase 1 review feedback is fully absorbed:
  - early-fail smoke manifests now report `failed` correctly
  - non-`ru-RU` review handoff rows keep current translated text
  - representative PLC milestone records now point to `milestone_state_H.md`
- Re-ran post-review acceptance successfully:
  - focused runtime: `31 passed`
  - focused executor + PLC docs: `21 passed`
  - PLC validator presets: `Validated 11 PLC governance artifact(s).`
- Current roadmap decision is now Phase 3, not Phase 4:
  - Phase 2 is already complete
  - `H` is merged, which removes the documented gate for broader `I/J/K/L`
  - the milestone-I bridge package is already on `main` as foundation
- Opened a new value-first gate for the next batch and scored the full Phase 3 batch `GO (25/30, High confidence)`.
- Opened `codex/phase3-language-governance-batch` from clean `main` and moved Phase 3 from planning into implementation.
- Frozen Phase 3 shared contracts/helpers before downstream wiring:
  - review ticket / feedback log / lifecycle / KPI contracts
  - `scripts/style_governance_runtime.py`
  - `scripts/review_governance.py`
  - `scripts/review_feedback_ingest.py`
- Active implementation split is now:
  - runtime style-governance enforcement in translate + soft QA
  - review ticket / feedback / lifecycle / KPI wiring in refresh + smoke pipeline
- Completed the shared Phase 3 governance helper layer:
  - `scripts/style_governance_runtime.py`
  - `scripts/review_governance.py`
  - `scripts/review_feedback_ingest.py`
  - `scripts/language_governance.py` as a thin compatibility wrapper over the new helper/contract surfaces
- Completed runtime consumer integration for the Phase 3 batch:
  - `translate_llm.py` and `soft_qa_llm.py` now fail closed on governed style-profile violations
  - `translate_refresh.py` now emits review tickets, feedback-log placeholders, lifecycle-aware KPI artifacts, and governed review handoff
  - `run_smoke_pipeline.py` now emits the same Phase 3 review / KPI artifacts without breaking the Phase 1 orchestration contract
- Phase 3 focused acceptance is green:
  - `python -m pytest tests/test_phase3_governance_helpers.py tests/test_phase3_runtime_governance.py tests/test_phase3_language_governance_contract.py tests/test_translate_refresh_contract.py tests/test_phase1_quality_runtime_contract.py tests/test_translate_style_contract.py tests/test_soft_qa_contract.py tests/test_plc_docs_contract.py -q` -> `44 passed`
  - `python scripts/style_sync_check.py` -> `pass`
  - `python scripts/plc_validate_records.py --preset representative --preset templates` -> `Validated 11 PLC governance artifact(s).`
- Live smoke feasibility was checked and blocked by environment only:
  - `python scripts/llm_ping.py` failed because `LLM_BASE_URL` / `LLM_API_KEY` are missing in the current shell
  - merge acceptance therefore uses the required representative smoke gate via deterministic orchestration coverage in `tests/test_phase1_quality_runtime_contract.py`
- Current branch status:
  - `codex/phase3-language-governance-batch` is implementation-complete
  - PR #17 is open: `feat(phase3): land language governance batch`
  - the next step is review absorption and merge, not more Phase 3 implementation

## 2026-03-26
- Confirmed PR #17 is merged into `main` as `88e9dba`; Phase 3 is now closed history, not the active execution lane.
- Opened `codex/phase4-operator-control-plane-batch` from clean `main`.
- Started Phase 4 as one phase-sized batch with bridge hardening included:
  - `repair_loop` target-column detection now excludes locale/language metadata columns
  - `language_governance` no longer falls back to the default lifecycle registry when an explicit caller registry is incomplete
- Added the Phase 4 operator control plane surface:
  - `workflow/operator_card_contract.yaml`
  - `scripts/operator_control_plane.py`
  - `tests/test_phase4_operator_control_plane.py`
- Accepted the operating-model ADR:
  - `docs/decisions/ADR-0003-operator-control-plane-operating-model.md`
- Focused bridge/operator acceptance is green:
  - `python -m pytest tests/test_repair_loop_contract.py tests/test_phase3_language_governance_contract.py tests/test_phase4_operator_control_plane.py -q` -> `22 passed`
  - `python -m py_compile scripts/operator_control_plane.py scripts/repair_loop.py scripts/language_governance.py`
- Remaining work in this phase is to:
  - sync PLC/TriadDev control-plane state to Phase 4
  - materialize the representative operator cards/report walkthrough from an existing run
  - run full focused acceptance and open one Phase 4 PR

## 2026-03-18
- Started M4 execution task for the 1000-row layered smoke input.
- Created `task_plan.md`, `findings.md`, and `progress.md`.
- Ran direct `llm_ping` successfully with the provided LLM credentials.
- Ran exact-input preflight and full pipeline attempts; both short-circuited at connectivity inside `run_smoke_pipeline.py`.
- Older full run on a related 1000-row artifact reached translation and QA Hard, then failed with `85` QA errors and `Translated 1002 / 1003 rows`.

## 2026-03-19
- Created and pushed checkpoint branch `codex/checkpoint-mainline-20260319`.
- Switched to `codex/deep-cleanup-r3` for deep-cleanup Batch 1.
- Materialized TriadDev brownfield control files and value gate artifacts.
- Added script authority manifest/report tooling for `main_worktree/scripts` vs `src/scripts`.
- Expanded Batch 1 runtime adapter coverage and added unit tests for the authority checker.
- Ran Batch 1 regression suite successfully: `29 passed`.
- Re-ran `m4_3_collect_coverage.py` and `m4_4_decision.py`; the decision summary remains `KEEP=6`.
- Current authority report is `WARN` because `runtime_adapter.py` is still alert-only drift, while required mirrors remain aligned.
- Started Batch 2 under the first-principles rule: preserve the smallest system needed for continued development, do not delete uncertain code.
- Added Batch 2 contract tests for `runtime_adapter`, `normalize_*`, and `soft_qa_llm`.
- Fixed explicit-router injection in `runtime_adapter.LLMClient`.
- Moved import-time standard-stream rewiring out of `normalize_tagger.py`, `normalize_tag_llm.py`, `translate_llm.py`, and `soft_qa_llm.py` into CLI-time configuration.
- Fixed `soft_qa_llm.py --dry-run` to use `batch_utils.SplitBatchConfig` and `split_into_batches`.
- Batch 2 focused test surface is green: `14 passed`.
- Started roadmap Phase 1 Batch 3/4 to convert near-core status decisions and frozen-zone
  boundaries into explicit governance artifacts.
- Collected branch-topology evidence for the later GitHub cleanup phase:
  several remote branches are fully contained in `origin/main`, while
  `reorg/v1.3.0-structure` remains the only audit-first diverged branch.
- Added `workflow/batch3_surface_inventory.json` and `workflow/batch4_frozen_zone_inventory.json`
  plus `reports/github_branch_audit_20260319.md` to make Phase 1 and Phase 2 decisions auditable.
- Added `tests/test_batch3_batch4_governance.py` to lock wrapper forwarding, CLI compatibility,
  and governance status expectations.
- Refined surface statuses:
  `normalize_ingest.py` is now `compat-keep documented ingest`,
  `normalize_tag_llm.py` is now `stress-only compat entrypoint`.
- Fixed `scripts/stress_test_3k_run.sh` so soft QA writes `--out_report` and `--out_tasks`,
  and the soft repair loop consumes the emitted tasks JSONL instead of the report JSON.
- Phase 1 regression plus evidence gate is green again: `50 passed`, authority remains `WARN`
  on `runtime_adapter.py` alert-only drift, and M4 remains at `KEEP=6`.
- Started Batch 5 on branch `codex/deep-cleanup-batch5` after local `main_worktree` was
  re-aligned with `origin/main` and GitHub governance was fully closed out.
- Added `tests/test_batch5_archive_candidates.py` to characterize the archived CLI shape of
  `repair_loop_v2.py` and the hard-coded recovery behavior of `repair_checkpoint_gaps.py`.
- Independent subagent review found hidden dependency blockers before archive could be
  finalized: active rules/root inventory still mention `repair_loop_v2.py`, and
  `repair_checkpoint_gaps.py` still participates in the documented translate-checkpoint recovery contract.
- Rolled the archive action back immediately, restored both files to `scripts/`, and
  converted Batch 5 into an audit-and-fallback step instead of a physical cleanup step.
- Updated the cleanup roadmap to treat Batch 5 as the point where these two repair-side
  utilities move from `archive-candidate` to `blocked` until their surrounding contracts
  are formally retired.
- Batch 5 regression and evidence gate are green:
  `56 passed`, authority is back to `WARN` on `runtime_adapter.py` only after required
  compat mirrors were resynced, and `M4_4_decision.jsonl` remains `KEEP=6`.
- Started Batch 6 on branch `codex/deep-cleanup-batch6` to retire repair-side governance
  contracts before any future archive attempt and to restore smoke metrics as optional observability.
- Rewrote the active rules, root inventory, and translate workflow so
  `repair_loop_v2.py` and `repair_checkpoint_gaps.py` are no longer presented as current tools.
- Downgraded both repair-side targets from `blocked` back to `archive-candidate` in
  `workflow/batch4_frozen_zone_inventory.json`; Batch 6 still does not physically archive them.
- Reconnected `scripts/metrics_aggregator.py` inside `scripts/run_smoke_pipeline.py` as a
  non-blocking Metrics stage that writes manifest-visible report artifacts before verify.
- Extended `scripts/metrics_aggregator.py` with usage fallback based on trace token fields
  and char-count estimation so sparse traces still produce stable totals and cost estimates.
- Added `tests/test_batch6_repair_metrics_contract.py` and turned the initial RED surface green:
  `7 passed`.
- Ran the full Batch 6 regression suite plus evidence gate successfully:
  `63 passed`, `scripts/check_script_authority.py` returned `WARN` on `runtime_adapter.py`
  only, and `scripts/m4_4_decision.py` still reports `KEEP=6`.
- Re-synced `src/scripts/run_smoke_pipeline.py` from the authority copy after the new
  Metrics stage introduced required-mirror drift; authority returned to the expected
  non-blocking state immediately afterward.
- Started Batch 7 on branch `codex/deep-cleanup-batch7` with the new top-level priority:
  restore sustainable production development rather than continue chasing script deletion.
- Added and expanded deterministic validation coverage in
  `tests/test_validation_contract.py` for explicit CLI paths, scoring, parse fallback,
  and metadata/report schema.
- Added and expanded deterministic repair coverage in
  `tests/test_repair_loop_contract.py` for hard-report JSON input, soft JSONL input,
  passthrough copy behavior, routing metadata, and runbook alignment.
- Updated `docs/repro_baseline.md` so validation commands now prefer explicit `--input`,
  `--output-dir`, `--report-dir`, and `--api-key-path` flags, and switched the retained
  credential example away from the drifted `config/api_key.txt` path.
- Updated `docs/WORKSPACE_RULES.md` so repair metadata steps now match the runtime truth
  (`repair_hard` / `repair_soft_major`) and checkpoint behavior is documented as
  snapshot-only rather than true resume support.
- Promoted `scripts/run_validation.py` and `scripts/build_validation_set.py` to
  `must-keep` in `workflow/batch4_frozen_zone_inventory.json`; `scripts/repair_loop.py`
  is being promoted in the same inventory as the retained repair authority.
- Ran focused Batch 7 contract tests successfully:
  `tests/test_validation_contract.py`, `tests/test_repair_loop_contract.py`, and
  `tests/test_batch3_batch4_governance.py` are green.
- Ran the full Batch 7 regression suite successfully:
  `77 passed`.
- Re-ran the evidence gate successfully:
  `scripts/check_script_authority.py` remains `WARN` on `runtime_adapter.py` only,
  `scripts/m4_3_collect_coverage.py` reports `0` issue hotspots,
  and `scripts/m4_4_decision.py` still reports `KEEP=6`.
- Committed Batch 7 as `ddd14e2` (`cleanup(batch7): recover production dev baselines`)
  and pushed branch `origin/codex/deep-cleanup-batch7` for PR review.
- Started Batch 8 on branch `codex/deep-cleanup-batch8`.
- Confirmed the retained mainline paths remain `scripts/repair_loop.py` and
  `scripts/rebuild_checkpoint.py`, while `repair_loop_v2.py` and
  `repair_checkpoint_gaps.py` are only historical archive targets now.
- Added Batch 8 characterization coverage for physical archive closeout and relaxed
  Batch 5/6 tests so they continue to validate historical evidence after the move.
- Physically moved `repair_loop_v2.py` and `repair_checkpoint_gaps.py` into
  `_obsolete/repair_archive/` and added an audit README plus Batch 8 closeout report.
- Ran focused Batch 8 archive-closeout coverage successfully:
  `17 passed`.
- Ran the full Batch 8 regression suite successfully:
  `81 passed`.
- Re-ran the evidence gate successfully:
  `scripts/check_script_authority.py` remains `WARN` on `runtime_adapter.py` only,
  `scripts/m4_3_collect_coverage.py` reports `0` issue hotspots,
  and `scripts/m4_4_decision.py` still reports `KEEP=6`.
- Committed Batch 8 as `3ae4fac` (`cleanup(batch8): close out repair archive migration`),
  pushed branch `origin/codex/deep-cleanup-batch8`, and opened PR #3.
- Started Batch 9 on branch `codex/deep-cleanup-batch9`.
- Added `tests/test_batch9_stress_surface_governance.py` to pin one retained stress shell
  path, explicit helper statuses, and the removal of the generic blocked stress bucket.
- Reclassified the stress surface in `workflow/batch4_frozen_zone_inventory.json` from one
  blocked umbrella to explicit shell/helper statuses.
- Updated `workflow/batch3_surface_inventory.json` so retained near-core references now
  point to `scripts/stress_test_3k_run.sh` rather than historical 5k acceptance helpers.
- Fixed the retained stress shell export invocation in `scripts/stress_test_3k_run.sh` so
  it now matches the current positional `rehydrate_export.py` contract.
- Started Batch 10 on branch `codex/deep-cleanup-batch10` as a stacked closeout branch on
  top of Batch 9 while PR #4 remains open.
- Reframed `src/scripts` from vague long-tail compat noise into an explicit
  `separate-exit-program` compatibility liability in the authority manifest and frozen-zone inventory.
- Removed the non-real `gate/**` placeholder from the frozen-zone inventory so closure is
  judged only against real surfaces.
- Added Batch 10 governance coverage for closeout decision semantics, root inventory
  wording, and the requirement that no real blocked surface remains in the cleanup inventory.
- Ran focused Batch 10 governance tests successfully: `15 passed`.
- Ran the full retained regression suite successfully with Batch 10 included: `92 passed`.
- Re-ran the evidence gate successfully:
  `scripts/check_script_authority.py` remains `WARN` on `runtime_adapter.py` only,
  `scripts/m4_3_collect_coverage.py` reports `0` issue hotspots,
  and `scripts/m4_4_decision.py` still reports `KEEP=6`.
- Batch 10 therefore closes the current cleanup roadmap:
  `src/scripts` remains operationally present, but any future mirror retirement now moves
  into a separate migration program instead of staying on the main cleanup path.
- Ran focused Batch 9 governance regression successfully:
  `42 passed`.
- Re-ran the evidence gate successfully:
  `scripts/check_script_authority.py` remains `WARN` on `runtime_adapter.py` only,
  `scripts/m4_3_collect_coverage.py` reports `0` issue hotspots,
  and `scripts/m4_4_decision.py` still reports `KEEP=6`.
- Re-ran the full explicit test-file suite successfully with `-s` to avoid the existing
  pytest capture issue in this workspace:
  `98 passed, 8 skipped`.
- Batch 9 now marks the roadmap as closeout-ready: Batch 10 should focus only on the
  long-term decision for `src/scripts` compat mirror rather than opening new cleanup
  surfaces.
