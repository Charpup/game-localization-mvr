---
description: Round2 glossary refresh - minimal rewrite for term changes only
---

# Round2 Glossary Refresh Workflow

## Purpose

When glossary changes are published, don't re-run the full 14-step pipeline.
Instead, perform minimal targeted refresh on affected rows only.

## When to Use

- After `glossary_compile.py` creates a new `compiled.yaml`
- When terms are added or translations changed
- To minimize LLM cost and translation drift

## Prerequisites

- Previous `translated.csv` exists
- New `glossary/compiled.yaml` is published
- Keep backup of old compiled: `cp glossary/compiled.yaml glossary/compiled.yaml.bak`

## Workflow Steps

// turbo
1. **Compute Delta** - Find changed terms and impacted rows
```bash
python scripts/glossary_delta.py \
    --old glossary/compiled.yaml.bak \
    --new glossary/compiled.yaml \
    --source_csv data/translated.csv \
    --out_impact data/glossary_impact.json
```

Output: `glossary_impact.json` containing:
- `delta_terms`: added/changed/removed terms
- `impact_set`: list of string_ids to refresh
- `glossary_hash_old/new`: for tracing

2. **Refresh Translation** - Minimal rewrite for glossary changes
```bash
python scripts/translate_refresh.py \
    --impact data/glossary_impact.json \
    --translated data/translated.csv \
    --glossary glossary/compiled.yaml \
    --style workflow/style_guide.md \
    --out_csv data/refreshed.csv
```

Trace metadata: `step: "translate_refresh"` with old/new hashes

// turbo
3. **QA Hard on Refreshed** - Validate refreshed rows
```bash
python scripts/qa_hard.py data/refreshed.csv data/placeholder_map.json \
    workflow/placeholder_schema.yaml workflow/forbidden_patterns.txt \
    data/qa_refresh_report.json
```

4. **Repair Loop** (if needed, `POST_SOFT_HARD_LOOP_MAX=2`)
```bash
python scripts/repair_loop.py data/refreshed.csv data/qa_refresh_report.json ...
```

5. **Merge** - Replace affected rows in main translated.csv
```bash
# Manual or script-based merge of refreshed rows
```

## Key Differences from Full Pipeline

| Aspect | Full Pipeline | Round2 Refresh |
|--------|---------------|----------------|
| Scope | All rows | Impact set only |
| Translation | Full re-translate | Minimal term update |
| Soft QA | Optional batch | Skipped by default |
| LLM Step | `translate` | `translate_refresh` |
| Cost | High | Proportional to changes |

## Metrics Tracking

Round2 calls use distinct trace metadata:
```python
metadata = {
    "step": "translate_refresh",
    "glossary_hash_old": "sha256:abc...",
    "glossary_hash_new": "sha256:def...",
    "terms_refreshed": 3
}
```

This enables:
- Cost breakdown by Round1 vs Round2
- Rollback tracking by glossary version
- Per-term refresh cost analysis

## Optional: Soft QA on High-Change Rows

If `--soft_qa_threshold 0.3` is passed to translate_refresh (future feature):
- Rows with >30% character change will also go through soft QA
- Disabled by default to minimize cost
