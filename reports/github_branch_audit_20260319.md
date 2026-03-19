# GitHub Branch Audit 2026-03-19

## Scope

This audit follows the cleanup roadmap order:

1. finish code cleanup and mainline verification
2. prepare branch audit decisions
3. merge necessary PRs
4. remove redundant remote branches and converge on a minimal branch model

The current mainline cleanup work remains on `codex/deep-cleanup-r3`. No remote deletion is performed in this step.

## Decision buckets

### keep-long-term

- `main`
  - default branch
  - target for cleanup PR merge
- `archive tag` (to be created after cleanup merge)
  - replaces long-lived archive branches

### delete-after-merge

- `codex/deep-cleanup-r3`
  - active cleanup branch; delete after merge into `main`
- `codex/checkpoint-mainline-20260319`
  - checkpoint branch; delete after merge and after archive tag exists
- `release/production-go-complete`
  - points to the same commit as `origin/main`
- `backup-before-cleanup`
  - `origin/main` is ahead and fully contains this branch
- `feat/apiyi-metrics-integration`
  - `origin/main` is ahead and fully contains this branch
- `feature/batch-llm-runtime`
  - `origin/main` is ahead and fully contains this branch
- `feature/omni-test-cost-monitoring`
  - `origin/main` is ahead and fully contains this branch
- `sync/local-baseline-20260122`
  - `origin/main` is ahead and fully contains this branch

### audit-first

- `reorg/v1.3.0-structure`
  - diverges from `origin/main`
  - ahead/behind summary relative to `origin/main`: `0/19`
  - latest branch tip touches:
    - `skill/v1.3.0/scripts/soft_qa_llm.py`
    - `src/scripts/qa_hard.py`

## Evidence snapshot

- `origin/main` and `origin/release/production-go-complete` currently resolve to the same commit: `c12dbee`
- Fully-contained history relative to `origin/main`:
  - `origin/backup-before-cleanup` -> `8/0`
  - `origin/feat/apiyi-metrics-integration` -> `30/0`
  - `origin/feature/batch-llm-runtime` -> `37/0`
  - `origin/feature/omni-test-cost-monitoring` -> `36/0`
  - `origin/sync/local-baseline-20260122` -> `1/0`
- Diverged branch:
  - `origin/reorg/v1.3.0-structure` -> `0/19`

Numbers above use `git rev-list --left-right --count origin/main...<branch>` where the first number is commits unique to `origin/main` and the second number is commits unique to the branch.

## Merge order

1. merge `codex/deep-cleanup-r3` into `main`
2. re-run smoke-focused pytest, authority gate, `m4_3_collect_coverage.py`, and `m4_4_decision.py` on the merge candidate
3. audit `reorg/v1.3.0-structure`
4. only if the audit proves unique retained value, merge or cherry-pick it separately
5. create a single archive tag
6. delete the remote branches in `delete-after-merge`

## Audit questions for `reorg/v1.3.0-structure`

- Does it contain code or docs still missing from `main`?
- Is its remaining value only as a historical reference for `v1.3.0` compatibility?
- Can any retained value be preserved by a tag, document import, or targeted cherry-pick instead of a long-lived branch?
- Does it touch `main_worktree` authority surfaces, or only `src/` and `skill/v1.3.0/` compatibility zones?

## End state target

- remote branches: `main` only
- historical anchor: one archive tag
- temporary PR branches: deleted after merge
- branch protection: focused on `main`
