#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
translate_llm.py (v6.2 - style profile aware + clean-worktree authority)
Purpose:
  Translate tokenized Chinese strings using unified batch interface.
  Adds style-contract hard rules from explicit or tracked style/glossary assets.
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

from style_governance_runtime import evaluate_runtime_governance, format_runtime_governance_issues


TOKEN_RE = re.compile(r"⟦(PH_\d+|TAG_\d+)⟧")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
RULE_VERSION = "1.0"

RULE_CATALOG = {
    "D-TL-001": {
        "version": RULE_VERSION,
        "message": "style_profile 缺失",
        "suggestion": "先执行 scripts/style_guide_bootstrap.py 生成 data/style_profile.yaml。",
    },
    "D-TL-002": {
        "version": RULE_VERSION,
        "message": "style_profile schema 不完整",
        "suggestion": "补齐 data/style_profile.yaml 的 project 与 ui.length_constraints 字段。",
    },
    "D-TL-003": {
        "version": RULE_VERSION,
        "message": "风格配置禁止词与 glossary 已批准术语冲突",
        "suggestion": "检查 data/glossary.yaml 中 approved 项，移除与 style_profile 冲突译项或更新问卷并重跑 bootstrap。",
    },
    "D-TL-004": {
        "version": RULE_VERSION,
        "message": "glossary 文件缺失或不可读",
        "suggestion": "确保 data/glossary.yaml 存在、可读且 YAML 合法。",
    },
}
STYLE_GATE_RULES = {
    "style_profile_presence": {
        "id": "D-TL-001",
        "version": "1.0",
        "suggestion": "先运行 scripts/style_guide_bootstrap.py 生成 style_profile。",
    },
    "style_profile_schema": {
        "id": "D-TL-002",
        "version": "1.0",
        "suggestion": "完善 style_profile.yaml 字段（project/source_target 与 ui.length_constraints）。",
    },
    "glossary_conflict": {
        "id": "D-TL-003",
        "version": "1.0",
        "suggestion": "移除 glossary 中与禁译词冲突的 approved 条目后重试。",
    },
    "glossary_missing": {
        "id": "D-TL-004",
        "version": "1.0",
        "suggestion": "确保 glossary.yaml 可读且 YAML 合法。",
    },
}


@dataclass
class GlossaryEntry:
    term_zh: str
    term_ru: str
    status: str
    notes: str = ""
    targets: Optional[Dict[str, str]] = None
    tags: Optional[List[str]] = None
    preferred_compact: bool = False
    avoid_long_form: Optional[List[str]] = None


DEFAULT_GLOSSARY_CANDIDATES = [
    "glossary/compiled.yaml",
    "workflow/smoke_glossary_compiled.yaml",
    "data/glossary.yaml",
]
DEFAULT_STYLE_PROFILE_CANDIDATES = [
    "workflow/style_profile.generated.yaml",
    "data/style_profile.yaml",
]
REPO_ROOT = Path(__file__).resolve().parent.parent


def resolve_asset_path(path: str, candidates: List[str]) -> str:
    if path and path.strip():
        return path
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return candidates[0]


def resolve_glossary_path(path: str = "") -> str:
    return resolve_asset_path(path, DEFAULT_GLOSSARY_CANDIDATES)


def resolve_style_profile_path(path: str = "") -> str:
    return resolve_asset_path(path, DEFAULT_STYLE_PROFILE_CANDIDATES)


def _is_repo_managed_path(path: str) -> bool:
    try:
        Path(path).resolve().relative_to(REPO_ROOT)
        return True
    except Exception:
        return False


def _normalize_locale(locale: str) -> str:
    value = str(locale or "").strip().replace("_", "-")
    if not value:
        return ""
    parts = [part for part in value.split("-") if part]
    if not parts:
        return ""
    if len(parts) == 1:
        return parts[0].lower()
    return "-".join([parts[0].lower(), parts[1].upper(), *parts[2:]])


def _is_ru_locale(target_locale: str) -> bool:
    return _normalize_locale(target_locale) == "ru-RU"


