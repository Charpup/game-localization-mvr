# Metrics & Cost Optimization Guide

## Overview

This document explains the cost monitoring system, trace analysis, and optimization strategies for the localization pipeline. It provides formulas for cost estimation and guides on interpreting the aggregated metrics report.

## 1. Cost Calculation Formulas

The system supports two billing modes in `pricing.yaml`:

### Mode A: Multiplier (Platform)

Cost is derived from a base rate multiplied by model and complexity factors.

- **Formula**: `Cost = (BaseRate * GroupMult * ModelMult * WeightedTokens) / Divisor`
- **WeightedTokens**: `Prompt + (Completion * CompletionMult)`
- **Use Case**: Internal platform billing or shared quotas.

### Mode B: Per Million (Direct API)

Standard Token-based billing (e.g., OpenAI/Anthropic).

- **Formula**: `(Prompt / 1M * InputPrice) + (Completion / 1M * OutputPrice)`
- **Use Case**: Direct API keys (OpenAI, Anthropic).

## 2. LLM Trace Structure

`llm_trace.jsonl` records every API call. Key fields:

```json
{"type": "llm_call", "step": "translate", "prompt_tokens": 450, "completion_tokens": 120, "cost_usd_est": 0.0021}
{"type": "llm_call", "step": "soft_qa", "prompt_tokens": 1200, "completion_tokens": 5, "cost_usd_est": 0.0015}
{"type": "llm_error", "step": "translate", "error": "rate_limit_exceeded", "model": "gpt-4"}
```

## 3. Cost Optimization Checklist

| Phase | Strategy | Optimization Action | Expected Saving |
| :--- | :--- | :--- | :--- |
| **Translation** | Batching | Ensure `batch_size=50` (Rule 14). | 40-60% (Lower overhead) |
| **QA** | Filter | Run `qa_hard.py` *before* Soft QA. | 100% of failed rows |
| **Repair** | Scope | Only repair *failed* rows (not full file). | 80-90% vs full re-run |
| **General** | Routing | Use Haiku/Mini for Soft QA & Tags. | 10x cheaper per token |

## 4. Interpreting Metrics Report

`metrics_aggregator.py` outputs `metrics_report.md`. Key indicators:

- **$/1k Rows**: The "Unit Cost". Target: <$2.00 for standard text.
- **Error Rate**: % of calls failing Hard QA. Target: <1%.
- **Escalation Rate**: % of repairs failing 3x. Target: <0.1%.
- **Cache Hit Rate**: (If enabled) Token savings.

## Quick Commands

```bash
# Generate report from trace
python scripts/metrics_aggregator.py --trace data/llm_trace.jsonl --out_md reports/metrics_report.md

# Analyze token usage distribution
python scripts/analyze_part1_metrics.py --trace data/llm_trace.jsonl
```

## Common Pitfalls

- **Trap 1**: **Leaving Debug On**.
  - **Consequence**: `metrics_report.md` cluttered with dry-run zeros.
  - **Fix**: Ensure `LLM_DRY_RUN=0` for production metrics.
- **Trap 2**: **Ignoring Unknown Steps**.
  - **Consequence**: Costs labeled "Unknown" in report.
  - **Fix**: Always pass `metadata={'step': 'name'}` in custom scripts.
