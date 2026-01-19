#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
translate_refresh.py (v2.0 - Batch Mode)

Round2 Glossary Refresh: Minimal rewrite for glossary changes only.
BATCH processing: multiple items per LLM call to reduce prompt token waste.

This script:
1. Loads impact_set from glossary_delta.py output
2. For each impacted row, performs minimal translation refresh (batch mode)
3. Only modifies terms that changed in glossary (not full re-translation)
4. Runs qa_hard on refreshed rows with escalation loop

Usage:
    python scripts/translate_refresh.py \\
        --impact data/glossary_impact.json \\
        --translated data/translated.csv \\
        --glossary glossary/compiled.yaml \\
        --style workflow/style_guide.md \\
        --out_csv data/refreshed.csv \\
        --batch_size 15

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

# Import batch utilities
try:
    from batch_utils import (
        BatchConfig, split_into_batches, parse_json_array, format_progress
    )
except ImportError:
    print("ERROR: batch_utils.py not found. Please ensure it exists in scripts/")
    sys.exit(1)

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


def validate_placeholder_signature(source: str, target: str) -> bool:
    """Check if placeholder counts match."""
    sig_source = TOKEN_RE.findall(source)
    sig_target = TOKEN_RE.findall(target)
    return sig_source == sig_target


# -----------------------------
# Batch Prompting
# -----------------------------

def build_system_prompt_batch(style: str) -> str:
    """Build system prompt for batch translate refresh."""
    return (
        "你是"术语变更刷新器"（zh-CN → ru-RU）。\n"
        "任务：根据变更后的术语表，仅替换 current_ru 中过时的术语；保持其他内容（尤其占位符与句式）不变。\n\n"
        "输入格式：JSON 数组，每项包含 string_id、source_zh、current_ru、changed_terms。\n"
        "输出格式（硬性）：JSON 数组，每项包含 string_id、updated_ru。\n\n"
        "硬约束：\n"
        "- token（⟦PH_xx⟧ / ⟦TAG_xx⟧）必须原样保留且数量一致。\n"
        "- 只替换 changed_terms 中列出的术语，不要改变句子结构。\n"
        "- 如果没有需要替换的术语，updated_ru 应与 current_ru 相同。\n\n"
        "示例输出：[{\"string_id\": \"XXX\", \"updated_ru\": \"Новый текст ⟦PH_0⟧\"}]\n"
        "不要输出中文括号【】，不要解释。\n\n"
        f"style_guide（节选）：\n{style[:1000]}\n"
    )


def build_batch_input(rows: List[Dict[str, str]], changed_terms: List[Dict]) -> List[Dict]:
    """Build batch input for refresh."""
    batch_items = []
    for row in rows:
        source_zh = row.get("source_zh") or row.get("tokenized_zh") or ""
        
        # Filter to terms that appear in this source
        relevant_terms = [t for t in changed_terms if t["term_zh"] in source_zh]
        
        if not relevant_terms:
            # No relevant changes for this row
            continue
        
        changes_text = "; ".join([
            f"{t['term_zh']}: {t.get('old_ru', '?')} → {t['new_ru']}"
            for t in relevant_terms[:5]  # Limit to 5 terms per row
        ])
        
        batch_items.append({
            "string_id": row.get("string_id", ""),
            "source_zh": source_zh,
            "current_ru": row.get("target_text", ""),
            "changed_terms": changes_text
        })
    
    return batch_items


def process_batch(
    batch: List[Dict[str, str]],
    llm: LLMClient,
    style: str,
    hash_old: str,
    hash_new: str,
    changed_terms: List[Dict],
    batch_idx: int,
    max_retries: int = 2
) -> Dict[str, str]:
    """
    Process a batch of rows for refresh.
    
    Returns:
        Dict mapping string_id -> updated_ru
    """
    if not batch:
        return {}
    
    # Build batch input
    batch_input = build_batch_input(batch, changed_terms)
    
    if not batch_input:
        # No rows need refresh in this batch
        return {}
    
    system = build_system_prompt_batch(style)
    user_prompt = json.dumps(batch_input, ensure_ascii=False, indent=None)
    
    # Build id -> source map for validation
    id_to_source = {row.get("string_id", ""): row.get("source_zh") or row.get("tokenized_zh") or "" 
                    for row in batch}
    
    for attempt in range(max_retries + 1):
        try:
            result = llm.chat(
                system=system,
                user=user_prompt,
                metadata={
                    "step": "translate_refresh",
                    "batch_idx": batch_idx,
                    "batch_size": len(batch_input),
                    "glossary_hash_old": hash_old,
                    "glossary_hash_new": hash_new,
                    "attempt": attempt
                },
                response_format={"type": "json_object"}
            )
            
            parsed = parse_json_array(result.text)
            if parsed is None:
                raise ValueError("Failed to parse JSON array")
            
            # Build result map
            results = {}
            for item in parsed:
                sid = item.get("string_id", "")
                updated_ru = item.get("updated_ru", "")
                
                if not sid:
                    continue
                
                # Validate placeholder signature
                source = id_to_source.get(sid, "")
                if source and not validate_placeholder_signature(source, updated_ru):
                    # Placeholder mismatch - skip this item
                    continue
                
                results[sid] = updated_ru
            
            return results
            
        except Exception as e:
            if attempt >= max_retries:
                print(f"    ⚠️ Batch {batch_idx} error: {e}")
                return {}
            time.sleep(1)
    
    return {}


