#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
translate_llm.py (v3.0 - Batch Mode)
Purpose:
  Translate tokenized Chinese strings (tokenized_zh) into target language with:
  - BATCH processing: multiple items per LLM call to reduce prompt token waste
  - checkpoint/resume at batch level
  - binary-split fallback on parse failure
  - glossary.yaml (approved hard, banned hard, proposed soft)
  - style_guide.md guidance

Usage:
  python scripts/translate_llm.py \\
    --input data/draft.csv \\
    --output data/translated.csv \\
    --style workflow/style_guide.md \\
    --glossary data/glossary.yaml \\
    --target ru-RU --batch_size 20 --max_retries 3

Environment (OpenAI-compatible):
  LLM_BASE_URL   e.g. https://api.openai.com/v1
  LLM_API_KEY    your key/token
  LLM_MODEL      e.g. gpt-4o
"""

import argparse
import csv
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Use shared runtime adapter for LLM calls
try:
    from runtime_adapter import LLMClient, LLMError
except ImportError:
    LLMClient = None
    LLMError = Exception

try:
    import yaml  # PyYAML
except Exception:
    yaml = None

# Import batch utilities
try:
    from batch_utils import (
        BatchConfig, split_into_batches, parse_json_array,
        BatchCheckpoint, filter_pending, format_progress
    )
except ImportError:
    print("ERROR: batch_utils.py not found. Please ensure it exists in scripts/")
    sys.exit(1)

TOKEN_RE = re.compile(r"⟦(PH_\d+|TAG_\d+)⟧")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# -----------------------------
# Glossary model
# -----------------------------
@dataclass
class GlossaryEntry:
    term_zh: str
    term_ru: str
    status: str  # approved | proposed | banned
    notes: str = ""


def load_style_guide(path: str) -> str:
    if not Path(path).exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()

def load_glossary_lock(compiled_path: str) -> Dict[str, Any]:
    """Load compiled.lock.json if exists."""
    lock_path = Path(compiled_path).with_suffix('.lock.json')
    if lock_path.exists():
        with open(lock_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def load_glossary(path: str) -> Tuple[List[GlossaryEntry], Optional[str]]:
    if not path or not Path(path).exists():
        return [], None
    if yaml is None:
        raise RuntimeError("PyYAML is required. Install with: pip install pyyaml")
    
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    entries: List[GlossaryEntry] = []
    glossary_hash = None
    
    lock = load_glossary_lock(path)
    if lock:
        glossary_hash = lock.get("hash", "")
    
    if isinstance(data, dict) and "entries" in data and isinstance(data["entries"], list):
        src = data["entries"]
        for it in src:
            term_zh = (it.get("term_zh") or "").strip()
            term_ru = (it.get("term_ru") or "").strip()
            status = (it.get("status") or "approved").strip()
            notes = (it.get("notes") or it.get("note") or "").strip()
            if term_zh:
                entries.append(GlossaryEntry(term_zh, term_ru, status, notes))
    elif isinstance(data, dict) and "candidates" in data and isinstance(data["candidates"], list):
        for it in data["candidates"]:
            term_zh = (it.get("term_zh") or "").strip()
            term_ru = (it.get("ru_suggestion") or "").strip()
            status = (it.get("status") or "proposed").strip()
            notes = (it.get("notes") or "").strip()
            if term_zh:
                entries.append(GlossaryEntry(term_zh, term_ru, status, notes))
    
    return entries, glossary_hash

def build_glossary_constraints(entries: List[GlossaryEntry], source_text: str) -> Tuple[Dict[str, str], List[str], Dict[str, List[str]]]:
    approved_map: Dict[str, str] = {}
    banned_terms: List[str] = []
    proposed_map: Dict[str, List[str]] = {}

    for e in entries:
        if e.term_zh and e.term_zh in source_text:
            st = e.status.lower()
            if st == "approved":
                if e.term_ru:
                    approved_map[e.term_zh] = e.term_ru
            elif st == "banned":
                banned_terms.append(e.term_zh)
            else:  # proposed
                if e.term_ru:
                    proposed_map.setdefault(e.term_zh, []).append(e.term_ru)

    return approved_map, banned_terms, proposed_map

# -----------------------------
# Helpers
# -----------------------------
def read_csv_rows(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)

def write_csv_rows(path: str, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

def append_csv_rows(path: str, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    exists = Path(path).exists()
    mode = "a" if exists else "w"
    with open(path, mode, encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            w.writeheader()
        w.writerows(rows)

def load_checkpoint(path: str) -> dict:
    if Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done_ids": {}, "stats": {"ok": 0, "fail": 0, "escalated": 0}, "batch_idx": 0}

def save_checkpoint(path: str, ckpt: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ckpt, f, ensure_ascii=False, indent=2)

def tokens_signature(text: str) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for m in TOKEN_RE.finditer(text or ""):
        k = m.group(1)
        counts[k] = counts.get(k, 0) + 1
    return counts

def validate_translation(tokenized_zh: str, ru: str) -> Tuple[bool, str]:
    if tokens_signature(tokenized_zh) != tokens_signature(ru):
        return False, "token_mismatch"
    if CJK_RE.search(ru or ""):
        return False, "cjk_remaining"
    if not (ru or "").strip():
        if (tokenized_zh or "").strip():
            return False, "empty"
    return True, "ok"

def backoff_sleep(attempt: int) -> None:
    base = min(2 ** attempt, 30)
    jitter = random.uniform(0.2, 1.0)
    time.sleep(base * jitter)

# -----------------------------
# Batch Prompt builder
# -----------------------------
def build_system_prompt_batch(style_guide: str, glossary_summary: str) -> str:
    """Build system prompt for batch translation."""
    return (
        '你是严谨的手游本地化译者（zh-CN → ru-RU），面向"官方系统文案为主，二次元口语为辅"的火影题材。\n\n'
        '目标：把给定的中文文本批量翻译成自然、简洁、符合俄语习惯的俄文 UI/系统文本。\n\n'
        '术语表规则（硬性）：\n'
        '- glossary 中出现的 term_zh → term_ru 必须严格使用 term_ru。\n'
        '- 若源文包含 term_zh，但译文难以直接套用 term_ru，必须在不破坏占位符的前提下改写句子以容纳 term_ru。\n\n'
        '占位符规则（硬性）：\n'
        '- 任何形如 ⟦PH_xx⟧ / ⟦TAG_xx⟧ 的占位符必须原样保留，不得翻译/改动/增删。\n'
        '- 输出中禁止出现中文括号符号【】；如源文含【】用于分组/强调，俄语侧用 «» 或改写为"X: …"。\n\n'
        '输入格式：JSON 数组，每项包含 string_id 和 tokenized_zh。\n'
        '输出格式（硬性）：JSON 数组，每项包含 string_id 和 target_ru。\n'
        '示例输出：[{"string_id": "XXX", "target_ru": "Привет ⟦PH_0⟧"}]\n'
        '- 不要解释，不要加额外字段，严格输出 JSON 数组。\n'
        '- 若源文为空字符串：target_ru 也输出空字符串。\n\n'
        f'术语表摘要（前 50 条 approved）：\n{glossary_summary[:2000]}\n\n'
        f'style_guide（节选）：\n{style_guide[:1500]}\n'
    )

def build_batch_input(rows: List[Dict[str, str]], glossary: List[GlossaryEntry]) -> List[Dict[str, Any]]:
    """Build batch input JSON for LLM."""
    batch_items = []
    for row in rows:
        source_zh = row.get("tokenized_zh") or row.get("source_zh") or ""
        
        # Build per-item glossary constraints (compact)
        approved, banned, proposed = build_glossary_constraints(glossary, source_zh)
        glossary_hint = ""
        if approved:
            glossary_hint = "; ".join([f"{k}→{v}" for k, v in list(approved.items())[:5]])
        
        item = {
            "string_id": row.get("string_id", ""),
            "tokenized_zh": source_zh,
        }
        if glossary_hint:
            item["glossary_hint"] = glossary_hint
        if row.get("context"):
            item["context"] = row["context"][:200]
        
        batch_items.append(item)
    
    return batch_items

def build_glossary_summary(entries: List[GlossaryEntry], max_entries: int = 50) -> str:
    """Build compact glossary summary for system prompt."""
    approved = [e for e in entries if e.status.lower() == "approved"][:max_entries]
    if not approved:
        return "(无)"
    lines = [f"- {e.term_zh} → {e.term_ru}" for e in approved]
    return "\n".join(lines)

# -----------------------------
# Batch processing
# -----------------------------
def process_batch(
    batch: List[Dict[str, str]],
    llm: LLMClient,
    glossary: List[GlossaryEntry],
    style_guide: str,
    glossary_summary: str,
    batch_idx: int,
    max_retries: int = 3
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """
    Process a batch of rows through LLM.
    
    Returns:
        (success_rows, escalated_rows)
    """
    if not batch:
        return [], []
    
    system = build_system_prompt_batch(style_guide, glossary_summary)
    batch_input = build_batch_input(batch, glossary)
    user_prompt = json.dumps(batch_input, ensure_ascii=False, indent=None)
    
    # Build string_id -> row map for result matching
    id_to_row = {r.get("string_id", ""): r for r in batch}
    
    for attempt in range(max_retries + 1):
        try:
            result = llm.chat(
                system=system,
                user=user_prompt,
                metadata={
                    "step": "translate",
                    "batch_idx": batch_idx,
                    "batch_size": len(batch),
                    "attempt": attempt
                },
                response_format={"type": "json_object"}
            )
            
            # Parse response
            parsed = parse_json_array(result.text)
            if parsed is None:
                raise ValueError(f"Failed to parse JSON array from response")
            
            # Match results to original rows
            success_rows = []
            matched_ids = set()
            
            for item in parsed:
                sid = item.get("string_id", "")
                target_ru = item.get("target_ru", "")
                
                if sid not in id_to_row:
                    continue  # Unknown ID, skip
                
                original_row = id_to_row[sid]
                source_zh = original_row.get("tokenized_zh") or original_row.get("source_zh") or ""
                
                # Validate translation
                ok, reason = validate_translation(source_zh, target_ru)
                if ok:
                    out_row = dict(original_row)
                    out_row["target_text"] = target_ru
                    success_rows.append(out_row)
                    matched_ids.add(sid)
                else:
                    # Validation failed - will be retried or escalated
                    pass
            
            # Check for missing IDs
            missing_ids = set(id_to_row.keys()) - matched_ids
            
            if not missing_ids:
                # All rows processed successfully
                return success_rows, []
            
            # Some rows missing - if this is last attempt, escalate
            if attempt >= max_retries:
                escalated = []
                for sid in missing_ids:
                    row = id_to_row[sid]
                    escalated.append({
                        "string_id": sid,
                        "reason": "missing_from_batch_response",
                        "tokenized_zh": row.get("tokenized_zh", ""),
                        "last_output": ""
                    })
                return success_rows, escalated
            
            # Retry with smaller batch (binary split)
            backoff_sleep(attempt)
            
        except Exception as e:
            if attempt >= max_retries:
                # Escalate entire batch
                escalated = []
                for row in batch:
                    escalated.append({
                        "string_id": row.get("string_id", ""),
                        "reason": f"batch_error: {str(e)[:100]}",
                        "tokenized_zh": row.get("tokenized_zh", ""),
                        "last_output": ""
                    })
                return [], escalated
            backoff_sleep(attempt)
    
    return [], []


def process_batch_with_fallback(
    batch: List[Dict[str, str]],
    llm: LLMClient,
    glossary: List[GlossaryEntry],
    style_guide: str,
    glossary_summary: str,
    batch_idx: int,
    max_retries: int = 3,
    depth: int = 0,
    max_depth: int = 5
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """
    Process batch with binary-split fallback on failure.
    """
    if not batch:
        return [], []
    
    # Try full batch first
    success, escalated = process_batch(
        batch, llm, glossary, style_guide, glossary_summary, batch_idx, max_retries
    )
    
    if not escalated:
        return success, []
    
    # If batch size is 1, can't split further
    if len(batch) <= 1 or depth >= max_depth:
        return success, escalated
    
    # Binary split and retry
    mid = len(batch) // 2
    left_batch = batch[:mid]
    right_batch = batch[mid:]
    
    left_success, left_esc = process_batch_with_fallback(
        left_batch, llm, glossary, style_guide, glossary_summary,
        batch_idx, max_retries, depth + 1, max_depth
    )
    
    right_success, right_esc = process_batch_with_fallback(
        right_batch, llm, glossary, style_guide, glossary_summary,
        batch_idx, max_retries, depth + 1, max_depth
    )
    
    return left_success + right_success, left_esc + right_esc


# -----------------------------
# Main
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="LLM Translate (Batch Mode v3.0)")
    parser.add_argument("--input", required=True, help="Input CSV")
    parser.add_argument("--output", required=True, help="Output Translated CSV")
    parser.add_argument("--style", default="workflow/style_guide.md", help="Style guide")
    parser.add_argument("--glossary", default="data/glossary.yaml", help="Glossary YAML")
    parser.add_argument("--escalate_csv", default="data/escalate_list.csv", help="Escalation CSV")
    parser.add_argument("--checkpoint", default="data/translate_checkpoint.json", help="Checkpoint JSON")
    parser.add_argument("--target", default="ru-RU")
    parser.add_argument("--batch_size", type=int, default=20, help="Items per batch")
    parser.add_argument("--max_batch_tokens", type=int, default=6000, help="Max tokens per batch")
    parser.add_argument("--max_retries", type=int, default=3)
    parser.add_argument("--progress_every", type=int, default=1, help="Report progress every N batches")
    parser.add_argument("--dry-run", action="store_true")
    
    args = parser.parse_args()
    
    print(f"🚀 Translate LLM v3.0 (Batch Mode)")
    print(f"   Input: {args.input}")
    print(f"   Batch size: {args.batch_size}")
    print()
    
    # 1. Load resources
    style_guide = load_style_guide(args.style)
    glossary, gloss_hash = load_glossary(args.glossary)
    glossary_summary = build_glossary_summary(glossary)
    
    # 2. Load input
    if not Path(args.input).exists():
        print(f"❌ Input file not found: {args.input}")
        sys.exit(1)
    
    rows = read_csv_rows(args.input)
    print(f"✅ Loaded {len(rows)} rows from {args.input}")
    print(f"   Glossary: {len(glossary)} entries")
    print(f"   Style guide: {len(style_guide)} chars")
    
    if args.dry_run:
        print()
        print("=" * 60)
        print("DRY-RUN MODE - Validation Summary")
        print("=" * 60)
        
        # Split into batches for preview
        config = BatchConfig(max_items=args.batch_size, max_tokens=args.max_batch_tokens)
        batches = split_into_batches(rows, config)
        print(f"[OK] Would create {len(batches)} batches")
        print(f"[OK] Average batch size: {len(rows) / max(1, len(batches)):.1f}")
        
        # Show sample system prompt
        sample_system = build_system_prompt_batch(style_guide, glossary_summary)
        print(f"[OK] System prompt: {len(sample_system)} chars (~{len(sample_system)//4} tokens)")
        
        print()
        print("[OK] Dry-run validation PASSED")
        print("=" * 60)
        return
    
    # 3. Checkpoint
    ckpt = load_checkpoint(args.checkpoint)
    done_ids = ckpt.get("done_ids", {})
    
    # 4. Filter pending
    pending = [r for r in rows if r.get("string_id") not in done_ids]
    print(f"   Pending items: {len(pending)}")
    
    if not pending:
        print("✅ All done.")
        return
    
    # 5. Initialize LLM
    if not LLMClient:
        print("❌ runtime_adapter not found. Cannot proceed.")
        sys.exit(1)
        
    try:
        llm = LLMClient()
        print(f"✅ LLM initialized: {llm.default_model}")
    except Exception as e:
        print(f"❌ Failed to init LLM: {e}")
        sys.exit(1)
    
    # 6. Split into batches
    config = BatchConfig(max_items=args.batch_size, max_tokens=args.max_batch_tokens)
    batches = split_into_batches(pending, config)
    print(f"   Batches: {len(batches)}")
    print()
    
    # 7. Initialize output
    sample_fields = list(rows[0].keys())
    if "target_text" not in sample_fields:
        sample_fields.append("target_text")
    
    esc_fields = ["string_id", "reason", "tokenized_zh", "last_output"]
    
    # 8. Process batches
    start_time = time.time()
    ok_count = ckpt.get("stats", {}).get("ok", 0)
    fail_count = ckpt.get("stats", {}).get("fail", 0)
    esc_count = ckpt.get("stats", {}).get("escalated", 0)
    
    for batch_idx, batch in enumerate(batches):
        batch_start = time.time()
        
        success_rows, escalated_rows = process_batch_with_fallback(
            batch, llm, glossary, style_guide, glossary_summary,
            batch_idx, args.max_retries
        )
        
        # Write success rows
        if success_rows:
            append_csv_rows(args.output, sample_fields, success_rows)
            for row in success_rows:
                done_ids[row.get("string_id", "")] = True
                ok_count += 1
        
        # Write escalated rows
        if escalated_rows:
            append_csv_rows(args.escalate_csv, esc_fields, escalated_rows)
            for row in escalated_rows:
                done_ids[row.get("string_id", "")] = True
                esc_count += 1
        
        # Update checkpoint
        ckpt["done_ids"] = done_ids
        ckpt["stats"] = {"ok": ok_count, "fail": fail_count, "escalated": esc_count}
        ckpt["batch_idx"] = batch_idx + 1
        save_checkpoint(args.checkpoint, ckpt)
        
        # Progress
        batch_time = time.time() - batch_start
        elapsed = time.time() - start_time
        total_done = ok_count + esc_count
        
        if (batch_idx + 1) % args.progress_every == 0 or batch_idx == len(batches) - 1:
            print(format_progress(
                total_done, len(pending), batch_idx + 1, len(batches),
                elapsed, batch_time
            ))
    
    # 9. Summary
    total_elapsed = time.time() - start_time
    print()
    print(f"✅ Translation complete!")
    print(f"   OK: {ok_count}")
    print(f"   Escalated: {esc_count}")
    print(f"   Total time: {int(total_elapsed)}s")
    print(f"   Output: {args.output}")
    if esc_count > 0:
        print(f"   Escalated: {args.escalate_csv}")


if __name__ == "__main__":
    main()
