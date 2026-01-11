---
description: Generate metrics summary for LLM usage and costs from localization pipeline
---

# /loc_metrics

Generate cost, token usage, success rate, and per-1k-line cost summary for the localization pipeline.

## Prerequisites

- `data/llm_trace.jsonl` - LLM call trace from runtime_adapter
- `data/translated.csv` and/or `data/repaired.csv` - for line count reference
- `config/pricing.yaml` - pricing configuration

## Run Metrics Aggregation

// turbo
```bash
python scripts/metrics_aggregator.py \
  --trace data/llm_trace.jsonl \
  --pricing_yaml config/pricing.yaml \
  --translated data/translated.csv \
  --repaired data/repaired.csv \
  --out_json data/metrics_summary.json \
  --out_md data/metrics_report.md
```

## Outputs

| File | Description |
|------|-------------|
| `data/metrics_summary.json` | Structured metrics data |
| `data/metrics_report.md` | Human-readable report |

## Key Metrics

- **Total LLM Calls**: Number of API calls made
- **Total Tokens**: Prompt + completion tokens
- **Total Cost**: Calculated from pricing.yaml
- **Cost per 1k Lines**: Normalized cost metric
- **Usage Presence Rate**: % of calls with actual token counts (vs estimated)

## Billing Mode

The script supports two billing modes (configured in `config/pricing.yaml`):

1. **multiplier** - Platform billing formula:
   ```
   cost = conversion_rate × group_mult × model_mult × 
          (prompt_tokens + completion_tokens × completion_ratio) / 500000
   ```

2. **per_1m** - Standard per-million-token pricing:
   ```
   cost = (prompt_tokens / 1M) × input_per_1M + 
          (completion_tokens / 1M) × output_per_1M
   ```

## Fallback Estimation

If `usage` data is missing from LLM response:
- Tokens estimated from character count: `tokens ≈ ceil(chars / 4)`
- Report shows `estimated_calls` count
- Cost from estimated tokens marked as `cost_estimated_portion`

## Warning Conditions

The report will show warnings if:
- **Unknown step ratio > 1%**: LLM calls missing `metadata.step`
- **Missing pricing**: Models not found in `config/pricing.yaml`