def _entry_targets(raw: Dict[str, Any], target_locale: str) -> Tuple[Dict[str, str], str]:
    targets: Dict[str, str] = {}
    legacy_ru = str(raw.get("term_ru") or "").strip()
    raw_targets = raw.get("targets") or {}
    if isinstance(raw_targets, dict):
        for locale, value in raw_targets.items():
            locale_key = _normalize_locale(str(locale))
            term_value = str(value or "").strip()
            if locale_key and term_value:
                targets[locale_key] = term_value

    resolved = targets.get(_normalize_locale(target_locale), "")
    if not resolved and legacy_ru and _is_ru_locale(target_locale):
        resolved = legacy_ru
    return targets, resolved


def load_text(path: str) -> str:
    if not Path(path).exists():
        return ""
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_glossary(path: str, target_locale: str = "ru-RU") -> Tuple[List[GlossaryEntry], Optional[str]]:
    if not path or not Path(path).exists() or yaml is None:
        return [], None
    with open(path, "r", encoding="utf-8") as f:
        g = yaml.safe_load(f) or {}

    meta = g.get("meta") or {}
    is_compiled = str(meta.get("type") or "").strip().lower() == "compiled"
    entries = []
    for it in g.get("entries", []):
        term_zh = (it.get("term_zh") or "").strip()
        targets, resolved_target = _entry_targets(it, target_locale)
        status = (it.get("status") or "").lower().strip()
        if not status and is_compiled:
            status = "approved"
        notes = (it.get("notes") or "").strip()
        if not notes:
            notes = str(it.get("note") or "").strip()
        tags = [str(tag).strip() for tag in (it.get("tags") or []) if str(tag).strip()]
        avoid_long_form = [str(term).strip() for term in (it.get("avoid_long_form") or []) if str(term).strip()]
        if term_zh and resolved_target and status in {"approved", "proposed", "banned"}:
            entries.append(
                GlossaryEntry(
                    term_zh=term_zh,
                    term_ru=resolved_target,
                    status=status,
                    notes=notes,
                    targets=targets or None,
                    tags=tags or None,
                    preferred_compact=bool(it.get("preferred_compact")),
                    avoid_long_form=avoid_long_form or None,
                )
            )

    return entries, meta.get("compiled_hash")


def is_ui_art_row(row: Dict[str, Any]) -> bool:
    module_tag = str(row.get("module_tag") or "").strip().lower()
    category = str(row.get("ui_art_category") or "").strip().lower()
    return module_tag == "ui_art_label" or bool(category)


def glossary_is_compact(entry: GlossaryEntry) -> bool:
    tags = {str(tag).strip().lower() for tag in (entry.tags or []) if str(tag).strip()}
    compact_tags = {"ui", "art", "short", "mobile"}
    return bool(entry.preferred_compact or (tags & compact_tags))


def build_glossary_preferences(entries: List[GlossaryEntry]) -> Tuple[Dict[str, str], Dict[str, str], Dict[str, List[str]]]:
    standard_map: Dict[str, str] = {}
    compact_map: Dict[str, str] = {}
    avoid_long_forms: Dict[str, List[str]] = {}
    for entry in entries:
        if entry.status != "approved" or not entry.term_zh or not entry.term_ru:
            continue
        standard_map.setdefault(entry.term_zh, entry.term_ru)
        if glossary_is_compact(entry):
            compact_map.setdefault(entry.term_zh, entry.term_ru)
            if entry.avoid_long_form:
                avoid_long_forms.setdefault(entry.term_zh, [])
                for term in entry.avoid_long_form:
                    if term not in avoid_long_forms[entry.term_zh]:
                        avoid_long_forms[entry.term_zh].append(term)
    return standard_map, compact_map, avoid_long_forms


