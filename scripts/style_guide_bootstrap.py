#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Style Guide Bootstrap (C-milestone)

Read startup questionnaire and generate:
  - workflow/style_guide.generated.md (LLM-readable guide)
  - workflow/style_profile.generated.yaml (machine-readable profile)
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import yaml
except Exception:
    yaml = None

try:
    from runtime_adapter import LLMClient
except Exception:
    LLMClient = None


SECTION_RE = re.compile(r"^\s*##\s*(.+)$")
CHECKBOX_RE = re.compile(r"^\s*-\s*\[([xX])\]\s*(.+?)\s*$")
KV_RE = re.compile(r"^\s*\*\*(.+?)\*\*:\s*(.+?)\s*$")
BULLET_RE = re.compile(r"^\s*[-*]\s*(.+?)\s*$")


def read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def parse_questionnaire(md: str) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    section = "global"
    bullets: Dict[str, List[str]] = {}

    for raw in md.splitlines():
        line = raw.strip()
        if not line:
            continue

        m = SECTION_RE.match(line)
        if m:
            section = m.group(1).strip().lower().replace(" ", "_")
            continue

        m = KV_RE.match(line)
        if m:
            key = f"{section}.{m.group(1).strip().lower().replace(' ', '_')}"
            data[key] = m.group(2).strip()
            continue

        m = CHECKBOX_RE.match(line)
        if m:
            sec_key = f"{section}.selected"
            bullets.setdefault(sec_key, []).append(m.group(2).strip())
            continue

        m = BULLET_RE.match(line)
        if m:
            sec_key = f"{section}.items"
            txt = m.group(1).strip()
            if txt:
                bullets.setdefault(sec_key, []).append(txt)

    data.update(bullets)
    return data


def _as_int(text: Any, default: int) -> int:
    if text is None:
        return default
    m = re.search(r"\d+", str(text))
    try:
        return int(m.group(0)) if m else int(default)
    except Exception:
        return default


def _as_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        return [x.strip() for x in value.split(",") if x.strip()]
    return []


