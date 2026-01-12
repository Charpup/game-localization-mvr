#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
translate_llm.py
Purpose:
  Translate tokenized Chinese strings (tokenized_zh) into target language with:
  - checkpoint/resume
  - retry + exponential backoff
  - fallback to escalate list after repeated failures
  - glossary.yaml (approved hard, banned hard, proposed soft)
  - style_guide.md guidance

Usage:
  python scripts/translate_llm.py \
    data/draft.csv data/translated.csv \
    workflow/style_guide.md data/glossary.yaml \
    --target ru-RU --batch_size 50 --max_retries 4

Environment (OpenAI-compatible):
  LLM_BASE_URL   e.g. https://api.openai.com/v1 (or your internal compatible gateway)
  LLM_API_KEY    your key/token
  LLM_MODEL      e.g. gpt-4.1-mini / gpt-4o-mini / claude-compatible gateway model name
Optional:
  LLM_TIMEOUT_S  default 60
"""

import argparse
import csv
import json
import os
import random
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Use shared runtime adapter for LLM calls
from runtime_adapter import LLMClient, LLMError, LLMResult

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

def load_style_guide(path: str) -> str:
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
    """
    Load glossary from YAML.
    
    Supports multiple formats:
    - compiled.yaml: {"entries": [{term_zh, term_ru, scope}]}
    - approved.yaml: {"entries": [{term_zh, term_ru, status, ...}]}
    - Legacy: {"candidates": [...]}
    
    Returns: (entries, glossary_hash)
    """
    if not path or not Path(path).exists():
        return [], None
    if yaml is None:
        raise RuntimeError("PyYAML is required. Install with: pip install pyyaml")
    
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    entries: List[GlossaryEntry] = []
    glossary_hash = None
    
    # Try to load lock file for version info
    lock = load_glossary_lock(path)
    if lock:
        glossary_hash = lock.get("hash", "")
    
    # Support multiple shapes:
    # 1) compiled.yaml format: {"entries": [{term_zh, term_ru, scope}]}
    # 2) approved.yaml format: {"entries": [{term_zh, term_ru, status, notes}]}
    # 3) Legacy candidates: {"candidates": [{term_zh, ru_suggestion, status, notes}]}
    if isinstance(data, dict) and "entries" in data and isinstance(data["entries"], list):
        src = data["entries"]
        for it in src:
            term_zh = (it.get("term_zh") or "").strip()
            term_ru = (it.get("term_ru") or "").strip()
            # compiled.yaml has scope but no status - treat as approved
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
    else:
        # If unknown shape, treat as empty to avoid crashing production runs.
        return [], None

    return entries, glossary_hash

def build_glossary_constraints(entries: List[GlossaryEntry], source_text: str) -> Tuple[Dict[str, str], List[str], Dict[str, List[str]]]:
    """
    Return:
      approved_map: zh -> ru (hard)
      banned_terms: list of zh terms (hard forbidden in translation output as ru equivalents are unknown)
      proposed_map: zh -> list of ru suggestions (soft reference)
    Only include entries that appear in source_text to keep prompts small.
    """
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
# LLMClient is now imported from runtime_adapter
# See runtime_adapter.py for implementation
# -----------------------------

# -----------------------------
# Helpers: checkpoint/resume
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
    """
    Hard checks for /loc_translate output (pre-qa_hard):
      - token counts must match
      - must not contain CJK
    """
    if tokens_signature(tokenized_zh) != tokens_signature(ru):
        return False, "token_mismatch"
    if CJK_RE.search(ru or ""):
        return False, "cjk_remaining"
    # basic: empty translation is invalid
    if not (ru or "").strip():
        return False, "empty"
    return True, "ok"

def backoff_sleep(attempt: int) -> None:
    # exponential backoff + jitter, capped
    base = min(2 ** attempt, 30)
    jitter = random.uniform(0.2, 1.0)
    time.sleep(base * jitter)

# -----------------------------
# Prompt builder
# -----------------------------
def build_system_prompt(style_guide: str) -> str:
    return (
        "你是一个严谨的手游本地化译者与校对员。\n"
        "目标：把中文（已包含不可变 token）翻译成俄语（ru-RU），输出必须可直接用于上线。\n"
        "硬约束：任何 token（形如 ⟦PH_1⟧ 或 ⟦TAG_1⟧）必须逐字保留，不能增删改、不能改变顺序。\n"
        "禁止：输出中出现任何中文字符。\n"
        "输出格式：你只输出 JSON（不要额外解释）。\n\n"
        "风格规范（必须遵守）：\n"
        f"{style_guide}\n"
    )

def build_user_prompt(batch: List[Dict[str, str]], glossary_entries: List[GlossaryEntry], target_lang: str) -> str:
    """
    Batch translation. Return JSON mapping string_id -> target_text.
    Glossary constraints injected per-row to keep prompt small.
    """
    items = []
    for r in batch:
        sid = (r.get("string_id") or "").strip()
        tok = r.get("tokenized_zh") or r.get("source_zh") or ""
        approved, banned, proposed = build_glossary_constraints(glossary_entries, tok)

        items.append({
            "string_id": sid,
            "tokenized_zh": tok,
            "glossary_hard": approved,              # zh->ru mandatory
            "glossary_banned_zh": banned,           # zh terms not to invent/rename; treated as "do not creatively rename"
            "glossary_soft": proposed,              # zh->ru suggestions
        })

    return (
        f"请将以下条目翻译为 {target_lang}。\n"
        "要求：\n"
        "1) 只输出 JSON 对象：key=string_id，value=target_text\n"
        "2) 必须保留 token（⟦PH_x⟧/⟦TAG_x⟧）并保持数量一致\n"
        "3) glossary_hard 里的译法必须使用（强制）；glossary_banned_zh 中的术语不要自创别名；glossary_soft 仅参考\n"
        "4) 默认是官方系统文案语域；仅当原文明显是活动/台词语气时才可略口语化\n"
        "5) 不要输出任何解释性文本\n\n"
        "条目：\n"
        + json.dumps(items, ensure_ascii=False, indent=2)
    )

def extract_json_object(text: str) -> Optional[dict]:
    """
    Try to extract a JSON object from model output.
    """
    text = (text or "").strip()
    # direct parse
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    # fallback: find first { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        snippet = text[start:end+1]
        try:
            obj = json.loads(snippet)
            if isinstance(obj, dict):
                return obj
        except Exception:
            return None
    return None

# -----------------------------
# Main pipeline
# -----------------------------
def main():
    ap = argparse.ArgumentParser(description="Translate tokenized Chinese to target language via LLM")
    ap.add_argument("input_draft_csv", help="data/draft.csv")
    ap.add_argument("output_translated_csv", help="data/translated.csv (append/resume)")
    ap.add_argument("style_guide_md", help="workflow/style_guide.md")
    ap.add_argument("glossary_yaml", help="data/glossary.yaml (can be empty/nonexistent)")
    ap.add_argument("--target", default="ru-RU")
    ap.add_argument("--batch_size", type=int, default=50)
    ap.add_argument("--max_retries", type=int, default=4)
    ap.add_argument("--checkpoint", default="data/translate_checkpoint.json")
    ap.add_argument("--escalate_csv", default="data/escalate_list.csv")
    ap.add_argument("--dry-run", action="store_true", 
                    help="Validate configuration without making LLM calls")
    args = ap.parse_args()

    # Load resources
    style_guide = load_style_guide(args.style_guide_md)
    
    # Load glossary with version tracking
    # Priority: glossary/compiled.yaml > data/glossary.yaml (fallback)
    glossary_path = args.glossary_yaml
    glossary_version = None
    
    # Check for compiled glossary first
    compiled_path = Path("glossary/compiled.yaml")
    if compiled_path.exists():
        glossary_path = str(compiled_path)
        print(f"[INFO] Using compiled glossary: {glossary_path}")
    
    glossary, glossary_version = load_glossary(glossary_path) if glossary_path else ([], None)
    if glossary_version:
        print(f"[INFO] Glossary version: {glossary_version}")

    # Dry-run mode: validate without LLM
    if getattr(args, 'dry_run', False):
        print()
        print("=" * 60)
        print("DRY-RUN MODE - Validating configuration")
        print("=" * 60)
        print()
        print(f"[OK] Style guide loaded: {args.style_guide_md} ({len(style_guide)} chars)")
        print(f"[OK] Glossary loaded: {len(glossary)} entries")
        if glossary_version:
            print(f"[OK] Glossary version: {glossary_version}")
        
        # Validate input file
        rows = read_csv_rows(args.input_draft_csv)
        if not rows:
            print(f"[FAIL] No rows in input file: {args.input_draft_csv}")
            sys.exit(1)
        print(f"[OK] Input loaded: {len(rows)} rows")
        
        # Check required columns
        sample = rows[0]
        required = ["string_id", "tokenized_zh"]
        for col in required:
            if col not in sample and (col == "tokenized_zh" and "source_zh" not in sample):
                print(f"[FAIL] Missing required column: {col}")
                sys.exit(1)
        print(f"[OK] Required columns present")
        
        # Validate LLM env vars
        import os
        llm_base = os.getenv("LLM_BASE_URL", "")
        llm_key = os.getenv("LLM_API_KEY", "")
        llm_model = os.getenv("LLM_MODEL", "")
        
        if llm_base and llm_key and llm_model:
            print(f"[OK] LLM config: model={llm_model} base_url={llm_base[:30]}...")
        else:
            missing = []
            if not llm_base: missing.append("LLM_BASE_URL")
            if not llm_key: missing.append("LLM_API_KEY")
            if not llm_model: missing.append("LLM_MODEL")
            print(f"[WARN] Missing LLM env vars: {', '.join(missing)}")
            print(f"       (Required for actual translation, not for dry-run)")
        
        # Show sample prompt
        print()
        print("Sample system prompt (first 500 chars):")
        print("-" * 40)
        sample_system = build_system_prompt(style_guide)
        print(sample_system[:500] + "...")
        print()
        
        print("=" * 60)
        print("[OK] Dry-run validation PASSED")
        print("     Configuration is valid. Ready for actual translation.")
        print("=" * 60)
        sys.exit(0)

    # LLM config - now uses runtime_adapter
    # Environment variables are read by LLMClient automatically
    try:
        llm = LLMClient()
        print(f"[INFO] Using LLM: {llm.model} via {llm.base_url}")
    except LLMError as e:
        print(f"ERROR: {e}")
        print("Set env vars: LLM_BASE_URL, LLM_API_KEY, LLM_MODEL")
        sys.exit(2)

    # Load input
    rows = read_csv_rows(args.input_draft_csv)
    if not rows:
        print("No rows found in input.")
        sys.exit(0)

    # Ensure tokenized_zh exists; if not, fall back to source_zh
    for r in rows:
        if "tokenized_zh" not in r or not (r.get("tokenized_zh") or "").strip():
            r["tokenized_zh"] = r.get("source_zh") or ""

    # Checkpoint
    ckpt = load_checkpoint(args.checkpoint)
    done_ids = ckpt.get("done_ids", {})

    # Prepare output fieldnames
    base_fields = list(rows[0].keys())
    # Ensure required columns exist
    for col in ["string_id", "source_zh", "tokenized_zh"]:
        if col not in base_fields:
            base_fields.append(col)
    out_fields = base_fields + (["target_text"] if "target_text" not in base_fields else [])

    # If output already exists, also mark done_ids by reading it (makes resume robust even if checkpoint lost)
    if Path(args.output_translated_csv).exists():
        existing = read_csv_rows(args.output_translated_csv)
        for r in existing:
            sid = (r.get("string_id") or "").strip()
            tgt = (r.get("target_text") or "").strip()
            if sid and tgt:
                done_ids[sid] = True

    # Build batches of pending rows
    pending = [r for r in rows if not done_ids.get((r.get("string_id") or "").strip(), False)]
    if not pending:
        print("[OK] All rows already translated. Nothing to do.")
        sys.exit(0)

    print(f"[INFO] total={len(rows)} pending={len(pending)} batch_size={args.batch_size}")

    # Escalate list fields
    esc_fields = ["string_id", "reason", "tokenized_zh", "last_output"]

    # Translate in batches
    i = 0
    while i < len(pending):
        batch = pending[i:i+args.batch_size]

        system = build_system_prompt(style_guide)
        user = build_user_prompt(batch, glossary, args.target)

        # Retry the whole batch; on repeated failure, fallback to per-row attempts, then escalate.
        success_obj = None
        last_err = ""
        for attempt in range(args.max_retries + 1):
            try:
                result = llm.chat(system=system, user=user, metadata={"step": "translate"})
                raw = result.text
                obj = extract_json_object(raw)
                if not obj:
                    last_err = "invalid_json"
                    raise ValueError("Model output is not valid JSON object.")
                success_obj = obj
                break
            except LLMError as e:
                last_err = f"batch_call_failed: {e.kind}: {e}"
                if not e.retryable or attempt >= args.max_retries:
                    break
                backoff_sleep(attempt)
            except Exception as e:
                last_err = f"batch_call_failed: {type(e).__name__}: {e}"
                if attempt >= args.max_retries:
                    break
                backoff_sleep(attempt)

        batch_results: Dict[str, str] = {}
        if success_obj:
            # normalize values to string
            for sid, val in success_obj.items():
                if isinstance(val, str):
                    batch_results[str(sid)] = val
                else:
                    batch_results[str(sid)] = json.dumps(val, ensure_ascii=False)

        # If batch-level failed, do per-row retries to salvage
        if not batch_results or len(batch_results) < len(batch) // 2:
            print(f"[WARN] batch low success ({len(batch_results)}/{len(batch)}). Fallback to per-row retries. reason={last_err}")
            batch_results = {}

            for r in batch:
                sid = (r.get("string_id") or "").strip()
                tok = r.get("tokenized_zh") or ""
                # Build minimal per-row prompt (smaller & more stable)
                approved, banned, proposed = build_glossary_constraints(glossary, tok)
                system = build_system_prompt(style_guide)
                user = (
                    f"翻译为 {args.target}，只输出 JSON：{{\"{sid}\": \"...\"}}。\n"
                    "硬约束：保留 token（⟦PH_x⟧/⟦TAG_x⟧），禁止中文。\n"
                    f"glossary_hard={json.dumps(approved, ensure_ascii=False)}\n"
                    f"glossary_banned_zh={json.dumps(banned, ensure_ascii=False)}\n"
                    f"glossary_soft={json.dumps(proposed, ensure_ascii=False)}\n"
                    f"tokenized_zh={json.dumps(tok, ensure_ascii=False)}"
                )

                per_ok = False
                per_last = ""
                for attempt in range(args.max_retries + 1):
                    try:
                        result = llm.chat(system=system, user=user, metadata={"step": "translate"})
                        raw = result.text
                        obj = extract_json_object(raw)
                        if not obj or sid not in obj:
                            per_last = "invalid_json_or_missing_key"
                            raise ValueError("Missing key in JSON.")
                        ru = obj[sid] if isinstance(obj[sid], str) else json.dumps(obj[sid], ensure_ascii=False)
                        ok, why = validate_translation(tok, ru)
                        if not ok:
                            per_last = why
                            raise ValueError(f"Validation failed: {why}")
                        batch_results[sid] = ru
                        per_ok = True
                        break
                    except LLMError as e:
                        per_last = f"{per_last} | {e.kind}: {e}".strip(" |")
                        if not e.retryable or attempt >= args.max_retries:
                            break
                        backoff_sleep(attempt)
                    except Exception as e:
                        per_last = f"{per_last} | {type(e).__name__}: {e}".strip(" |")
                        if attempt >= args.max_retries:
                            break
                        backoff_sleep(attempt)

                if not per_ok:
                    # escalate this row
                    append_csv_rows(
                        args.escalate_csv,
                        esc_fields,
                        [{
                            "string_id": sid,
                            "reason": f"translate_failed_after_retries: {per_last}",
                            "tokenized_zh": tok,
                            "last_output": "",
                        }]
                    )
                    ckpt["stats"]["fail"] = ckpt.get("stats", {}).get("fail", 0) + 1

        # Write successful translations, validate tokens & CJK, else escalate.
        out_rows = []
        for r in batch:
            sid = (r.get("string_id") or "").strip()
            tok = r.get("tokenized_zh") or ""
            ru = batch_results.get(sid, "").strip()

            if not ru:
                # already escalated in fallback stage, or batch output missing this item
                append_csv_rows(
                    args.escalate_csv,
                    esc_fields,
                    [{
                        "string_id": sid,
                        "reason": "missing_translation_in_batch_output",
                        "tokenized_zh": tok,
                        "last_output": "",
                    }]
                )
                ckpt["stats"]["fail"] = ckpt.get("stats", {}).get("fail", 0) + 1
                continue

            ok, why = validate_translation(tok, ru)
            if not ok:
                # Retry per-row quickly for validation failure
                per_last = why
                fixed = ""
                for attempt in range(args.max_retries):
                    backoff_sleep(attempt)
                    try:
                        approved, banned, proposed = build_glossary_constraints(glossary, tok)
                        system = build_system_prompt(style_guide)
                        user = (
                            f"你上一次输出不符合硬约束（原因：{why}）。请重新翻译为 {args.target}。\n"
                            "只输出 JSON：{\"string_id\": \"target_text\"}，key 必须等于该 string_id。\n"
                            "再次强调：token 必须逐字保留且数量一致；禁止中文。\n"
                            f"string_id={sid}\n"
                            f"glossary_hard={json.dumps(approved, ensure_ascii=False)}\n"
                            f"glossary_banned_zh={json.dumps(banned, ensure_ascii=False)}\n"
                            f"glossary_soft={json.dumps(proposed, ensure_ascii=False)}\n"
                            f"tokenized_zh={json.dumps(tok, ensure_ascii=False)}"
                        )
                        result = llm.chat(system=system, user=user, metadata={"step": "translate"})
                        raw = result.text
                        obj = extract_json_object(raw)
                        if not obj or sid not in obj:
                            per_last = "invalid_json_or_missing_key"
                            continue
                        cand = obj[sid] if isinstance(obj[sid], str) else json.dumps(obj[sid], ensure_ascii=False)
                        ok2, why2 = validate_translation(tok, cand)
                        if ok2:
                            fixed = cand
                            break
                        per_last = why2
                    except Exception as e:
                        per_last = f"{per_last} | {type(e).__name__}: {e}"

                if not fixed:
                    append_csv_rows(
                        args.escalate_csv,
                        esc_fields,
                        [{
                            "string_id": sid,
                            "reason": f"validation_failed_after_retries: {per_last}",
                            "tokenized_zh": tok,
                            "last_output": ru[:300],
                        }]
                    )
                    ckpt["stats"]["fail"] = ckpt.get("stats", {}).get("fail", 0) + 1
                    continue
                ru = fixed

            # success: write to output
            out = dict(r)
            out["target_text"] = ru
            out_rows.append(out)
            done_ids[sid] = True
            ckpt["stats"]["ok"] = ckpt.get("stats", {}).get("ok", 0) + 1

        if out_rows:
            # append to translated.csv for resume safety
            append_csv_rows(args.output_translated_csv, out_fields, out_rows)

        ckpt["done_ids"] = done_ids
        save_checkpoint(args.checkpoint, ckpt)

        i += args.batch_size
        print(f"[PROGRESS] done_ok={ckpt['stats']['ok']} fail={ckpt['stats']['fail']} / remaining={max(0, len(pending)-i)}")

    print(f"[DONE] ok={ckpt['stats']['ok']} fail={ckpt['stats']['fail']}")
    print(f"[FILES] translated={args.output_translated_csv} checkpoint={args.checkpoint} escalate={args.escalate_csv}")

if __name__ == "__main__":
    main()
