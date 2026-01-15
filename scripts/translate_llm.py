#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
translate_llm.py (v2.1 - Concurrent)
Purpose:
  Translate tokenized Chinese strings (tokenized_zh) into target language with:
  - checkpoint/resume
  - retry + exponential backoff
  - fallback to escalate list after repeated failures
  - glossary.yaml (approved hard, banned hard, proposed soft)
  - style_guide.md guidance
  - Controlled concurrency via --max_inflight

Usage:
  python scripts/translate_llm.py \
    --input data/draft.csv \
    --output data/translated.csv \
    --style workflow/style_guide.md \
    --glossary data/glossary.yaml \
    --target ru-RU --max_retries 4 --max_inflight 3

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
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

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


@dataclass
class TranslateResult:
    """Result of processing a single row."""
    idx: int
    string_id: str
    success: bool
    target_text: str = ""
    error_msg: str = ""
    row: Dict[str, str] = field(default_factory=dict)
    queue_wait_ms: int = 0


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
    return {"done_ids": {}, "stats": {"ok": 0, "fail": 0, "skipped": 0}}

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
# Prompt builder
# -----------------------------
def build_system_prompt(style_guide: str) -> str:
    return (
        '你是严谨的手游本地化译者（zh-CN → ru-RU），面向"官方系统文案为主，二次元口语为辅"的火影题材。\n\n'
        '目标：把给定的中文文本翻译成自然、简洁、符合俄语习惯的俄文 UI/系统文本。\n\n'
        '术语表规则（硬性）：\n'
        '- glossary 中出现的 term_zh → term_ru 必须严格使用 term_ru（大小写/词形按 glossary 指定；如需要变格请保持词根一致并优先保持 glossary 形式）。\n'
        '- 若源文包含 term_zh，但译文难以直接套用 term_ru，必须在不破坏占位符的前提下改写句子以容纳 term_ru。\n\n\n'
        '占位符规则（硬性）：\n'
        '- 任何形如 ⟦PH_xx⟧ / ⟦TAG_xx⟧ / {0} / %s 的占位符必须原样保留，不得翻译/改动/增删/移动。\n'
        '- 输出中禁止出现中文括号符号【】；如源文含【】用于分组/强调，俄语侧用 «» 或改写为"X: …"。\n\n\n'
        '输出格式（硬性）：\n'
        '- 只输出最终俄文译文纯文本，不要解释，不要加引号，不要加编号，不要 Markdown。\n'
        '- 若源文为空字符串：输出空字符串（不要输出 null）。\n'
    )

def build_user_prompt(row: Dict[str, str], glossary_entries: List[GlossaryEntry], style_guide_excerpt: str) -> str:
    source_zh = row.get("tokenized_zh") or row.get("source_zh") or ""
    approved, banned, proposed = build_glossary_constraints(glossary_entries, source_zh)
    
    glossary_lines = []
    if approved:
        glossary_lines.append("【强制使用】")
        for k, v in approved.items():
            glossary_lines.append(f"- {k} → {v}")
    if banned:
        glossary_lines.append("【禁止自创】")
        for k in banned:
            glossary_lines.append(f"- {k}")
    if proposed:
        glossary_lines.append("【参考建议】")
        for k, vals in proposed.items():
            glossary_lines.append(f"- {k} → {', '.join(vals)}")
            
    glossary_text = "\n".join(glossary_lines) if glossary_lines else "(无)"

    return (
        "源文（已冻结占位符）：\n"
        f"{source_zh}\n\n"
        "可用术语摘录（如为空则表示无匹配）：\n"
        f"{glossary_text}\n\n"
        "style_guide（节选）：\n"
        f"{style_guide_excerpt[:2000]}\n"
    )

# -----------------------------
# Worker function (runs in thread)
# -----------------------------
def process_row(
    idx: int,
    row: Dict[str, str],
    llm: LLMClient,
    glossary: List[GlossaryEntry],
    style_guide: str,
    max_retries: int,
    submit_time: float,
    inflight_limit: int
) -> TranslateResult:
    """
    Process a single row translation with retries.
    Thread-safe: only reads shared data, returns result object.
    """
    worker_start = time.time()
    queue_wait_ms = int((worker_start - submit_time) * 1000)
    
    sid = (row.get("string_id") or "").strip()
    tok = row.get("tokenized_zh") or row.get("source_zh") or ""
    
    system = build_system_prompt(style_guide)
    user = build_user_prompt(row, glossary, style_guide)

    ru_result = ""
    last_err = ""
    success = False

    for attempt in range(max_retries + 1):
        try:
            result = llm.chat(
                system=system, 
                user=user, 
                metadata={
                    "step": "translate", 
                    "string_id": sid,
                    "queue_wait_ms": queue_wait_ms,
                    "inflight_limit": inflight_limit
                }
            )
            ru = result.text.strip()
            
            ok, why = validate_translation(tok, ru)
            if not ok:
                last_err = why
                raise ValueError(f"Validation failed: {why}")
                
            ru_result = ru
            success = True
            break
        except Exception as e:
            last_err = str(e)
            if attempt >= max_retries:
                break
            backoff_sleep(attempt)

    return TranslateResult(
        idx=idx,
        string_id=sid,
        success=success,
        target_text=ru_result,
        error_msg=last_err,
        row=row,
        queue_wait_ms=queue_wait_ms
    )