def load_style_profile(path: str) -> Dict[str, Any]:
    if not path or not Path(path).exists() or yaml is None:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def validate_style_profile_for_translate(profile: Dict[str, Any]) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    if not profile:
        issues.append(
            {
                "rule_id": "D-TL-001",
                "rule_version": RULE_VERSION,
                "severity": "major",
                "detail": "style_profile missing or invalid",
                "suggestion": RULE_CATALOG["D-TL-001"]["suggestion"],
            }
        )
        return issues

    project = profile.get("project", {})
    if not isinstance(project, dict) or not project.get("source_language") or not project.get("target_language"):
        issues.append(
            {
                "rule_id": "D-TL-002",
                "rule_version": RULE_VERSION,
                "severity": "major",
                "detail": "project.source_language / project.target_language missing",
                "suggestion": RULE_CATALOG["D-TL-002"]["suggestion"],
            }
        )

    ui = profile.get("ui", {})
    if not isinstance(ui, dict) or not ui.get("length_constraints"):
        issues.append(
            {
                "rule_id": "D-TL-002",
                "rule_version": RULE_VERSION,
                "severity": "major",
                "detail": "ui.length_constraints missing",
                "suggestion": RULE_CATALOG["D-TL-002"]["suggestion"],
            }
        )

    return issues


def validate_glossary_profile_conflict(
    glossary: List[GlossaryEntry],
    profile: Dict[str, Any],
) -> List[Dict[str, str]]:
    terms = profile.get("terminology", {}) if isinstance(profile, dict) else {}
    forbidden_terms = set(str(x).strip() for x in (terms.get("forbidden_terms", []) or []) if str(x).strip())
    banned_terms = set(str(x).strip() for x in (terms.get("banned_terms", []) or []) if str(x).strip())
    blocked = {t for t in forbidden_terms | banned_terms if t}
    if not blocked:
        return []

    issues: List[Dict[str, str]] = []
    for entry in glossary:
        if entry.status != "approved":
            continue
        term = (entry.term_zh or "").strip()
        if term and term in blocked:
            issues.append(
                {
                    "rule_id": "D-TL-003",
                    "rule_version": RULE_VERSION,
                    "severity": "major",
                    "detail": f"approved glossary term conflicts with forbidden policy: {term}",
                    "suggestion": RULE_CATALOG["D-TL-003"]["suggestion"],
                }
            )
    return issues


def print_hard_gate_failures(issues: List[Dict[str, str]]) -> None:
    print("❌ Translate hard gate failed:")
    for it in issues:
        rid = it.get("rule_id", "D-TL-000")
        version = it.get("rule_version", RULE_VERSION)
        detail = it.get("detail", "")
        suggestion = it.get("suggestion", "")
        print(f"- {rid} v{version}: {detail}")
        if suggestion:
            print(f"  suggestion: {suggestion}")


def _collect_translate_gate_issues(profile: Dict[str, Any], glossary: List[GlossaryEntry], style_profile_path: str) -> List[str]:
    issues = []
    if not style_profile_path or not Path(style_profile_path).exists():
        rule = STYLE_GATE_RULES["style_profile_presence"]
        issues.append(f'[{rule["id"]} v{rule["version"]}] style profile missing: {style_profile_path} | {rule["suggestion"]}')
        return issues

    if not profile.get("project", {}).get("source_language") or not profile.get("project", {}).get("target_language"):
        rule = STYLE_GATE_RULES["style_profile_schema"]
        issues.append(f'[{rule["id"]} v{rule["version"]}] style_profile project language missing | {rule["suggestion"]}')
    if not profile.get("ui", {}).get("length_constraints"):
        rule = STYLE_GATE_RULES["style_profile_schema"]
        issues.append(f'[{rule["id"]} v{rule["version"]}] style_profile ui.length_constraints missing | {rule["suggestion"]}')

    forbidden = {str(item).strip() for item in profile.get("terminology", {}).get("forbidden_terms", []) if str(item).strip()}
    for entry in glossary or []:
        term = (entry.term_zh or "").strip()
        if entry.status == "approved" and forbidden and term and term in forbidden:
            rule = STYLE_GATE_RULES["glossary_conflict"]
            issues.append(
                f'[{rule["id"]} v{rule["version"]}] glossary contains forbidden conflict "{term}" | '
                f"{rule['suggestion']}"
            )

    return issues


def _format_gate_report(issues: List[str]) -> str:
    if not issues:
        return "style gate: pass"
    lines = ["style gate: fail"]
    lines.extend([f"🚫 {it}" for it in issues])
    return "\n".join(lines)


