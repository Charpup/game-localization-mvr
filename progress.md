# Progress Log

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
