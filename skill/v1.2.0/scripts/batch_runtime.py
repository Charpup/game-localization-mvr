#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
batch_runtime.py
Shared batch processing runtime for translating tokenized Chinese strings.
Contains:
- Worker logic (process_batch_worker)
- JSON Schema validation
- Inflight tracking
- Structure repair
- EMPTY GATE V2 SHORT-CIRCUIT
"""

import json
import re
import time
import random
import threading
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any

try:
    import jsonschema
except ImportError:
    jsonschema = None
    # print("WARNING: jsonschema not installed. Schema validation disabled.")

try:
    from runtime_adapter import LLMClient, LLMError
except ImportError:
    LLMClient = None
    LLMError = Exception

try:
    from batch_utils import parse_json_array
except ImportError:
    # Minimal fallback if batch_utils invalid
    def parse_json_array(text):
        try:
             # Basic regex to find array
            match = re.search(r'\[.*\]', text, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            return json.loads(text)
        except:
            return None

TOKEN_RE = re.compile(r"⟦(PH_\d+|TAG_\d+)⟧")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# JSON Schema for Batch Output
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

# Token estimation
EXPECTED_TOKENS_PER_ROW = 40
COMPLETION_MARGIN = 1.3

@dataclass
class GlossaryEntry:
    term_zh: str
    term_ru: str
    status: str
    notes: str = ""

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
    empty_short_circuit: bool = False  # Track if short-circuit was used
    sent_to_llm_count: int = 0         # Verification hook: how many rows were actually sent

class InflightTracker:
    def __init__(self):
        self._lock = threading.Lock()
        self._val = 0

    def acquire(self) -> int:
        with self._lock:
            self._val += 1
            return self._val

    def release(self) -> None:
        with self._lock:
            self._val -= 1

# ... (Lines 218-226)

# -----------------------------
# Validation & Logic
# -----------------------------

def validate_batch_schema(data: Any) -> Tuple[bool, str]:
    """Validate parsed JSON against batch output schema."""
    if jsonschema is None:
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
    # Strict empty check: if source was not empty but result is empty -> fail? 
    # Current logic: allows empty result if source is empty.
    # Logic below handles explicit empty source -> empty target mapping.
    if not (ru or "").strip() and (tokenized_zh or "").strip():
        return False, "empty"
    return True, "ok"

def backoff_sleep(attempt: int) -> None:
    time.sleep(min(2 ** attempt, 30) * random.uniform(0.5, 1.5))

def build_glossary_constraints(glossary: List[GlossaryEntry], source_zh: str) -> Dict[str, str]:
    approved = {}
    for e in glossary:
        if e.term_zh and e.term_zh in source_zh and e.status == "approved":
            approved[e.term_zh] = e.term_ru
    return approved

def build_system_prompt(style_guide: str, glossary_summary: str) -> str:
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
# Core Worker
# -----------------------------

def process_batch_worker(
    batch: List[Dict[str, str]],
    batch_idx: int,
    glossary: List[GlossaryEntry],
    style_guide: str,
    glossary_summary: str,
    max_retries: int,
    inflight_tracker: InflightTracker,
    disable_short_circuit: bool = False  # Feature Flag
) -> BatchResult:
    """
    Worker: creates own LLMClient, returns BatchResult.
    IMPLEMENTS EMPTY GATE V2 SHORT-CIRCUIT (Optional).
    """
    planned_size = len(batch)
    result = BatchResult(batch_idx=batch_idx, planned_batch_size=planned_size)
    
    if not batch:
        return result

    # -----------------------------
    # Empty Gate V2 Short-Circuit
    # -----------------------------
    empty_rows = []
    active_rows = []
    
    # If disabled, treat everything as active (bypass extraction)
    if disable_short_circuit:
        active_rows = list(batch)
    else:
        # Default V2 behavior: extract empty rows
        for row in batch:
            src = row.get("tokenized_zh") or row.get("source_zh") or ""
            if not src.strip():
                 empty_rows.append(row)
            else:
                 active_rows.append(row)
                 
        # Handle empty rows immediately
        if empty_rows:
            result.empty_short_circuit = True 
            for row in empty_rows:
                result.success_rows.append({
                    **row,
                    "target_text": "", 
                    "status": "empty", 
                    "llm_skipped": "true"
                })
            
    # If no active rows, we can return early
    if not active_rows:
        result.effective_batch_size = 0
        return result
    
    # Record verification metric
    result.sent_to_llm_count = len(active_rows)

    # -----------------------------
    # Active Rows Processing (LLM)
    # -----------------------------
    
    # Update batch to only be active rows for LLM part
    # We still track original batch_idx, but the processing logic operates on subset
    # NOTE: Complex mapping logic needed if we want to support partial batch LLM calls strictly.
    # Current simplistic approach: if partial, we process active_rows as the batch.
    
    current_batch = active_rows
    # Need id_to_row lookup for result mapping
    id_to_row = {r.get("string_id", ""): r for r in current_batch}
    
    # Dynamic max_tokens
    max_tokens = int(len(current_batch) * EXPECTED_TOKENS_PER_ROW * COMPLETION_MARGIN)
    result.max_tokens_used = max_tokens
    
    # Per-worker LLMClient
    try:
        llm = LLMClient()
    except LLMError as e:
        result.error_type = f"client_init: {e.kind}"
        for row in current_batch:
            result.escalated_rows.append({
                "string_id": row.get("string_id", ""),
                "reason": f"client_init_failed",
                "batch_idx": str(batch_idx)
            })
        return result
    
    system_prompt = build_system_prompt(style_guide, glossary_summary)
    batch_input = build_batch_input(current_batch, glossary)
    user_prompt = json.dumps(batch_input, ensure_ascii=False)
    
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
                        "planned_batch_size": len(current_batch),
                        "effective_batch_size": len(current_batch),
                        "inflight_at_submit": inflight_count,
                        "max_tokens": max_tokens,
                        "attempt": attempt,
                        "is_batch": True 
                    }
                )
                
                result.latency_ms = llm_result.latency_ms
                result.effective_batch_size = len(current_batch)
                if llm_result.usage:
                    result.completion_tokens += llm_result.usage.get("completion_tokens", 0)
                
                parsed = parse_json_array(llm_result.text)
                
                if parsed is None:
                     # Attempt object extraction fallbacks
                    try:
                        obj = json.loads(llm_result.text.strip())
                        if isinstance(obj, dict):
                            if "string_id" in obj and "target_ru" in obj: parsed = [obj]
                            elif "results" in obj and isinstance(obj["results"], list): parsed = obj["results"]
                            elif "translations" in obj and isinstance(obj["translations"], list): parsed = obj["translations"]
                            elif "items" in obj and isinstance(obj["items"], list): parsed = obj["items"]
                            else: parsed = [{"string_id": str(k), "target_ru": str(v)} for k, v in obj.items()]
                    except: pass
                
                if parsed is None:
                    if attempt >= max_retries:
                        result.error_type = "parse_failed"
                        break
                    backoff_sleep(attempt)
                    continue
                
                valid, schema_error = validate_batch_schema(parsed)
                
                if not valid:
                    if not result.structure_repair_attempted:
                        result.structure_repair_attempted = True
                        try:
                            repair_result = llm.chat(
                                system=STRUCTURE_REPAIR_PROMPT,
                                user=f"Fix this JSON:\n{llm_result.text[:4000]}",
                                temperature=0.0,
                                max_tokens=max_tokens,
                                metadata={"step": "translate", "batch_idx": batch_idx, "repair_attempt": True}
                            )
                            repaired = parse_json_array(repair_result.text)
                            if repaired and validate_batch_schema(repaired)[0]:
                                parsed = repaired
                                valid = True
                        except: pass
                    
                    if not valid:
                        if attempt >= max_retries:
                            result.error_type = f"schema_violation: {schema_error}"
                            break
                        backoff_sleep(attempt)
                        continue
                
                matched_ids = set()
                for item in parsed:
                    sid = str(item.get("string_id", ""))
                    target_ru = item.get("target_ru", "")
                    
                    if sid not in id_to_row:
                        continue
                        
                    original = id_to_row[sid]
                    source_zh = original.get("tokenized_zh") or original.get("source_zh") or ""
                    
                    # Logic note: if original was empty, it should have been caught by short-circuit.
                    # But if we are here, it's non-empty.
                    ok, _ = validate_translation(source_zh, target_ru)
                    
                    if ok:
                        out_row = dict(original)
                        out_row["target_text"] = target_ru
                        result.success_rows.append(out_row)
                        matched_ids.add(sid)
                
                missing = set(id_to_row.keys()) - matched_ids
                if not missing:
                    return result # Success for this subset of current_batch
                
                # Retry missing
                if attempt < max_retries:
                    current_batch = [id_to_row[sid] for sid in missing]
                    batch_input = build_batch_input(current_batch, glossary)
                    user_prompt = json.dumps(batch_input, ensure_ascii=False)
                    id_to_row = {r.get("string_id", ""): r for r in current_batch}
                    max_tokens = int(len(current_batch) * EXPECTED_TOKENS_PER_ROW * COMPLETION_MARGIN)
                    backoff_sleep(attempt)
                    continue
                
                # Fallback repair logic omitted for brevity in V1 extraction, assuming main flow is enough.
                # Adding simplified final fallback or escalation.
                for sid in missing:
                    result.escalated_rows.append({
                        "string_id": sid,
                        "reason": "missing_after_retries",
                        "batch_idx": str(batch_idx)
                    })
                return result
                
            except LLMError as e:
                if not e.retryable or attempt >= max_retries:
                    result.error_type = f"llm_{e.kind}"
                    for row in current_batch:
                        result.escalated_rows.append({
                            "string_id": row.get("string_id",""),
                            "reason": f"llm_error: {e.kind}",
                            "batch_idx": str(batch_idx)
                        })
                    return result
                backoff_sleep(attempt)
                
        # End of retries
        if result.error_type:
             for row in current_batch:
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
