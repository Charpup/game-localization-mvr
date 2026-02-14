#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
glossary_make_review_queue.py

Convert glossary proposals YAML to a human-reviewable CSV queue.

Usage:
    python scripts/glossary_make_review_queue.py \
        --proposals data/glossary_proposals.yaml \
        --out_csv data/glossary_review_queue.csv

The output CSV has columns for user review:
    - term_zh, term_ru_suggested, scope, support, confidence, examples
    - decision: user fills approve/reject/edit
    - term_ru_final: if decision=edit, the final term
    - note: user notes
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


def load_proposals(path: str) -> Dict[str, Any]:
    """Load proposals YAML file."""
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return data


def format_examples(examples: List[str], max_count: int = 3) -> str:
    """Format examples as single-line string."""
    if not examples:
        return ""
    truncated = examples[:max_count]
    # Escape quotes and join with separator
    formatted = " | ".join(e.replace('"', "'").replace('\n', ' ')[:80] for e in truncated)
    return formatted


def proposals_to_csv_rows(data: Dict[str, Any]) -> List[Dict[str, str]]:
    """Convert proposals to CSV rows."""
    rows = []
    # Support both 'proposals' and 'entries' keys
    proposals = data.get("proposals") or data.get("entries") or []
    
    for p in proposals:
        term_zh = (p.get("term_zh") or "").strip()
        term_ru = (p.get("term_ru") or p.get("term_ru_suggested") or "").strip()
        
        if not term_zh:
            continue
        
        row = {
            "term_zh": term_zh,
            "term_ru_suggested": term_ru,
            "scope": p.get("scope", "base"),
            "support": str(p.get("support", p.get("count", 1))),
            "confidence": str(p.get("confidence", 0.5)),
            "examples": format_examples(p.get("examples", [])),
            "decision": "",  # User fills: approve/reject/edit
            "term_ru_final": "",  # User fills if decision=edit
            "note": "",  # User notes
        }
        rows.append(row)
    
    return rows


def write_csv(path: str, rows: List[Dict[str, str]]) -> None:
    """Write rows to CSV file."""
    if not rows:
        print("⚠️  No proposals to write")
        return
    
    fieldnames = [
        "term_zh", "term_ru_suggested", "scope", "support", "confidence",
        "examples", "decision", "term_ru_final", "note"
    ]
    
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    ap = argparse.ArgumentParser(
        description="Convert glossary proposals YAML to reviewable CSV queue"
    )
    ap.add_argument("--proposals", required=True, 
                    help="Input proposals YAML (e.g., data/glossary_proposals.yaml)")
    ap.add_argument("--out_csv", required=True,
                    help="Output CSV for review (e.g., data/glossary_review_queue.csv)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate without writing output")
    args = ap.parse_args()
    
    print("📋 Glossary Make Review Queue")
    print(f"   Input: {args.proposals}")
    print(f"   Output: {args.out_csv}")
    print()
    
    # Load proposals
    if not Path(args.proposals).exists():
        print(f"❌ Proposals file not found: {args.proposals}")
        return 1
    
    data = load_proposals(args.proposals)
    proposals = data.get("proposals") or data.get("entries") or []
    
    print(f"✅ Loaded {len(proposals)} proposals")
    
    # Convert to rows
    rows = proposals_to_csv_rows(data)
    print(f"✅ Generated {len(rows)} review items")
    
    if args.dry_run:
        print()
        print("=" * 60)
        print("DRY-RUN MODE - Validation Summary")
        print("=" * 60)
        print(f"[OK] Would write {len(rows)} rows to {args.out_csv}")
        print("[OK] Dry-run validation PASSED")
        print("=" * 60)
        return 0
    
    # Write CSV
    write_csv(args.out_csv, rows)
    print(f"✅ Wrote review queue to: {args.out_csv}")
    
    # Summary
    print()
    print("📊 Review Queue Summary:")
    print(f"   Total terms: {len(rows)}")
    print()
    print("📝 Next steps:")
    print("   1. Open the CSV in Excel/Sheets")
    print("   2. Fill 'decision' column: approve / reject / edit")
    print("   3. If decision=edit, fill 'term_ru_final'")
    print("   4. Run: python scripts/glossary_apply_review.py")
    
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
