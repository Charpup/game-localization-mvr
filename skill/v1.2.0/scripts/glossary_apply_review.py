#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
glossary_apply_review.py

Apply user review decisions from CSV to glossary files.

Usage:
    python scripts/glossary_apply_review.py \
        --review_csv data/glossary_review_queue.csv \
        --approved glossary/approved.yaml \
        --rejected glossary/rejected.yaml

Reads the review CSV and:
    - decision=approve: append to approved.yaml
    - decision=edit: append with term_ru_final to approved.yaml
    - decision=reject: append to rejected.yaml
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

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


def read_csv_rows(path: str) -> List[Dict[str, str]]:
    """Read CSV file and return list of row dicts."""
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def load_yaml_entries(path: str) -> List[Dict[str, Any]]:
    """Load existing entries from YAML file."""
    if not Path(path).exists():
        return []
    
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    
    return data.get("entries", [])


def save_yaml_entries(path: str, entries: List[Dict[str, Any]], 
                      file_type: str = "approved") -> None:
    """Save entries to YAML file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "meta": {
            "type": file_type,
            "updated_at": datetime.now().isoformat(),
            "entry_count": len(entries)
        },
        "entries": entries
    }
    
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def apply_review(review_rows: List[Dict[str, str]], 
                 existing_approved: List[Dict[str, Any]],
                 existing_rejected: List[Dict[str, Any]]) -> tuple:
    """
    Apply review decisions.
    
    Returns: (new_approved, new_rejected, stats)
    """
    approved = list(existing_approved)
    rejected = list(existing_rejected)
    
    # Build existing sets to avoid duplicates
    approved_set = {(e.get("term_zh", ""), e.get("term_ru", "")) for e in approved}
    rejected_set = {(e.get("term_zh", ""), e.get("term_ru", "")) for e in rejected}
    
    stats = {
        "total": 0,
        "approved": 0,
        "edited": 0,
        "rejected": 0,
        "skipped": 0,
        "duplicate": 0
    }
    
    for row in review_rows:
        stats["total"] += 1
        
        term_zh = (row.get("term_zh") or "").strip()
        term_ru_suggested = (row.get("term_ru_suggested") or "").strip()
        decision = (row.get("decision") or "").strip().lower()
        term_ru_final = (row.get("term_ru_final") or "").strip()
        scope = (row.get("scope") or "base").strip()
        note = (row.get("note") or "").strip()
        
        if not term_zh:
            stats["skipped"] += 1
            continue
        
        if not decision or decision not in ("approve", "edit", "reject"):
            stats["skipped"] += 1
            continue
        
        if decision == "approve":
            term_ru = term_ru_suggested
            key = (term_zh, term_ru)
            
            if key in approved_set:
                stats["duplicate"] += 1
                continue
            
            entry = {
                "term_zh": term_zh,
                "term_ru": term_ru,
                "scope": scope,
                "status": "approved",
                "approved_at": datetime.now().isoformat(),
                "note": note if note else None
            }
            approved.append(entry)
            approved_set.add(key)
            stats["approved"] += 1
            
        elif decision == "edit":
            if not term_ru_final:
                # No final term provided, skip
                stats["skipped"] += 1
                continue
            
            term_ru = term_ru_final
            key = (term_zh, term_ru)
            
            if key in approved_set:
                stats["duplicate"] += 1
                continue
            
            entry = {
                "term_zh": term_zh,
                "term_ru": term_ru,
                "scope": scope,
                "status": "approved",
                "approved_at": datetime.now().isoformat(),
                "original_suggestion": term_ru_suggested,
                "note": note if note else "User edited"
            }
            approved.append(entry)
            approved_set.add(key)
            stats["edited"] += 1
            
        elif decision == "reject":
            key = (term_zh, term_ru_suggested)
            
            if key in rejected_set:
                stats["duplicate"] += 1
                continue
            
            entry = {
                "term_zh": term_zh,
                "term_ru": term_ru_suggested,
                "scope": scope,
                "status": "rejected",
                "rejected_at": datetime.now().isoformat(),
                "reason": note if note else "User rejected"
            }
            rejected.append(entry)
            rejected_set.add(key)
            stats["rejected"] += 1
    
    return approved, rejected, stats


def main():
    ap = argparse.ArgumentParser(
        description="Apply user review decisions from CSV to glossary files"
    )
    ap.add_argument("--review_csv", required=True,
                    help="Input review CSV (e.g., data/glossary_review_queue.csv)")
    ap.add_argument("--approved", default="glossary/approved.yaml",
                    help="Output approved YAML (default: glossary/approved.yaml)")
    ap.add_argument("--rejected", default="glossary/rejected.yaml",
                    help="Output rejected YAML (default: glossary/rejected.yaml)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate without writing output")
    args = ap.parse_args()
    
    print("📝 Glossary Apply Review")
    print(f"   Review CSV: {args.review_csv}")
    print(f"   Approved YAML: {args.approved}")
    print(f"   Rejected YAML: {args.rejected}")
    print()
    
    # Load review CSV
    if not Path(args.review_csv).exists():
        print(f"❌ Review CSV not found: {args.review_csv}")
        return 1
    
    review_rows = read_csv_rows(args.review_csv)
    print(f"✅ Loaded {len(review_rows)} review items")
    
    # Load existing entries
    existing_approved = load_yaml_entries(args.approved)
    existing_rejected = load_yaml_entries(args.rejected)
    print(f"✅ Existing approved: {len(existing_approved)} entries")
    print(f"✅ Existing rejected: {len(existing_rejected)} entries")
    
    # Apply review
    new_approved, new_rejected, stats = apply_review(
        review_rows, existing_approved, existing_rejected
    )
    
    # Summary
    print()
    print("📊 Review Summary:")
    print(f"   Total reviewed: {stats['total']}")
    print(f"   ✅ Approved: {stats['approved']}")
    print(f"   ✏️  Edited: {stats['edited']}")
    print(f"   ❌ Rejected: {stats['rejected']}")
    print(f"   ⏭️  Skipped: {stats['skipped']}")
    print(f"   🔄 Duplicate: {stats['duplicate']}")
    
    if args.dry_run:
        print()
        print("=" * 60)
        print("DRY-RUN MODE - Validation Summary")
        print("=" * 60)
        print(f"[OK] Would write {len(new_approved)} entries to {args.approved}")
        print(f"[OK] Would write {len(new_rejected)} entries to {args.rejected}")
        print("[OK] Dry-run validation PASSED")
        print("=" * 60)
        return 0
    
    # Save files
    save_yaml_entries(args.approved, new_approved, "approved")
    save_yaml_entries(args.rejected, new_rejected, "rejected")
    
    print()
    print(f"✅ Saved {len(new_approved)} approved entries to: {args.approved}")
    print(f"✅ Saved {len(new_rejected)} rejected entries to: {args.rejected}")
    
    print()
    print("📝 Next steps:")
    print("   Run: python scripts/glossary_compile.py --approved glossary/approved.yaml")
    
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
