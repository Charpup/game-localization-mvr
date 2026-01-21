#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_mixed_gate.py

Generate Empty Gate V3 Mixed Batch dataset (100 rows).
- 10 batches.
- Each batch: 6 non-empty + 4 empty.
- Deterministic selection via SHA256 sort.
- Output: v3_mixed.csv + v3_mixed.meta.json

Usage:
  python scripts/build_mixed_gate.py --source data/draft.csv --force --seed 123
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from typing import List, Dict, Any

# V3 Spec
BATCH_COUNT = 10
ROWS_PER_BATCH = 10
NON_EMPTY_PER_BATCH = 6
EMPTY_PER_BATCH = 4
TOTAL_ROWS = BATCH_COUNT * ROWS_PER_BATCH # 100

# Bucket defs (Simplified for mixed gate)
BUCKETS = ["placeholder", "ui_short", "dialogue_long", "system_rules", "ui_mid", "adversarial"]

PLACEHOLDER_PATTERN = re.compile(r'(\{[^}]+\}|%[sd]|⟦PH_\d+⟧|\{\{[^}]+\}\}|\[.*?\]|<[^>]+>|\\n)')

def calculate_sha256(path: str) -> str:
    sha256 = hashlib.sha256()
    if os.path.exists(path):
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
    return sha256.hexdigest()

def sha256_hash(s: str) -> str:
    """Stable hash for deterministic sorting (SHA256)."""
    return hashlib.sha256(s.encode()).hexdigest()

def load_source_data(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def classify_row(row: Dict[str, str]) -> str:
    src = row.get("source_zh", "") or row.get("tokenized_zh", "") or ""
    if not src.strip():
        return "empty"
    if PLACEHOLDER_PATTERN.search(src):
        return "placeholder"
    # Basic fallbacks (simplified classification for gate selection)
    if len(src) <= 10: return "ui_short"
    if len(src) >= 50: return "dialogue_long"
    return "ui_mid"

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--output-dir", default="data")
    args = parser.parse_args()
    
    out_csv = os.path.join(args.output_dir, "empty_gate_v3_mixed.csv")
    out_meta = os.path.join(args.output_dir, "empty_gate_v3_mixed.meta.json")
    
    if os.path.exists(out_csv) and not args.force:
        print(f"File exists: {out_csv}. Use --force to regenerate.")
        sys.exit(0)

    print(f"Loading source: {args.source}")
    all_rows = load_source_data(args.source)
    
    # Bucketize
    buckets: Dict[str, List] = {k: [] for k in BUCKETS + ["empty", "other"]}
    for r in all_rows:
        cat = classify_row(r)
        if cat in buckets:
            buckets[cat].append(r)
        else:
            buckets["other"].append(r)

    # Need 40 empty, 60 non-empty
    # Sort buckets deterministically
    seed_str = str(args.seed)
    
    # Prepare Candidates
    # Empty
    empty_candidates = sorted(buckets["empty"], key=lambda r: sha256_hash(r.get("string_id","") + seed_str))
    
    # Synthesize empties if needed
    if len(empty_candidates) < (BATCH_COUNT * EMPTY_PER_BATCH):
        needed = (BATCH_COUNT * EMPTY_PER_BATCH) - len(empty_candidates)
        for i in range(needed):
            empty_candidates.append({
                "string_id": f"SYNTH_EMPTY_{i}", 
                "source_zh": "", 
                "tokenized_zh": "",
                "is_empty_source": "true" # Explicit marker
            })
            
    # Non-Empty (Prioritize Placeholders ensure 1 per batch)
    placeholder_candidates = sorted(buckets["placeholder"], key=lambda r: sha256_hash(r.get("string_id","") + seed_str))
    other_candidates = []
    for k in ["ui_short", "dialogue_long", "system_rules", "ui_mid", "adversarial", "other"]:
        other_candidates.extend(buckets[k])
    other_candidates = sorted(other_candidates, key=lambda r: sha256_hash(r.get("string_id","") + seed_str))
    
    final_rows = []
    used_ids = set()
    
    print(f"\nBuilding {BATCH_COUNT} batches (Seed {args.seed})...")
    
    p_idx = 0
    o_idx = 0
    e_idx = 0
    
    for b in range(BATCH_COUNT):
        batch_rows = []
        
        # 1. Add 4 Empty
        for _ in range(EMPTY_PER_BATCH):
            row = empty_candidates[e_idx % len(empty_candidates)]
            e_idx += 1
            # Ensure is_empty_source is set
            row["is_empty_source"] = "true"
            batch_rows.append(row)
            
        # 2. Add 1 Placeholder (Non-Empty)
        if placeholder_candidates:
            row = placeholder_candidates[p_idx % len(placeholder_candidates)]
            p_idx += 1
            row["is_empty_source"] = "false"
            batch_rows.append(row)
            
        # 3. Add 5 Other Non-Empty
        needed_ne = NON_EMPTY_PER_BATCH - 1
        for _ in range(needed_ne):
            if other_candidates:
                 row = other_candidates[o_idx % len(other_candidates)]
                 o_idx += 1
                 row["is_empty_source"] = "false"
                 batch_rows.append(row)
        
        # Add to final
        final_rows.extend(batch_rows)

    # Write CSV
    print(f"Writing {len(final_rows)} rows to {out_csv}...")
    fieldnames = ["string_id", "source_zh", "tokenized_zh", "is_empty_source"]
    # Preserve other fields if present in source, but ensure these 4 exist
    if final_rows:
        keys = list(final_rows[0].keys())
        for f in fieldnames: 
            if f not in keys: keys.append(f)
        fieldnames = keys

    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(final_rows)
        
    # Write Meta
    meta = {
        "source_dataset_id": os.path.basename(args.source),
        "source_sha256": calculate_sha256(args.source),
        "rules_version": "v3",
        "sha256": calculate_sha256(out_csv),
        "row_count": len(final_rows),
        "batches": BATCH_COUNT,
        "seed": args.seed
    }
    with open(out_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
        
    print(f"Meta written to {out_meta}")
    print(f"SHA256: {meta['sha256']}")

if __name__ == "__main__":
    main()
