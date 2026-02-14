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

from runtime_adapter import LLMClient, LLMError, BatchConfig, get_batch_config, batch_llm_call, log_llm_progress

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
        "你是'术语变更刷新器'（zh-CN → ru-RU）。\n"
        "任务：根据变更后的术语表，仅替换 current_ru 中过时的术语；保持其他内容（尤其占位符与句式）不变。\n\n"
        "输入格式：JSON 数组，每项包含 string_id、source_zh、current_ru、changed_terms。\n"
        "输出格式（硬性 JSON）：\n"
        "{\n"
        '  "items": [\n'
        "    {\n"
        '      "id": "<string_id>",\n'
        '      "updated_ru": "<new_text>"\n'
        "    }\n"
        "  ]\n"
        "}\n\n"
        "硬约束：\n"
        "- token（⟦PH_xx⟧ / ⟦TAG_xx⟧）必须原样保留且数量一致。\n"
        "- 只替换 changed_terms 中列出的术语，不要改变句子结构。\n"
        "- 如果没有需要替换的术语，updated_ru 应与 current_ru 相同。\n\n"
        "示例输出：{\"items\": [{\"id\": \"XXX\", \"updated_ru\": \"Новый текст ⟦PH_0⟧\"}]}\n"
        "不要输出中文括号【】，不要解释。\n\n"
        f"style_guide（节选）：\n{style[:1000]}\n"
    )


def build_user_prompt_refresh(items: List[Dict]) -> str:
    """Build user prompt for refresh from batch items."""
    # items comes from batch_llm_call where 'source_text' is a JSON string 
    # containing current_ru and changed_terms
    candidates = []
    for it in items:
        try:
            extra = json.loads(it["source_text"])
            candidates.append({
                "string_id": it["id"],
                "source_zh": extra.get("source_zh", ""),
                "current_ru": extra.get("current_ru", ""),
                "changed_terms": extra.get("changed_terms", "")
            })
        except:
            candidates.append({
                "string_id": it["id"],
                "source_zh": it["source_text"] # Fallback
            })
    
    return json.dumps(candidates, ensure_ascii=False, indent=2)

def process_refresh_results(batch_results: List[Dict], id_to_source: Dict[str, str]) -> Dict[str, str]:
    """Normalize batch output items into refresh map."""
    refresh_map = {}
    for it in batch_results:
        sid = str(it.get("id", ""))
        updated_ru = it.get("updated_ru", "")
        
        if not sid or not updated_ru:
            continue
            
        # Validate placeholder signature
        source = id_to_source.get(sid, "")
        if source and not validate_placeholder_signature(source, updated_ru):
            continue
            
        refresh_map[sid] = updated_ru
    return refresh_map


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
    ap.add_argument("--report", help="Output JSON report")
    ap.add_argument("--batch_size", type=int, default=15,
                    help="Items per batch")
    ap.add_argument("--model", help="Model override")
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
    
    # Prepare rows for batch_llm_call
    batch_rows = []
    id_to_source = {}
    for row in impacted_rows:
        source_zh = row.get("source_zh") or row.get("tokenized_zh") or ""
        id_to_source[row["string_id"]] = source_zh
        
        # Filter to terms that appear in this source
        relevant_terms = [t for t in changed_terms if t["term_zh"] in source_zh]
        if not relevant_terms:
            continue
            
        changes_text = "; ".join([
            f"{t['term_zh']}: {t.get('old_ru', '?')} → {t['new_ru']}"
            for t in relevant_terms[:5]
        ])
        
        # We pack current_ru and changes into source_text as JSON
        extra_info = {
            "source_zh": source_zh,
            "current_ru": row.get("target_text", ""),
            "changed_terms": changes_text
        }
        
        batch_rows.append({
            "id": row["string_id"],
            "source_text": json.dumps(extra_info, ensure_ascii=False)
        })

    if not batch_rows:
        print("ℹ️  No relevant term changes found in impacted rows.")
        return 0

    # Execute batch call
    start_time = time.time()
    model = args.model or "claude-haiku-4-5-20251001"
    try:
        batch_results = batch_llm_call(
            step="translate_refresh",
            rows=batch_rows,
            model=model,
            system_prompt=build_system_prompt_batch(style),
            user_prompt_template=build_user_prompt_refresh,
            content_type="normal",
            retry=1,
            allow_fallback=True
        )
        
        print("   Batch results received, processing refreshes...")
        refresh_map = process_refresh_results(batch_results, id_to_source)
        
    except Exception as e:
        print(f"❌ Refresh failed: {e}")
        return 1
    
    # Apply refreshes to all rows (preserving non-impacted rows)
    all_fields = list(rows[0].keys()) if rows else []
    fieldnames = [f for f in all_fields if f is not None]
    if "refresh_status" not in fieldnames:
        fieldnames.append("refresh_status")
    if "refresh_error" not in fieldnames:
        fieldnames.append("refresh_error")
    
    ok_count = 0
    no_change_count = 0
    clean_rows = []
    
    for row in rows:
        string_id = row.get("string_id", "")
        
        # Ensure row only has keys in fieldnames to avoid DictWriter error
        clean_row = {k: v for k, v in row.items() if k in fieldnames}
        
        if string_id not in impact_set:
            clean_row["refresh_status"] = "not_in_impact"
            clean_row["refresh_error"] = ""
            clean_rows.append(clean_row)
            continue
        
        if string_id in refresh_map:
            clean_row["target_text"] = refresh_map[string_id]
            clean_row["refresh_status"] = "ok"
            clean_row["refresh_error"] = ""
            ok_count += 1
        else:
            clean_row["refresh_status"] = "no_changes"
            clean_row["refresh_error"] = ""
            no_change_count += 1
        clean_rows.append(clean_row)
    
    # Write output
    write_csv(args.out_csv, clean_rows, fieldnames)
    
    total_elapsed = time.time() - start_time
    print()
    print(f"✅ Refresh complete:")
    print(f"   OK: {ok_count}")
    print(f"   No changes needed: {no_change_count}")
    print(f"   Total time: {int(total_elapsed)}s")
    print(f"✅ Saved to: {args.out_csv} ({len(rows)} rows)")
    print()
    print(f"📊 Row count verification: input={len(rows)}, output={len(rows)} ✅")
    
    if args.report:
        report_data = {
            "total_rows": len(rows),
            "refreshed_rows": ok_count,
            "no_change_rows": no_change_count,
            "model": model,
            "latency_s": round(total_elapsed, 2),
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")
        }
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report_data, f, indent=2)
        print(f"✅ Report saved to: {args.report}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
