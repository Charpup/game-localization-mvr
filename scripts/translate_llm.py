#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
translate_llm.py (v6.1 - style profile aware)
Purpose:
  Translate tokenized Chinese strings using unified batch interface.
  Adds style-contract hard rules from data/style_profile.yaml.
"""

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def configure_standard_streams() -> None:
    if sys.platform != "win32":
        return
    import io

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream and hasattr(stream, "buffer"):
            try:
                setattr(sys, stream_name, io.TextIOWrapper(stream.buffer, encoding="utf-8", errors="replace"))
            except Exception:
                pass


try:
    import yaml
except ImportError:
    yaml = None

try:
    from runtime_adapter import LLMClient, LLMError, batch_llm_call
except ImportError:
    print("ERROR: scripts/runtime_adapter.py not found.")
    sys.exit(1)


TOKEN_RE = re.compile(r"⟦(PH_\d+|TAG_\d+)⟧")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


@dataclass
class GlossaryEntry:
    term_zh: str
    term_ru: str
    status: str
    notes: str = ""


def load_text(path: str) -> str:
    if not Path(path).exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
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
        notes = (it.get("notes") or "").strip()
        if term_zh and status in {"approved", "proposed", "banned"}:
            entries.append(GlossaryEntry(term_zh=term_zh, term_ru=term_ru, status=status, notes=notes))

    return entries, (g.get("meta") or {}).get("compiled_hash")


def load_style_profile(path: str) -> Dict[str, Any]:
    if not path or not Path(path).exists() or yaml is None:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def build_glossary_summary(glossary: List[GlossaryEntry]) -> str:
    if not glossary:
        return "(无)"
    return "\n".join([f"- {e.term_zh} → {e.term_ru}" for e in glossary[:80] if e.status == "approved"])


def build_style_contract(profile: Dict[str, Any]) -> str:
    if not profile:
        return "Style profile unavailable, apply workflow/style_guide.md only."

    project = profile.get("project", {}) or {}
    contract = profile.get("style_contract", {}) or {}
    style_guard = contract.get("style_guard", {}) or {}
    language_policy = contract.get("language_policy", {}) or {}
    placeholder = contract.get("placeholder_protection", {}) or {}
    terminology = profile.get("terminology", {}) or {}
    ui = profile.get("ui", {}) or {}
    segments = profile.get("segmentation", {}) or {}
    units = profile.get("units", {}) or {}
    char_policy = ui.get("length_constraints", {}) or {}

    forbidden_terms = terminology.get("forbidden_terms", []) or []
    preferred_terms = terminology.get("preferred_terms", []) or []

    lines = [
        "【Project Style Contract】",
        f"- Source: {project.get('source_language', 'zh-CN')} → {project.get('target_language', 'ru-RU')}",
        f"- Domain hint: {segments.get('domain_hint', 'game')}",
        f"- Preserve placeholder tokens: {placeholder.get('preserve_ph_tokens', True)}",
        f"- Preserve markup: {placeholder.get('preserve_markup', True)}",
        f"- Protected token patterns: {', '.join(placeholder.get('variables', ['⟦PH_xx⟧', '⟦TAG_xx⟧', '{0}', '%s']))}",
        f"- No over-localization: {language_policy.get('no_over_localization', True)}",
        f"- No over-literal: {language_policy.get('no_over_literal', True)}",
        f"- Max UI button chars: {char_policy.get('button_max_chars', 18)}",
        f"- Max dialogue chars: {char_policy.get('dialogue_max_chars', 120)}",
        f"- Time unit mapping: {units.get('time', {}).get('source_unit', '秒')} -> {units.get('time', {}).get('target_unit', 'секунд')}",
        f"- Currency mapping: {units.get('currency', {}).get('source_unit', '原石')} -> {units.get('currency', {}).get('target_unit', 'алмазы')}",
        f"- Character name policy: {style_guard.get('character_name_policy', 'keep')}",
        f"- Proper noun strategy: {style_guard.get('proper_noun_strategy', 'hybrid')}",
        f"- Keep named entities unchanged: {style_guard.get('keep_named_entities', True)}",
        f"- Avoid joke distortion: {style_guard.get('no_humor_overreach', True)}",
        f"- Avoid wordplay distortion: {style_guard.get('avoid_wordplay_distortion', True)}",
    ]

    if forbidden_terms:
        lines.append("- Forbidden terms:")
        for it in forbidden_terms[:25]:
            lines.append(f"  - {it}")
    if preferred_terms:
        lines.append("- Preferred term mapping:")
        for it in preferred_terms[:25]:
            if isinstance(it, dict):
                zh = str(it.get("term_zh", "")).strip()
                ru = str(it.get("term_ru", "")).strip()
                if zh and ru:
                    lines.append(f"  - {zh} -> {ru}")

    return "\n".join(lines)


def build_system_prompt_factory(
    style_guide: str,
    glossary_summary: str,
    style_profile: Optional[Dict[str, Any]] = None,
    target_lang: str = "ru-RU",
    target_key: str = "target_ru",
):
    def _builder(rows: List[Dict]) -> str:
        constraints = ""
        for r in rows:
            max_len = r.get("max_length_target") or r.get("max_len_target")
            if max_len and int(max_len) > 0:
                constraints += f"- Row {r.get('string_id')}: max {max_len} chars\n"

        constraint_section = ""
        if constraints:
            constraint_section = (
                "\n【Length Constraints】\n"
                f"Each translation MUST NOT exceed its limit:\n{constraints}"
            )

        return (
            f'你是严谨的手游本地化译者（zh-CN → {target_lang}）。\n\n'
            '【Output Contract】\n'
            f'1. Output MUST be valid JSON object with "items".\n'
            f'2. Structure: {{"items":[{{"id":"...","{target_key}":"..."}}]}}\n'
            '3. 每个输入 id 必须出现在输出.\n\n'
            '【Translation Rules】\n'
            '- 术语匹配必须一致。\n'
            '- 占位符 ⟦PH_xx⟧ / ⟦TAG_xx⟧ / {0} / %s / %d 必须保留。\n'
            '- 保留中文方括号【】、\\n 与所有 markup，不得删除或重排。\n'
            f'{build_style_contract(style_profile or {})}\n\n'
            f'{constraint_section}\n'
            f'术语表摘要:\n{glossary_summary}\n\n'
            f'style_guide:\n{style_guide}\n'
        )

    return _builder


def build_repair_system_prompt_factory(
    style_guide: str,
    glossary_summary: str,
    style_profile: Optional[Dict[str, Any]] = None,
    target_lang: str = "ru-RU",
    target_key: str = "target_ru",
):
    def _builder(rows: List[Dict]) -> str:
        base = build_system_prompt_factory(
            style_guide=style_guide,
            glossary_summary=glossary_summary,
            style_profile=style_profile,
            target_lang=target_lang,
            target_key=target_key,
        )
        row_rules = []
        for r in rows:
            tokenized = r.get("source_text", "")
            signature = tokens_signature(tokenized)
            sig_text = ", ".join([f"{k}:{v}" for k, v in sorted(signature.items())]) or "none"
            row_rules.append(f"- Row {r.get('id')}: keep token multiset exactly ({sig_text}).")
        return (
            f"{base(rows)}\n"
            "【Repair Guard】\n"
            "1. 不允许改写、移除、增添任何占位符。\n"
            "2. token 数量必须与源字符串一致。\n"
            "3. 若无法稳定保持闭合，优先保守输出原 token 布局。\n"
            + "\n".join(row_rules)
        )

    return _builder


def build_user_prompt(rows: List[Dict]) -> str:
    return json.dumps(rows, ensure_ascii=False, indent=2)


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
    norm = (target_lang or "").split("-", 1)[0].strip().lower().replace("_", "")
    if not norm:
        return "target_ru"
    return f"target_{norm}"


def load_checkpoint(path: str) -> set:
    if not Path(path).exists():
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f).get("done_ids", []))
    except Exception:
        return set()


def save_checkpoint(path: str, done_ids: set):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"done_ids": list(done_ids)}, f)


def _batch_translate(
    rows: List[Dict],
    args: argparse.Namespace,
    style_guide: str,
    glossary_summary: str,
    style_profile: Optional[Dict[str, Any]],
    target_key: str,
    content_type: str,
    system_prompt_builder,
) -> Dict[str, str]:
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
        allow_fallback=True,
    )

    out: Dict[str, str] = {}
    for it in results:
        sid = str(it.get("id") or it.get("string_id") or "")
        if not sid:
            continue
        target_text = it.get(target_key) or it.get("target_ru") or ""
        out[sid] = target_text
    return out


def _single_row_retry(
    row: Dict[str, str],
    args: argparse.Namespace,
    target_key: str,
    style_guide: str,
    glossary_summary: str,
    style_profile: Optional[Dict[str, Any]],
    content_type: str,
) -> Tuple[str, bool, str]:
    sid = str(row.get("string_id") or row.get("id") or "")
    src = row.get("tokenized_zh") or row.get("source_zh") or ""
    repair_row = {"id": sid, "source_text": src}
    repair_prompt = build_repair_system_prompt_factory(
        style_guide=style_guide,
        glossary_summary=glossary_summary,
        style_profile=style_profile,
        target_lang=args.target_lang,
        target_key=target_key,
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
            allow_fallback=True,
        )
        if repaired_items:
            candidate = repaired_items[0].get(target_key) or repaired_items[0].get("target_ru") or ""
            ok, err = validate_translation(src, candidate)
            if ok:
                return candidate, True, "ok"
            return candidate, False, err
    except Exception as e:
        return "", False, str(e)
    return "", False, "no_repair_output"


def main():
    configure_standard_streams()
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--style", default="workflow/style_guide.md")
    parser.add_argument("--glossary", default="data/glossary.yaml")
    parser.add_argument("--style-profile", default="data/style_profile.yaml")
    parser.add_argument("--target-lang", default="ru-RU")
    parser.add_argument("--target-key", default="", help="target_ru / target_en")
    parser.add_argument("--checkpoint", default="data/translate_checkpoint.json")
    args = parser.parse_args()

    print("🚀 Translate LLM v6.1 (Style Profile)")
    style_guide = load_text(args.style)
    style_profile = load_style_profile(args.style_profile)
    glossary, _ = load_glossary(args.glossary)
    glossary_summary = build_glossary_summary(glossary)

    if not Path(args.input).exists():
        print(f"❌ Input not found: {args.input}")
        return

    with open(args.input, "r", encoding="utf-8-sig", newline="") as f:
        all_rows = list(csv.DictReader(f))

    if not all_rows:
        print("⚠️ Empty input.")
        return

    headers = list(all_rows[0].keys())
    target_key = args.target_key.strip() or derive_target_key(args.target_lang)
    for col in ("target_text", "target", target_key, "translate_status", "translate_validation"):
        if col and col not in headers:
            headers.append(col)

    done_ids = load_checkpoint(args.checkpoint)
    pending_rows = [r for r in all_rows if str(r.get("string_id") or "") not in done_ids]
    if not pending_rows:
        print("✅ No pending rows to process.")
        return

    print(f"   Total rows: {len(all_rows)}, Pending: {len(pending_rows)}")

    long_rows = [r for r in pending_rows if str(r.get("is_long_text", "")).lower() == "true"]
    normal_rows = [r for r in pending_rows if r not in long_rows]

    batch_inputs_normal = [{"id": r.get("string_id"), "source_text": r.get("tokenized_zh") or r.get("source_zh") or ""} for r in normal_rows]
    batch_inputs_long = [{"id": r.get("string_id"), "source_text": r.get("tokenized_zh") or r.get("source_zh") or ""} for r in long_rows]

    try:
        system_prompt_builder = build_system_prompt_factory(
            style_guide=style_guide,
            glossary_summary=glossary_summary,
            style_profile=style_profile,
            target_lang=args.target_lang,
            target_key=target_key,
        )

        res_map = {}
        res_map.update(_batch_translate(
            rows=batch_inputs_normal,
            args=args,
            style_guide=style_guide,
            glossary_summary=glossary_summary,
            style_profile=style_profile,
            target_key=target_key,
            content_type="normal",
            system_prompt_builder=system_prompt_builder,
        ))

        for row in batch_inputs_long:
            row_res = _batch_translate(
                rows=[row],
                args=args,
                style_guide=style_guide,
                glossary_summary=glossary_summary,
                style_profile=style_profile,
                target_key=target_key,
                content_type="long_text",
                system_prompt_builder=system_prompt_builder,
            )
            res_map.update(row_res)

        final_rows = []
        new_done = set()
        for row in pending_rows:
            sid = str(row.get("string_id") or "")
            translated = res_map.get(sid, "")
            ok, err = validate_translation(row.get("tokenized_zh") or row.get("source_zh") or "", translated)
            if not ok:
                row_content_type = "long_text" if str(row.get("is_long_text", "")).lower() == "true" else "normal"
                repair_text, repaired_ok, repair_err = _single_row_retry(
                    row=row,
                    args=args,
                    target_key=target_key,
                    style_guide=style_guide,
                    glossary_summary=glossary_summary,
                    style_profile=style_profile,
                    content_type=row_content_type,
                )
                if repaired_ok:
                    translated = repair_text
                    ok = True
                    err = "ok"
                else:
                    if repair_err:
                        print(f"    Repair check: {repair_err}")
                    translated = row.get("tokenized_zh") or translated or ""
                    err = "fallback_tokenized_layout"

            row["translate_validation"] = err if not ok else "ok"
            row["translate_status"] = "ok" if ok else "validation_failed"
            if target_key and target_key not in row:
                row[target_key] = ""
            if "target_text" not in row:
                row["target_text"] = ""
            if "target" not in row:
                row["target"] = ""

            if ok:
                if target_key:
                    row[target_key] = translated
                row["target"] = translated
                row["target_text"] = translated
            else:
                print(f"⚠️ Validation failed for {sid}: {err}")
                print(f"   Target was: {translated[:80]}...")
                if target_key:
                    row[target_key] = translated
                row["target_text"] = translated
                row["target"] = translated

            final_rows.append(row)
            new_done.add(sid)

        write_mode = "a" if Path(args.output).exists() else "w"
        with open(args.output, write_mode, encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if write_mode == "w":
                writer.writeheader()
            writer.writerows(final_rows)

        done_ids.update(new_done)
        save_checkpoint(args.checkpoint, done_ids)
        print(f"✅ Translated {len(new_done)} / {len(pending_rows)} rows.")
    except Exception as e:
        print(f"❌ Translation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
