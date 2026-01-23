#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_mixed_gate.py

Generates a deterministic dataset for Mixed Empty Batch Gate (MEBG).
Total rows: 100 (10 batches * 10 rows).
Batch Composition: 6 Non-Empty + 4 Empty.

Source: data/gate_sample.csv (or attempts fallback to validation_set.csv)
"""

import csv
import hashlib
import json
import os
import random
import sys
from datetime import datetime

OUTPUT_CSV = "data/empty_gate_v3_mixed.csv"
OUTPUT_META = "data/empty_gate_v3_mixed.meta.json"
TARGET_BATCHES = 10
BATCH_SIZE = 10
EMPTY_PER_BATCH = 4
NON_EMPTY_PER_BATCH = 6

def load_source_rows():
    """Load candidate rows from source CSVs."""
    candidates = []
    
    # Priority 1: gate_sample.csv
    if os.path.exists("data/gate_sample.csv"):
        print("Loading from data/gate_sample.csv...")
        with open("data/gate_sample.csv", "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("source_zh", "").strip():  # Only non-empty
                    candidates.append(row)
    
    # Priority 2: validation_set.csv fallback
    elif os.path.exists("data/validation_set.csv"):
        print("Loading from data/validation_set.csv...")
        with open("data/validation_set.csv", "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get("source_zh", "").strip():
                    candidates.append(row)
    
    else:
        print("Error: No source CSV found (gate_sample.csv or validation_set.csv).")
        sys.exit(1)
        
    print(f"Loaded {len(candidates)} non-empty candidate rows.")
    return candidates

def get_stable_hash(s):
    """Return a consistent integer hash for sorting."""
    return int(hashlib.sha256(s.encode("utf-8")).hexdigest(), 16)

def main():
    source_rows = load_source_rows()
    
    # Sort deterministically
    source_rows.sort(key=lambda r: get_stable_hash(r["string_id"]))
    
    final_rows = []
    
    non_empty_needed = TARGET_BATCHES * NON_EMPTY_PER_BATCH
    if len(source_rows) < non_empty_needed:
        # Cycle if not enough
        print(f"Warning: Not enough source rows ({len(source_rows)} < {non_empty_needed}). Recycling.")
        while len(source_rows) < non_empty_needed:
            source_rows.extend(source_rows)
            
    # Slice required non-empty
    selected_non_empty = source_rows[:non_empty_needed]
    
    print(f"Generating {TARGET_BATCHES} batches...")
    
    for b_idx in range(TARGET_BATCHES):
        batch_rows = []
        
        # 1. Add 6 Non-Empty
        start = b_idx * NON_EMPTY_PER_BATCH
        end = start + NON_EMPTY_PER_BATCH
        chunk = selected_non_empty[start:end]
        
        for r in chunk:
            r_new = r.copy()
            # Ensure proper keys
            batch_rows.append({
                "string_id": r_new["string_id"],
                "source_zh": r_new["source_zh"],
                "type": r_new.get("type", "Unknown")
            })
            
        # 2. Add 4 Empty
        for e_idx in range(EMPTY_PER_BATCH):
            batch_rows.append({
                "string_id": f"MEBG_EMPTY_B{b_idx}_E{e_idx}",
                "source_zh": "",
                "type": "Empty"
            })
            
        # 3. Shuffle Deterministically per batch
        # Seed with batch index to keep order consistent across runs
        rng = random.Random(42 + b_idx)
        rng.shuffle(batch_rows)
        
        final_rows.extend(batch_rows)
        
    # Write Output
    os.makedirs("data", exist_ok=True)
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["string_id", "source_zh", "type"])
        writer.writeheader()
        writer.writerows(final_rows)
        
    print(f"Wrote {len(final_rows)} rows to {OUTPUT_CSV}")
    
    # Write Meta
    meta = {
        "generated_at": datetime.now().isoformat(),
        "total_rows": len(final_rows),
        "batches": TARGET_BATCHES,
        "batch_size": BATCH_SIZE,
        "non_empty_ratio": f"{NON_EMPTY_PER_BATCH}/{BATCH_SIZE}",
        "source_candidates": len(source_rows)
    }
    with open(OUTPUT_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"Wrote metadata to {OUTPUT_META}")

if __name__ == "__main__":
    main()
