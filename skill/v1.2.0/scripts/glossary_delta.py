#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
glossary_delta.py

Compute glossary delta between old and new compiled.yaml versions.
Output impact_set of string_ids that need refreshing.

Usage:
    python scripts/glossary_delta.py \
        --old glossary/compiled.yaml.bak \
        --new glossary/compiled.yaml \
        --source_csv data/translated.csv \
        --out_impact data/glossary_impact.json

Output:
    {
        "delta_terms": {
            "added": [{"term_zh": "...", "term_ru": "..."}],
            "changed": [{"term_zh": "...", "old_ru": "...", "new_ru": "..."}],
            "removed": [{"term_zh": "...", "term_ru": "..."}]
        },
        "impact_set": ["string_id_1", "string_id_2", ...],
        "glossary_hash_old": "sha256:...",
        "glossary_hash_new": "sha256:..."
    }
"""

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import yaml
except ImportError:
    print("❌ Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


def load_compiled(path: str) -> Tuple[Dict[str, str], str]:
    """
    Load compiled.yaml and return (term_map, hash).
    
    term_map: {term_zh: term_ru}
    """
    if not Path(path).exists():
        return {}, ""
    
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    
    entries = data.get("entries", [])
    term_map = {}
    for e in entries:
        term_zh = (e.get("term_zh") or "").strip()
        term_ru = (e.get("term_ru") or "").strip()
        if term_zh:
            term_map[term_zh] = term_ru
    
    # Load hash from lock file
    lock_path = Path(path).with_suffix('.lock.json')
    hash_val = ""
    if lock_path.exists():
        with open(lock_path, 'r', encoding='utf-8') as f:
            lock = json.load(f)
            hash_val = lock.get("hash", "")
    
    return term_map, hash_val


def compute_delta(old_map: Dict[str, str], new_map: Dict[str, str]) -> Dict[str, List]:
    """Compute added, changed, removed terms."""
    old_keys = set(old_map.keys())
    new_keys = set(new_map.keys())
    
    added = []
    changed = []
    removed = []
    
    # Added terms
    for term_zh in (new_keys - old_keys):
        added.append({
            "term_zh": term_zh,
            "term_ru": new_map[term_zh]
        })
    
    # Removed terms
    for term_zh in (old_keys - new_keys):
        removed.append({
            "term_zh": term_zh,
            "term_ru": old_map[term_zh]
        })
    
    # Changed terms
    for term_zh in (old_keys & new_keys):
        if old_map[term_zh] != new_map[term_zh]:
            changed.append({
                "term_zh": term_zh,
                "old_ru": old_map[term_zh],
                "new_ru": new_map[term_zh]
            })
    
    return {
        "added": added,
        "changed": changed,
        "removed": removed
    }


def read_csv_rows(path: str) -> List[Dict[str, str]]:
    """Read CSV file as list of dicts."""
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def compute_impact_set(delta: Dict[str, List], rows: List[Dict[str, str]]) -> List[str]:
    """
    Scan source_zh to find rows impacted by glossary changes.
    
    A row is impacted if its source_zh contains any added/changed term.
    """
    # Build set of terms that need checking
    affected_terms = set()
    for item in delta.get("added", []):
        affected_terms.add(item["term_zh"])
    for item in delta.get("changed", []):
        affected_terms.add(item["term_zh"])
    
    if not affected_terms:
        return []
    
    impact_set = []
    for row in rows:
        string_id = row.get("string_id", "")
        source_zh = row.get("source_zh") or row.get("tokenized_zh") or ""
        
        # Check if any affected term appears in source
        for term in affected_terms:
            if term in source_zh:
                impact_set.append(string_id)
                break
    
    return impact_set


def main():
    ap = argparse.ArgumentParser(
        description="Compute glossary delta and impact set for Round2 refresh"
    )
    ap.add_argument("--old", required=True, help="Old compiled.yaml")
    ap.add_argument("--new", required=True, help="New compiled.yaml")
    ap.add_argument("--source_csv", required=True, help="Source CSV with source_zh column")
    ap.add_argument("--out_impact", default="data/glossary_impact.json",
                    help="Output impact JSON")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate without writing output")
    args = ap.parse_args()
    
    print("🔍 Glossary Delta Analysis")
    print(f"   Old: {args.old}")
    print(f"   New: {args.new}")
    print(f"   Source CSV: {args.source_csv}")
    print()
    
    # Load glossaries
    old_map, old_hash = load_compiled(args.old)
    new_map, new_hash = load_compiled(args.new)
    
    print(f"✅ Old glossary: {len(old_map)} terms")
    print(f"✅ New glossary: {len(new_map)} terms")
    
    if old_hash:
        print(f"   Old hash: {old_hash}")
    if new_hash:
        print(f"   New hash: {new_hash}")
    
    # Compute delta
    delta = compute_delta(old_map, new_map)
    
    print()
    print(f"📊 Delta Summary:")
    print(f"   Added: {len(delta['added'])} terms")
    print(f"   Changed: {len(delta['changed'])} terms")
    print(f"   Removed: {len(delta['removed'])} terms")
    
    if not delta['added'] and not delta['changed']:
        print()
        print("ℹ️  No terms added or changed. No refresh needed.")
        
        if not args.dry_run:
            output = {
                "delta_terms": delta,
                "impact_set": [],
                "glossary_hash_old": old_hash,
                "glossary_hash_new": new_hash,
                "refresh_needed": False
            }
            Path(args.out_impact).parent.mkdir(parents=True, exist_ok=True)
            with open(args.out_impact, 'w', encoding='utf-8') as f:
                json.dump(output, f, ensure_ascii=False, indent=2)
        return 0
    
    # Load source CSV and compute impact
    if not Path(args.source_csv).exists():
        print(f"❌ Source CSV not found: {args.source_csv}")
        return 1
    
    rows = read_csv_rows(args.source_csv)
    print(f"✅ Loaded {len(rows)} source rows")
    
    impact_set = compute_impact_set(delta, rows)
    print(f"🎯 Impact set: {len(impact_set)} rows need refresh")
    
    # Show sample impacts
    if impact_set[:5]:
        print()
        print("   Sample impacted IDs:")
        for sid in impact_set[:5]:
            print(f"     - {sid}")
        if len(impact_set) > 5:
            print(f"     ... and {len(impact_set) - 5} more")
    
    if args.dry_run:
        print()
        print("=" * 60)
        print("DRY-RUN MODE - Validation Summary")
        print("=" * 60)
        print(f"[OK] Would write impact data to {args.out_impact}")
        print(f"[OK] {len(impact_set)} rows would be queued for refresh")
        print("=" * 60)
        return 0
    
    # Write output
    output = {
        "delta_terms": delta,
        "impact_set": impact_set,
        "glossary_hash_old": old_hash,
        "glossary_hash_new": new_hash,
        "refresh_needed": len(impact_set) > 0
    }
    
    Path(args.out_impact).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out_impact, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print()
    print(f"✅ Saved impact data to: {args.out_impact}")
    print()
    print("📝 Next steps:")
    print("   python scripts/translate_refresh.py --impact data/glossary_impact.json")
    
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
