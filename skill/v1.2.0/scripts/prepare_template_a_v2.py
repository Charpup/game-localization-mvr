#!/usr/bin/env python3
"""
Step 1: Generate Template A_v2 for Phase 2 long text testing.
Uses source_zh field length to identify long texts (>300 chars).
"""
import pandas as pd
import hashlib
import json
import os
from datetime import datetime

INPUT_FILE = "data/normalized_pool_v1.csv"
OUTPUT_CSV = "data/destructive_v1_template_A_v2.csv"
OUTPUT_META = "data/destructive_v1_template_A_v2.meta.json"

TOTAL_ROWS = 30
LONG_TEXT_RATIO = 0.8  # 80% long text
LONG_TEXT_COUNT = int(TOTAL_ROWS * LONG_TEXT_RATIO)  # 24
OTHER_COUNT = TOTAL_ROWS - LONG_TEXT_COUNT  # 6

LONG_TEXT_THRESHOLD = 300  # characters
FALLBACK_THRESHOLD = 200  # if not enough long texts

def main():
    print(f"Loading {INPUT_FILE}...")
    pool = pd.read_csv(INPUT_FILE, encoding="utf-8")
    print(f"Loaded {len(pool)} rows")
    
    # Add length column for filtering
    pool["source_len"] = pool["source_zh"].astype(str).str.len()
    
    # Filter long texts (>300 chars)
    long_texts = pool[pool["source_len"] > LONG_TEXT_THRESHOLD]
    print(f"Found {len(long_texts)} rows with length > {LONG_TEXT_THRESHOLD}")
    
    # Fallback if not enough long texts
    if len(long_texts) < LONG_TEXT_COUNT:
        print(f"Not enough long texts, falling back to threshold {FALLBACK_THRESHOLD}")
        long_texts = pool[pool["source_len"] > FALLBACK_THRESHOLD]
        print(f"Found {len(long_texts)} rows with length > {FALLBACK_THRESHOLD}")
    
    # Sample long texts
    if len(long_texts) >= LONG_TEXT_COUNT:
        long_sample = long_texts.sample(n=LONG_TEXT_COUNT, random_state=42)
    else:
        print(f"WARNING: Only {len(long_texts)} long texts available, using all")
        long_sample = long_texts
    
    # Sample other texts (shorter ones)
    short_texts = pool[~pool.index.isin(long_sample.index)]
    if len(short_texts) >= OTHER_COUNT:
        other_sample = short_texts.sample(n=OTHER_COUNT, random_state=42)
    else:
        other_sample = short_texts.sample(n=min(len(short_texts), OTHER_COUNT), random_state=42)
    
    # Combine and shuffle
    template = pd.concat([long_sample, other_sample])
    template = template.sample(frac=1, random_state=42)  # Shuffle
    
    # Keep only string_id and source_zh columns
    template = template[["string_id", "source_zh"]].reset_index(drop=True)
    
    print(f"\nGenerated template with {len(template)} rows")
    print(f"- Long texts (>{LONG_TEXT_THRESHOLD} chars): {len(long_sample)}")
    print(f"- Other texts: {len(other_sample)}")
    
    # Show length distribution
    lengths = template["source_zh"].str.len()
    print(f"\nLength distribution:")
    print(f"  Min: {lengths.min()}")
    print(f"  Max: {lengths.max()}")
    print(f"  Mean: {lengths.mean():.1f}")
    print(f"  Median: {lengths.median():.1f}")
    
    # Save CSV
    template.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"\nSaved to {OUTPUT_CSV}")
    
    # Generate SHA256
    with open(OUTPUT_CSV, "rb") as f:
        sha256 = hashlib.sha256(f.read()).hexdigest()
    
    # Save metadata
    meta = {
        "source_dataset_id": "normalized_pool_v1",
        "sha256": sha256,
        "template_type": "A_v2",
        "total_rows": len(template),
        "composition": {
            "long_text": len(long_sample),
            "long_text_threshold": LONG_TEXT_THRESHOLD,
            "others": len(other_sample)
        },
        "created_at": datetime.now().isoformat()
    }
    
    with open(OUTPUT_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"Saved metadata to {OUTPUT_META}")

if __name__ == "__main__":
    main()
