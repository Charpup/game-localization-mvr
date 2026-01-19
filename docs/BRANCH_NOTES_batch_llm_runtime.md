# Branch Notes: feature/batch-llm-runtime

## Purpose

This branch experiments with a **batch-calling LLM runtime** for the localization pipeline.
It shifts from single-item LLM calls (high prompt duplication) to dynamic batch calls (amortized prompt cost).

## Baseline

- **Parent branch**: `main`
- **Baseline commit**: `6582943` (v0.5.0)
- **Baseline behavior**: Single-item LLM calls for translate/soft_qa/autopromote/refresh

## Branch Behavior Changes

### 1. Batch Processing

| Step | Old (main) | New (this branch) |
|------|------------|-------------------|
| translate | 1 row per call, ~574 tokens/call | 10-20 rows per call, ~800-1200 tokens/batch |
| soft_qa | 1 row per call | 10-15 rows per call, JSONL issues-only output |
| glossary_autopromote | 1 row per call | 10-15 rows per call, aggregated proposals |
| translate_refresh | 1 row per call | 10-15 rows per call, batch placeholder validation |

### 2. New CLI Parameters

```
--batch_size N          # Items per batch (default: 20 for translate, 15 for others)
--max_batch_tokens N    # Token budget per batch (default: 6000)
```

### 3. Output Format Changes

- **translate**: JSON array `[{string_id, target_ru}, ...]`
- **soft_qa**: JSONL, only problem items
- **glossary_autopromote**: Proposals with aggregation stats
- **translate_refresh**: JSON array `[{string_id, updated_ru}, ...]`

### 4. Error Handling

- **Binary-split fallback**: On parse failure, batch is split in half recursively
- **Escalation**: Items that fail at batch_size=1 are escalated to CSV

## Files Changed

### New Files

- `scripts/batch_utils.py` - Token estimation, batch splitting, fallback logic

### Modified Scripts

- `scripts/translate_llm.py` (v3.0)
- `scripts/soft_qa_llm.py` (v2.0)
- `scripts/glossary_autopromote.py` (v2.0)
- `scripts/translate_refresh.py` (v2.0)

### Config

- `config/llm_routing.yaml` - Added max_tokens, response_format for batch steps

## How to Test (Real LLM)

```powershell
# 1. Set environment
Get-Content .env | ForEach-Object { if ($_ -match '^([^=]+)=(.*)$') { 
    [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2], 'Process') 
}}

# 2. Create 50-row test sample
python -c "import csv; r=list(csv.DictReader(open('data/draft.csv','r',encoding='utf-8-sig')))[:50]; f=open('data/test_batch_50.csv','w',encoding='utf-8-sig',newline=''); w=csv.DictWriter(f,fieldnames=list(r[0].keys())); w.writeheader(); w.writerows(r); f.close()"

# 3. Run batch translate
python scripts/translate_llm.py --input data/test_batch_50.csv --output data/test_batch_50_out.csv --batch_size 10

# 4. Run batch soft_qa
python scripts/soft_qa_llm.py data/test_batch_50_out.csv workflow/style_guide.md data/glossary.yaml workflow/soft_qa_rubric.yaml --batch_size 10

# 5. Check trace for batch evidence
Get-Content data/llm_trace.jsonl -Tail 10
```

**Expected trace fields**: `batch_idx`, `batch_size`, `prompt_tokens`, `completion_tokens`, `selected_model`

## Rollback Plan

1. **Switch branches**: `git checkout main`
2. **Or force single-item mode** (if needed): Reduce `--batch_size 1`

## Known Limitations

- Batch size tuning may be needed based on model context limits
- Very long source texts may need custom batch splitting
- Full pipeline E2E test pending on larger dataset

## Token Efficiency Estimate

| Scenario | Old (single-item) | New (batch) | Savings |
|----------|------------------|-------------|---------|
| 500 rows translate | ~287K tokens | ~50K tokens | ~5-6x |
| 500 rows soft_qa | ~200K tokens | ~35K tokens | ~5-6x |

---
*Branch created: 2026-01-19*
*Baseline: v0.5.0 (6582943)*