# -----------------------------
# Main
# -----------------------------
def main():
    parser = argparse.ArgumentParser(description="LLM Translate (Concurrent)")
    parser.add_argument("--input", required=True, help="Input CSV")
    parser.add_argument("--output", required=True, help="Output Translated CSV")
    parser.add_argument("--style", default="workflow/style_guide.md", help="Style guide")
    parser.add_argument("--glossary", default="data/glossary.yaml", help="Glossary YAML")
    parser.add_argument("--escalate_csv", default="data/escalate_list.csv", help="Escalation CSV")
    parser.add_argument("--checkpoint", default="data/translate_checkpoint.json", help="Checkpoint JSON")
    parser.add_argument("--target", default="ru-RU")
    parser.add_argument("--max_retries", type=int, default=3)
    parser.add_argument("--max_inflight", type=int, default=3, help="Max concurrent requests")
    parser.add_argument("--progress_every", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    
    args = parser.parse_args()
    
    # 1. Load resources
    style_guide = load_style_guide(args.style)
    glossary, gloss_hash = load_glossary(args.glossary)
    
    # 2. Load input
    if not Path(args.input).exists():
        print(f"Input file not found: {args.input}")
        sys.exit(1)
    
    rows = read_csv_rows(args.input)
    print(f"Loaded {len(rows)} rows from {args.input}")
    print(f"Concurrency: max_inflight={args.max_inflight}")
    
    if args.dry_run:
        print("[Dry-Run] Validation passed.")
        print(f"Glossary: {len(glossary)} entries")
        print(f"Style Guide: {len(style_guide)} chars")
        return

    # 3. Checkpoint
    ckpt = load_checkpoint(args.checkpoint)
    done_ids = ckpt["done_ids"]
    
    # 4. Filter pending
    pending = []
    for r in rows:
        sid = (r.get("string_id") or "").strip()
        if sid and not done_ids.get(sid):
            pending.append(r)
            
    print(f"Pending items: {len(pending)}")
    
    if not pending:
        print("All done.")
        return

    # 5. Initialize Output
    sample_fields = list(rows[0].keys())
    if "target_text" not in sample_fields:
        sample_fields.append("target_text")
    
    esc_fields = ["string_id", "reason", "tokenized_zh", "last_output"]

    # 6. Initialize LLM
    if not LLMClient:
        print("runtime_adapter not found. Cannot proceed.")
        sys.exit(1)
        
    try:
        llm = LLMClient()
    except Exception as e:
        print(f"Failed to init LLM: {e}")
        sys.exit(1)

    # 7. Concurrent execution with as_completed + write buffer
    start_time = time.time()
    
    # Write buffer: idx -> TranslateResult
    result_buffer: Dict[int, TranslateResult] = {}
    next_write_idx = 0
    
    ok_count = ckpt["stats"].get("ok", 0)
    fail_count = ckpt["stats"].get("fail", 0)
    
    with ThreadPoolExecutor(max_workers=args.max_inflight) as executor:
        # Submit all tasks
        future_to_idx = {}
        for idx, row in enumerate(pending):
            submit_time = time.time()
            future = executor.submit(
                process_row,
                idx, row, llm, glossary, style_guide, 
                args.max_retries, submit_time, args.max_inflight
            )
            future_to_idx[future] = idx
        
        # Process as completed
        for future in as_completed(future_to_idx):
            try:
                result = future.result()
            except Exception as e:
                # Unexpected error in worker
                idx = future_to_idx[future]
                result = TranslateResult(
                    idx=idx,
                    string_id=pending[idx].get("string_id", ""),
                    success=False,
                    error_msg=f"Worker exception: {e}",
                    row=pending[idx],
                    queue_wait_ms=0
                )
            
            # Store in buffer
            result_buffer[result.idx] = result
            
            # Flush buffer in order
            while next_write_idx in result_buffer:
                res = result_buffer.pop(next_write_idx)
                
                if res.success:
                    out = dict(res.row)
                    out["target_text"] = res.target_text
                    append_csv_rows(args.output, sample_fields, [out])
                    done_ids[res.string_id] = True
                    ok_count += 1
                else:
                    tok = res.row.get("tokenized_zh") or res.row.get("source_zh") or ""
                    append_csv_rows(args.escalate_csv, esc_fields, [{
                        "string_id": res.string_id,
                        "reason": f"translate_failed: {res.error_msg}",
                        "tokenized_zh": tok,
                        "last_output": ""
                    }])
                    fail_count += 1
                
                # Update checkpoint
                ckpt["done_ids"] = done_ids
                ckpt["stats"]["ok"] = ok_count
                ckpt["stats"]["fail"] = fail_count
                save_checkpoint(args.checkpoint, ckpt)
                
                next_write_idx += 1
                
                # Progress reporting
                total_done = ok_count + fail_count
                if total_done % args.progress_every == 0 or next_write_idx >= len(pending):
                    elapsed = time.time() - start_time
                    rate = total_done / elapsed if elapsed > 0 else 0
                    print(f"[PROGRESS] {total_done}/{len(pending)} | elapsed={int(elapsed)}s | rate={rate:.2f}/s")

    total_elapsed = time.time() - start_time
    print(f"[DONE] ok={ok_count} fail={fail_count} | total_time={int(total_elapsed)}s")

if __name__ == "__main__":
    main()
