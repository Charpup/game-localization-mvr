# Phase 3 Milestone I Prepare Note

- scope: `milestone_I_prepare`
- phase: `phase-3-language-governance`
- branch: `codex/milestone-i-prepare`
- planning_mode: `planning-only`

## Existing Style Governance Surface
- canonical candidate:
  - `data/style_profile.yaml`
- generated artifacts:
  - `workflow/style_guide.generated.md`
- mirror/operator-facing artifacts:
  - `workflow/style_guide.md`
  - `.agent/workflows/style-guide.md`
- generators and sync checks:
  - `scripts/style_guide_bootstrap.py`
  - `scripts/style_sync_check.py`
- current runtime consumers:
  - `scripts/translate_llm.py`
  - `scripts/soft_qa_llm.py`
  - `tests/test_translate_style_contract.py`
  - `tests/test_soft_qa_contract.py`

## Planning Conclusion
- `milestone_I_prepare` should start with a bounded style-governance contract package, not runtime enforcement.
- The first implementation package should define:
  - `style_guide_id`
  - `version`
  - `status`
  - `owner`
  - `approval_ref`
  - `adr_refs`
  - `supersedes`
  - `deprecated_by`
  - `generated_at`
  - `lineage`
- Runtime implementation remains blocked until `H` completes and Phase 3 is explicitly moved from `planning-only` to `implementation-started`.

## Recommended Next Implementation Slice
- add a machine-readable style-governance contract artifact
- add an entry validator for `approved/loadable/deprecated` semantics
- extend focused style-contract tests to cover governance metadata and lineage