def _to_bool(value: Any, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    txt = str(value or "").strip().lower()
    if not txt:
        return default
    return txt not in {"no", "false", "0", "off", "禁用", "否"}


def _qv(q: Dict[str, Any], keys: List[str], default: Any = "") -> Any:
    for key in keys:
        if key in q and str(q.get(key)).strip():
            return q.get(key)
    return default


def _safe_list(q: Dict[str, Any], key: str) -> List[str]:
    return _as_list(q.get(key, []))


def build_style_profile(q: Dict[str, Any]) -> Dict[str, Any]:
    target_locale = _qv(q, ["project_context.target_language", "project_context.target"], "ru-RU")
    project_id = _qv(q, ["project_context.project_code", "project_context.project_id"], "") or "game_localization_project"
    profile_version = "1.2"
    style_guide_id = f"{project_id}-{target_locale}-style-v{profile_version}"
    preferred_terms_raw = _safe_list(q, "terminology_policy.preferred_terms")
    preferred = []
    for row in preferred_terms_raw:
        if ":" in row:
            zh, ru = [x.strip() for x in row.split(":", 1)]
            if zh and ru:
                preferred.append({"term_zh": zh, "term_ru": ru, "targets": {target_locale: ru}})

    return {
        "version": profile_version,
        "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S%z") or datetime.now().isoformat(),
        "project": {
            "source_language": _qv(q, ["project_context.source_language", "project_context.source"], "zh-CN"),
            "target_language": target_locale,
            "target_locale": target_locale,
            "project_id": project_id,
            "franchise": _qv(q, ["project_context.ip_name", "project_context.franchise"], ""),
            "title_zh": _qv(q, ["project_context.official_title_(zh)", "project_context.title_zh"], ""),
            "title_ru": _qv(q, ["project_context.official_title_(ru)", "project_context.title_ru"], ""),
            "genre": _qv(q, ["project_context.genre", "project_context.ip_genre"], ""),
            "audience": _qv(q, ["project_context.target_audience", "project_context.audience"], ""),
            "key_themes": _safe_list(q, "project_context.key_themes"),
            "domain_hint": _qv(q, ["segmentation_and_context.domain_hint", "segmentation_and_domain.domain_hint", "project_context.domain_hint"], "game"),
        },
        "style_contract": {
            "tone": {
                "official_ratio": _as_int(_qv(q, ["text_tone&_voice.official_ratio", "text_tone&_style.official_ratio", "register.official_ratio"], 70), 70),
                "anime_ratio": _as_int(_qv(q, ["text_tone&_voice.anime_ratio", "text_tone&_style.anime_ratio"], 30), 30),
                "register": _qv(q, ["text_tone&_voice.preferred_register", "text_tone&_style.preferred_register", "register"], ""),
                "forbidden_patterns": _safe_list(q, "forbidden_patterns.specific_terms"),
            },
            "language_policy": {
                "no_over_localization": _to_bool(_qv(q, ["register_and_voice.no_over_localization", "register_and_voice.over_localization", "register.over_localization", "register.over_localization"], True), True),
                "no_over_literal": _to_bool(_qv(q, ["register_and_voice.no_over_literal", "register_and_voice.over_literal", "register.over_literal"], True), True),
            },
            "placeholder_protection": {
                "preserve_ph_tokens": True,
                "preserve_markup": True,
                "variables": ["⟦PH_xx⟧", "⟦TAG_xx⟧", "{0}", "%s", "%d"],
            },
            "style_guard": {
                "no_humor_overreach": True,
                "avoid_wordplay_distortion": True,
                "keep_named_entities": True,
                "character_name_policy": _qv(q, ["names_and_nouns.character_name_policy", "terminology_policy.character_name_policy"], "keep"),
                "proper_noun_strategy": _qv(q, ["naming_conventions.proper_nouns", "terminology_policy.proper_noun_strategy"], "hybrid"),
            },
        },
        "segmentation": {
            "backend_chain": _qv(q, ["segmentation_and_domain.segmentation_backend_chain", "segmentation_and_context.segmentation_backend_chain"], "pkuseg,thulac,lac,jieba"),
            "domain_hint": _qv(q, ["segmentation_and_domain.domain_hint", "segmentation_and_context.domain_hint"], "game"),
            "named_entities": _safe_list(q, "segmentation_and_domain.named_entity_sample"),
        },
        "terminology": {
            "forbidden_terms": _safe_list(q, "terminology_policy.forbidden_terms"),
            "preferred_terms": preferred,
            "prohibited_aliases": _safe_list(q, "terminology_policy.prohibited_aliases"),
            "banned_terms": _safe_list(q, "terminology_policy.banned_terms"),
        },
        "ui": {
            "length_constraints": {
                "button_max_chars": _as_int(_qv(q, ["ui_constraints.button_length", "ui_constraints.button_max_chars", "ui_constraints.button_limit"], 18), 18),
                "dialogue_max_chars": _as_int(_qv(q, ["ui_constraints.dialogue_length", "ui_constraints.dialogue_max_chars"], 120), 120),
                "max_expansion_pct": _as_int(_qv(q, ["ui_constraints.max_length_expansion", "ui_constraints.length_expansion"], 30), 30),
            },
            "abbreviation_policy": _qv(q, ["ui_constraints.abbreviation_policy", "ui_constraints.abbreviation_policy_style"], "moderate"),
            "strictness": _qv(q, ["ui_constraints.length_policy", "ui_constraints.strictness"], "balanced"),
        },
        "units": {
            "time": {
                "source_unit": _qv(q, ["units.time_unit", "units.time.source"], "秒"),
                "target_unit": _qv(q, ["units.time_unit_target", "units.time.target"], "секунд"),
            },
            "currency": {
                "source_unit": _qv(q, ["units.currency_unit", "units.currency.source"], "原石"),
                "target_unit": _qv(q, ["units.currency_target", "units.currency.target"], "алмазы"),
            },
        },
        "evidence_hints": {
            "source_fields": ["module_tag", "max_length_target"],
            "placeholder_fields": ["source_zh", "tokenized_zh"],
        },
        "style_governance": {
            "style_guide_id": style_guide_id,
            "owner": "Codex",
            "status": "approved",
            "approval_ref": "docs/decisions/ADR-0002-skill-governance-framework.md",
            "adr_refs": [
                "docs/decisions/ADR-0001-project-continuity-framework.md",
                "docs/decisions/ADR-0002-skill-governance-framework.md",
            ],
            "generated_from_script": "scripts/style_guide_bootstrap.py",
            "source_questionnaire": "workflow/style_guide_questionnaire.md",
            "supersedes": "none",
            "deprecated_by": "none",
            "entry_audit": {
                "loadable": True,
                "approved": True,
                "deprecated": False,
            },
            "lineage": {
                "canonical_profile": "data/style_profile.yaml",
                "generated_guide": "workflow/style_guide.generated.md",
                "mirror_guides": [
                    "workflow/style_guide.md",
                    ".agent/workflows/style-guide.md",
                ],
            },
        },
    }


