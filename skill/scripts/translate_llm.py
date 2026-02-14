#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
translate_llm.py (v7.0 - Optimized Batch Mode with High Throughput)
Purpose:
  Translate tokenized Chinese strings using the optimized batch infrastructure.
  - Supports --model argument
  - Dynamically switches to content_type="long_text" if is_long_text is present
  - Uses batch_optimizer for dynamic sizing and parallel processing
  - Preserves token consistency validation
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import yaml
except ImportError:
    yaml = None

# Import optimized batch processor
try:
    from batch_optimizer import optimized_batch_call, BatchConfig, BatchProcessor
except ImportError:
    print("WARNING: batch_optimizer.py not found. Falling back to runtime_adapter.")
    from runtime_adapter import batch_llm_call as optimized_batch_call
    BatchConfig = None
    BatchProcessor = None

try:
    from runtime_adapter import LLMClient, LLMError, log_llm_progress
except ImportError:
    print("ERROR: scripts/runtime_adapter.py not found.")
    sys.exit(1)

TOKEN_RE = re.compile(r"⟦(PH_\d+|TAG_\d+)⟧")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# -----------------------------
# Glossary & Style Utils
# -----------------------------
@dataclass
class GlossaryEntry:
    term_zh: str
    term_ru: str
    status: str
    notes: str = ""

def build_glossary_constraints(glossary: List[GlossaryEntry], source_zh: str) -> Dict[str, str]:
    approved = {}
    for e in glossary:
        if e.term_zh and e.term_zh in source_zh and e.status.lower() == "approved":
            approved[e.term_zh] = e.term_ru
    return approved

def load_text(p: str) -> str:
    if not Path(p).exists(): return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read().strip()

def load_glossary(path: str) -> Tuple[List[GlossaryEntry], Optional[str]]:
    if not path or not Path(path).exists() or yaml is None:
        return [], None
    with open(path, "r", encoding="utf-8") as f:
        g = yaml.safe_load(f) or {}
    entries = []
    for it in g.get("entries", []):
        term_zh = (it.get("term_zh") or "").strip()
        term_ru = (it.get("term_ru") or "").strip()
        status = (it.get("status") or "").lower().strip()
        if term_zh and status == "approved":
            entries.append(GlossaryEntry(term_zh, term_ru, status))
    meta = g.get("meta", {})
    return entries, meta.get("compiled_hash")

def build_glossary_summary(glossary: List[GlossaryEntry]) -> str:
    if not glossary: return "(无)"
    return "\n".join([f"- {e.term_zh} → {e.term_ru}" for e in glossary[:50]])

# -----------------------------
# Token Validation
# -----------------------------
def tokens_signature(text: str) -> Dict[str, int]:
    counts = {}
    for m in TOKEN_RE.finditer(text or ""):
        counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts

def validate_translation(tokenized_zh: str, ru: str) -> Tuple[bool, str]:
    if tokens_signature(tokenized_zh) != tokens_signature(ru):
        return False, "token_mismatch"
    if CJK_RE.search(ru or ""):
        return False, "cjk_remaining"
    if not (ru or "").strip() and (tokenized_zh or "").strip():
        return False, "empty"
    return True, "ok"

# -----------------------------
# Prompt Builders
# -----------------------------
def build_system_prompt_factory(style_guide: str, glossary_summary: str):
    """Factory to create a dynamic system prompt builder."""
    def _builder(rows: List[Dict]) -> str:
        constraints = ""
        for r in rows:
            max_len = r.get("max_length_target") or r.get("max_len_target")
            if max_len and int(max_len) > 0:
                constraints += f"- Row {r.get('string_id')}: max {max_len} chars\n"
        
        constraint_section = ""
        if constraints:
            constraint_section = (
                f"\n【Length Constraints (Mandatory)】\n"
                f"Each translation MUST NOT exceed its limit:\n{constraints}\n"
                f"If too long: use abbreviations/synonyms but preserve meaning.\n"
            )

        return (
            '你是严谨的手游本地化译者（zh-CN → ru-RU）。\n\n'
            '【Output Contract v6】\n'
            '1. Output MUST be valid JSON (Object with "items" key).\n'
            '2. Structure MUST be: {"items": [{"id": "...", "target_ru": "..."}]}\n'
            '3. Every input "id" MUST appear in the output.\n\n'
            '【Translation Rules】\n'
            '- 术语匹配必须一致。\n'
            '- 占位符 ⟦PH_xx⟧ / ⟦TAG_xx⟧ 必须保留。\n'
            '- 禁止中文括号【】。\n'
            f'{constraint_section}\n'
            f'术语表摘要：\n{glossary_summary}\n\n'
            f'style_guide：\n{style_guide}\n'
        )
    return _builder

def build_user_prompt(rows: List[Dict]) -> str:
    # rows are items prepared for batch_llm_call
    return json.dumps(rows, ensure_ascii=False, indent=2)

# -----------------------------
# Checkpoint Logic
# -----------------------------
def load_checkpoint(path: str) -> set:
    if not Path(path).exists(): return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("done_ids", []))
    except: return set()

