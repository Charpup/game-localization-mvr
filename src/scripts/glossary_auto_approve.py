#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
glossary_auto_approve.py

Auto-approve translations from glossary_translate output based on confidence.
"""
import argparse
import sys
from datetime import datetime
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required")
    sys.exit(1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Translated YAML")
    ap.add_argument("--approved", required=True, help="Approved YAML")
    ap.add_argument("--min_confidence", type=float, default=0.7)
    args = ap.parse_args()

    if not Path(args.input).exists():
        print(f"Input not found: {args.input}")
        return 1

    with open(args.input, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    
    entries = data.get("entries", [])
    approved_entries = []

    for e in entries:
        if e.get("confidence", 0) >= args.min_confidence:
            # Convert to approved format
            approved_entries.append({
                "term_zh": e["term_zh"],
                "term_ru": e["term_ru"],
                "status": "approved",
                "approved_at": datetime.now().isoformat(),
                "note": f"Auto-approved (confidence={e['confidence']})"
            })

    output = {
        "meta": {
            "type": "approved",
            "source": args.input,
            "min_confidence": args.min_confidence,
            "count": len(approved_entries)
        },
        "entries": approved_entries
    }

    Path(args.approved).parent.mkdir(parents=True, exist_ok=True)
    with open(args.approved, 'w', encoding='utf-8') as f:
        yaml.dump(output, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"✅ Approved {len(approved_entries)} / {len(entries)} entries")
    return 0

if __name__ == "__main__":
    sys.exit(main())
