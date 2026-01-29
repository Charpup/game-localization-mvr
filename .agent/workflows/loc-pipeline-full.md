---
description: Full 14-step localization pipeline with dual repair loops
---

# Localization Pipeline v2.0 - Full Workflow

## Prerequisites

- Python 3.7+ with PyYAML
- LLM environment variables: `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`
- `glossary/compiled.yaml` (or will be created in Step 3)

## Pipeline Steps

### Phase 1: Preparation

// turbo
0. **Style Guide Sync Check**

```bash
python scripts/style_sync_check.py
```

// turbo

1. **Normalize** - Freeze placeholders

```bash
python scripts/normalize_guard.py data/input.csv data/draft.csv data/placeholder_map.json workflow/placeholder_schema.yaml
```

1. **Check Glossary** - Verify compiled.yaml exists with matching scope

```bash
# If glossary/compiled.lock.json exists and matches language_pair+genre+franchise, skip Step 3
```

1. **Extract & Translate Glossary** (if needed)

```bash
python scripts/extract_terms.py data/draft.csv --out data/term_candidates.yaml
# Then manually translate or use LLM, then compile
python scripts/glossary_compile.py --approved glossary/approved.yaml
```

1. **Check Style Guide** - Verify workflow/style_guide.md

### Phase 2: Translation (Loop A - Hard Gate)

1. **Translate**

```bash
python scripts/translate_llm.py data/draft.csv data/translated.csv workflow/style_guide.md data/glossary.yaml --target ru-RU
```

1. **QA Hard**

```bash
python scripts/qa_hard.py data/translated.csv data/placeholder_map.json workflow/placeholder_schema.yaml workflow/forbidden_patterns.txt data/qa_hard_report.json
```

1. **Repair Loop Hard** (if qa_hard fails, max 3 attempts)

```bash
python scripts/repair_loop.py data/translated.csv data/qa_hard_report.json data/repair_tasks.jsonl workflow/style_guide.md data/glossary.yaml --out_csv data/repaired.csv
# Then repeat Step 6
```

### Phase 3: Soft QA (Loop B - Safety)

1. **Soft QA**

```bash
python scripts/soft_qa_llm.py data/translated.csv workflow/style_guide.md data/glossary.yaml workflow/soft_qa_rubric.yaml
```

1. **Repair Loop Soft**

```bash
python scripts/repair_loop.py data/translated.csv data/qa_hard_report.json data/repair_tasks.jsonl workflow/style_guide.md --only_soft_major
```

6b. **QA Hard Recheck** (verify soft repair didn't break hard constraints)

```bash
python scripts/qa_hard.py data/repaired.csv data/placeholder_map.json workflow/placeholder_schema.yaml workflow/forbidden_patterns.txt data/qa_recheck_report.json
```

7b. **Repair Loop Hard Post-Soft** (if 6b fails, max 2 attempts, minimal changes)

### Phase 4: Export & Metrics

// turbo
10. **Export** - Rehydrate placeholders

```bash
python scripts/rehydrate_export.py data/repaired.csv data/placeholder_map.json data/final.csv
```

// turbo
11. **Metrics** - Aggregate LLM costs

```bash
python scripts/metrics_aggregator.py
```

### Phase 5: Glossary Lifecycle

1. **Glossary Autopromote** - Generate proposals

```bash
python scripts/glossary_autopromote.py --before data/translated.csv --after data/repaired.csv --style workflow/style_guide.md --glossary data/glossary.yaml
```

1. **Review Proposals** - User fills decision in CSV

```bash
python scripts/glossary_make_review_queue.py --proposals data/glossary_proposals.yaml --out_csv data/glossary_review_queue.csv
# User edits CSV: approve/reject/edit
python scripts/glossary_apply_review.py --review_csv data/glossary_review_queue.csv
```

1. **Publish Glossary** - Compile for next round

```bash
python scripts/glossary_compile.py --approved glossary/approved.yaml --language_pair zh-CN->ru-RU
```

## Loop Thresholds

| Loop | Max Attempts | On Exceed |
|------|-------------|-----------|
| Loop A (Hard Gate) | `HARD_LOOP_MAX=3` | Escalation |
| Loop B (Post-Soft) | `POST_SOFT_HARD_LOOP_MAX=2` | Escalation |

## Escalation Output

Failed items go to `data/escalations.csv` for manual handling.
