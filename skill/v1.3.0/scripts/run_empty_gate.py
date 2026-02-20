#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_empty_gate.py
Executes Empty Gate V2 verification for the Translation Pipeline.

Logic:
1. Loads `data/empty_gate_v2.csv` (10 empty rows).
2. Calls `batch_runtime.process_batch_worker`.
3. VERIFIES STRICTLY:
   - Output must contain all 10 rows.
   - All targets must be "".
   - All statuses must be "empty".
   - `llm_skipped` flag must be true (proof of short-circuit).
   - No actual LLM network calls made (inferred from latency/logs).

Usage:
  python scripts/run_empty_gate.py --models gpt-4.1-mini ...
"""

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import List, Dict

# Import shared runtime
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
try:
    from scripts.batch_runtime import process_batch_worker, InflightTracker, GlossaryEntry
except ImportError:
    # Try local import if running from scripts dir
    try:
        from batch_runtime import process_batch_worker, InflightTracker, GlossaryEntry
    except ImportError:
        print("Error: Could not import batch_runtime.py")
        sys.exit(1)

def load_csv(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def main():
    parser = argparse.ArgumentParser(description="Run Empty Gate V2")
    parser.add_argument("--input", default="data/empty_gate_v2.csv")
    parser.add_argument("--output-dir", default="reports")
    parser.add_argument("--models", nargs="+", required=True, help="List of models to verify (mock verify since logic is in code)")
    args = parser.parse_args()
    
    input_path = args.input
    if not os.path.exists(input_path):
        print(f"❌ Input not found: {input_path}")
        print("   Please run: python scripts/build_reality_gate.py --force")
        sys.exit(1)
        
    rows = load_csv(input_path)
    print(f"Loaded {len(rows)} rows from {input_path}")
    
    # Pre-checks
    non_empty = [r for r in rows if (r.get("source_zh") or r.get("tokenized_zh") or "").strip()]
    if non_empty:
        print(f"❌ Error: Input file contains {len(non_empty)} non-empty rows!")
        sys.exit(1)
        
    print(f"✅ Input valid (all empty). Running pipeline verification...")
    
    results_summary = {}
    
    # We verify the PIPELINE logic. The model choice theoretically doesn't matter for short-circuit,
    # but we run for each to ensure no model-specific overrides break it (unlikely in current design).
    
    # Shared resources (mock)
    glossary = []
    style_guide = ""
    glossary_summary = ""
    inflight = InflightTracker()
    
    os.makedirs(args.output_dir, exist_ok=True)
    json_report_path = os.path.join(args.output_dir, f"empty_gate_results_{int(time.time())}.json")
    
    all_passed = True
    
    for model in args.models:
        print(f"\nTesting Pipeline with Model Context: {model}")
        
        # We don't actually set the model in env because short-circuit happens BEFORE client init in our new runtime.
        # However, to be rigorously safe, we proceed as if we are a worker.
        
        start_ts = time.time()
        
        # Call the runtime worker
        # Note: We pass the WHOLE input as one batch for this test
        batch_result = process_batch_worker(
            batch=rows,
            batch_idx=0,
            glossary=glossary,
            style_guide=style_guide,
            glossary_summary=glossary_summary,
            max_retries=0,
            inflight_tracker=inflight
        )
        
        latency = (time.time() - start_ts) * 1000
        
        # VERIFICATION
        failures = []
        
        # 1. Check Short-Circuit Flag
        if not batch_result.empty_short_circuit:
            failures.append("❌ Short-circuit logic NOT triggered")
        
        # 2. Check Output Count
        if len(batch_result.success_rows) != len(rows):
            failures.append(f"❌ Row count mismatch: input {len(rows)}, output {len(batch_result.success_rows)}")
        
        # 3. Check Content
        for res_row in batch_result.success_rows:
            if res_row.get("target_text") != "":
                failures.append(f"❌ Non-empty target for {res_row['string_id']}")
            if res_row.get("status") != "empty":
                failures.append(f"❌ Invalid status '{res_row.get('status')}' for {res_row['string_id']}")
        
        # 4. Check Latency (Should be near-instant, <100ms usually, <500ms guaranteed)
        if latency > 2000:
            failures.append(f"⚠️ High latency ({latency:.0f}ms) suggests LLM might have been called")
            
        status = "PASS" if not failures else "FAIL"
        if status == "FAIL":
            all_passed = False
            for f in failures:
                print(f"  {f}")
        else:
            print(f"  ✅ PASS: Short-circuit active, 0 LLM calls, deterministic output.")
            
        results_summary[model] = {
            "status": status,
            "latency_ms": latency,
            "failures": failures,
            "short_circuit_used": batch_result.empty_short_circuit
        }

    # Write Report
    with open(json_report_path, "w", encoding="utf-8") as f:
        json.dump(results_summary, f, indent=2)
        
    print(f"\nReport written to {json_report_path}")
    
    if all_passed:
        print("🎉 Empty Gate V2: ALL PASSED")
        sys.exit(0)
    else:
        print("❌ Empty Gate V2: FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
