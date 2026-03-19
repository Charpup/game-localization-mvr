#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
translate_llm.py (v6.0 - Unified Batch Mode)
Purpose:
  Translate tokenized Chinese strings using the unified batch infrastructure.
  - Supports --model argument
  - Dynamically switches to content_type="long_text" if is_long_text is present
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

def configure_standard_streams() -> None:
    """Configure stdout/stderr only for CLI execution, not on import."""
    if sys.platform != 'win32':
        return
    import io
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if not stream or not hasattr(stream, "buffer"):
            continue
        try:
            wrapped = io.TextIOWrapper(stream.buffer, encoding='utf-8', errors='replace')
            setattr(sys, stream_name, wrapped)
        except Exception:
            pass

try:
    import yaml
except ImportError:
    yaml = None

# Integrated runtime adapter
try:
    from runtime_adapter import LLMClient, LLMError, batch_llm_call, log_llm_progress
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


def derive_target_key(target_lang: str) -> str:
    if not target_lang:
        return "target_ru"
    norm = target_lang.split("-", 1)[0].strip().lower().replace("_", "")
    if not norm:
        return "target_ru"
    return f"target_{norm}"

# -----------------------------
# Prompt Builders
# -----------------------------
def build_system_prompt_factory(style_guide: str, glossary_summary: str, target_lang: str = "ru-RU", target_key: str = "target_ru"):
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
            f'你是严谨的手游本地化译者（zh-CN → {target_lang}）。\n\n'
            '【Output Contract v6】\n'
            '1. Output MUST be valid JSON (Object with "items" key).\n'
            f'2. Structure MUST be: {{"items": [{{"id": "...", "{target_key}": "..."}}]}} \n'
            '3. Every input "id" MUST appear in the output.\n\n'
            '【Translation Rules】\n'
            '- 术语匹配必须一致。\n'
            '- 占位符 ⟦PH_xx⟧ / ⟦TAG_xx⟧ 必须保留。\n'
            '- 保留中文方括号【】与字面量转义序列（例如 "\\n"），不删除、不替换。\n'
            f'{constraint_section}\n'
            f'术语表摘要：\n{glossary_summary}\n\n'
            f'style_guide：\n{style_guide}\n'
        )
    return _builder


def build_repair_system_prompt_factory(
    style_guide: str,
    glossary_summary: str,
    target_lang: str = "ru-RU",
    target_key: str = "target_ru"
) -> Any:
    """专门用于 token 修复场景的更强约束 prompt."""
    def _builder(rows: List[Dict]) -> str:
        base = build_system_prompt_factory(
            style_guide=style_guide,
            glossary_summary=glossary_summary,
            target_lang=target_lang,
            target_key=target_key
        )

        row_rules = []
        for r in rows:
            tokenized = r.get("source_text", "")
            signature = tokens_signature(tokenized)
            signature_text = ", ".join([f"{k}:{v}" for k, v in sorted(signature.items())]) or "none"
            row_rules.append(
                f"- Row {r.get('id')}: KEEP token multiset unchanged. "
                f"Expected: [{signature_text}], and NO extra tokens."
            )

        repair_hint = "\n".join(row_rules)
        return (
            f"{base(rows)}\n"
            "【Hard Repair Guard】\n"
            "1. 不允许改写、移除、增添任何 ⟦PH_xxx⟧ / ⟦TAG_xxx⟧。\n"
            "2. 对每一行，token 的出现次数必须与来源完全一致。\n"
            "3. 允许适度调整翻译词序，但 token 对应关系与总量必须闭合。\n"
            "4. 若无法稳定保持闭合，请保守输出与 source 相同 token 布局（可保留中文），避免新增错误。\n"
            f"{repair_hint}"
        )
    return _builder

def build_user_prompt(rows: List[Dict]) -> str:
    # rows are items prepared for batch_llm_call
    return json.dumps(rows, ensure_ascii=False, indent=2)


