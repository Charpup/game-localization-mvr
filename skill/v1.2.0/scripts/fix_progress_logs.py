#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
fix_progress_logs.py

Goal:
  Backfill missing `usage` and `request_id` in progress logs (repair_hard, repair_soft)
  by correlating with data/llm_trace.jsonl based on timestamps and step names.

Usage:
  python scripts/fix_progress_logs.py
"""

import json
import os
import shutil
from datetime import datetime
from typing import List, Dict, Any

TRACE_PATH = "data/llm_trace.jsonl"
PROGRESS_DIR = "reports"
TARGET_STEPS = ["repair_hard", "repair_soft"]

def load_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        return []
    data = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    data.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return data

def parse_iso(ts: str) -> float:
    # Handle ISO formats like '2026-01-27T17:33:03.191697'
    # Python 3.7+ fromisoformat handles most, but let's be safe
    try:
        return datetime.fromisoformat(ts).timestamp()
    except ValueError:
        return 0.0

def main():
    print("🚀 Starting log fix process...")

    # 1. Load Traces
    print(f"📂 Loading {TRACE_PATH}...")
    traces = load_jsonl(TRACE_PATH)
    # Filter for relevant success calls with usage
    llm_calls = [
        t for t in traces 
        if t.get("type") == "llm_call" 
        and "usage" in t 
        and t.get("step") in TARGET_STEPS
    ]
    
    # Sort by timestamp for easier matching
    llm_calls.sort(key=lambda x: parse_iso(x.get("timestamp", "")))
    
    print(f"   Found {len(llm_calls)} relevant LLM calls in trace.")

    # 2. Process each target log
    for step in TARGET_STEPS:
        log_filename = f"{step}_progress.jsonl"
        log_path = os.path.join(PROGRESS_DIR, log_filename)
        
        if not os.path.exists(log_path):
            print(f"⚠️  {log_filename} not found, skipping.")
            continue
            
        print(f"🔧 Processing {log_filename}...")
        
        # Backup
        shutil.copy2(log_path, log_path + ".bak")
        
        progress_events = load_jsonl(log_path)
        fixed_events = []
        match_count = 0
        
        # Filter traces for this step
        step_traces = [t for t in llm_calls if t.get("step") == step]
        
        for event in progress_events:
            # Only fix batch_complete events that lack usage
            if (event.get("event") == "batch_complete" and 
                "usage" not in event and 
                event.get("status") != "error"):
                
                # Logic: Find trace that finished just before this event
                # Event timestamp is when batch completed (including parsing)
                # LLM trace timestamp is when HTTP request completed
                # So trace_ts <= event_ts
                
                evt_ts = parse_iso(event.get("timestamp", ""))
                latency_sec = (event.get("latency_ms", 0) / 1000.0) + 5.0 # buffer
                
                # Candidates: traces within [evt_ts - latency - buffer, evt_ts]
                candidates = []
                for t in step_traces:
                    trace_ts = parse_iso(t.get("timestamp", ""))
                    if trace_ts <= evt_ts and trace_ts >= (evt_ts - latency_sec):
                        candidates.append((t, trace_ts))
                
                # Sort by closeness to event time
                candidates.sort(key=lambda x: x[1], reverse=True)
                
                if candidates:
                    best_match = candidates[0][0]
                    # Inject metrics
                    event["usage"] = best_match["usage"]
                    event["request_id"] = best_match.get("request_id")
                    
                    # Also update metadata if present
                    if "metadata" in event:
                        event["metadata"]["usage"] = best_match["usage"]
                        event["metadata"]["request_id"] = best_match.get("request_id")
                    else:
                        event["metadata"] = {
                            "usage": best_match["usage"],
                            "request_id": best_match.get("request_id")
                        }
                    
                    match_count += 1
                    # Remove used trace to avoid double matching? 
                    # Actually keeping it is safer if multiple batches (unlikely) or retries happened
                    # But for now let's assume 1-to-1 mapping mostly
            
            fixed_events.append(event)
            
        print(f"   Fixed {match_count} events in {log_filename}")
        
        # Write back
        with open(log_path, 'w', encoding='utf-8') as f:
            for ev in fixed_events:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")

    print("✅ Done! Backups created with .bak extension.")

if __name__ == "__main__":
    main()
