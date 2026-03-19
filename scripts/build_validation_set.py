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
REQUIRED_COLUMNS = ["string_id"]
SOURCE_TEXT_COLUMNS = ["source_zh", "tokenized_zh"]

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
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames or []
    validate_source_columns(fieldnames, path)
    return rows


def load_source_columns(path: str) -> List[str]:
    """Load CSV header columns without mutating row data."""
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
    validate_source_columns(fieldnames, path)
    return fieldnames


def validate_source_columns(fieldnames: List[str], path: str) -> None:
    """Validate the source CSV contract before sampling."""
    missing = [column for column in REQUIRED_COLUMNS if column not in fieldnames]
    if missing:
        raise ValueError(f"Missing required columns in {path}: {', '.join(missing)}")
    if not any(column in fieldnames for column in SOURCE_TEXT_COLUMNS):
        supported = ", ".join(SOURCE_TEXT_COLUMNS)
        raise ValueError(f"Missing source text column in {path}; expected one of: {supported}")


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
    if total_count > total_classified:
        raise ValueError(
            f"Requested {total_count} validation rows but only {total_classified} source rows are available."
        )

    raw_targets = {
        stratum: (total_count * len(strata_rows[stratum]) / total_classified)
        for stratum in STRATA
    }
    stratum_targets = {stratum: int(raw_targets[stratum]) for stratum in STRATA}
    assigned = sum(stratum_targets.values())

    remainder_order = sorted(
        STRATA,
        key=lambda stratum: (
            raw_targets[stratum] - stratum_targets[stratum],
            len(strata_rows[stratum]),
            -STRATA.index(stratum),
        ),
        reverse=True,
    )

    while assigned < total_count:
        progressed = False
        for stratum in remainder_order:
            if stratum_targets[stratum] >= len(strata_rows[stratum]):
                continue
            stratum_targets[stratum] += 1
            assigned += 1
            progressed = True
            if assigned == total_count:
                break
        if not progressed:
            break

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


def write_csv(rows: List[Dict[str, str]], path: str, fieldnames: List[str] | None = None) -> None:
    """Write rows to CSV file."""
    if not rows:
        print(f"Warning: No rows to write to {path}")
        return

    os.makedirs(os.path.dirname(path), exist_ok=True)
    csv_fieldnames = fieldnames or list(rows[0].keys())

    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_meta(
    output_path: str,
    stratum_counts: Dict[str, int],
    seed: int,
    source_path: str,
    row_count: int,
    meta_path: str,
    input_columns: List[str],
    output_columns: List[str],
) -> None:
    """Write metadata JSON file."""
    meta = {
        "version": "v1",
        "seed": seed,
        "source_file": os.path.basename(source_path),
        "source_sha256": calculate_sha256(source_path),
        "target_rows": row_count,
        "actual_rows": sum(stratum_counts.values()),
        "path": os.path.basename(output_path),
        "sha256": calculate_sha256(output_path) if os.path.exists(output_path) else None,
        "input_columns": input_columns,
        "output_columns": output_columns,
        "required_columns": REQUIRED_COLUMNS,
        "source_text_columns": SOURCE_TEXT_COLUMNS,
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
    input_columns = load_source_columns(args.source)
    print(f"Loaded {len(rows)} rows.")

    # Stratified sampling
    print(f"\nBuilding validation set ({args.rows} rows, seed={args.seed})...")
    try:
        selected, stratum_counts = stratified_sample(rows, args.rows, args.seed)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        sys.exit(1)

    if len(selected) != args.rows:
        print(
            f"ERROR: Sampling contract violation for {args.source}: "
            f"expected {args.rows} rows, produced {len(selected)} rows."
        )
        sys.exit(1)

    # Write output
    write_csv(selected, output_path, fieldnames=input_columns)
    print(f"\nWrote {len(selected)} rows to {output_path}")

    # Write metadata
    write_meta(
        output_path,
        stratum_counts,
        args.seed,
        args.source,
        args.rows,
        meta_path,
        input_columns=input_columns,
        output_columns=input_columns,
    )
    print(f"Wrote metadata to {meta_path}")
    
    # Summary
    print(f"\n=== Summary ===")
    print(f"Validation Set: {output_path}")
    print(f"SHA256: {calculate_sha256(output_path)[:16]}...")
    print(f"Rows: {len(selected)}")


if __name__ == "__main__":
    main()