def render_style_guide(profile: Dict[str, Any]) -> str:
    sc = profile.get("style_contract", {})
    style = sc.get("tone", {})
    style_guard = sc.get("style_guard", {})
    ui = profile.get("ui", {})
    limits = ui.get("length_constraints", {})
    terms = profile.get("terminology", {})
    proj = profile.get("project", {})

    preferred = terms.get("preferred_terms", [])
    banned = terms.get("forbidden_terms", [])
    governance = profile.get("style_governance", {})
    lines = [
        "# Project Style Guide (Generated)",
        "",
        f"- Style guide ID: {governance.get('style_guide_id', 'unknown')}",
        f"- Style contract version: {profile.get('version', 'unknown')}",
        f"- Governance status: {governance.get('status', 'unknown')}",
        f"- Owner: {governance.get('owner', 'unknown')}",
        f"- Approval ref: {governance.get('approval_ref', 'none')}",
        f"- Source: {proj.get('source_language', 'zh-CN')} -> {proj.get('target_language', 'ru-RU')}",
        f"- Project: {proj.get('franchise', '')} / {proj.get('title_zh', '')} / {proj.get('title_ru', '')}",
        "",
        "## 1. Register & Tone",
        f"- Official ratio target: {style.get('official_ratio', 70)}%",
        f"- Anime ratio target: {style.get('anime_ratio', 30)}%",
        f"- Register: {style.get('register', 'neutral')}",
        f"- 禁止过度本地化: {'是' if sc.get('language_policy', {}).get('no_over_localization', True) else '否'}",
        f"- 禁止过度直译: {'是' if sc.get('language_policy', {}).get('no_over_literal', True) else '否'}",
        "",
        "## 2. 内容体裁",
        "- UI/System strings: 简洁直译，优先术语一致",
        "- Dialogue/Narrative: 允许适度口语化",
        "- 系统提示与错误提示: 不使用梗与隐喻",
        "",
        "## 3. 术语策略",
        "- 禁用词/禁译项：",
    ]
    for item in banned:
        lines.append(f"  - {item}")
    if not banned:
        lines.append("  - （无）")
    lines.append("- 优先译法：")
    for item in preferred:
        zh_term = item.get("term_zh", "")
        ru_term = item.get("term_ru", "")
        if zh_term and ru_term:
            lines.append(f"  - {zh_term} -> {ru_term}")

    lines.extend([
        "",
        "## 4. 占位符与变量保护（硬性）",
        "- 保护 token: `⟦PH_xx⟧`、`⟦TAG_xx⟧`、`{0}`、`%s`、`%d`",
        "- 保护 markup: `<color>`、`\\n`、XML / 自定义 tags",
        "",
        "## 5. UI 长度约束（硬性）",
        f"- 按钮: ≤ {limits.get('button_max_chars', 18)} 字符",
        f"- 对话/长文: ≤ {limits.get('dialogue_max_chars', 120)} 字符",
        f"- 单位/货币: {profile.get('units', {}).get('time', {}).get('source_unit', '秒')} -> "
        f"{profile.get('units', {}).get('time', {}).get('target_unit', 'секунд')}，"
        f"{profile.get('units', {}).get('currency', {}).get('source_unit', '原石')} -> "
        f"{profile.get('units', {}).get('currency', {}).get('target_unit', 'алмазы')}",
        "",
        "## 6. 名称与文化位点",
        f"- 角色名策略: {style_guard.get('character_name_policy', 'keep')}",
        f"- 专有名词策略: {style_guard.get('proper_noun_strategy', 'hybrid')}",
        "- 文化位点：优先保留专有语境，不进行强制本地化替代。",
        "",
        "## 7. 错误避让规则",
        "- 幽默/双关: 不改写为与原意冲突的梗；保守处理可不译。",
        "- 变量一致性: 源字符串中所有变量与参数保持一一对应。",
        "- 标点风格: 避免中文括号、统一俄式引号与空格规则。",
        "",
        "## 8. 术语一致性与优先级",
        "- Approved glossary is mandatory.",
        "- Proposed glossary is advisory; verify with repair tasks.",
        "- Banned terms should be avoided unless explicitly reviewed.",
        "",
        "## 9. Quality Checklist",
        "- [ ] All placeholders and tags preserved exactly.",
        "- [ ] Terminology matched with approved glossary entries.",
        "- [ ] Length constraints respected.",
        "- [ ] No Chinese-only tokens in finalized UI strings.",
        "- [ ] Tone follows this project contract.",
    ])
    return "\n".join(lines).strip() + "\n"


