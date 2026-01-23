#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
translate_llm.py (v5.0 - Structured Output Contract)
Purpose:
  Translate tokenized Chinese strings with:
  - CONCURRENT batch processing
  - JSON schema validation (strict)
  - Structure-repair retry (1 attempt)
  - Dynamic max_tokens calculation
  - Batch-based progress with ETA

Usage:
  python scripts/translate_llm.py \\
    --input data/draft.csv \\
    --output data/translated.csv \\
    --batch_size 10 --max_concurrent 6
"""

import argparse
import csv
import json
import os
import random
import re
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# sys.stdout wrapping moved to __main__ block

# JSON Schema validation
try:
    import jsonschema
except ImportError:
    jsonschema = None
    print("WARNING: jsonschema not installed. Schema validation disabled.")

try:
    from runtime_adapter import LLMClient, LLMError
except ImportError:
    LLMClient = None
    LLMError = Exception

try:
    import yaml
except Exception:
    yaml = None

try:
    from batch_utils import BatchConfig, split_into_batches, parse_json_array
except ImportError:
    print("ERROR: batch_utils.py not found.")
    sys.exit(1)

TOKEN_RE = re.compile(r"⟦(PH_\d+|TAG_\d+)⟧")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# -----------------------------
# JSON Schema for Batch Output
# -----------------------------
BATCH_OUTPUT_SCHEMA = {
    "type": "array",
    "minItems": 1,
    "items": {
        "type": "object",
        "required": ["string_id", "target_ru"],
        "properties": {
            "string_id": {"type": "string", "minLength": 1},
            "target_ru": {"type": "string"}
        },
        "additionalProperties": False
    }
}

# Token estimation constants
EXPECTED_TOKENS_PER_ROW = 40
COMPLETION_MARGIN = 1.3


def validate_batch_schema(data: Any) -> Tuple[bool, str]:
    """Validate parsed JSON against batch output schema."""
    if jsonschema is None:
        # Fallback: basic structure check
        if not isinstance(data, list):
            return False, "not_array"
        for item in data:
            if not isinstance(item, dict):
                return False, "item_not_object"
            if "string_id" not in item or "target_ru" not in item:
                return False, "missing_required_fields"
        return True, "ok"
    
    try:
        jsonschema.validate(instance=data, schema=BATCH_OUTPUT_SCHEMA)
        return True, "ok"
    except jsonschema.ValidationError as e:
        return False, f"schema_error: {str(e.message)[:100]}"


# -----------------------------
# Inflight Tracker
# -----------------------------
class InflightTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._count = 0
        self._peak = 0
    
    def acquire(self) -> int:
        with self._lock:
            self._count += 1
            self._peak = max(self._peak, self._count)
            return self._count
    
    def release(self) -> None:
        with self._lock:
            self._count -= 1
    
    @property
    def current(self) -> int:
        with self._lock:
            return self._count
    
    @property
    def peak(self) -> int:
        with self._lock:
            return self._peak


# -----------------------------
# Glossary
# -----------------------------
@dataclass
class GlossaryEntry:
    term_zh: str
    term_ru: str
    status: str
    notes: str = ""


def load_style_guide(path: str) -> str:
    if not Path(path).exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_glossary(path: str) -> Tuple[List[GlossaryEntry], Optional[str]]:
    if not path or not Path(path).exists():
        return [], None
    if yaml is None:
        return [], None
    with open(path, "r", encoding="utf-8") as f:
        g = yaml.safe_load(f) or {}
    entries = []
    for it in g.get("entries", []):
        term_zh = (it.get("term_zh") or "").strip()
        term_ru = (it.get("term_ru") or "").strip()
        status = (it.get("status") or "").lower().strip()
        if term_zh and status in ("approved", "proposed", "banned"):
            entries.append(GlossaryEntry(term_zh, term_ru, status))
    meta = g.get("meta", {})
    return entries, meta.get("compiled_hash")


def build_glossary_summary(glossary: List[GlossaryEntry], max_entries: int = 50) -> str:
    approved = [e for e in glossary if e.status == "approved"][:max_entries]
    if not approved:
        return "(无)"
    return "\n".join([f"- {e.term_zh} → {e.term_ru}" for e in approved])


def build_glossary_constraints(glossary: List[GlossaryEntry], source_zh: str) -> Dict[str, str]:
    approved = {}
    for e in glossary:
        if e.term_zh and e.term_zh in source_zh and e.status == "approved":
            approved[e.term_zh] = e.term_ru
    return approved


# -----------------------------
# CSV / Checkpoint
# -----------------------------
def read_csv_rows(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def append_csv_rows(path: str, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    exists = Path(path).exists()
    with open(path, "a" if exists else "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            w.writeheader()
        w.writerows(rows)


def load_checkpoint(path: str) -> dict:
    if Path(path).exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"done_ids": {}, "stats": {"ok": 0, "escalated": 0}, "batch_idx": 0}


def save_checkpoint(path: str, ckpt: dict) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(ckpt, f, ensure_ascii=False, indent=2)


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


def backoff_sleep(attempt: int) -> None:
    time.sleep(min(2 ** attempt, 30) * random.uniform(0.5, 1.5))


# -----------------------------
# Prompt Builder (Hardened)
# -----------------------------
def build_system_prompt(style_guide: str, glossary_summary: str) -> str:
    """Build system prompt for translation."""
    return (
        '你是严谨的手游本地化译者（zh-CN → ru-RU）。\n\n'
        '【Output Contract v6 - 强制要求】\n'
        '1. Output MUST be valid JSON (Array of Objects).\n'
        '2. Top-level structure MUST be an Array `[...]`, NOT an Object `{"key": [...]}`.\n'
        '3. Each object MUST contain keys: "string_id", "target_ru".\n'
        '4. Every input "string_id" MUST appear in the output. Do not skip items.\n'
        '5. If translation fails, return empty string "" for "target_ru".\n'
        '6. Do NOT wrap the array in markdown blocks or keys.\n\n'
        '【Translation Rules】\n'
        '- 术语表中 term_zh → term_ru 必须严格使用。\n'
        '- 占位符 ⟦PH_xx⟧ / ⟦TAG_xx⟧ 必须原样保留。\n'
        '- 禁止中文括号【】，用 «» 或 "X: …" 替代。\n'
        '- 空字符串源文输出空字符串。\n\n'
        '【Example Output】\n'
        '[{"string_id": "1", "target_ru": "Текст ⟦PH_0⟧"}, {"string_id": "2", "target_ru": ""}]\n\n'
        f'术语表摘要：\n{glossary_summary[:1500]}\n\n'
        f'style_guide：\n{style_guide[:1000]}\n'
    )


STRUCTURE_REPAIR_PROMPT = """Fix the JSON STRUCTURE ONLY.

