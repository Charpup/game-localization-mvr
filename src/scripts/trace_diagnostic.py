#!/usr/bin/env python3
"""
Translation Trace Diagnostic - Omni Test Part 2
Only read trace data, no code changes.
"""

import json
import os
from collections import defaultdict
from datetime import datetime

trace_path = 'data/test06_outputs/llm_trace.jsonl'

# Parse trace entries (focus on Part 2 = after Part 1 pause)
entries = []
with open(trace_path, 'r', encoding='utf-8') as f:
    for line in f:
        try:
            d = json.loads(line.strip())
            entries.append(d)
        except:
            pass

print(f"Total trace entries: {len(entries)}")

# Filter to translate step only (Part 2 focus)
translate_entries = [e for e in entries if e.get('step') == 'translate']
print(f"Translate entries: {len(translate_entries)}")

# Find Part 2 entries (after pause at ~18820 rows)
# Part 2 started at ~23:03 on 2026-01-19
# Let's filter by timestamp to get recent entries

# Parse timestamps
def parse_ts(e):
    ts = e.get('timestamp') or e.get('ts') or e.get('time')
    if ts:
        try:
            if isinstance(ts, (int, float)):
                return ts
            return datetime.fromisoformat(ts.replace('Z', '+00:00')).timestamp()
        except:
            pass
    return 0

# Sort by timestamp
translate_entries.sort(key=parse_ts)

# Get entries from last 60 minutes (or last N entries)
# Since we don't have exact timestamps, use last 1000 entries as proxy for Part 2
part2_entries = translate_entries[-2000:] if len(translate_entries) > 2000 else translate_entries[-1000:]

print(f"Part 2 sample size: {len(part2_entries)}")

# Analyze metrics
batch_sizes = []
latencies = []
errors = []
retries = defaultdict(int)
status_codes = defaultdict(int)
batch_splits = 0
single_item_calls = 0
parse_failures = 0

for e in part2_entries:
    # Batch size
    bs = e.get('batch_size') or e.get('batch_idx') or 1
    if isinstance(bs, int):
        batch_sizes.append(bs)
        if bs == 1:
            single_item_calls += 1
    
    # Latency
    lat = e.get('latency_ms') or e.get('duration_ms') or e.get('elapsed_ms')
    if lat:
        latencies.append(lat)
    
    # Errors / retries
    err = e.get('error') or e.get('error_type')
    if err:
        errors.append(err)
        
    retry = e.get('retry') or e.get('retry_count') or e.get('attempt')
    if retry and retry > 1:
        retries['retry'] += 1
    
    # HTTP status
    status = e.get('http_status') or e.get('status_code')
    if status:
        status_codes[status] += 1
    
    # Split indicator
    if e.get('split') or e.get('binary_split') or 'split' in str(e.get('reason', '')).lower():
        batch_splits += 1
    
    # Parse failure
    if 'parse' in str(e.get('error', '')).lower() or 'json' in str(e.get('error', '')).lower():
        parse_failures += 1

# Calculate statistics
def percentile(data, p):
    if not data:
        return 0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p / 100)
    return sorted_data[min(idx, len(sorted_data)-1)]

print("\n=== KEY METRICS ===")
print(f"Sample entries: {len(part2_entries)}")
print(f"Avg batch size: {sum(batch_sizes)/len(batch_sizes):.2f}" if batch_sizes else "No batch size data")
print(f"Single-item calls: {single_item_calls} ({single_item_calls/len(part2_entries)*100:.1f}%)" if part2_entries else "N/A")

if latencies:
    print(f"Avg latency: {sum(latencies)/len(latencies):.0f}ms")
    print(f"P50 latency: {percentile(latencies, 50):.0f}ms")
    print(f"P95 latency: {percentile(latencies, 95):.0f}ms")
    print(f"Max latency: {max(latencies):.0f}ms")
else:
    print("No latency data in trace")

print("\n=== FAILURE STATS ===")
print(f"Total errors: {len(errors)}")
print(f"Batch splits: {batch_splits}")
print(f"Parse failures: {parse_failures}")
print(f"Retries: {dict(retries)}")

print("\n=== HTTP STATUS CODES ===")
for code, count in sorted(status_codes.items()):
    print(f"  {code}: {count}")

# Check if trace has detailed timing info
print("\n=== TRACE SCHEMA SAMPLE ===")
if part2_entries:
    sample = part2_entries[-1]
    print(f"Keys: {list(sample.keys())}")
    
# Output for report
print("\n=== DIAGNOSTIC DATA ===")
print(json.dumps({
    'sample_size': len(part2_entries),
    'avg_batch_size': sum(batch_sizes)/len(batch_sizes) if batch_sizes else 0,
    'single_item_ratio': single_item_calls/len(part2_entries) if part2_entries else 0,
    'avg_latency_ms': sum(latencies)/len(latencies) if latencies else 0,
    'p95_latency_ms': percentile(latencies, 95) if latencies else 0,
    'max_latency_ms': max(latencies) if latencies else 0,
    'total_errors': len(errors),
    'batch_splits': batch_splits,
    'parse_failures': parse_failures,
    'status_429': status_codes.get(429, 0),
    'status_503': status_codes.get(503, 0),
}, indent=2))
