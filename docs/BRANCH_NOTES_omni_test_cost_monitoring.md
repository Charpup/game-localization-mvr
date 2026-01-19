# Branch Notes: feature/omni-test-cost-monitoring

## Overview

This branch is a **mid-run experimental snapshot** for Omni Test observability and cost accounting.

> **⚠️ This branch is intentionally NOT merged into main.**
> It serves as a mid-run iteration checkpoint for Omni Test cost monitoring development.

---

## (A) Context: Mid-Run Iteration

This branch was created **during Omni Test Part 2 execution**.

- **Does NOT affect** Part 1 metrics conclusions
- **Provides** cost observability for Part 2 continuation
- **Serves as** baseline for future optimizations

---

## (B) Problems Solved

| Problem | Solution |
|---------|----------|
| Cannot distinguish token/cost source | Added `usage_source: api_usage \| local_estimate` |
| Cannot compare platform vs local usage | API易 conditional reconciliation |
| Cannot detect max_tokens anomalies | Anomaly detection in cost_snapshot |
| Cannot segment costs by run | Added `run_id` and `batch_id` to trace |

---

## (C) Known Issues (Intentionally Deferred)

The following are **NOT bugs** - they are deliberately deferred optimization points:

1. **Escalation rate ~7%** (target <3%) - partial batch retry implemented but not fully tuned
2. **Batch long-tail latency** - still has optimization room
3. **Style Guide pipeline** - not yet included in cost optimization scope

---

## (D) Usage

### Environment Variables

```bash
# Set run identifier for cost segmentation
export LLM_RUN_ID="omni_test_part2"

# Trace output path (default: data/llm_trace.jsonl)
export LLM_TRACE_PATH="data/llm_trace.jsonl"
```

### API易 Conditional Triggering

API易 usage reconciliation is **automatically enabled** when:

```
base_url == "https://api.apiyi.com/v1"
```

Otherwise, falls back to local token estimation (chars/4).

### Generate Cost Snapshot

```bash
python scripts/cost_snapshot.py \
    --trace data/llm_trace.jsonl \
    --run_id omni_test_part2 \
    --output_dir reports/cost
```

---

## Files Changed

### New Files

| File | Purpose |
|------|---------|
| `config/cost_monitoring.yaml` | Monitoring config with API易 settings |
| `scripts/cost_monitor.py` | Coordinator with signal handling |
| `scripts/cost_snapshot.py` | Trace aggregation + anomaly detection |
| `scripts/apiyi_usage_client.py` | Conditional API易 usage client |

### Modified Files

| File | Changes |
|------|---------|
| `scripts/runtime_adapter.py` | Trace enrichment: base_url, run_id, batch_id, cost_usd_est, max_tokens, usage_source |
| `scripts/translate_llm.py` | v5.0: Structured output contract, partial batch retry |

---

## Trace Field Contract

Every LLM call trace now includes:

```json
{
  "ts": "2026-01-20T03:34:17.474616",
  "step": "translate",
  "batch_id": "translate:000042",
  "base_url": "https://api.apiyi.com/v1",
  "run_id": "omni_test_part2",
  "selected_model": "gpt-4.1-mini",
  "prompt_tokens": 998,
  "completion_tokens": 129,
  "total_tokens": 1127,
  "usage_source": "api_usage",
  "cost_usd_est": 0.000321,
  "max_tokens": 520
}
```

---

## Baseline Commit

- Parent branch: `feature/batch-llm-runtime`
- Created: 2026-01-20

---

*This branch supports Omni Test observability. Do not merge without explicit review.*
