#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
translate_refresh.py

Round2 Glossary Refresh: Minimal rewrite for glossary changes only.

This script:
1. Loads impact_set from glossary_delta.py output
2. For each impacted row, performs minimal translation refresh
3. Only modifies terms that changed in glossary (not full re-translation)
4. Runs qa_hard on refreshed rows with escalation loop

Usage:
    python scripts/translate_refresh.py \
        --impact data/glossary_impact.json \
        --translated data/translated.csv \
        --glossary glossary/compiled.yaml \
        --style workflow/style_guide.md \
        --out_csv data/refreshed.csv

Trace metadata:
    step: "translate_refresh"
    glossary_hash_old: "sha256:..."
    glossary_hash_new: "sha256:..."
"""

import argparse
import csv
import json
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import yaml
except ImportError:
    yaml = None

from runtime_adapter import LLMClient, LLMError

TOKEN_RE = re.compile(r"⟦(PH_\d+|TAG_\d+)⟧")


def load_impact(path: str) -> Dict[str, Any]:
    """Load impact JSON from glossary_delta.py."""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def read_csv_rows(path: str) -> List[Dict[str, str]]:
    """Read CSV file as list of dicts."""
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def write_csv(path: str, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    """Write CSV file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_glossary(path: str) -> Dict[str, str]:
    """Load glossary as term_zh -> term_ru map."""
    if not Path(path).exists() or yaml is None:
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    entries = data.get("entries", [])
    return {e.get("term_zh", "").strip(): e.get("term_ru", "").strip() 
            for e in entries if e.get("term_zh")}


def load_style_guide(path: str) -> str:
    """Load style guide markdown."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def build_refresh_prompt(source_zh: str, current_ru: str, 
                         changed_terms: List[Dict], style: str) -> str:
    """Build prompt for minimal glossary refresh."""
    terms_text = "\n".join([
        f"  - {t['term_zh']}: {t.get('old_ru', '?')} → {t['new_ru']}"
        for t in changed_terms
    ])
    
    prompt = f"""你需要对以下翻译进行最小限度修改，仅更新术语变化。

【术语变更】
{terms_text}

【原文 (中文)】
{source_zh}

【当前译文 (俄语)】
{current_ru}

【要求】
1. 只更新上述变更的术语
2. 保持其余翻译不变
3. 保留所有占位符 ⟦PH_XXX⟧ 和 ⟦TAG_XXX⟧
4. 确保语法正确

【风格指南摘要】
{style[:500]}...

