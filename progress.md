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