def save_checkpoint(path: str, done_ids: set):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"done_ids": list(done_ids)}, f)

# -----------------------------
# Main Process
# -----------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--style", default="workflow/style_guide.md")
    parser.add_argument("--glossary", default="data/glossary.yaml")
    parser.add_argument("--checkpoint", default="data/translate_checkpoint.json")
    parser.add_argument("--batch_size", type=int, default=None, help="Override batch size (default: auto)")
    parser.add_argument("--workers", type=int, default=None, help="Override worker count (default: from config)")
    parser.add_argument("--use-optimized", action="store_true", default=True, help="Use optimized batch processing")
    args = parser.parse_args()

    print(f"🚀 Translate LLM v7.0 (Optimized Batch Mode)")
    
    # Load resources
    style_guide = load_text(args.style)
    glossary, _ = load_glossary(args.glossary)
    glossary_summary = build_glossary_summary(glossary)
    
    # Read CSV
    if not Path(args.input).exists():
        print(f"❌ Input not found: {args.input}")
        return
    
    with open(args.input, "r", encoding="utf-8-sig") as f:
        all_rows = list(csv.DictReader(f))
    
    headers = list(all_rows[0].keys()) if all_rows else []
    if "target_text" not in headers: headers.append("target_text")
    
    # Checkpoint
    done_ids = load_checkpoint(args.checkpoint)
    pending_rows = [r for r in all_rows if r.get("string_id") not in done_ids]
    
    if not pending_rows:
        print("✅ No pending rows to process.")
        return

    print(f"   Total rows: {len(all_rows)}, Pending: {len(pending_rows)}")
    
    # Detect long text status for ANY row in the pending set
    # Check for is_long_text == 1 or is_long_text == "1"
    has_long_text = any(
        str(r.get("is_long_text", "0")) == "1" or r.get("is_long_text") == 1
        for r in pending_rows
    )
    content_type = "long_text" if has_long_text else "normal"
    
    if has_long_text:
        print("   [Tagger Hint] Long text detected. Using content_type='long_text' for lower batch density.")

    # Prepare for batch_llm_call
    batch_inputs = []
    for r in pending_rows:
        src = r.get("tokenized_zh") or r.get("source_zh") or ""
        batch_inputs.append({
            "id": r.get("string_id"),
            "source_text": src,
            "max_length_target": r.get("max_length_target") or r.get("max_len_target"),
            "string_id": r.get("string_id")  # For prompt builder
        })

    # Execute with optimized batch processing
    try:
        system_prompt_builder = build_system_prompt_factory(style_guide, glossary_summary)
        
        # Check if we should use optimized processing
        config = None
        if args.use_optimized and BatchConfig is not None:
            config = BatchConfig.from_yaml()
            if args.workers:
                config.max_workers = args.workers
            if args.batch_size:
                config.dynamic_sizing = False  # Disable dynamic sizing if explicit size given
            print(f"   [Optimizer] Dynamic sizing: {config.dynamic_sizing}, Workers: {config.max_workers}")
        
        # Use optimized batch processing
        results = optimized_batch_call(
            step="translate",
            rows=batch_inputs,
            model=args.model,
            system_prompt=system_prompt_builder,
            user_prompt_template=build_user_prompt,
            content_type=content_type,
            retry=2,
            config=config,
            pre_computed_glossary=glossary_summary if glossary else None
        )
        
        # Merge results back to original rows
        res_map = {str(it.get("id")): it.get("target_ru", "") for it in results}
        
        # Validation and Final output prep
        final_rows = []
        new_done = set()
        failed_validations = []
        
        for r in pending_rows:
            sid = str(r.get("string_id"))
            ru = res_map.get(sid, "")
            
            # Validation
            ok, err = validate_translation(r.get("tokenized_zh") or r.get("source_zh") or "", ru)
            if ok:
                r["target_text"] = ru
                final_rows.append(r)
                new_done.add(sid)
            else:
                failed_validations.append({"id": sid, "error": err, "translation": ru})
                print(f"⚠️  Validation failed for {sid}: {err}")
        
        # Write Output
        write_mode = "a" if Path(args.output).exists() else "w"
        with open(args.output, write_mode, encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if write_mode == "w": writer.writeheader()
            writer.writerows(final_rows)
            
        # Update checkpoint
        done_ids.update(new_done)
        save_checkpoint(args.checkpoint, done_ids)
        
        # Summary
        print(f"\n{'='*60}")
        print(f"✅ Translation Complete")
        print(f"   Translated: {len(new_done)} / {len(pending_rows)} rows")
        print(f"   Validation failures: {len(failed_validations)}")
        print(f"{'='*60}")
        
        # Save validation failures if any
        if failed_validations:
            fail_path = "reports/translate_validation_failures.json"
            Path(fail_path).parent.mkdir(parents=True, exist_ok=True)
            with open(fail_path, "w", encoding="utf-8") as f:
                json.dump({
                    "timestamp": datetime.now().isoformat(),
                    "failures": failed_validations
                }, f, indent=2, ensure_ascii=False)
            print(f"⚠️  Validation failures saved to: {fail_path}")
        
    except Exception as e:
        print(f"❌ Translation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
