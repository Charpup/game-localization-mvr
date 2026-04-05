#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
soft_qa_llm.py (v2.3 - D hard gate)

LLM-based soft quality review for translations.

Review dimensions:
  - terminology_consistency
  - style_contract
  - length
  - placeholders
  - ambiguity_high_risk
"""

import argparse
import csv
import json
import math
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

def configure_standard_streams() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if not stream:
            continue
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
            except Exception:
                pass

try:
    import yaml
except Exception:
    yaml = None

from runtime_adapter import (
    LLMClient,
    LLMError,
    BatchConfig,
    get_batch_config,
    batch_llm_call,
    log_llm_progress,
)
from batch_utils import BatchConfig as SplitBatchConfig, split_into_batches

try:
    from glossary_vectorstore import GlossaryVectorStore
    HAS_RAG = True
except Exception:
    HAS_RAG = False

try:
    from semantic_scorer import SemanticScorer
    HAS_SEMANTIC = True
except Exception:
    HAS_SEMANTIC = False

from translate_llm import GlossaryEntry, build_glossary_preferences, is_ui_art_row, load_glossary
from style_governance_runtime import evaluate_runtime_governance, format_runtime_governance_issues

TOKEN_RE = re.compile(r"⟦(PH_\d+|TAG_\d+)⟧")
RULE_VERSION = "1.0"
REPO_ROOT = Path(__file__).resolve().parent.parent

RULE_CATALOG = {
    "D-SQA-001": {
        "version": RULE_VERSION,
        "issue_type": "length",
        "suggestion": "请按风格合同中的 UI/对话长度上限缩短翻译。",
    },
    "D-SQA-002": {
        "version": RULE_VERSION,
        "issue_type": "placeholder",
        "suggestion": "严格保留变量 token 数量和出现位置，不得新增或改写。",
    },
    "D-SQA-003": {
        "version": RULE_VERSION,
        "issue_type": "style_contract",
        "suggestion": "命中禁译/风格优先项时，按 style_profile 建议修正。",
    },
    "D-SQA-004": {
        "version": RULE_VERSION,
        "issue_type": "terminology",
        "suggestion": "按 approved glossary 替换一致译法，疑难项交由人工确认。",
    },
    "D-SQA-005": {
        "version": RULE_VERSION,
        "issue_type": "ambiguity_high_risk",
        "suggestion": "降低歧义表达，优先保守且一致的译法。",
    },
    "D-SQA-006": {
        "version": RULE_VERSION,
        "issue_type": "style_contract",
        "suggestion": "补齐 style_profile 后重跑软质检。",
    },
    "D-SQA-007": {
        "version": RULE_VERSION,
        "issue_type": "punctuation",
        "suggestion": "修复标点、括号、引号或标签语义偏移后重跑。",
    },
    "D-SQA-008": {
        "version": RULE_VERSION,
        "issue_type": "mistranslation",
        "suggestion": "回退到保守直译并对照 glossary/style_contract 重新翻译。",
    },
    "D-SQA-009": {
        "version": RULE_VERSION,
        "issue_type": "style_contract",
        "suggestion": "修复 style governance / lifecycle gate 后重跑软质检。",
    },
    "D-SQA-010": {
        "version": RULE_VERSION,
        "issue_type": "compact_term_miss",
        "suggestion": "UI-art 行必须优先使用 compact glossary 短译，不要回退到通用长译。",
    },
    "D-SQA-011": {
        "version": RULE_VERSION,
        "issue_type": "compact_mapping_missing",
        "suggestion": "badge / micro label 只能使用已批准的极短译法；没有 compact mapping 时直接进入人工复核。",
    },
    "D-SQA-012": {
        "version": RULE_VERSION,
        "issue_type": "line_budget_overflow",
        "suggestion": "banner / slogan 保持原始行数预算，必要时压缩成更短标题式表达。",
    },
    "D-SQA-013": {
        "version": RULE_VERSION,
        "issue_type": "headline_budget_overflow",
        "suggestion": "headline 类美术字只能保留标题核心，不得扩写成完整说明句。",
    },
    "D-SQA-014": {
        "version": RULE_VERSION,
        "issue_type": "promo_expansion_forbidden",
        "suggestion": "promo compact 标题禁止补 Превью / Выбор / Ниндзя 等冗余扩写。",
    },
}

ISSUE_PRIORITY = {
    "placeholder": 0,
    "compact_mapping_missing": 1,
    "line_budget_overflow": 2,
    "headline_budget_overflow": 3,
    "promo_expansion_forbidden": 4,
    "compact_term_miss": 5,
    "style_contract": 6,
    "terminology": 7,
    "ambiguity_high_risk": 8,
    "mistranslation": 9,
    "punctuation": 10,
    "length": 11,
}

UI_ART_POLICY_TABLE = {
    "badge_micro_1c": {"hard_floor": 4, "review_floor": 6, "review_only": False},
    "badge_micro_2c": {"hard_floor": 6, "review_floor": 8, "review_only": False},
    "label_generic_short": {"hard_floor": 8, "review_floor": 10, "review_ratio": 2.5, "review_only": False},
    "title_name_short": {"hard_floor": 10, "review_floor": 12, "review_ratio": 2.5, "review_only": False},
    "promo_short": {"hard_floor": 10, "review_floor": 12, "review_ratio": 2.6, "review_only": False},
    "item_skill_name": {"hard_floor": 10, "hard_ratio": 2.6, "review_floor": 12, "review_ratio": 3.0, "review_only": False},
    "slogan_long": {"hard_floor": 10, "hard_ratio": 2.6, "review_floor": 12, "review_ratio": 3.2, "review_only": False},
    "other_review": {"hard_floor": 10, "review_floor": 14, "review_ratio": 2.6, "review_only": False},
}
PROMO_BANNED_EXPANSIONS = ("превью", "выбор", "ниндзя")
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+", re.UNICODE)


def load_text(p: str) -> str:
    with open(p, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_yaml(p: str) -> dict:
    if yaml is None:
        raise RuntimeError("PyYAML required: pip install pyyaml")
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_style_profile(path: str) -> dict:
    if not path or not os.path.exists(path):
        return {}
    return load_yaml(path)


def _is_repo_managed_path(path: str) -> bool:
    try:
        Path(path).resolve().relative_to(REPO_ROOT)
        return True
    except Exception:
        return False


def read_gate_config(rubric_yaml: str) -> dict:
    try:
        rubric = load_yaml(rubric_yaml)
        gate = rubric.get("gate", {}) if isinstance(rubric, dict) else {}
    except Exception:
        gate = {}
    return {
        "enabled": bool(gate.get("enabled", False)),
        "severity_threshold": str(gate.get("severity_threshold", gate.get("gate_severity", "major"))).lower(),
        "fail_on_types": [str(x) for x in gate.get("fail_on_types", [])],
    }


def severity_rank(level: str) -> int:
    return {"minor": 1, "major": 2, "critical": 3}.get((level or "").lower(), 0)


def infer_rule_id(issue_type: str) -> str:
    return {
        "length": "D-SQA-001",
        "placeholder": "D-SQA-002",
        "style_contract": "D-SQA-003",
        "terminology": "D-SQA-004",
        "ambiguity_high_risk": "D-SQA-005",
        "punctuation": "D-SQA-007",
        "mistranslation": "D-SQA-008",
        "compact_term_miss": "D-SQA-010",
        "compact_mapping_missing": "D-SQA-011",
        "line_budget_overflow": "D-SQA-012",
        "headline_budget_overflow": "D-SQA-013",
        "promo_expansion_forbidden": "D-SQA-014",
    }.get(issue_type, "D-SQA-006")


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _count_visual_lines(text: str) -> int:
    if not text:
        return 1
    return max(1, len(re.split(r"(?:\\n|\n)", text)))


def _ui_art_length_policy(row: Dict[str, str]) -> Dict[str, Any]:
    category = str(row.get("ui_art_category") or "other_review").strip() or "other_review"
    spec = UI_ART_POLICY_TABLE.get(category, UI_ART_POLICY_TABLE["other_review"])
    source_len = _parse_int(row.get("source_len_clean") or len((row.get("source_zh") or "").strip()))
    placeholder_budget = _parse_int(row.get("placeholder_budget") or 0)
    base_target = _parse_int(row.get("max_length_target") or row.get("max_len_target") or 0)
    base_review = _parse_int(row.get("max_len_review_limit") or 0)
    hard_ratio = spec.get("hard_ratio")
    hard_ratio_limit = math.floor(source_len * float(hard_ratio)) + placeholder_budget if hard_ratio else 0
    review_ratio = spec.get("review_ratio")
    ratio_limit = math.floor(source_len * float(review_ratio)) + placeholder_budget if review_ratio else 0
    target_limit = max(base_target, int(spec.get("hard_floor", 0)) + placeholder_budget, hard_ratio_limit)
    review_limit = max(base_review, int(spec.get("review_floor", 0)) + placeholder_budget, ratio_limit)
    return {
        "category": category,
        "target_limit": target_limit,
        "review_limit": review_limit,
        "review_only": bool(spec.get("review_only", False)),
        "source_lines": _count_visual_lines(row.get("source_zh") or row.get("tokenized_zh") or ""),
        "strategy_hint": str(row.get("ui_art_strategy_hint") or "").strip(),
    }


def _contains_promo_expansion(text: str) -> bool:
    normalized = str(text or "").lower()
    return any(term in normalized for term in PROMO_BANNED_EXPANSIONS)


def _content_word_count(text: str) -> int:
    words = [token for token in WORD_RE.findall(text or "") if not token.isdigit()]
    return len(words)


def read_csv(p: str) -> List[Dict[str, str]]:
    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_json(p: str, obj: Any) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def append_jsonl(p: str, items: List[dict]) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def write_jsonl(p: str, items: List[dict]) -> None:
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def load_checkpoint(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def token_counts(s: str) -> Dict[str, int]:
    d = {}
    for m in TOKEN_RE.finditer(s or ""):
        d[m.group(1)] = d.get(m.group(1), 0) + 1
    return d


def build_style_contract_block(profile: dict) -> str:
    if not profile:
        return "- style_profile unavailable"
    proj = profile.get("project", {}) or {}
    style = profile.get("style_contract", {}) or {}
    ui = profile.get("ui", {}) or {}
    limits = ui.get("length_constraints", {}) or {}
    ui_art_policies = ui.get("ui_art_category_policies", {}) or {}
    guard = style.get("style_guard", {}) or {}
    terms = profile.get("terminology", {}) or {}
    lines = [
        f"- Source/Target: {proj.get('source_language', 'zh-CN')} → {proj.get('target_language', 'ru-RU')}",
        f"- Style policy: over_localization={style.get('language_policy', {}).get('no_over_localization', True)}, over_literal={style.get('language_policy', {}).get('no_over_literal', True)}",
        f"- Placeholder hard protection: {style.get('placeholder_protection', {}).get('preserve_ph_tokens', True)}",
        f"- UI length: button≤{limits.get('button_max_chars', 18)}; dialogue≤{limits.get('dialogue_max_chars', 120)}",
        f"- UI-art target/review ratio: {limits.get('ui_art_target_ratio', 2.3)} / {limits.get('ui_art_review_ratio', 2.5)}",
        f"- Character name policy: {guard.get('character_name_policy', 'keep')}",
        f"- Proper noun strategy: {guard.get('proper_noun_strategy', 'hybrid')}",
        f"- Humor restraint: {guard.get('no_humor_overreach', True)}",
    ]
    for t in terms.get("forbidden_terms", [])[:10]:
        lines.append(f"- Forbidden term: {t}")
    for t in terms.get("banned_terms", [])[:10]:
        lines.append(f"- Banned term: {t}")
    for alias in _prohibited_aliases(profile)[:10]:
        lines.append(f"- Prohibited alias: {alias}")
    for category, policy in list(ui_art_policies.items())[:8]:
        if isinstance(policy, dict):
            lines.append(
                f"- UI-art {category}: {policy.get('translation_rule', 'compact')} / "
                f"hard<={policy.get('hard_limit', '')} / review<={policy.get('review_limit', '')}"
            )
    return "\n".join(lines)


def build_system_batch(style: str, glossary_summary: str, style_profile: Optional[dict] = None) -> str:
    return (
        "你是手游本地化软质检（zh-CN → ru-RU）。\n\n"
        "任务：分析翻译质量，仅列出有问题的项。\n\n"
        "检查维度（只报问题，不要夸）：\n"
        "- 术语一致性（glossary）\n"
        "- compact glossary 是否优先于通用长译\n"
        "- 术语歧义高风险（同一中文术语映射不稳定）\n"
        "- style_contract（禁用语体、角色名策略、变量保护）\n"
        "- UI 长度（按钮/文本上限）\n"
        "- UI-art 分类长度/行数预算\n"
        "- 占位符保护\n"
        "- 标点与符号（中文括号、引号、变量语义）\n\n"
        "输出格式（硬性，仅输出 JSON）：\n"
        "{\n"
        '  "items": [\n'
        "    {\n"
        '      "id": "<id>",\n'
        '      "severity": "minor|major",\n'
        '      "issue_type": "terminology|style_contract|length|placeholder|ambiguity_high_risk|punctuation|mistranslation|compact_term_miss|compact_mapping_missing|line_budget_overflow|headline_budget_overflow|promo_expansion_forbidden",\n'
        '      "problem": "<一句话描述问题>",\n'
        '      "suggestion": "<一句话给出修复方向>",\n'
        '      "preferred_fix_ru": "<可选：建议的修复后俄文>"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "规则：\n"
        "- 没问题则项目不出现在 items 中。\n"
        "- problem/suggestion 为短句。\n"
        "- 每个 id 只输出一条最严重项。\n\n"
        "- 对 UI 美术字：compact glossary 优先级高于通用 glossary。\n"
        "- badge_micro_* 若未使用批准短译，优先报 compact_mapping_missing。\n"
        "- slogan_long 若扩成说明句或增加行数，优先报 line_budget_overflow。\n\n"
        f"术语表摘要（前 50 条）：\n{glossary_summary[:1500]}\n\n"
        f"style_guide（节选）：\n{style[:1000]}\n"
        f"style_contract：\n{build_style_contract_block(style_profile or {})}\n"
    )


def build_user_prompt(items: List[Dict]) -> str:
    return json.dumps(items, ensure_ascii=False, indent=2)


def build_glossary_summary(entries: List[GlossaryEntry], max_entries: int = 50) -> str:
    approved = [e for e in entries if e.status.lower() == "approved"]
    if not approved:
        return "(无)"
    compact = [e for e in approved if e.preferred_compact][: max_entries // 2 or 1]
    standard = [e for e in approved if not e.preferred_compact][: max_entries - len(compact)]
    lines: List[str] = []
    if compact:
        lines.append("[Compact UI-art terms]")
        lines.extend(f"- {e.term_zh} → {e.term_ru}" for e in compact)
    if standard:
        lines.append("[General approved terms]")
        lines.extend(f"- {e.term_zh} → {e.term_ru}" for e in standard)
    return "\n".join(lines)


def _pick_terms(seq: Any) -> List[str]:
    if not isinstance(seq, list):
        return []
    return [str(item).strip() for item in seq if str(item).strip()]


def _prohibited_aliases(profile: dict) -> List[str]:
    aliases: List[str] = []
    items = profile.get("terminology", {}).get("prohibited_aliases", []) or []
    for item in items:
        if isinstance(item, dict):
            alias = str(item.get("alias") or item.get("term_ru") or "").strip()
            if alias:
                aliases.append(alias)
            continue
        text = str(item).strip()
        if not text:
            continue
        if "->" in text:
            text = text.split("->", 1)[1].strip()
        aliases.append(text.strip("\"'[](){} "))
    return [alias for alias in aliases if alias]


def _task_sort_key(task: dict) -> tuple[int, int]:
    severity = severity_rank(str(task.get("severity", "")).lower())
    issue_type = str(task.get("type") or task.get("issue_type") or "")
    return (-severity, ISSUE_PRIORITY.get(issue_type, 99))


def preflight_tasks(rows: List[Dict[str, str]], style_profile: dict, glossary_entries: List[GlossaryEntry]) -> List[dict]:
    tasks: List[dict] = []
    seen = set()
    style_profile = style_profile or {}
    ui = style_profile.get("ui", {}) or {}
    limits = ui.get("length_constraints", {}) or {}
    btn_max = int(limits.get("button_max_chars", 18))
    dlg_max = int(limits.get("dialogue_max_chars", 120))
    terms = style_profile.get("terminology", {}) or {}
    forbidden = set(_pick_terms(terms.get("forbidden_terms", [])))
    banned = set(_pick_terms(terms.get("banned_terms", [])))
    blocked_terms = forbidden | banned
    prohibited_aliases = set(_prohibited_aliases(style_profile))
    preferred = style_profile.get("terminology", {}).get("preferred_terms", []) or []
    preferred_map = {str(p.get("term_zh", "")).strip(): str(p.get("term_ru", "")).strip() for p in preferred if isinstance(p, dict)}

    glossary_map, compact_map, avoid_long_forms = build_glossary_preferences(glossary_entries)

    for r in rows:
        sid = str(r.get("string_id") or r.get("id") or "")
        if not sid:
            continue

        src = r.get("source_zh") or r.get("tokenized_zh") or ""
        tgt = r.get("target_text") or ""
        module = (r.get("module_tag") or "").strip().lower()
        if is_ui_art_row(r):
            policy = _ui_art_length_policy(r)
            target_limit = int(policy["target_limit"] or 0)
            review_limit = int(policy["review_limit"] or 0)
            target_lines = _count_visual_lines(tgt)
            strategy_hint = str(policy.get("strategy_hint") or "")
            compact_rule = str(r.get("compact_rule") or "")
            compact_term = str(r.get("ui_art_compact_term") or "").strip()
            compact_mapping_status = str(r.get("compact_mapping_status") or "")
            exact_compact_pass = compact_term and tgt.strip() == compact_term and (
                compact_rule == "dictionary_only" or strategy_hint in {"promo_exact_head", "headline_nameplate"}
            )
            if (
                str(policy["category"]) == "slogan_long"
                and strategy_hint in {"", "headline_multiline"}
                and target_lines > int(policy["source_lines"] or 1)
            ):
                tasks.append({
                    "string_id": sid,
                    "type": "line_budget_overflow",
                    "severity": "critical",
                    "note": "target line count exceeds source line budget",
                    "problem": "美术字行数预算超限",
                    "suggestion": RULE_CATALOG["D-SQA-012"]["suggestion"],
                    "suggested_fix": tgt,
                    "rule_id": "D-SQA-012",
                    "rule_version": RULE_VERSION,
                    "remediation": RULE_CATALOG["D-SQA-012"]["suggestion"],
                })
                seen.add((sid, "line_budget_overflow"))
            elif compact_rule == "dictionary_only" and compact_mapping_status == "manual_review_required":
                tasks.append({
                    "string_id": sid,
                    "type": "compact_mapping_missing",
                    "severity": "major",
                    "note": "compact-only badge has no approved mapping",
                    "problem": "badge 缺少批准短译",
                    "suggestion": RULE_CATALOG["D-SQA-011"]["suggestion"],
                    "suggested_fix": tgt,
                    "rule_id": "D-SQA-011",
                    "rule_version": RULE_VERSION,
                    "remediation": RULE_CATALOG["D-SQA-011"]["suggestion"],
                })
                seen.add((sid, "compact_mapping_missing"))
            elif exact_compact_pass:
                pass
            elif (
                (compact_rule == "dictionary_only" or strategy_hint == "promo_exact_head")
                and compact_term
                and tgt.strip() != compact_term
            ):
                tasks.append({
                    "string_id": sid,
                    "type": "compact_term_miss",
                    "severity": "major",
                    "note": f"compact-constrained row expects {compact_term}",
                    "problem": "未使用批准短译",
                    "suggestion": f"{RULE_CATALOG['D-SQA-010']['suggestion']} 优先使用 {compact_term}",
                    "suggested_fix": compact_term,
                    "rule_id": "D-SQA-010",
                    "rule_version": RULE_VERSION,
                    "remediation": RULE_CATALOG["D-SQA-010"]["suggestion"],
                })
                seen.add((sid, "compact_term_miss"))
            elif strategy_hint == "promo_compound_pack" and _contains_promo_expansion(tgt):
                tasks.append({
                    "string_id": sid,
                    "type": "promo_expansion_forbidden",
                    "severity": "major",
                    "note": "promo compact title contains banned expansion tail",
                    "problem": "promo 短标题出现冗余扩写",
                    "suggestion": RULE_CATALOG["D-SQA-014"]["suggestion"],
                    "suggested_fix": compact_term or tgt,
                    "rule_id": "D-SQA-014",
                    "rule_version": RULE_VERSION,
                    "remediation": RULE_CATALOG["D-SQA-014"]["suggestion"],
                })
                seen.add((sid, "promo_expansion_forbidden"))
            elif (
                str(policy["category"]) == "item_skill_name"
                and compact_term
                and tgt.strip() != compact_term
                and _content_word_count(tgt) > 2
            ):
                tasks.append({
                    "string_id": sid,
                    "type": "compact_term_miss",
                    "severity": "major",
                    "note": f"item compact noun should prefer {compact_term} and stay within 2 content words",
                    "problem": "item/skill 名称结构过长",
                    "suggestion": f"{RULE_CATALOG['D-SQA-010']['suggestion']} 优先使用 {compact_term}",
                    "suggested_fix": compact_term,
                    "rule_id": "D-SQA-010",
                    "rule_version": RULE_VERSION,
                    "remediation": RULE_CATALOG["D-SQA-010"]["suggestion"],
                })
                seen.add((sid, "compact_term_miss"))
            elif review_limit > 0 and len(tgt) > review_limit:
                overflow_type = "headline_budget_overflow" if strategy_hint.startswith("headline_") else "length"
                rule_id = infer_rule_id(overflow_type)
                tasks.append({
                    "string_id": sid,
                    "type": overflow_type,
                    "severity": "critical",
                    "note": "target length exceeds category review limit",
                    "problem": "headline 预算超出人工复核红线" if overflow_type == "headline_budget_overflow" else "长度超过人工复核红线",
                    "suggestion": RULE_CATALOG[rule_id]["suggestion"],
                    "suggested_fix": tgt,
                    "rule_id": rule_id,
                    "rule_version": RULE_VERSION,
                    "remediation": RULE_CATALOG[rule_id]["suggestion"],
                })
                seen.add((sid, overflow_type))
            elif target_limit > 0 and len(tgt) > target_limit:
                overflow_type = "headline_budget_overflow" if strategy_hint.startswith("headline_") else "length"
                rule_id = infer_rule_id(overflow_type)
                tasks.append({
                    "string_id": sid,
                    "type": overflow_type,
                    "severity": "major",
                    "note": "target length exceeds category target limit",
                    "problem": "headline 超出类别目标上限" if overflow_type == "headline_budget_overflow" else "长度超出类别目标上限",
                    "suggestion": RULE_CATALOG[rule_id]["suggestion"],
                    "suggested_fix": tgt,
                    "rule_id": rule_id,
                    "rule_version": RULE_VERSION,
                    "remediation": RULE_CATALOG[rule_id]["suggestion"],
                })
                seen.add((sid, overflow_type))
        else:
            limit = btn_max if module in {"ui_button", "button", "tab"} else dlg_max
            if limit and len(tgt) > limit:
                tasks.append({
                    "string_id": sid,
                    "type": "length",
                    "severity": "minor",
                    "note": f"target length > {limit}",
                    "problem": "疑似长度过长",
                    "suggestion": RULE_CATALOG["D-SQA-001"]["suggestion"],
                    "suggested_fix": tgt,
                    "rule_id": "D-SQA-001",
                    "rule_version": RULE_VERSION,
                    "remediation": RULE_CATALOG["D-SQA-001"]["suggestion"],
                })
                seen.add((sid, "length"))

        if token_counts(src) != token_counts(tgt):
            key = (sid, "placeholder")
            if key not in seen:
                tasks.append({
                    "string_id": sid,
                    "type": "placeholder",
                    "severity": "major",
                    "note": "token_count_mismatch",
                    "problem": "占位符保护失败",
                    "suggestion": RULE_CATALOG["D-SQA-002"]["suggestion"],
                    "suggested_fix": tgt,
                    "rule_id": "D-SQA-002",
                    "rule_version": RULE_VERSION,
                    "remediation": RULE_CATALOG["D-SQA-002"]["suggestion"],
                })
                seen.add(key)

        for t in blocked_terms:
            if t and t in tgt:
                key = (sid, "blocked_term")
                if key not in seen:
                    tasks.append({
                        "string_id": sid,
                        "type": "style_contract",
                        "severity": "major",
                        "note": f"blocked term {t}",
                        "problem": "命中禁译项",
                        "suggestion": RULE_CATALOG["D-SQA-003"]["suggestion"],
                        "suggested_fix": tgt,
                        "rule_id": "D-SQA-003",
                        "rule_version": RULE_VERSION,
                        "remediation": RULE_CATALOG["D-SQA-003"]["suggestion"],
                    })
                    seen.add(key)

        for alias in prohibited_aliases:
            if alias and alias in tgt:
                key = (sid, "prohibited_alias")
                if key not in seen:
                    tasks.append({
                        "string_id": sid,
                        "type": "style_contract",
                        "severity": "major",
                        "note": f"prohibited alias {alias}",
                        "problem": "命中禁用别名",
                        "suggestion": RULE_CATALOG["D-SQA-003"]["suggestion"],
                        "suggested_fix": tgt,
                        "rule_id": "D-SQA-003",
                        "rule_version": RULE_VERSION,
                        "remediation": RULE_CATALOG["D-SQA-003"]["suggestion"],
                    })
                    seen.add(key)

        if is_ui_art_row(r):
            category = str(r.get("ui_art_category") or "other_review")
            for zh, ru in compact_map.items():
                if zh not in src or not ru:
                    continue
                long_forms = avoid_long_forms.get(zh, [])
                long_form_hit = any(term and term in tgt for term in long_forms)
                if ru not in tgt or long_form_hit:
                    issue_type = "compact_mapping_missing" if category.startswith("badge_micro_") else "compact_term_miss"
                    key = (sid, issue_type)
                    if key in seen:
                        continue
                    catalog = RULE_CATALOG["D-SQA-011" if issue_type == "compact_mapping_missing" else "D-SQA-010"]
                    tasks.append({
                        "string_id": sid,
                        "type": issue_type,
                        "severity": "major" if issue_type == "compact_mapping_missing" else "minor",
                        "note": f"missing compact glossary term {zh}->{ru}",
                        "problem": "UI-art 未使用批准短译",
                        "suggestion": f"{catalog['suggestion']} 优先使用 {ru}",
                        "suggested_fix": tgt,
                        "rule_id": "D-SQA-011" if issue_type == "compact_mapping_missing" else "D-SQA-010",
                        "rule_version": RULE_VERSION,
                        "remediation": catalog["suggestion"],
                    })
                    seen.add(key)

        for zh, ru in glossary_map.items():
            if zh in src and ru and ru not in tgt:
                if is_ui_art_row(r) and zh in compact_map:
                    continue
                if (sid, "term") not in seen:
                    tasks.append({
                        "string_id": sid,
                        "type": "terminology",
                        "severity": "minor",
                        "note": f"missing glossary term {zh}->{ru}",
                        "problem": "疑似术语未按既定译法出现",
                        "suggestion": f"优先使用 {ru}",
                        "suggested_fix": tgt,
                        "rule_id": "D-SQA-004",
                        "rule_version": RULE_VERSION,
                        "remediation": RULE_CATALOG["D-SQA-004"]["suggestion"],
                    })
                    seen.add((sid, "term"))

        for zh, ru in preferred_map.items():
            if is_ui_art_row(r) and zh in compact_map:
                continue
            if zh and ru and zh in src and ru not in tgt and (sid, "style_pref") not in seen:
                tasks.append({
                    "string_id": sid,
                    "type": "style_contract",
                    "severity": "minor",
                    "note": f"preferred form mismatch for {zh}",
                    "problem": "与风格偏好译法不一致",
                    "suggestion": f"优先使用 {ru}",
                    "suggested_fix": tgt,
                    "rule_id": "D-SQA-003",
                    "rule_version": RULE_VERSION,
                    "remediation": RULE_CATALOG["D-SQA-003"]["suggestion"],
                })
                seen.add((sid, "style_pref"))

    if not style_profile:
        tasks.append({
            "string_id": "system",
            "type": "style_contract",
            "severity": "minor",
            "note": "style_profile missing",
            "problem": "风格配置缺失，无法做完整软门禁评审",
            "suggestion": RULE_CATALOG["D-SQA-006"]["suggestion"],
            "suggested_fix": "",
            "rule_id": "D-SQA-006",
            "rule_version": RULE_VERSION,
            "remediation": RULE_CATALOG["D-SQA-006"]["suggestion"],
        })

    return tasks


def process_batch_results(batch_items: List[Dict]) -> List[dict]:
    valid_tasks = []
    for t in batch_items:
        sid = t.get("id", "").strip()
        if not sid:
            continue
        issue_type = str(t.get("issue_type", "issue")).strip()
        rid = t.get("rule_id") or infer_rule_id(issue_type)
        rver = t.get("rule_version") or RULE_CATALOG.get(rid, {}).get("version", RULE_VERSION)
        valid_tasks.append({
            "string_id": sid,
            "type": issue_type,
            "severity": t.get("severity", "minor"),
            "note": f"{t.get('problem', '')} | Suggestion: {t.get('suggestion', '')}",
            "problem": t.get("problem", ""),
            "suggestion": t.get("suggestion", ""),
            "suggested_fix": t.get("preferred_fix_ru", ""),
            "rule_id": rid,
            "rule_version": rver,
            "remediation": RULE_CATALOG.get(rid, {}).get("suggestion", ""),
        })
    return valid_tasks


def merge_tasks(pref: List[dict], llm_tasks: List[dict], cap_per_row: int = 1) -> List[dict]:
    merged = []
    seen = set()
    for task in sorted(pref + llm_tasks, key=_task_sort_key):
        sid = task.get("string_id") or task.get("id")
        typ = task.get("type") or task.get("issue_type")
        if not sid:
            continue
        key = (str(sid), typ)
        if key in seen:
            continue
        seen.add(key)
        if sum(1 for x in merged if x.get("string_id") == sid) >= cap_per_row:
            continue
        merged.append(task)
    return merged


def build_hard_gate(all_tasks: List[dict], gate: dict) -> tuple[bool, List[dict]]:
    if not gate.get("enabled"):
        return False, []
    fail_threshold = severity_rank(gate.get("severity_threshold"))
    fail_types = set(gate.get("fail_on_types", []))
    violations = [
        t for t in all_tasks
        if t.get("type") in fail_types and severity_rank(t.get("severity")) >= fail_threshold
    ]
    return bool(violations), violations


def build_gate_remediation(violations: List[dict]) -> List[str]:
    actions = []
    seen = set()
    for item in violations:
        suggestion = str(item.get("remediation") or item.get("suggestion") or "").strip()
        if suggestion and suggestion not in seen:
            actions.append(suggestion)
            seen.add(suggestion)
    return actions


def build_governance_failure_tasks(report: Dict[str, Any]) -> List[dict]:
    return [
        {
            "string_id": "system",
            "type": "style_contract",
            "severity": "major",
            "note": "style_governance_blocked",
            "problem": "Phase 3 style governance gate failed",
            "suggestion": RULE_CATALOG["D-SQA-009"]["suggestion"],
            "suggested_fix": "",
            "rule_id": "D-SQA-009",
            "rule_version": RULE_VERSION,
            "remediation": RULE_CATALOG["D-SQA-009"]["suggestion"],
            "governance_issues": report.get("issues", []),
        }
    ]


def main():
    configure_standard_streams()
    ap = argparse.ArgumentParser(description="LLM-based soft QA (Batch Mode v2.3)")
    ap.add_argument("translated_csv", nargs="?", help="Input translated.csv")
    ap.add_argument("--input", help="Alias for translated_csv")
    ap.add_argument("style_guide_md", nargs="?", default="workflow/style_guide.md", help="Style guide file")
    ap.add_argument("glossary_yaml", nargs="?", default="data/glossary.yaml", help="Glossary file")
    ap.add_argument("rubric_yaml", nargs="?", default="workflow/soft_qa_rubric.yaml", help="rubric config")
    ap.add_argument("--style-profile", default="data/style_profile.yaml", help="Style profile")
    ap.add_argument("--lifecycle-registry", default="workflow/lifecycle_registry.yaml", help="Lifecycle registry for governed assets")
    ap.add_argument("--batch_size", type=int, default=15)
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    ap.add_argument("--max_batch_tokens", type=int, default=4000)
    ap.add_argument("--out_report", default="data/qa_soft_report.json")
    ap.add_argument("--out_tasks", default="data/repair_tasks.jsonl")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--enable-rag", action="store_true")
    ap.add_argument("--enable-semantic", action="store_true")
    ap.add_argument("--rag-top-k", type=int, default=15)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    input_path = args.input or args.translated_csv
    if not input_path:
        ap.print_help()
        return 1

    print(f"🔍 Soft QA v2.3 (Batch Mode + Style Profile)")
    use_rag = args.enable_rag and HAS_RAG
    use_semantic = args.enable_semantic and HAS_SEMANTIC

    if args.enable_rag and not HAS_RAG:
        print("⚠️  RAG requested but glossary_vectorstore not available")
    if args.enable_semantic and not HAS_SEMANTIC:
        print("⚠️  Semantic requested but semantic_scorer not available")

    rows = read_csv(input_path)
    style = load_text(args.style_guide_md)
    style_profile = load_style_profile(args.style_profile)
    runtime_governance = {"passed": True, "issues": [], "mode": "external_fixture"}
    if _is_repo_managed_path(args.style_profile):
        runtime_governance = evaluate_runtime_governance(
            style_profile_path=args.style_profile,
            glossary_path=args.glossary_yaml if Path(args.glossary_yaml).exists() else "",
            policy_paths=[args.rubric_yaml, "workflow/style_governance_contract.yaml"],
            lifecycle_registry_path=args.lifecycle_registry,
        )
    gate = read_gate_config(args.rubric_yaml)

    glossary_entries = []
    if args.glossary_yaml and Path(args.glossary_yaml).exists():
        glossary_entries, _ = load_glossary(args.glossary_yaml)
    glossary_summary = build_glossary_summary(glossary_entries)

    rows_with_target = [r for r in rows if r.get("target_text")]
    checkpoint_path = Path(args.out_report).parent / "soft_qa_checkpoint.json"
    if args.resume:
        checkpoint = load_checkpoint(checkpoint_path)
        rows_processed = int(checkpoint.get("rows_processed", 0) or 0)
        if rows_processed > 0:
            rows_with_target = rows_with_target[rows_processed:]
    print(f"✅ Loaded {len(rows)} rows, target rows {len(rows_with_target)}")

    if not runtime_governance["passed"]:
        governance_tasks = build_governance_failure_tasks(runtime_governance)
        report = {
            "version": "2.3",
            "mode": "batch",
            "has_findings": True,
            "summary": {"major": 1, "minor": 0, "total_tasks": len(governance_tasks)},
            "outputs": {"repair_tasks_jsonl": args.out_tasks},
            "metadata": {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "rubric_profile_version": (style_profile.get("version") or ""),
                "gate": gate,
                "runtime_governance": runtime_governance,
            },
            "hard_gate": {
                "enabled": True,
                "rule_id": "PHASE3_STYLE_GOVERNANCE",
                "rule_version": RULE_VERSION,
                "severity_threshold": "major",
                "fail_on_types": ["style_contract"],
                "violations": governance_tasks,
                "suggested_actions": [RULE_CATALOG["D-SQA-009"]["suggestion"]],
                "status": "fail",
                "remediation": RULE_CATALOG["D-SQA-009"]["suggestion"],
            },
        }
        print(format_runtime_governance_issues(runtime_governance))
        write_json(args.out_report, report)
        write_jsonl(args.out_tasks, governance_tasks)
        return 2

    pre_tasks = preflight_tasks(rows_with_target, style_profile, glossary_entries)
    hard_fail_pre, pre_failures = build_hard_gate(pre_tasks, gate)

    if args.dry_run:
        print("⚙️  dry-run mode")
        report = {
            "version": "2.3",
            "mode": "batch",
            "has_findings": bool(pre_tasks),
            "summary": {"major": 0, "minor": 0, "total_tasks": len(pre_tasks)},
            "outputs": {"repair_tasks_jsonl": args.out_tasks},
            "metadata": {
                "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "dry_run": True,
                "runtime_governance": runtime_governance,
            },
            "hard_gate": {
                "enabled": gate.get("enabled", False),
                "rule_id": gate.get("rule_id", "STEP1_TERM_STYLE_DRIFT"),
                "rule_version": gate.get("rule_version", RULE_VERSION),
                "severity_threshold": gate.get("severity_threshold"),
                "fail_on_types": gate.get("fail_on_types", []),
                "violations": pre_failures,
                "suggested_actions": build_gate_remediation(pre_failures),
                "status": "fail" if hard_fail_pre else "pass",
            },
        }
        if pre_failures:
            report["hard_gate"]["remediation"] = "修复 style profile / 禁译词 / 长度 / 占位符问题后重试。"
        if pre_tasks:
            for t in pre_tasks:
                t["severity"] = t.get("severity", "minor")
                t["rule_id"] = t.get("rule_id", "D-SQA-006")
                t["rule_version"] = t.get("rule_version", RULE_VERSION)
            major = sum(1 for x in pre_tasks if x.get("severity") == "major")
            report["summary"]["major"] = major
            report["summary"]["minor"] = len(pre_tasks) - major
            append_jsonl(args.out_tasks, pre_tasks)
        write_json(args.out_report, report)
        if hard_fail_pre:
            print("❌ Soft QA hard gate triggered.")
            return 2
        print("✅ Dry-run complete.")
        return 0

    llm = LLMClient()
    start_time = time.time()
    major = 0
    minor = 0

    batch_rows = []
    for r in rows_with_target:
        src = r.get("source_zh") or r.get("tokenized_zh") or ""
        tgt = r.get("target_text") or ""
        batch_rows.append({"id": r.get("string_id"), "source_text": f"SRC: {src} | TGT: {tgt}"})

    try:
        batch_results = batch_llm_call(
            step="soft_qa",
            rows=batch_rows,
            model=args.model,
            system_prompt=build_system_batch(style, glossary_summary, style_profile=style_profile),
            user_prompt_template=build_user_prompt,
            content_type="normal",
            retry=1,
            allow_fallback=True,
            partial_match=True,
            output_dir=str(Path(args.out_report).parent),
        )
        llm_tasks = process_batch_results(batch_results)
    except Exception as e:
        print(f"❌ Soft QA failed: {e}")
        return 1

    all_tasks = merge_tasks(pre_tasks, llm_tasks)
    hard_fail, hard_failures = build_hard_gate(all_tasks, gate)
    if all_tasks:
        append_jsonl(args.out_tasks, all_tasks)
        major = sum(1 for t in all_tasks if t.get("severity") == "major")
        minor = len(all_tasks) - major

    elapsed = int(time.time() - start_time)
    report = {
        "version": "2.3",
        "mode": "batch",
        "has_findings": bool(all_tasks),
        "summary": {
            "major": major,
            "minor": minor,
            "total_tasks": len(all_tasks),
            "rows_processed": len(rows_with_target),
            "runtime_seconds": elapsed,
            "preflight_tasks": len(pre_tasks),
        },
        "outputs": {"repair_tasks_jsonl": args.out_tasks},
        "metadata": {
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "rubric_profile_version": (style_profile.get("version") or ""),
            "gate": gate,
            "runtime_governance": runtime_governance,
        },
        "hard_gate": {
            "enabled": gate.get("enabled", False),
            "rule_id": gate.get("rule_id", "STEP1_TERM_STYLE_DRIFT"),
            "rule_version": gate.get("rule_version", RULE_VERSION),
            "severity_threshold": gate.get("severity_threshold"),
            "fail_on_types": gate.get("fail_on_types", []),
            "violations": hard_failures,
            "suggested_actions": build_gate_remediation(hard_failures),
            "status": "fail" if hard_fail else "pass",
        },
    }
    if hard_fail:
        report["hard_gate"]["remediation"] = "修复触发规则项后重跑 soft QA，不允许跳过硬门禁。"
    write_json(args.out_report, report)

    print(f"📊 Soft QA Summary: rows={len(rows_with_target)} major={major} minor={minor} total={len(all_tasks)}")
    if all_tasks:
        print(f"✅ Report: {args.out_report}")
        print(f"✅ Tasks: {args.out_tasks}")
    if hard_fail:
        print("❌ Soft QA hard gate triggered.")
        return 2
    return 0


if __name__ == "__main__":
    exit(main())
