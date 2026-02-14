#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_validation_set.py

Generate N-row validation dataset from source data with stratified sampling.

Usage:
  python scripts/build_validation_set.py --source data/draft.csv --rows 300
  python scripts/build_validation_set.py --source data/draft.csv --rows 1000 --force --seed 42
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from typing import List, Dict, Any

VALID_ROW_COUNTS = [100, 300, 500, 1000]

# Stratification categories
STRATA = ["UI", "Dialogue", "System", "Placeholder", "Other"]

# Detection patterns
PLACEHOLDER_PATTERN = re.compile(r'(\{[^}]+\}|%[sd]|⟦PH_\d+⟧|\{\{[^}]+\}\})')
SYSTEM_KEYWORDS = re.compile(r'(注意|禁止|必须|不可|提示|说明|警告|错误|失败|系统)')


def calculate_sha256(path: str) -> str:
    """Calculate SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def stable_hash(s: str, seed: int) -> int:
    """Stable hash for deterministic sorting."""
    return int(hashlib.md5((s + str(seed)).encode()).hexdigest(), 16)


def classify_stratum(row: Dict[str, str]) -> str:
    """Classify row into a stratum."""
    source = row.get("source_zh", "") or row.get("tokenized_zh", "") or ""
    length = len(source)
    
    if not source.strip():
        return "Other"
    
    if PLACEHOLDER_PATTERN.search(source):
        return "Placeholder"
    if SYSTEM_KEYWORDS.search(source):
        return "System"
    if length <= 30:
        return "UI"
    if length >= 50:
        return "Dialogue"
    
    return "Other"


def load_source_data(path: str) -> List[Dict[str, str]]:
    """Load source CSV data."""
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def stratified_sample(
    rows: List[Dict[str, str]], 
    total_count: int, 
    seed: int
) -> tuple[List[Dict[str, str]], Dict[str, int]]:
    """
    Perform stratified sampling across strata.
    Returns (selected_rows, stratum_counts).
    """
    # Classify all rows
    strata_rows: Dict[str, List[Dict[str, str]]] = {s: [] for s in STRATA}
    for row in rows:
        stratum = classify_stratum(row)
        strata_rows[stratum].append(row)
    
    # Calculate proportional counts
    total_classified = sum(len(v) for v in strata_rows.values())
    if total_classified == 0:
        return [], {}
    
    stratum_targets = {}
    remaining = total_count
    
    for i, stratum in enumerate(STRATA):
        if i == len(STRATA) - 1:
            # Last stratum gets remainder
            stratum_targets[stratum] = remaining
        else:
            proportion = len(strata_rows[stratum]) / total_classified
            count = min(int(total_count * proportion), len(strata_rows[stratum]))
            stratum_targets[stratum] = count
            remaining -= count
    
    # Sample from each stratum
    selected = []
    actual_counts = {}
    
    for stratum in STRATA:
        candidates = strata_rows[stratum]
        target = stratum_targets[stratum]
        
        # Sort deterministically
        sorted_candidates = sorted(
            candidates,
            key=lambda r: stable_hash(r.get("string_id", ""), seed)
        )
        
        sampled = sorted_candidates[:target]
        selected.extend(sampled)
        actual_counts[stratum] = len(sampled)
        print(f"  {stratum}: {len(sampled)}/{target} (available: {len(candidates)})")
    
    return selected, actual_counts


def write_csv(rows: List[Dict[str, str]], path: str) -> None:
    """Write rows to CSV file."""
    if not rows:
        print(f"Warning: No rows to write to {path}")
        return
    
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = list(rows[0].keys())
    
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_meta(
    output_path: str,
    stratum_counts: Dict[str, int],
    seed: int,
    source_path: str,
    row_count: int,
    meta_path: str
) -> None:
    """Write metadata JSON file."""
    meta = {
        "version": "v1",
        "seed": seed,
        "source_file": os.path.basename(source_path),
        "target_rows": row_count,
        "actual_rows": sum(stratum_counts.values()),
        "path": os.path.basename(output_path),
        "sha256": calculate_sha256(output_path) if os.path.exists(output_path) else None,
        "stratum_distribution": stratum_counts,
    }
    
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Build validation dataset with stratified sampling")
    parser.add_argument("--source", default="data/draft.csv", help="Source CSV file")
    parser.add_argument("--rows", type=int, default=300, choices=VALID_ROW_COUNTS, 
                        help="Number of rows to sample")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for determinism")
    parser.add_argument("--output-dir", default="data", help="Output directory")
    args = parser.parse_args()
    
    output_path = os.path.join(args.output_dir, f"validation_{args.rows}_v1.csv")
    meta_path = os.path.join(args.output_dir, f"validation_{args.rows}_v1.meta.json")
    
    # Check existing files
    if not args.force:
        existing = [p for p in [output_path, meta_path] if os.path.exists(p)]
        if existing:
            print(f"Files already exist: {existing}")
            print("Use --force to overwrite.")
            sys.exit(0)
    
    # Load source data
    print(f"Loading source data from {args.source}...")
    rows = load_source_data(args.source)
    print(f"Loaded {len(rows)} rows.")
    
    # Stratified sampling
    print(f"\nBuilding validation set ({args.rows} rows, seed={args.seed})...")
    selected, stratum_counts = stratified_sample(rows, args.rows, args.seed)
    
    # Write output
    write_csv(selected, output_path)
    print(f"\nWrote {len(selected)} rows to {output_path}")
    
    # Write metadata
    write_meta(output_path, stratum_counts, args.seed, args.source, args.rows, meta_path)
    print(f"Wrote metadata to {meta_path}")
    
    # Summary
    print(f"\n=== Summary ===")
    print(f"Validation Set: {output_path}")
    print(f"SHA256: {calculate_sha256(output_path)[:16]}...")
    print(f"Rows: {len(selected)}")


if __name__ == "__main__":
    main()
