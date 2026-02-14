#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_reality_gate.py

Generate Reality Gate and Empty Gate test datasets from source data.
Implements deterministic sampling with bucket-based stratification.

Usage:
  python scripts/build_reality_gate.py --source data/draft.csv
  python scripts/build_reality_gate.py --source data/draft.csv --force --seed 42
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
from typing import List, Dict, Any, Tuple

# Bucket definitions for Reality Gate (50 rows total)
BUCKET_DEFS = {
    "ui_short": {"count": 10, "desc": "UI short text (len<=8)"},
    "ui_mid": {"count": 6, "desc": "UI mid text (9<=len<=30)"},
    "dialogue_long": {"count": 10, "desc": "Dialogue long text (len>=60)"},
    "system_rules": {"count": 6, "desc": "System/rules text"},
    "placeholder": {"count": 10, "desc": "Contains placeholders/variables"},
    "adversarial": {"count": 8, "desc": "Adversarial/extreme characters"},
}

EMPTY_GATE_COUNT = 10

# Patterns for detection
PLACEHOLDER_PATTERN = re.compile(r'(\{[^}]+\}|%[sd]|⟦PH_\d+⟧|\{\{[^}]+\}\}|\[.*?\]|<[^>]+>|\\n)')
ADVERSARIAL_PATTERN = re.compile(r'(["\'\\/{}[\]:@#]|https?://|[\U0001F600-\U0001F64F]|[!?]{2,}|\.{3,})')
SYSTEM_KEYWORDS = re.compile(r'(注意|禁止|必须|不可|提示|说明|警告|错误|失败)')