Requirements:
- Preserve all text content exactly.
- Output MUST be a JSON ARRAY of objects.
- Each object MUST contain: string_id, target_ru.
- Do NOT translate or rewrite content.
- Do NOT add or remove items.

Return ONLY valid JSON."""


def build_batch_input(rows: List[Dict[str, str]], glossary: List[GlossaryEntry]) -> List[Dict[str, Any]]:
    batch_items = []
    for row in rows:
        source_zh = row.get("tokenized_zh") or row.get("source_zh") or ""
        approved = build_glossary_constraints(glossary, source_zh)
        item = {"string_id": row.get("string_id", ""), "tokenized_zh": source_zh}
        if approved:
            item["glossary_hint"] = "; ".join([f"{k}→{v}" for k, v in list(approved.items())[:5]])
        batch_items.append(item)
    return batch_items


# -----------------------------
# Batch Result
# -----------------------------
@dataclass
class BatchResult:
    batch_idx: int
    planned_batch_size: int
    effective_batch_size: int = 0
    success_rows: List[Dict[str, str]] = field(default_factory=list)
    escalated_rows: List[Dict[str, str]] = field(default_factory=list)
    inflight_at_submit: int = 0
    latency_ms: int = 0
    completion_tokens: int = 0
    max_tokens_used: int = 0
    structure_repair_attempted: bool = False
    error_type: Optional[str] = None


# -----------------------------
# Worker Function
# -----------------------------
def process_batch_worker(
    batch: List[Dict[str, str]],
    batch_idx: int,
    glossary: List[GlossaryEntry],
    style_guide: str,
    glossary_summary: str,
    max_retries: int,
    inflight_tracker: InflightTracker
) -> BatchResult:
    """Worker: creates own LLMClient, returns BatchResult, NO file writes."""
    planned_size = len(batch)
    result = BatchResult(batch_idx=batch_idx, planned_batch_size=planned_size)
    
    if not batch:
        return result
    
    # Dynamic max_tokens
    max_tokens = int(planned_size * EXPECTED_TOKENS_PER_ROW * COMPLETION_MARGIN)
    result.max_tokens_used = max_tokens
    
    # Per-worker LLMClient
    try:
        llm = LLMClient()
    except LLMError as e:
        result.error_type = f"client_init: {e.kind}"
        for row in batch:
            result.escalated_rows.append({
                "string_id": row.get("string_id", ""),
                "reason": f"client_init_failed",
                "batch_idx": str(batch_idx)
            })
        return result
    
    system_prompt = build_system_prompt(style_guide, glossary_summary)
    batch_input = build_batch_input(batch, glossary)
    user_prompt = json.dumps(batch_input, ensure_ascii=False)
    id_to_row = {r.get("string_id", ""): r for r in batch}
    
    inflight_count = inflight_tracker.acquire()
    result.inflight_at_submit = inflight_count
    start_time = time.time()
    
    try:
        for attempt in range(max_retries + 1):
            try:
                llm_result = llm.chat(
                    system=system_prompt,
                    user=user_prompt,
                    temperature=0.1,
                    max_tokens=max_tokens,
                    metadata={
                        "step": "translate",
                        "batch_idx": batch_idx,
                        "planned_batch_size": planned_size,
                        "effective_batch_size": planned_size,
                        "inflight_at_submit": inflight_count,
                        "max_tokens": max_tokens,
                        "inflight_at_submit": inflight_count,
                        "max_tokens": max_tokens,
                        "attempt": attempt,
                        "is_batch": True  # Signal to Runtime for capability check
                    }
                    # Note: removed response_format={type:json_object} as it forces object output
                )
                
                result.latency_ms = llm_result.latency_ms
                result.effective_batch_size = planned_size
                if llm_result.usage:
                    result.completion_tokens = llm_result.usage.get("completion_tokens", 0)
                
                # Parse JSON
                parsed = parse_json_array(llm_result.text)
                
                if parsed is None:
                    # Try extracting from object if LLM returned wrong format
                    try:
                        obj = json.loads(llm_result.text.strip())
                        if isinstance(obj, dict):
                            # Case 1: Single item with correct keys {"string_id": "1", "target_ru": "..."}
                            if "string_id" in obj and "target_ru" in obj:
                                parsed = [obj]
                            # Case 2: Wrapper object with array inside {"results": [...]}
                            elif "results" in obj and isinstance(obj["results"], list):
                                parsed = obj["results"]
                            elif "translations" in obj and isinstance(obj["translations"], list):
                                parsed = obj["translations"]
                            elif "items" in obj and isinstance(obj["items"], list):
                                parsed = obj["items"]
                            # Case 3: Key-value map {"1": "text", "2": "text"}
                            else:
                                parsed = [{"string_id": str(k), "target_ru": str(v)} for k, v in obj.items()]
                    except:
                        pass
                
                if parsed is None:
                    if attempt >= max_retries:
                        result.error_type = "parse_failed"
                        break
                    backoff_sleep(attempt)
                    continue
                
                # Schema validation
                valid, schema_error = validate_batch_schema(parsed)
                
                if not valid:
                    # Structure-repair retry (1 attempt only)
                    if not result.structure_repair_attempted:
                        result.structure_repair_attempted = True
                        try:
                            repair_result = llm.chat(
                                system=STRUCTURE_REPAIR_PROMPT,
                                user=f"Fix this JSON:\n{llm_result.text[:4000]}",
                                temperature=0.0,
                                max_tokens=max_tokens,
                                metadata={
                                    "step": "translate",
                                    "batch_idx": batch_idx,
                                    "repair_attempt": True
                                }
                            )
                            repaired = parse_json_array(repair_result.text)
                            if repaired:
                                valid2, _ = validate_batch_schema(repaired)
                                if valid2:
                                    parsed = repaired
                                    valid = True
                        except:
                            pass
                    
                    if not valid:
                        if attempt >= max_retries:
                            result.error_type = f"schema_violation_after_retry: {schema_error}"
                            break
                        backoff_sleep(attempt)
                        continue
                
                # Match and validate translations
                matched_ids = set()
                for item in parsed:
                    sid = str(item.get("string_id", ""))
                    target_ru = item.get("target_ru", "")
                    
                    if sid not in id_to_row:
                        continue
                    
                    original = id_to_row[sid]
                    source_zh = original.get("tokenized_zh") or original.get("source_zh") or ""
                    ok, _ = validate_translation(source_zh, target_ru)
                    
                    if ok:
                        out_row = dict(original)
                        out_row["target_text"] = target_ru
                        result.success_rows.append(out_row)
                        matched_ids.add(sid)
                
                missing = set(id_to_row.keys()) - matched_ids
                if not missing:
                    return result
                
                # Has missing items - update working batch to only missing items for next attempt
                # Has missing items - retry logic
                if attempt < max_retries:
                    # Retry 1+: Rebuild batch with only missing items
                    batch = [id_to_row[sid] for sid in missing]
                    batch_input = build_batch_input(batch, glossary)
                    user_prompt = json.dumps(batch_input, ensure_ascii=False)
                    id_to_row = {r.get("string_id", ""): r for r in batch}
                    max_tokens = int(len(batch) * EXPECTED_TOKENS_PER_ROW * COMPLETION_MARGIN)
                    backoff_sleep(attempt)
                    continue
                
                # Max retries reached - Try ONE FINAL ESCALATION (Fallback Repair)
                # Use 'repair_hard' step which maps to strong model (e.g. Sonnet)
                try:
                    batch = [id_to_row[sid] for sid in missing]
                    batch_input = build_batch_input(batch, glossary)
                    user_prompt = json.dumps(batch_input, ensure_ascii=False)
                    
                    fallback_res = llm.chat(
                        system=system_prompt,
                        user=user_prompt,
                        temperature=0.0,
                        max_tokens=max_tokens,
                        metadata={
                            "step": "repair_hard", # Force fallback model
                            "batch_idx": batch_idx,
                            "planned_batch_size": len(batch),
                            "is_batch": True,
                            "reason": "missing_id_fallback"
                        }
                    )
                    
                    # Parse Fallback Result
                    fallback_parsed = parse_json_array(fallback_res.text)
                    if fallback_parsed:
                         for item in fallback_parsed:
                            sid = str(item.get("string_id", ""))
                            target_ru = item.get("target_ru", "")
                            if sid in missing:
                                original = id_to_row[sid]
                                ok, _ = validate_translation(original.get("tokenized_zh",""), target_ru)
                                if ok:
                                    out_row = dict(original)
                                    out_row["target_text"] = target_ru
                                    result.success_rows.append(out_row)
                                    missing.remove(sid)
                except Exception:
                    pass # Fallback failed, proceed to escalate remaining
                
                # Final Escalation of stubbornly missing items
                for sid in missing:
                    result.escalated_rows.append({
                        "string_id": sid,
                        "reason": "missing_after_fallback_repair",
                        "batch_idx": str(batch_idx)
                    })
                return result
                
            except LLMError as e:
                if not e.retryable or attempt >= max_retries:
                    result.error_type = f"llm_{e.kind}"
                    for row in batch:
                        result.escalated_rows.append({
                            "string_id": row.get("string_id", ""),
                            "reason": f"llm_error: {e.kind}",
                            "batch_idx": str(batch_idx)
                        })
                    return result
                backoff_sleep(attempt)
        
        # If loop finished without return, escalate remaining
        if result.error_type:
            for row in batch:
                if row.get("string_id") not in [r.get("string_id") for r in result.success_rows]:
                    result.escalated_rows.append({
                        "string_id": row.get("string_id", ""),
                        "reason": result.error_type,
                        "batch_idx": str(batch_idx)
                    })
                    
    finally:
        inflight_tracker.release()
        result.latency_ms = int((time.time() - start_time) * 1000)
    
    return result


# -----------------------------
# Progress Formatting
# -----------------------------
def format_time(seconds: float) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def format_batch_progress(
    completed: int, 
    total: int, 
    inflight: int,
    elapsed: float,
    avg_batch_time: float
) -> str:
    pct = completed / total * 100 if total > 0 else 0
    eta = avg_batch_time * (total - completed) if completed > 0 else 0
    return (
        f"[PROGRESS]\n"
        f"  Batches: {completed} / {total} ({pct:.1f}%)\n"
        f"  Inflight: {inflight}\n"
        f"  Elapsed: {format_time(elapsed)}\n"
        f"  ETA: {format_time(eta)}\n"
        f"  Avg batch time: {avg_batch_time:.1f}s"
    )


# -----------------------------
# Main
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="LLM Translate v5.0 (Structured Output)")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--style", default="workflow/style_guide.md")
    parser.add_argument("--glossary", default="data/glossary.yaml")
    parser.add_argument("--escalate_csv", default="data/escalate_list.csv")
    parser.add_argument("--checkpoint", default="data/translate_checkpoint.json")
    parser.add_argument("--batch_size", type=int, default=10)
    parser.add_argument("--max_batch_tokens", type=int, default=6000)
    parser.add_argument("--max_concurrent", type=int, default=6)
    parser.add_argument("--max_retries", type=int, default=2)
    parser.add_argument("--progress_every", type=int, default=5)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    
    print(f"🚀 Translate LLM v5.0 (Structured Output Contract)")
    print(f"   Batch size: {args.batch_size}, Concurrent: {args.max_concurrent}")
    print()
    
    # Load resources
    style_guide = load_style_guide(args.style)
    glossary, _ = load_glossary(args.glossary)
    glossary_summary = build_glossary_summary(glossary)
    
    if not Path(args.input).exists():
        print(f"❌ Input not found: {args.input}")
        sys.exit(1)
    
    rows = read_csv_rows(args.input)
    for i, row in enumerate(rows):
        if "row_index" not in row:
            row["row_index"] = str(i)
    
    print(f"✅ Loaded {len(rows)} rows")
    
    if args.dry_run:
        config = BatchConfig(max_items=args.batch_size, max_tokens=args.max_batch_tokens)
        batches = split_into_batches(rows, config)
        print(f"[DRY-RUN] Would create {len(batches)} batches")
        return
    
    # Checkpoint
    ckpt = load_checkpoint(args.checkpoint)
    done_ids = ckpt.get("done_ids", {})
    pending = [r for r in rows if r.get("string_id") not in done_ids]
    print(f"   Pending: {len(pending)}")
    
    if not pending:
        print("✅ All done.")
        return
    
    # LLM check
    try:
        test_llm = LLMClient()
        print(f"✅ LLM: {test_llm.default_model}")
    except Exception as e:
        print(f"❌ LLM init failed: {e}")
        sys.exit(1)
    
    # Split batches
    config = BatchConfig(max_items=args.batch_size, max_tokens=args.max_batch_tokens)
    batches = split_into_batches(pending, config)
    print(f"   Batches: {len(batches)}")
    print()
    
    # Output fields
    sample_fields = list(rows[0].keys())
    if "target_text" not in sample_fields:
        sample_fields.append("target_text")
    esc_fields = ["string_id", "reason", "batch_idx"]
    
    # Tracker
    inflight = InflightTracker()
    
    # Process
    start_time = time.time()
    ok_count = ckpt.get("stats", {}).get("ok", 0)
    esc_count = ckpt.get("stats", {}).get("escalated", 0)
    batches_done = 0
    results_buffer = {}
    next_write = 0
    
    with ThreadPoolExecutor(max_workers=args.max_concurrent) as executor:
        futures = {
            executor.submit(
                process_batch_worker, batch, idx,
                glossary, style_guide, glossary_summary,
                args.max_retries, inflight
            ): idx for idx, batch in enumerate(batches)
        }
        
        for future in as_completed(futures):
            idx = futures[future]
            try:
                res = future.result()
            except Exception as e:
                res = BatchResult(batch_idx=idx, planned_batch_size=len(batches[idx]))
                res.error_type = f"exception: {str(e)[:50]}"
                for row in batches[idx]:
                    res.escalated_rows.append({
                        "string_id": row.get("string_id", ""),
                        "reason": f"worker_exception",
                        "batch_idx": str(idx)
                    })
            
            results_buffer[idx] = res
            batches_done += 1
            
            # Write in order
            while next_write in results_buffer:
                r = results_buffer.pop(next_write)
                if r.success_rows:
                    sorted_rows = sorted(r.success_rows, key=lambda x: int(x.get("row_index", 0)))
                    append_csv_rows(args.output, sample_fields, sorted_rows)
                    for row in sorted_rows:
                        done_ids[row.get("string_id", "")] = True
                        ok_count += 1
                if r.escalated_rows:
                    append_csv_rows(args.escalate_csv, esc_fields, r.escalated_rows)
                    for row in r.escalated_rows:
                        done_ids[row.get("string_id", "")] = True
                        esc_count += 1
                ckpt["done_ids"] = done_ids
                ckpt["stats"] = {"ok": ok_count, "escalated": esc_count}
                ckpt["batch_idx"] = next_write + 1
                save_checkpoint(args.checkpoint, ckpt)
                next_write += 1
            
            # Progress
            elapsed = time.time() - start_time
            avg_batch = elapsed / batches_done if batches_done > 0 else 0
            if batches_done % args.progress_every == 0 or batches_done == len(batches):
                print(format_batch_progress(
                    batches_done, len(batches), inflight.current, elapsed, avg_batch
                ))
    
    # Summary
    elapsed = time.time() - start_time
    rate = (ok_count + esc_count) / elapsed if elapsed > 0 else 0
    esc_rate = esc_count / (ok_count + esc_count) * 100 if (ok_count + esc_count) > 0 else 0
    
    print()
    print(f"✅ Complete!")
    print(f"   OK: {ok_count}")
    print(f"   Escalated: {esc_count} ({esc_rate:.1f}%)")
    print(f"   Time: {format_time(elapsed)}")
    print(f"   Peak inflight: {inflight.peak}")
    print(f"   Throughput: {rate * 60:.1f} rows/min")


if __name__ == "__main__":
    # Ensure UTF-8 output on Windows
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    main()