def load_template(path: Optional[str]) -> str:
    if not path:
        return ""
    if not Path(path).exists():
        return ""
    return read_text(path)


def make_llm_style_guide(profile: Dict[str, Any], questionnaire: Dict[str, Any], template: str = "") -> str:
    if LLMClient is None:
        return render_style_guide(profile)
    try:
        client = LLMClient()
    except Exception:
        return render_style_guide(profile)

    system_prompt = (
        "你是游戏本地化项目风格管理员。请基于问卷与机器可验证 profile 输出可用于翻译的 Markdown 风格指南。\n"
        "要求：\n"
        "1) 语言为中文。\n"
        "2) 仅输出完整 Markdown，不要输出解释。\n"
        "3) 强调硬规则（占位符、长度、术语、角色名、错误避让）。\n"
        "4) 保持与 profile 的字段映射可追溯。\n"
    )
    if template:
        system_prompt += f"\n参考模板：\n{template}\n"

    user_prompt = (
        "questionnaire:\n" + json.dumps(questionnaire, ensure_ascii=False, indent=2)
        + "\n\nstyle_profile:\n"
        + json.dumps(profile, ensure_ascii=False, indent=2)
    )
    try:
        result = client.chat(
            system=system_prompt,
            user=user_prompt,
            metadata={"step": "style_guide_bootstrap"},
            response_format={"type": "text"},
        )
        return str(result.text).strip() if hasattr(result, "text") else str(result).strip()
    except Exception:
        return render_style_guide(profile)


def validate_profile(profile: Dict[str, Any]) -> List[str]:
    issues = []
    project = profile.get("project", {})
    ui = profile.get("ui", {})
    terms = profile.get("terminology", {})
    governance = profile.get("style_governance", {})
    if not isinstance(project, dict):
        issues.append("project section invalid")
    else:
        if not project.get("source_language"):
            issues.append("Missing project.source_language")
        if not project.get("target_language"):
            issues.append("Missing project.target_language")
    if not isinstance(ui, dict) or not ui.get("length_constraints"):
        issues.append("Missing ui.length_constraints")
    if not isinstance(terms, dict):
        issues.append("Missing terminology section")
    if not isinstance(governance, dict):
        issues.append("Missing style_governance section")
    else:
        if not governance.get("style_guide_id"):
            issues.append("Missing style_governance.style_guide_id")
        if not governance.get("status"):
            issues.append("Missing style_governance.status")
        if not governance.get("entry_audit"):
            issues.append("Missing style_governance.entry_audit")
    return issues


def main():
    ap = argparse.ArgumentParser(description="Bootstrap style guide + profile from startup questionnaire")
    ap.add_argument("--questionnaire", default="workflow/style_guide_questionnaire.md")
    ap.add_argument("--template", default="")
    ap.add_argument("--guide-output", default="workflow/style_guide.generated.md")
    ap.add_argument("--profile-output", default="workflow/style_profile.generated.yaml")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    questionnaire = parse_questionnaire(read_text(args.questionnaire))
    profile = build_style_profile(questionnaire)
    template = load_template(args.template)

    if not yaml:
        raise RuntimeError("PyYAML required")
    Path(args.profile_output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.profile_output, "w", encoding="utf-8") as f:
        yaml.safe_dump(profile, f, allow_unicode=True, sort_keys=False)

    if args.dry_run:
        guide = render_style_guide(profile)
    else:
        guide = make_llm_style_guide(profile, questionnaire, template)

    issues = validate_profile(profile)
    if issues:
        raise RuntimeError("Style profile schema issue: " + ", ".join(issues))

    Path(args.guide_output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.guide_output, "w", encoding="utf-8") as f:
        f.write(guide + "\n")

    print(f"✅ wrote style profile: {args.profile_output}")
    print(f"✅ wrote generated style guide: {args.guide_output}")


if __name__ == "__main__":
    main()
