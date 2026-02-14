#!/usr/bin/env python3
"""Generate Omni Test Part 1 Metrics Report"""

import json
import os
from collections import defaultdict

import yaml

# Load pricing config
with open('config/pricing.yaml', 'r', encoding='utf-8') as f:
    pricing_config = yaml.safe_load(f)

pricing = pricing_config.get('models', {})

# Parse trace
steps = defaultdict(lambda: {'calls': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0})
models = defaultdict(lambda: {'calls': 0, 'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0})

trace_path = 'data/test06_outputs/llm_trace.jsonl'
with open(trace_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            d = json.loads(line.strip())
            step = d.get('step', 'unknown')
            model = d.get('model', 'unknown')
            usage = d.get('usage', {})
            pt = usage.get('prompt_tokens', 0) or 0
            ct = usage.get('completion_tokens', 0) or 0
            
            steps[step]['calls'] += 1
            steps[step]['prompt_tokens'] += pt
            steps[step]['completion_tokens'] += ct
            steps[step]['total_tokens'] += pt + ct
            
            models[model]['calls'] += 1
            models[model]['prompt_tokens'] += pt
            models[model]['completion_tokens'] += ct
            models[model]['total_tokens'] += pt + ct
        except Exception as e:
            pass

# Calculate totals
total_calls = sum(v['calls'] for v in steps.values())
total_prompt = sum(v['prompt_tokens'] for v in steps.values())
total_comp = sum(v['completion_tokens'] for v in steps.values())
total_tokens = total_prompt + total_comp

print("=== BY STEP ===")
for s, v in sorted(steps.items(), key=lambda x: -x[1]['total_tokens']):
    print(f"  {s}: calls={v['calls']}, prompt={v['prompt_tokens']}, comp={v['completion_tokens']}, total={v['total_tokens']}")

print()
print("=== BY MODEL ===")
for m, v in sorted(models.items(), key=lambda x: -x[1]['total_tokens']):
    print(f"  {m}: calls={v['calls']}, prompt={v['prompt_tokens']}, comp={v['completion_tokens']}, total={v['total_tokens']}")

print()
print("=== TOTALS ===")
print(f"  Total calls: {total_calls}")
print(f"  Total prompt tokens: {total_prompt}")
print(f"  Total completion tokens: {total_comp}")
print(f"  Total tokens: {total_tokens}")

# Calculate costs using pricing config
def get_model_price(model_name, pricing):
    """Get pricing for a model, with fallback"""
    if model_name in pricing:
        return pricing[model_name]
    # Try to match partial name
    for k, v in pricing.items():
        if k in model_name or model_name in k:
            return v
    # Default fallback
    return {'input_per_1M': 3.0, 'output_per_1M': 15.0}

total_cost = 0.0
step_costs = {}
model_costs = {}

for step, v in steps.items():
    # Use default pricing for step-level calculation
    cost = (v['prompt_tokens'] / 1_000_000 * 3.0) + (v['completion_tokens'] / 1_000_000 * 15.0)
    step_costs[step] = cost
    total_cost += cost

# Recalculate using model-specific pricing
total_cost = 0.0
for model, v in models.items():
    price = get_model_price(model, pricing)
    input_rate = price.get('input_per_1M', 3.0)
    output_rate = price.get('output_per_1M', 15.0)
    cost = (v['prompt_tokens'] / 1_000_000 * input_rate) + (v['completion_tokens'] / 1_000_000 * output_rate)
    model_costs[model] = cost
    total_cost += cost

# Recalculate step costs based on actual model usage in each step
# For now, use simple approximation
for step, v in steps.items():
    cost = (v['prompt_tokens'] / 1_000_000 * 3.0) + (v['completion_tokens'] / 1_000_000 * 15.0)
    step_costs[step] = cost

print()
print("=== COSTS (USD, estimated) ===")
print(f"  Total cost: ${total_cost:.4f}")
for s, c in sorted(step_costs.items(), key=lambda x: -x[1]):
    print(f"  {s}: ${c:.4f}")

# Rows processed
rows_translated = 18820  # From translated_r1.csv line count - 1
total_rows = 30453

print()
print("=== PROGRESS ===")
print(f"  Rows translated: {rows_translated}/{total_rows} ({rows_translated/total_rows*100:.1f}%)")
print(f"  Cost per 1k rows: ${total_cost / rows_translated * 1000:.4f}")

# Output data for report
output = {
    'total_calls': total_calls,
    'total_prompt_tokens': total_prompt,
    'total_completion_tokens': total_comp,
    'total_tokens': total_tokens,
    'total_cost_usd': total_cost,
    'rows_translated': rows_translated,
    'total_rows': total_rows,
    'cost_per_1k_rows': total_cost / rows_translated * 1000 if rows_translated > 0 else 0,
    'steps': dict(steps),
    'models': dict(models),
    'step_costs': step_costs,
    'model_costs': model_costs
}

# Save as JSON for further processing
with open('data/test06_outputs/part1_metrics.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print()
print("=== SAVED ===")
print("  data/test06_outputs/part1_metrics.json")