def build_glossary_summary(glossary: List[GlossaryEntry]) -> str:
    if not glossary:
        return "(无)"
    compact = [e for e in glossary if e.status == "approved" and glossary_is_compact(e)]
    standard = [e for e in glossary if e.status == "approved" and not glossary_is_compact(e)]
    lines: List[str] = []
    if compact:
        lines.append("[Compact UI-art priority terms]")
        lines.extend(f"- {e.term_zh} → {e.term_ru}" for e in compact[:40])
    if standard:
        lines.append("[General approved terms]")
        lines.extend(f"- {e.term_zh} → {e.term_ru}" for e in standard[:40])
    return "\n".join(lines) if lines else "(无)"


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
    ui_art_policies = ui.get("ui_art_category_policies", {}) or {}

    forbidden_terms = terminology.get("forbidden_terms", []) or []
    preferred_terms = terminology.get("preferred_terms", []) or []
    prohibited_aliases = terminology.get("prohibited_aliases", []) or []
    banned_terms = terminology.get("banned_terms", []) or []

    def _string_items(items: Any) -> List[str]:
        if not isinstance(items, list):
            return []
        return [str(item).strip() for item in items if str(item).strip()]

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
        f"- UI-art target ratio: {char_policy.get('ui_art_target_ratio', 2.3)}",
        f"- UI-art review ratio: {char_policy.get('ui_art_review_ratio', 2.5)}",
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
            else:
                value = str(it).strip()
                if value:
                    lines.append(f"  - {value}")
    alias_items = _string_items(prohibited_aliases)
    if alias_items:
        lines.append("- Prohibited aliases:")
        for item in alias_items[:25]:
            lines.append(f"  - {item}")
    banned_items = _string_items(banned_terms)
    if banned_items:
        lines.append("- Banned terms:")
        for item in banned_items[:25]:
            lines.append(f"  - {item}")
    if ui_art_policies:
        lines.append("- UI-art category contract:")
        for category, policy in ui_art_policies.items():
            if not isinstance(policy, dict):
                continue
            rule = str(policy.get("translation_rule") or "").strip()
            hard_limit = policy.get("hard_limit")
            review_limit = policy.get("review_limit")
            lines.append(
                f"  - {category}: rule={rule or 'compact'}; hard<={hard_limit}; review<={review_limit}"
            )

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
        residual_lanes = set()
        has_residual_reference = False
        for r in rows:
            max_len = r.get("max_length_target") or r.get("max_len_target")
            review_len = r.get("max_len_review_limit")
            category = str(r.get("ui_art_category") or "default").strip()
            strategy_hint = str(r.get("ui_art_strategy_hint") or "").strip()
            residual_lane = str(r.get("residual_lane") or "").strip()
            residual_prompt_hint = str(r.get("residual_prompt_hint") or "").strip()
            if residual_lane:
                residual_lanes.add(residual_lane)
            if str(r.get("current_target_text") or "").strip():
                has_residual_reference = True
            if max_len and int(max_len) > 0:
                constraints += (
                    f"- Row {r.get('id') or r.get('string_id')}: category={category}; "
                    f"hint={strategy_hint or 'default'}; "
                    f"lane={residual_lane or 'default'}; "
                    f"repair={residual_prompt_hint or 'default'}; "
                    f"target<={max_len}; review<={review_len or 'n/a'} chars\n"
                )

        constraint_section = ""
        if constraints:
            constraint_section = (
                "\n【Length Constraints】\n"
                f"Each translation MUST NOT exceed its limit:\n{constraints}"
            )

        residual_section = ""
        if residual_lanes or has_residual_reference:
            lane_rules = []
            if "promo_exact_or_compound" in residual_lanes:
                lane_rules.append("- residual_lane=promo_exact_or_compound: keep only the shortest promo head or qualifier + pack noun; forbid explanatory tails like Превью / Выбор / Ниндзя / Обзор.")
            if "item_skill_family_compact" in residual_lanes:
                lane_rules.append("- residual_lane=item_skill_family_compact: produce a compact canonical title in at most 1-2 content words; prefer approved compact family forms over literal explanations.")
            if "headline_slogan_repair" in residual_lanes:
                lane_rules.append("- residual_lane=headline_slogan_repair: output headline-only RU, not a sentence; preserve line budget and keep existing line count unless the source itself is multiline.")
            if "canonical_title_compact" in residual_lanes:
                lane_rules.append("- residual_lane=canonical_title_compact: repair repeated short titles only; keep proper nouns, use 1-2 content words max, and prefer stable compact noun titles over decorative phrasing.")
            if "lore_skill_compact" in residual_lanes:
                lane_rules.append("- residual_lane=lore_skill_compact: repair lore/skill names conservatively; preserve canonical meaning, keep at most 1-2 content words, and never expand into an explanation.")
            if "warning_family_compact" in residual_lanes:
                lane_rules.append("- residual_lane=warning_family_compact: this is a near-limit compaction pass; shorten carefully without changing meaning or inventing new lore.")
            if "badge_micro_gap_cleanup" in residual_lanes:
                lane_rules.append("- residual_lane=badge_micro_gap_cleanup: exact approved short form only; no free expansion, no punctuation flourish.")
            if "creative_title_manual" in residual_lanes:
                lane_rules.append("- residual_lane=creative_title_manual should normally be skipped; if present, keep the current target conservative and do not invent lore meaning.")
            residual_section = (
                "\n【Residual Repair Mode】\n"
                "- This is targeted residual repair against an existing Russian output, not a broad retranslation pass.\n"
                "- If current_target_text is present, use it as the baseline and change only what is necessary to fix length, ambiguity, or headline/compact issues.\n"
                "- Do not broaden the meaning or add explanatory wording during repair.\n"
            )
            if lane_rules:
                residual_section += "\n".join(lane_rules) + "\n"

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
            '- UI 美术字必须优先采用 compact glossary；若存在短译，不得回退到解释性长译。\n'
            '- 若行带 ui_art_category，则该 category 视为硬约束：badge 只允许短词/缩写；slogan_long 必须压成 banner headline，不得展开成说明句。\n'
            '- 若 residual_prompt_hint 存在，必须把它视为本行额外硬约束。\n'
            '- 若 hint=badge_exact_map，仅允许批准短译，不允许自由发挥。\n'
            '- 若 hint=promo_exact_head，仅保留最短 promo 头词，不得补 Превью / 预览类解释尾巴。\n'
            '- 若 hint=promo_compound_pack，压成 qualifier + 核心礼包词，不得补 Выбор / Ниндзя 等泛词。\n'
            '- 若 hint=item_compact_noun，仅允许 1-2 个实词，不得写解释性属格链。\n'
            '- 若 hint=headline_singleline/headline_multiline/headline_nameplate，只写标题式 headline，不写完整说明句。\n'
            f'{build_style_contract(style_profile or {})}\n\n'
            f'{residual_section}'
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