def _single_row_retry(row: Dict[str, str], args: argparse.Namespace, target_key: str, style_guide: str,
                      glossary_summary: str, content_type: str) -> Tuple[str, bool, str]:
    """Retry a single row with repair prompt and return translated text + status."""
    sid = str(row.get("string_id") or row.get("id") or "")
    src = row.get("tokenized_zh") or row.get("source_zh") or ""
    repair_row = {"id": sid, "source_text": src}
    repair_prompt = build_repair_system_prompt_factory(
        style_guide=style_guide,
        glossary_summary=glossary_summary,
        target_lang=args.target_lang,
        target_key=target_key
    )

    try:
        repaired_items = batch_llm_call(
            step="translate_repair",
            rows=[repair_row],
            model=args.model,
            system_prompt=repair_prompt,
            user_prompt_template=build_user_prompt,
            content_type=content_type,
            retry=2,
            allow_fallback=True
        )
        if repaired_items:
            candidate = repaired_items[0].get(target_key, "")
            if candidate is None:
                candidate = repaired_items[0].get("target_ru", "")
            if candidate is None:
                candidate = ""
            ok, err = validate_translation(src, candidate)
            if ok:
                return candidate, True, "ok"
            return candidate, False, err
    except Exception as e:
        return "", False, str(e)

    return "", False, "no_repair_output"