def calculate_sha256(path: str) -> str:
    """Calculate SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def stable_hash(s: str) -> int:
    """Stable hash for deterministic sorting."""
    return int(hashlib.md5(s.encode()).hexdigest(), 16)


def classify_row(row: Dict[str, str]) -> List[str]:
    """Classify a row into potential buckets."""
    source = row.get("source_zh", "") or row.get("tokenized_zh", "") or ""
    length = len(source)
    buckets = []
    
    # Empty check
    if not source.strip():
        return ["empty"]
    
    # Length-based buckets
    if length <= 8:
        buckets.append("ui_short")
    elif 9 <= length <= 30:
        buckets.append("ui_mid")
    if length >= 60:
        buckets.append("dialogue_long")
    
    # Content-based buckets
    if SYSTEM_KEYWORDS.search(source):
        buckets.append("system_rules")
    if PLACEHOLDER_PATTERN.search(source):
        buckets.append("placeholder")
    if len(ADVERSARIAL_PATTERN.findall(source)) >= 2:
        buckets.append("adversarial")
    
    return buckets if buckets else ["other"]


def compute_extremity_score(row: Dict[str, str]) -> Tuple[int, int]:
    """
    Compute extremity score for deterministic selection.
    Higher score = more extreme (prefer these).
    Returns (length_score, special_char_count).
    """
    source = row.get("source_zh", "") or row.get("tokenized_zh", "") or ""
    length = len(source)
    special_count = len(PLACEHOLDER_PATTERN.findall(source)) + len(ADVERSARIAL_PATTERN.findall(source))
    return (length, special_count)


def load_source_data(path: str) -> List[Dict[str, str]]:
    """Load source CSV data."""
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def sample_bucket(
    candidates: List[Dict[str, str]], 
    count: int, 
    seed: int
) -> List[Dict[str, str]]:
    """
    Deterministically sample from candidates.
    Priority: extremity score (desc), then stable hash of string_id.
    """
    # Sort by extremity (desc), then by stable hash for tie-breaking
    sorted_candidates = sorted(
        candidates,
        key=lambda r: (
            -compute_extremity_score(r)[0],  # Longer first
            -compute_extremity_score(r)[1],  # More special chars first
            stable_hash(r.get("string_id", "") + str(seed))  # Stable tie-breaker
        )
    )
    return sorted_candidates[:count]


def build_reality_gate(
    rows: List[Dict[str, str]], 
    seed: int
) -> Tuple[List[Dict[str, str]], Dict[str, int]]:
    """
    Build Reality Gate dataset (50 rows) with bucket stratification.
    Returns (selected_rows, bucket_counts).
    """
    # Classify all rows
    bucket_candidates: Dict[str, List[Dict[str, str]]] = {k: [] for k in BUCKET_DEFS}
    
    for row in rows:
        classifications = classify_row(row)
        for bucket in classifications:
            if bucket in bucket_candidates:
                bucket_candidates[bucket].append(row)
    
    # Sample from each bucket
    selected = []
    used_ids = set()
    bucket_counts = {}
    
    for bucket_name, bucket_def in BUCKET_DEFS.items():
        candidates = [r for r in bucket_candidates[bucket_name] if r.get("string_id") not in used_ids]
        sampled = sample_bucket(candidates, bucket_def["count"], seed)
        
        for row in sampled:
            selected.append(row)
            used_ids.add(row.get("string_id"))
        
        bucket_counts[bucket_name] = len(sampled)
        print(f"  {bucket_name}: {len(sampled)}/{bucket_def['count']} (available: {len(candidates)})")
    
    return selected, bucket_counts


def build_empty_gate(rows: List[Dict[str, str]], seed: int) -> List[Dict[str, str]]:
    """Build Empty Gate dataset (10 rows of empty source)."""
    empty_rows = [
        r for r in rows 
        if not (r.get("source_zh", "") or r.get("tokenized_zh", "")).strip()
    ]
    
    # Sort by stable hash for determinism
    sorted_empty = sorted(empty_rows, key=lambda r: stable_hash(r.get("string_id", "") + str(seed)))
    
    # Synthesize if not enough
    if len(sorted_empty) < EMPTY_GATE_COUNT:
        missing = EMPTY_GATE_COUNT - len(sorted_empty)
        print(f"  Note: Source has insufficient empty rows. Synthesizing {missing} rows.")
        for i in range(missing):
            sorted_empty.append({
                "string_id": f"EMPTY_SYNTH_{i}",
                "source_zh": "",
                "tokenized_zh": ""
            })
            
    return sorted_empty[:EMPTY_GATE_COUNT]


def write_csv(rows: List[Dict[str, str]], path: str, default_fields: List[str] = None) -> None:
    """Write rows to CSV file. Creates empty file with headers if no rows."""
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    
    if not rows:
        # Write empty file with default headers
        fieldnames = default_fields or ["string_id", "source_zh", "tokenized_zh"]
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
        print(f"Warning: No rows to write, created empty file: {path}")
        return
    
    fieldnames = list(rows[0].keys())
    
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_meta(
    reality_path: str,
    empty_path: str,
    bucket_counts: Dict[str, int],
    seed: int,
    source_path: str,
    meta_path: str
) -> None:
    """Write metadata JSON file."""
    meta = {
        "version": "v1",
        "seed": seed,
        "source_file": os.path.basename(source_path),
        "reality_gate": {
            "path": os.path.basename(reality_path),
            "sha256": calculate_sha256(reality_path) if os.path.exists(reality_path) else None,
            "row_count": sum(bucket_counts.values()),
            "bucket_distribution": bucket_counts,
        },
        "empty_gate": {
            "path": os.path.basename(empty_path),
            "sha256": calculate_sha256(empty_path) if os.path.exists(empty_path) else None,
            "row_count": EMPTY_GATE_COUNT,
        },
        "bucket_rules": {k: v["desc"] for k, v in BUCKET_DEFS.items()},
    }
    
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Build Reality Gate and Empty Gate datasets")
    parser.add_argument("--source", default="data/draft.csv", help="Source CSV file")
    parser.add_argument("--force", action="store_true", help="Overwrite existing v1 files")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for determinism")
    parser.add_argument("--output-dir", default="data", help="Output directory")
    args = parser.parse_args()
    
    reality_path = os.path.join(args.output_dir, "reality_gate_v1.csv")
    empty_path = os.path.join(args.output_dir, "empty_gate_v2.csv")
    meta_path = os.path.join(args.output_dir, "reality_gate_v1.meta.json")
    
    # Check existing files
    if not args.force:
        existing = [p for p in [reality_path, empty_path, meta_path] if os.path.exists(p)]
        if existing:
            print(f"Files already exist: {existing}")
            print("Use --force to overwrite.")
            sys.exit(0)
    
    # Load source data
    print(f"Loading source data from {args.source}...")
    rows = load_source_data(args.source)
    print(f"Loaded {len(rows)} rows.")
    
    # Build Reality Gate
    print(f"\nBuilding Reality Gate (seed={args.seed})...")
    reality_rows, bucket_counts = build_reality_gate(rows, args.seed)
    write_csv(reality_rows, reality_path)
    print(f"Wrote {len(reality_rows)} rows to {reality_path}")
    
    # Build Empty Gate
    print(f"\nBuilding Empty Gate V2...")
    empty_rows = build_empty_gate(rows, args.seed)
    write_csv(empty_rows, empty_path)
    print(f"Wrote {len(empty_rows)} rows to {empty_path}")
    
    # Write metadata
    write_meta(reality_path, empty_path, bucket_counts, args.seed, args.source, meta_path)
    print(f"Wrote metadata to {meta_path}")
    
    # Summary
    print(f"\n=== Summary ===")
    reality_sha = calculate_sha256(reality_path)[:16] if os.path.exists(reality_path) else "N/A"
    empty_sha = calculate_sha256(empty_path)[:16] if os.path.exists(empty_path) else "N/A"
    print(f"Reality Gate: {reality_path} (SHA256: {reality_sha}...)")
    print(f"Empty Gate:   {empty_path} (SHA256: {empty_sha}...)")
    print(f"Metadata:     {meta_path}")


if __name__ == "__main__":
    main()