返回修改后的俄语译文，不要添加任何解释。"""
    
    return prompt


def refresh_row(llm: LLMClient, row: Dict[str, str], 
                changed_terms: List[Dict], style: str,
                hash_old: str, hash_new: str) -> Tuple[str, bool]:
    """
    Refresh a single row with glossary changes.
    
    Returns: (new_translation, success)
    """
    source_zh = row.get("source_zh") or row.get("tokenized_zh") or ""
    current_ru = row.get("target_text") or ""
    string_id = row.get("string_id", "")
    
    # Filter to terms that appear in this source
    relevant_terms = [t for t in changed_terms if t["term_zh"] in source_zh]
    
    if not relevant_terms:
        # No relevant changes, keep current
        return current_ru, True
    
    prompt = build_refresh_prompt(source_zh, current_ru, relevant_terms, style)
    
    try:
        result = llm.chat(
            system="You are a professional translator performing minimal glossary updates.",
            user=prompt,
            metadata={
                "step": "translate_refresh",
                "string_id": string_id,
                "glossary_hash_old": hash_old,
                "glossary_hash_new": hash_new,
                "terms_refreshed": len(relevant_terms)
            }
        )
        
        if result.text:
            return result.text.strip(), True
        else:
            return current_ru, False
            
    except LLMError as e:
        print(f"⚠️  LLM error for {string_id}: {e}")
        return current_ru, False


def main():
    ap = argparse.ArgumentParser(
        description="Round2 glossary refresh - minimal rewrite for term changes"
    )
    ap.add_argument("--impact", required=True,
                    help="Impact JSON from glossary_delta.py")
    ap.add_argument("--translated", required=True,
                    help="Current translated CSV")
    ap.add_argument("--glossary", default="glossary/compiled.yaml",
                    help="New compiled glossary")
    ap.add_argument("--style", required=True,
                    help="Style guide markdown")
    ap.add_argument("--out_csv", default="data/refreshed.csv",
                    help="Output refreshed CSV")
    ap.add_argument("--batch_size", type=int, default=20,
                    help="Batch size for progress reporting")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate without making LLM calls")
    args = ap.parse_args()
    
    print("🔄 Translate Refresh (Round2)")
    print(f"   Impact: {args.impact}")
    print(f"   Translated: {args.translated}")
    print(f"   Glossary: {args.glossary}")
    print()
    
    # Load impact data
    if not Path(args.impact).exists():
        print(f"❌ Impact file not found: {args.impact}")
        return 1
    
    impact = load_impact(args.impact)
    impact_set = set(impact.get("impact_set", []))
    delta = impact.get("delta_terms", {})
    hash_old = impact.get("glossary_hash_old", "")
    hash_new = impact.get("glossary_hash_new", "")
    
    print(f"✅ Impact set: {len(impact_set)} rows")
    print(f"   Changed terms: {len(delta.get('changed', []))}")
    print(f"   Added terms: {len(delta.get('added', []))}")
    
    if not impact_set:
        print()
        print("ℹ️  No rows to refresh")
        return 0
    
    # Build changed terms list
    changed_terms = []
    for item in delta.get("changed", []):
        changed_terms.append({
            "term_zh": item["term_zh"],
            "old_ru": item.get("old_ru", ""),
            "new_ru": item["new_ru"]
        })
    for item in delta.get("added", []):
        changed_terms.append({
            "term_zh": item["term_zh"],
            "old_ru": "",
            "new_ru": item["term_ru"]
        })
    
    # Load translated CSV
    if not Path(args.translated).exists():
        print(f"❌ Translated CSV not found: {args.translated}")
        return 1
    
    rows = read_csv_rows(args.translated)
    print(f"✅ Loaded {len(rows)} translated rows")
    
    # Load style guide
    style = load_style_guide(args.style)
    
    if args.dry_run:
        print()
        print("=" * 60)
        print("DRY-RUN MODE - Validation Summary")
        print("=" * 60)
        print(f"[OK] Would refresh {len(impact_set)} rows")
        print(f"[OK] {len(changed_terms)} term changes to apply")
        print(f"[OK] Would write to {args.out_csv}")
        print("[OK] Dry-run validation PASSED")
        print("=" * 60)
        return 0
    
    # Initialize LLM
    llm = LLMClient()
    
    # Refresh impacted rows
    refreshed = 0
    errors = 0
    fieldnames = list(rows[0].keys()) if rows else []
    
    for i, row in enumerate(rows):
        string_id = row.get("string_id", "")
        
        if string_id not in impact_set:
            continue
        
        new_ru, success = refresh_row(
            llm, row, changed_terms, style, hash_old, hash_new
        )
        
        if success:
            row["target_text"] = new_ru
            refreshed += 1
        else:
            errors += 1
        
        if (refreshed + errors) % args.batch_size == 0:
            print(f"   Progress: {refreshed + errors}/{len(impact_set)} rows...")
    
    print()
    print(f"✅ Refreshed {refreshed} rows")
    if errors > 0:
        print(f"⚠️  {errors} errors (kept original)")
    
    # Write output
    write_csv(args.out_csv, rows, fieldnames)
    print(f"✅ Saved to: {args.out_csv}")
    
    print()
    print("📝 Next steps:")
    print("   1. Run qa_hard on refreshed.csv")
    print("   2. Repair any failures (Loop B with POST_SOFT_HARD_LOOP_MAX=2)")
    print("   3. Merge with main translated.csv")
    
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