def _batch_translate(
    rows: List[Dict],
    args: argparse.Namespace,
    style_guide: str,
    glossary_summary: str,
    target_key: str,
    content_type: str,
    system_prompt_builder,
) -> Dict[str, str]:
    """Run batch translation and return id->translated text map."""
    if not rows:
        return {}

    results = batch_llm_call(
        step="translate",
        rows=rows,
        model=args.model,
        system_prompt=system_prompt_builder,
        user_prompt_template=build_user_prompt,
        content_type=content_type,
        retry=2,
        allow_fallback=True
    )

    out = {}
    for it in results:
        sid = str(it.get("id") or it.get("string_id") or "")
        if not sid:
            continue
        target_text = it.get(target_key)
        if target_text is None:
            target_text = it.get("target_ru", "")
        if target_text is None:
            target_text = ""
        out[sid] = target_text
    return out

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
    configure_standard_streams()
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--style", default="workflow/style_guide.md")
    parser.add_argument("--glossary", default="data/glossary.yaml")
    parser.add_argument("--target-lang", default="ru-RU", help="Target language code, e.g., ru-RU or en-US")
    parser.add_argument("--target-key", default="", help="Result target field, e.g., target_ru / target_en")
    parser.add_argument("--checkpoint", default="data/translate_checkpoint.json")
    parser.add_argument("--batch_size", type=int, default=10) # Used to force specific batch size if needed
    args = parser.parse_args()

    print(f"🚀 Translate LLM v6.0 (Unified Batch Mode)")
    
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

    target_key = args.target_key.strip() or derive_target_key(args.target_lang)
    # Backward compatible column plus language-specific target column.
    for col in ("target_text", "target", target_key, "translate_status", "translate_validation"):
        if col and col not in headers:
            headers.append(col)
    
    # Checkpoint
    done_ids = load_checkpoint(args.checkpoint)
    pending_rows = [r for r in all_rows if r.get("string_id") not in done_ids]
    
    if not pending_rows:
        print("✅ No pending rows to process.")
        return

    print(f"   Total rows: {len(all_rows)}, Pending: {len(pending_rows)}")
    
    # Detect long text per row and mark strict mode for each.
    long_rows = []
    normal_rows = []
    for r in pending_rows:
        if str(r.get("is_long_text", "")).lower() == "true":
            long_rows.append(r)
        else:
            normal_rows.append(r)

    has_long_text = bool(long_rows)
    if has_long_text:
        print(f"   [Tagger Hint] {len(long_rows)} long-text rows will be translated one-by-one with long_text mode.")
    content_type = "long_text" if has_long_text else "normal"
    
    if has_long_text:
        print("   [Tagger Hint] Long text detected. Using content_type='long_text' for lower batch density.")

    # Prepare for batch_llm_call
    batch_inputs_normal = []
    batch_inputs_long = []
    for r in normal_rows:
        src = r.get("tokenized_zh") or r.get("source_zh") or ""
        batch_inputs_normal.append({
            "id": r.get("string_id"),
            "source_text": src
        })
    for r in long_rows:
        src = r.get("tokenized_zh") or r.get("source_zh") or ""
        batch_inputs_long.append({
            "id": r.get("string_id"),
            "source_text": src
        })

    # Execute
    try:
        system_prompt_builder = build_system_prompt_factory(
            style_guide,
            glossary_summary,
            target_lang=args.target_lang,
            target_key=target_key
        )
        
        res_map = {}
        # Normal rows: batch mode
        res_map.update(_batch_translate(
            rows=batch_inputs_normal,
            args=args,
            style_guide=style_guide,
            glossary_summary=glossary_summary,
            target_key=target_key,
            content_type="normal",
            system_prompt_builder=system_prompt_builder
        ))
        # Long rows: strict single-row translate
        for r in batch_inputs_long:
            row_res = _batch_translate(
                rows=[r],
                args=args,
                style_guide=style_guide,
                glossary_summary=glossary_summary,
                target_key=target_key,
                content_type="long_text",
                system_prompt_builder=system_prompt_builder
            )
            res_map.update(row_res)
        
        # Validation and Final output prep
        final_rows = []
        new_done = set()
        for r in pending_rows:
            sid = str(r.get("string_id"))
            translated = res_map.get(sid, "")
            
            # Validation
            ok, err = validate_translation(r.get("tokenized_zh") or r.get("source_zh") or "", translated)
            if not ok:
                row_content_type = "long_text" if str(r.get("is_long_text", "")).lower() == "true" else "normal"
                repair_text, repaired_ok, repair_err = _single_row_retry(
                    row=r,
                    args=args,
                    target_key=target_key,
                    style_guide=style_guide,
                    glossary_summary=glossary_summary,
                    content_type=row_content_type,
                )
                if repaired_ok:
                    translated = repair_text
                    ok = True
                    err = "ok"
                else:
                    # 最后兜底：保留 tokenized 布局，避免阻断后续链路
                    if repair_err:
                        print(f"    Repair check: {repair_err}")
                    translated = r.get("tokenized_zh") or translated or ""
                    err = "fallback_tokenized_layout"
                    ok = False

            r["translate_validation"] = err if not ok else "ok"
            r["translate_status"] = "ok" if ok else "validation_failed"
            if target_key and target_key not in r:
                r[target_key] = ""
            if "target_text" not in r:
                r["target_text"] = ""
            if "target" not in r:
                r["target"] = ""
            if ok:
                # Write to both dynamic target field and legacy target_text for compatibility
                if target_key:
                    r[target_key] = translated
                r["target"] = translated
                r["target_text"] = translated
            else:
                print(f"⚠️  Validation failed for {sid}: {err}")
                print(f"    Target was: {translated[:50]}...")
                # Preserve the row in the output so downstream stages keep row parity.
                # Keep the translated text if present, otherwise retain the existing fallback value.
                if target_key:
                    r[target_key] = translated
                r["target_text"] = translated
                r["target"] = translated

            final_rows.append(r)
            new_done.add(sid)
        
        print(f"DEBUG: Batch processed. New done: {len(new_done)}")
        
        # Write Output
        write_mode = "a" if Path(args.output).exists() else "w"
        with open(args.output, write_mode, encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if write_mode == "w": writer.writeheader()
            writer.writerows(final_rows)
            
        # Update checkpoint
        done_ids.update(new_done)
        save_checkpoint(args.checkpoint, done_ids)
        
        print(f"✅ Translated {len(new_done)} / {len(pending_rows)} rows.")
        
    except Exception as e:
        print(f"❌ Translation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