def build_batch_row_payload(row: Dict[str, str]) -> Dict[str, str]:
    return {
        "id": str(row.get("string_id") or row.get("id") or ""),
        "source_text": row.get("tokenized_zh") or row.get("source_zh") or "",
        "current_target_text": str(row.get("current_target_text") or row.get("target_text") or ""),
        "ui_art_category": str(row.get("ui_art_category") or ""),
        "ui_art_strategy_hint": str(row.get("ui_art_strategy_hint") or ""),
        "ui_art_compact_term": str(row.get("ui_art_compact_term") or ""),
        "max_len_target": str(row.get("max_length_target") or row.get("max_len_target") or ""),
        "max_len_review_limit": str(row.get("max_len_review_limit") or ""),
        "translation_mode": str(row.get("translation_mode") or "llm"),
        "residual_lane": str(row.get("residual_lane") or ""),
        "residual_prompt_hint": str(row.get("residual_prompt_hint") or ""),
    }


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
    repair_row = build_batch_row_payload(row)
    repair_row["id"] = sid
    repair_row["source_text"] = src
    repair_row["current_target_text"] = str(row.get("target_text") or row.get("current_target_text") or "")
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
    parser.add_argument("--glossary", default="", help="Glossary asset path. Defaults to tracked authority candidates.")
    parser.add_argument("--style-profile", default="", help="Style profile path. Defaults to tracked authority candidates.")
    parser.add_argument("--lifecycle-registry", default="workflow/lifecycle_registry.yaml", help="Lifecycle registry for governed assets.")
    parser.add_argument("--target-lang", default="ru-RU")
    parser.add_argument("--target-key", default="", help="target_ru / target_en")
    parser.add_argument("--checkpoint", default="data/translate_checkpoint.json")
    parser.add_argument("--dry-run", action="store_true", help="Validate resolved assets and gates without performing translation.")
    args = parser.parse_args()

    args.glossary = resolve_glossary_path(args.glossary)
    args.style_profile = resolve_style_profile_path(args.style_profile)

    print("🚀 Translate LLM v6.1 (Style Profile)")
    style_guide = load_text(args.style)
    style_profile = load_style_profile(args.style_profile)
    glossary, _ = load_glossary(args.glossary, args.target_lang)
    glossary_summary = build_glossary_summary(glossary)

    runtime_governance = {"passed": True, "issues": [], "mode": "external_fixture"}
    if _is_repo_managed_path(args.style_profile):
        runtime_governance = evaluate_runtime_governance(
            style_profile_path=args.style_profile,
            glossary_path=args.glossary,
            policy_paths=["workflow/style_governance_contract.yaml"],
            lifecycle_registry_path=args.lifecycle_registry,
        )
    if not runtime_governance["passed"]:
        print(format_runtime_governance_issues(runtime_governance))
        return 1

    style_gate_issues: List[Dict[str, str]] = []
    style_gate_issues.extend(validate_style_profile_for_translate(style_profile))
    style_gate_issues.extend(validate_glossary_profile_conflict(glossary, style_profile))
    if style_gate_issues:
        print_hard_gate_failures(style_gate_issues)
        return 1
    gate_issues = _collect_translate_gate_issues(style_profile, glossary, args.style_profile)
    if gate_issues:
        print(_format_gate_report(gate_issues))
        print("🛑 translate_llm hard gate failed, please fix style profile / glossary first.")
        return 1

    if args.dry_run:
        print(f"✅ Resolved style guide: {args.style}")
        print(f"✅ Resolved style profile: {args.style_profile}")
        print(f"✅ Resolved glossary: {args.glossary}")
        if not Path(args.input).exists():
            print(f"ℹ️ Input not found during dry-run, skipped row validation: {args.input}")
        else:
            print(f"✅ Input available for translation: {args.input}")
        print(f"✅ Target locale: {args.target_lang}")
        print("✅ Dry-run validation complete.")
        return 0

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

    exact_rows = [
        r for r in pending_rows
        if str(r.get("translation_mode") or "").strip().lower() == "prefill_exact"
        and str(r.get("prefill_target_ru") or "").strip()
    ]
    llm_rows = [r for r in pending_rows if r not in exact_rows]
    long_rows = [r for r in llm_rows if str(r.get("is_long_text", "")).lower() == "true"]
    normal_rows = [r for r in llm_rows if r not in long_rows]

    batch_inputs_normal = [build_batch_row_payload(r) for r in normal_rows]
    batch_inputs_long = [build_batch_row_payload(r) for r in long_rows]

    try:
        system_prompt_builder = build_system_prompt_factory(
            style_guide=style_guide,
            glossary_summary=glossary_summary,
            style_profile=style_profile,
            target_lang=args.target_lang,
            target_key=target_key,
        )

        res_map = {}
        prefilled = 0
        for row in exact_rows:
            sid = str(row.get("string_id") or "")
            target_text = str(row.get("prefill_target_ru") or "").strip()
            ok, err = validate_translation(row.get("tokenized_zh") or row.get("source_zh") or "", target_text)
            if ok:
                res_map[sid] = target_text
                prefilled += 1
            else:
                print(f"⚠️ Prefill validation failed for {sid}: {err}; falling back to LLM.")
                batch_row = build_batch_row_payload(row)
                if str(row.get("is_long_text", "")).lower() == "true":
                    batch_inputs_long.append(batch_row)
                else:
                    batch_inputs_normal.append(batch_row)
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
        print(f"✅ Translated {len(new_done)} / {len(pending_rows)} rows (prefill_exact={prefilled}).")
    except Exception as e:
        print(f"❌ Translation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