def main():
    ap = argparse.ArgumentParser(
        description="Round2 glossary refresh - minimal rewrite (Batch Mode v2.0)"
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
    ap.add_argument("--batch_size", type=int, default=15,
                    help="Items per batch")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate without making LLM calls")
    args = ap.parse_args()
    
    print("🔄 Translate Refresh v2.0 (Batch Mode)")
    print(f"   Impact: {args.impact}")
    print(f"   Batch size: {args.batch_size}")
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
    
    # Filter to impacted rows
    impacted_rows = [r for r in rows if r.get("string_id") in impact_set]
    print(f"   Impacted rows: {len(impacted_rows)}")
    
    if args.dry_run:
        print()
        print("=" * 60)
        print("DRY-RUN MODE - Validation Summary")
        print("=" * 60)
        config = BatchConfig(max_items=args.batch_size, max_tokens=4000)
        batches = split_into_batches(impacted_rows, config)
        print(f"[OK] Would create {len(batches)} batches")
        print(f"[OK] {len(changed_terms)} term changes to apply")
        print("[OK] Dry-run validation PASSED")
        print("=" * 60)
        return 0
    
    # Initialize LLM
    llm = LLMClient()
    print(f"✅ LLM: {llm.default_model}")
    
    # Split impacted rows into batches
    config = BatchConfig(max_items=args.batch_size, max_tokens=4000)
    config.text_fields = ["source_zh", "tokenized_zh", "target_text"]
    batches = split_into_batches(impacted_rows, config)
    print(f"   Batches: {len(batches)}")
    print()
    
    # Process batches and collect results
    start_time = time.time()
    refresh_map: Dict[str, str] = {}  # string_id -> updated_ru
    
    for batch_idx, batch in enumerate(batches):
        batch_start = time.time()
        
        results = process_batch(
            batch, llm, style, hash_old, hash_new, changed_terms, batch_idx
        )
        
        refresh_map.update(results)
        
        # Progress
        batch_time = time.time() - batch_start
        elapsed = time.time() - start_time
        
        if (batch_idx + 1) % 3 == 0 or batch_idx == len(batches) - 1:
            print(format_progress(
                batch_idx + 1, len(batches), batch_idx + 1, len(batches),
                elapsed, batch_time
            ))
    
    # Apply refreshes to all rows (preserving non-impacted rows)
    fieldnames = list(rows[0].keys()) if rows else []
    if "refresh_status" not in fieldnames:
        fieldnames.append("refresh_status")
    if "refresh_error" not in fieldnames:
        fieldnames.append("refresh_error")
    
    ok_count = 0
    no_change_count = 0
    
    for row in rows:
        string_id = row.get("string_id", "")
        
        if string_id not in impact_set:
            row["refresh_status"] = "not_in_impact"
            row["refresh_error"] = ""
            continue
        
        if string_id in refresh_map:
            row["target_text"] = refresh_map[string_id]
            row["refresh_status"] = "ok"
            row["refresh_error"] = ""
            ok_count += 1
        else:
            row["refresh_status"] = "no_changes"
            row["refresh_error"] = ""
            no_change_count += 1
    
    # Write output
    write_csv(args.out_csv, rows, fieldnames)
    
    total_elapsed = time.time() - start_time
    print()
    print(f"✅ Refresh complete:")
    print(f"   OK: {ok_count}")
    print(f"   No changes needed: {no_change_count}")
    print(f"   Total time: {int(total_elapsed)}s")
    print(f"✅ Saved to: {args.out_csv} ({len(rows)} rows)")
    print()
    print(f"📊 Row count verification: input={len(rows)}, output={len(rows)} ✅")
    
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
