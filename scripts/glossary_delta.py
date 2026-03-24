#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Milestone E typed delta engine with a compatibility layer for legacy glossary
and translated row shapes.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml
except ImportError:
    print("PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


GLOSSARY_RULE = "glossary"
STYLE_RULE = "style_profile"
RUBRIC_RULE = "rubric"
PLACEHOLDER_RULE = "rule"
CONTENT_RULE = "content"
LEGACY_TARGET_FIELDS = ("target_text", "target_ru", "target")
HIGH_RISK_CLASSES = {"payment", "system", "proper_noun", "live_ops", "ui_button"}
PLACEHOLDER_PATTERN = re.compile(r"(⟦(?:PH|TAG)_\d+⟧|\{[^{}]+\}|%[sdif]|\[[A-Z0-9_]+\]|\\[ntr]|【|】)")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


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


def _read_yaml(path: str) -> Dict[str, Any]:
    if not path or not Path(path).exists():
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _sha256_path(path: str) -> str:
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    digest = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def _load_hash_with_lock(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return ""
    lock_path = p.with_suffix(".lock.json")
    if lock_path.exists():
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            if lock.get("hash"):
                return str(lock["hash"])
        except Exception:
            pass
    return _sha256_path(path)


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


def _target_value_for_locale(targets: Any, target_locale: str) -> str:
    if not isinstance(targets, dict):
        return ""
    normalized_targets: Dict[str, str] = {}
    for locale, value in targets.items():
        locale_key = _normalize_locale(locale)
        term_value = str(value or "").strip()
        if locale_key and term_value:
            normalized_targets[locale_key] = term_value
    return normalized_targets.get(_normalize_locale(target_locale), "")


def _pick_target_locale(explicit: str, profile: Dict[str, Any], glossary_data: Dict[str, Any]) -> str:
    if explicit:
        return _normalize_locale(explicit) or explicit
    locale = str((profile.get("project", {}) or {}).get("target_language") or "").strip()
    if locale:
        return _normalize_locale(locale) or locale
    locales = glossary_data.get("meta", {}).get("target_locales", []) if isinstance(glossary_data, dict) else []
    if isinstance(locales, list) and locales:
        first_locale = _normalize_locale(str(locales[0]).strip())
        return first_locale or "ru-RU"
    return "ru-RU"


def _legacy_target_from_entry(entry: Dict[str, Any], target_locale: str) -> str:
    resolved = _target_value_for_locale(entry.get("targets"), target_locale)
    if resolved:
        return resolved
    if _is_ru_locale(target_locale):
        return str(entry.get("term_ru") or "").strip()
    return ""


def load_compiled(path: str, target_locale: str = "ru-RU") -> Tuple[Dict[str, str], str, Dict[str, Any]]:
    data = _read_yaml(path)
    entries = data.get("entries", []) if isinstance(data, dict) else []
    term_map: Dict[str, str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        term_zh = str(entry.get("term_zh") or "").strip()
        if not term_zh:
            continue
        target_value = _legacy_target_from_entry(entry, target_locale)
        if target_value:
            term_map[term_zh] = target_value
    return term_map, _load_hash_with_lock(path), data


def compute_glossary_delta(old_map: Dict[str, str], new_map: Dict[str, str], target_locale: str) -> Dict[str, List[Dict[str, Any]]]:
    added: List[Dict[str, Any]] = []
    changed: List[Dict[str, Any]] = []
    removed: List[Dict[str, Any]] = []
    old_keys = set(old_map)
    new_keys = set(new_map)

    for term_zh in sorted(new_keys - old_keys):
        added.append({"term_zh": term_zh, "targets": {target_locale: new_map[term_zh]}, "delta_type": "term_added"})
    for term_zh in sorted(old_keys & new_keys):
        if old_map[term_zh] != new_map[term_zh]:
            changed.append(
                {
                    "term_zh": term_zh,
                    "old_targets": {target_locale: old_map[term_zh]},
                    "new_targets": {target_locale: new_map[term_zh]},
                    "delta_type": "term_changed",
                }
            )
    for term_zh in sorted(old_keys - new_keys):
        removed.append({"term_zh": term_zh, "old_targets": {target_locale: old_map[term_zh]}, "delta_type": "term_removed"})
    return {"added": added, "changed": changed, "removed": removed}


def _preferred_map(profile: Dict[str, Any], target_locale: str) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for item in (profile.get("terminology", {}) or {}).get("preferred_terms", []) or []:
        if not isinstance(item, dict):
            continue
        term_zh = str(item.get("term_zh") or "").strip()
        target = _target_value_for_locale(item.get("targets"), target_locale)
        if not target and _is_ru_locale(target_locale):
            target = str(item.get("term_ru") or item.get("term_target") or "").strip()
        if term_zh and target:
            result[term_zh] = target
    return result


def _string_set(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    result: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            alias = str(item.get("alias") or item.get("term") or item.get("term_ru") or "").strip()
            if alias:
                result.add(alias)
            continue
        text = str(item or "").strip()
        if not text:
            continue
        if "->" in text:
            text = text.split("->", 1)[1].strip()
        result.add(text.strip("\"'[](){} "))
    return result


def diff_style_profile(old_profile: Dict[str, Any], new_profile: Dict[str, Any], target_locale: str) -> Dict[str, Any]:
    old_terms = old_profile.get("terminology", {}) or {}
    new_terms = new_profile.get("terminology", {}) or {}
    old_pref = _preferred_map(old_profile, target_locale)
    new_pref = _preferred_map(new_profile, target_locale)
    preferred_changed: List[Dict[str, Any]] = []

    for term_zh in sorted(set(old_pref) | set(new_pref)):
        if old_pref.get(term_zh) != new_pref.get(term_zh):
            preferred_changed.append(
                {
                    "term_zh": term_zh,
                    "old_targets": {target_locale: old_pref.get(term_zh, "")},
                    "new_targets": {target_locale: new_pref.get(term_zh, "")},
                    "delta_type": "preferred_term_changed",
                }
            )

    return {
        "preferred_term_changed": preferred_changed,
        "banned_term_changed": sorted(_string_set(new_terms.get("banned_terms", [])) - _string_set(old_terms.get("banned_terms", []))),
        "prohibited_alias_changed": sorted(
            _string_set(new_terms.get("prohibited_aliases", [])) - _string_set(old_terms.get("prohibited_aliases", []))
        ),
        "style_contract_changed": old_profile.get("style_contract", {}) != new_profile.get("style_contract", {}),
        "risk_class_changed": old_profile.get("ui", {}) != new_profile.get("ui", {}),
    }


def diff_rubric(old_rubric: Dict[str, Any], new_rubric: Dict[str, Any]) -> bool:
    return (old_rubric.get("gate", {}) if isinstance(old_rubric, dict) else {}) != (
        new_rubric.get("gate", {}) if isinstance(new_rubric, dict) else {}
    )


def diff_placeholder_schema(old_schema: Dict[str, Any], new_schema: Dict[str, Any]) -> bool:
    return bool(old_schema and new_schema and old_schema != new_schema)


def read_csv_rows(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def _content_class(row: Dict[str, str]) -> str:
    module = str(row.get("module_tag") or row.get("module") or row.get("segment_type") or "").strip().lower()
    if any(token in module for token in ("button", "tab", "menu")):
        return "ui_button"
    if any(token in module for token in ("payment", "billing", "shop", "charge", "currency")):
        return "payment"
    if any(token in module for token in ("system", "error", "notice", "warning", "tutorial")):
        return "system"
    if any(token in module for token in ("dialog", "dialogue")):
        return "dialogue"
    if any(token in module for token in ("story", "narrative", "quest", "cutscene")):
        return "narrative"
    if any(token in module for token in ("character", "npc", "name", "proper", "place")):
        return "proper_noun"
    if any(token in module for token in ("event", "live", "activity", "season")):
        return "live_ops"
    return "general"


def _risk_level(content_class: str) -> str:
    if content_class in HIGH_RISK_CLASSES:
        return "high"
    if content_class in {"dialogue", "narrative"}:
        return "medium"
    return "low"


def _current_target(row: Dict[str, str], target_locale: str) -> str:
    locale_field = f"target_{_normalize_locale(target_locale).split('-', 1)[0]}"
    keys = (locale_field,)
    if _is_ru_locale(target_locale):
        keys = keys + LEGACY_TARGET_FIELDS
    for key in keys:
        value = str(row.get(key) or "").strip()
        if value:
            return value
    return ""


def _target_locale(row: Dict[str, str], fallback: str) -> str:
    value = str(row.get("target_locale") or row.get("locale") or "").strip()
    return value or fallback


def _has_placeholder(text: str) -> bool:
    return bool(PLACEHOLDER_PATTERN.search(text or ""))


def _normalize_change_events(change_events: Any) -> List[Dict[str, Any]]:
    if not isinstance(change_events, list):
        return []
    return [event for event in change_events if isinstance(event, dict) and event.get("change_type")]


def _event_applies(event: Dict[str, Any], row: Dict[str, str], content_class: str) -> bool:
    string_ids = event.get("string_ids") or []
    if isinstance(string_ids, list) and row.get("string_id") in {str(v) for v in string_ids}:
        return True
    classes = event.get("content_classes") or []
    return isinstance(classes, list) and content_class in {str(v) for v in classes}


def _append_reason(bucket: Dict[str, Any], delta_type: str, reason_code: str, reason_text: str, rule_ref: str) -> None:
    bucket["delta_types"].append(delta_type)
    bucket["reason_codes"].append(reason_code)
    bucket["reason_text_parts"].append(reason_text)
    bucket["rule_refs"].append(rule_ref)


def _build_recommended_action(delta_types: Iterable[str], content_class: str, risk_level: str) -> Tuple[str, bool, str]:
    delta_set = set(delta_types)
    hard_gate_types = {
        "term_removed",
        "banned_term_changed",
        "prohibited_alias_changed",
        "style_contract_changed",
        "placeholder_policy_changed",
    }
    if risk_level == "high" and delta_set:
        return "manual_review", True, f"high-risk content class {content_class}"
    if delta_set & hard_gate_types:
        reason = ", ".join(sorted(delta_set & hard_gate_types))
        return "manual_review", True, f"hard gate reason(s): {reason}"
    if delta_set & {"rubric_gate_changed", "risk_class_changed", "text_diff"}:
        return "retranslate", False, ""
    if delta_set & {"term_added", "term_changed", "preferred_term_changed"}:
        return "auto_refresh", False, ""
    return "skip", False, ""


def build_row_impacts(
    rows: List[Dict[str, str]],
    target_locale: str,
    glossary_delta: Dict[str, List[Dict[str, Any]]],
    style_delta: Dict[str, Any],
    rubric_changed: bool,
    placeholder_changed: bool,
    change_events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    impacts: List[Dict[str, Any]] = []
    preferred_changed = style_delta.get("preferred_term_changed", [])
    banned_terms = set(style_delta.get("banned_term_changed", []))
    aliases = set(style_delta.get("prohibited_alias_changed", []))
    normalized_target_locale = _normalize_locale(target_locale)

    for row in rows:
        string_id = str(row.get("string_id") or "").strip()
        if not string_id:
            continue
        source_zh = str(row.get("source_zh") or row.get("tokenized_zh") or "").strip()
        current_target = _current_target(row, target_locale)
        row_locale = _target_locale(row, target_locale)
        content_class = _content_class(row)
        risk_level = _risk_level(content_class)
        bucket: Dict[str, Any] = {
            "delta_types": [],
            "reason_codes": [],
            "reason_text_parts": [],
            "rule_refs": [],
        }

        glossary_locale_matches = _normalize_locale(row_locale) == normalized_target_locale

        for item in glossary_delta.get("added", []):
            if glossary_locale_matches and item["term_zh"] in source_zh:
                _append_reason(bucket, "term_added", "GLOSSARY_TERM_ADDED", f"source contains newly added glossary term {item['term_zh']}", GLOSSARY_RULE)

        for item in glossary_delta.get("changed", []):
            old_target = str((item.get("old_targets") or {}).get(row_locale) or "").strip()
            if glossary_locale_matches and (item["term_zh"] in source_zh or (old_target and old_target in current_target)):
                _append_reason(bucket, "term_changed", "GLOSSARY_TERM_CHANGED", f"source depends on changed glossary term {item['term_zh']}", GLOSSARY_RULE)

        for item in glossary_delta.get("removed", []):
            old_target = str((item.get("old_targets") or {}).get(row_locale) or "").strip()
            if glossary_locale_matches and (item["term_zh"] in source_zh or (old_target and old_target in current_target)):
                _append_reason(bucket, "term_removed", "GLOSSARY_TERM_REMOVED", f"row depends on removed glossary term {item['term_zh']}", GLOSSARY_RULE)

        for item in preferred_changed:
            if item["term_zh"] in source_zh:
                _append_reason(bucket, "preferred_term_changed", "STYLE_PREFERRED_TERM_CHANGED", f"preferred term changed for {item['term_zh']}", STYLE_RULE)

        for banned_term in banned_terms:
            if banned_term and banned_term in current_target:
                _append_reason(bucket, "banned_term_changed", "STYLE_BANNED_TERM_CHANGED", f"current target contains banned term {banned_term}", STYLE_RULE)

        for alias in aliases:
            if alias and alias in current_target:
                _append_reason(bucket, "prohibited_alias_changed", "STYLE_PROHIBITED_ALIAS_CHANGED", f"current target contains prohibited alias {alias}", STYLE_RULE)

        if style_delta.get("style_contract_changed") and current_target:
            _append_reason(bucket, "style_contract_changed", "STYLE_CONTRACT_CHANGED", "style contract changed for active locale", STYLE_RULE)
        if style_delta.get("risk_class_changed") and current_target:
            _append_reason(bucket, "risk_class_changed", "RISK_CLASS_CHANGED", f"risk classification inputs changed for {content_class}", STYLE_RULE)
        if placeholder_changed and _has_placeholder(source_zh):
            _append_reason(
                bucket,
                "placeholder_policy_changed",
                "PLACEHOLDER_POLICY_CHANGED",
                "placeholder schema changed for placeholder-bearing row",
                PLACEHOLDER_RULE,
            )
        if rubric_changed and current_target:
            _append_reason(bucket, "rubric_gate_changed", "RUBRIC_GATE_CHANGED", "rubric gate semantics changed for review routing", RUBRIC_RULE)

        for event in change_events:
            change_type = str(event.get("change_type") or "").strip()
            if not change_type or not _event_applies(event, row, content_class):
                continue
            if change_type == "content":
                _append_reason(bucket, "text_diff", "CONTENT_TEXT_DIFF", str(event.get("reason") or "explicit content delta event"), CONTENT_RULE)
            elif change_type == "rule":
                _append_reason(bucket, "risk_class_changed", "RULE_CHANGE_EVENT", str(event.get("reason") or "explicit rule change event"), CONTENT_RULE)

        if not bucket["delta_types"]:
            continue

        recommended_action, manual_review_required, manual_review_reason = _build_recommended_action(
            bucket["delta_types"], content_class, risk_level
        )
        impacts.append(
            {
                "string_id": string_id,
                "source_zh": source_zh,
                "current_target": current_target,
                "target_locale": row_locale,
                "content_class": content_class,
                "risk_level": risk_level,
                "delta_types": sorted(set(bucket["delta_types"])),
                "reason_codes": sorted(set(bucket["reason_codes"])),
                "reason_text": "; ".join(dict.fromkeys(bucket["reason_text_parts"])),
                "rule_refs": sorted(set(bucket["rule_refs"])),
                "placeholder_locked": _has_placeholder(source_zh),
                "manual_review_required": manual_review_required,
                "manual_review_reason": manual_review_reason,
                "recommended_action": recommended_action,
            }
        )

    impacts.sort(key=lambda item: item["string_id"])
    return impacts


def _write_json(path: str, payload: Dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: str, rows: List[Dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _derive_rows_path(report_path: str) -> str:
    return str(Path(report_path).parent / "delta_rows.jsonl")


def _build_inputs_meta(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "source_csv": args.source_csv,
        "old_glossary": {"path": args.old, "hash": _load_hash_with_lock(args.old)},
        "new_glossary": {"path": args.new, "hash": _load_hash_with_lock(args.new)},
        "old_style_profile": {"path": args.old_style_profile, "hash": _sha256_path(args.old_style_profile)},
        "new_style_profile": {"path": args.new_style_profile, "hash": _sha256_path(args.new_style_profile)},
        "old_rubric": {"path": args.old_rubric, "hash": _sha256_path(args.old_rubric)},
        "new_rubric": {"path": args.new_rubric, "hash": _sha256_path(args.new_rubric)},
        "old_placeholder_schema": {"path": args.old_placeholder_schema, "hash": _sha256_path(args.old_placeholder_schema)},
        "new_placeholder_schema": {"path": args.new_placeholder_schema, "hash": _sha256_path(args.new_placeholder_schema)},
    }


def _change_counts(glossary_delta: Dict[str, List[Dict[str, Any]]], style_delta: Dict[str, Any], rubric_changed: bool, placeholder_changed: bool) -> Dict[str, int]:
    return {
        "term_added": len(glossary_delta.get("added", [])),
        "term_changed": len(glossary_delta.get("changed", [])),
        "term_removed": len(glossary_delta.get("removed", [])),
        "preferred_term_changed": len(style_delta.get("preferred_term_changed", [])),
        "banned_term_changed": len(style_delta.get("banned_term_changed", [])),
        "prohibited_alias_changed": len(style_delta.get("prohibited_alias_changed", [])),
        "style_contract_changed": int(bool(style_delta.get("style_contract_changed"))),
        "placeholder_policy_changed": int(bool(placeholder_changed)),
        "rubric_gate_changed": int(bool(rubric_changed)),
        "risk_class_changed": int(bool(style_delta.get("risk_class_changed"))),
    }


def _recommended_rerun_scope(impacts: List[Dict[str, Any]]) -> str:
    actions = {impact["recommended_action"] for impact in impacts}
    if "manual_review" in actions:
        return "manual_review_required"
    if "retranslate" in actions:
        return "retranslate_rows"
    if "auto_refresh" in actions:
        return "auto_refresh_candidates"
    return "no_op"


def load_request(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _apply_request_defaults(args: argparse.Namespace, request: Dict[str, Any]) -> None:
    args.run_id = str(request.get("run_id") or args.run_id or "milestone-e-delta")
    args.source_csv = str(request.get("source_csv") or args.source_csv or "")
    args.old = str(request.get("old_glossary") or args.old or "")
    args.new = str(request.get("new_glossary") or args.new or "")
    args.old_style_profile = str(request.get("old_style_profile") or args.old_style_profile or "")
    args.new_style_profile = str(request.get("new_style_profile") or request.get("style_profile") or args.new_style_profile or "")
    args.old_rubric = str(request.get("old_rubric") or args.old_rubric or "")
    args.new_rubric = str(request.get("rubric") or request.get("new_rubric") or args.new_rubric or "")
    args.old_placeholder_schema = str(request.get("old_placeholder_schema") or args.old_placeholder_schema or "")
    args.new_placeholder_schema = str(request.get("new_placeholder_schema") or request.get("placeholder_schema") or args.new_placeholder_schema or "")
    args.target_locale = str(request.get("target_locale") or args.target_locale or "")
    if not args.out_impact and request.get("out_report"):
        args.out_impact = str(request["out_report"])
    if not args.out_rows and request.get("out_rows"):
        args.out_rows = str(request["out_rows"])
    args.change_events = _normalize_change_events(request.get("change_events"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Milestone E typed delta engine")
    parser.add_argument("--request", help="delta_request.json path")
    parser.add_argument("--run-id", default="milestone-e-delta")
    parser.add_argument("--target-locale", default="")
    parser.add_argument("--old", default="", help="Old glossary path")
    parser.add_argument("--new", default="", help="New glossary path")
    parser.add_argument("--source_csv", default="", help="Translated/source CSV path")
    parser.add_argument("--old-style-profile", default="")
    parser.add_argument("--new-style-profile", default="")
    parser.add_argument("--old-rubric", default="")
    parser.add_argument("--new-rubric", default="")
    parser.add_argument("--old-placeholder-schema", default="")
    parser.add_argument("--new-placeholder-schema", default="")
    parser.add_argument("--out_impact", default="data/delta_report.json", help="Delta report JSON")
    parser.add_argument("--out_rows", default="", help="Delta row impacts JSONL")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    args.change_events = []
    if args.request:
        _apply_request_defaults(args, load_request(args.request))
    if not args.old or not args.new or not args.source_csv:
        parser.error("--old, --new, and --source_csv are required unless provided via --request")

    preview_glossary = _read_yaml(args.new)
    preview_profile = _read_yaml(args.new_style_profile)
    target_locale = _pick_target_locale(args.target_locale, preview_profile, preview_glossary)
    args.target_locale = target_locale
    if not args.out_rows:
        args.out_rows = _derive_rows_path(args.out_impact)

    old_glossary, old_hash, _ = load_compiled(args.old, target_locale)
    new_glossary, new_hash, _ = load_compiled(args.new, target_locale)
    rows = read_csv_rows(args.source_csv)
    glossary_delta = compute_glossary_delta(old_glossary, new_glossary, target_locale)
    style_delta = diff_style_profile(_read_yaml(args.old_style_profile), _read_yaml(args.new_style_profile), target_locale)
    rubric_changed = diff_rubric(_read_yaml(args.old_rubric), _read_yaml(args.new_rubric))
    placeholder_changed = diff_placeholder_schema(_read_yaml(args.old_placeholder_schema), _read_yaml(args.new_placeholder_schema))
    impacts = build_row_impacts(
        rows,
        target_locale,
        glossary_delta,
        style_delta,
        rubric_changed,
        placeholder_changed,
        args.change_events,
    )
    impacted_rows_by_content_class: Dict[str, int] = {}
    impacted_rows_by_locale: Dict[str, int] = {}
    high_risk_queue_total = 0
    for impact in impacts:
        impact_locale = str(impact.get("target_locale") or target_locale).strip() or target_locale
        impacted_rows_by_locale[impact_locale] = impacted_rows_by_locale.get(impact_locale, 0) + 1
        impacted_rows_by_content_class[impact["content_class"]] = impacted_rows_by_content_class.get(impact["content_class"], 0) + 1
        if impact["risk_level"] == "high":
            high_risk_queue_total += 1

    report = {
        "delta_version": "1.0",
        "run_id": args.run_id,
        "target_locale": target_locale,
        "inputs": _build_inputs_meta(args),
        "change_counts": _change_counts(glossary_delta, style_delta, rubric_changed, placeholder_changed),
        "impacted_rows_total": len(impacts),
        "impacted_rows_by_locale": impacted_rows_by_locale,
        "impacted_rows_by_content_class": impacted_rows_by_content_class,
        "high_risk_queue_total": high_risk_queue_total,
        "recommended_rerun_scope": _recommended_rerun_scope(impacts),
        "row_impacts_path": args.out_rows,
        "generated_at": _now_iso(),
        "delta_terms": glossary_delta,
        "impact_set": [impact["string_id"] for impact in impacts],
        "glossary_hash_old": old_hash,
        "glossary_hash_new": new_hash,
        "refresh_needed": bool(impacts),
    }

    print("Typed Delta Analysis")
    print(f"  target_locale: {target_locale}")
    print(f"  old_glossary_terms: {len(old_glossary)}")
    print(f"  new_glossary_terms: {len(new_glossary)}")
    print(f"  impacted_rows: {len(impacts)}")
    print(f"  rerun_scope: {report['recommended_rerun_scope']}")

    if args.dry_run:
        return 0

    _write_json(args.out_impact, report)
    _write_jsonl(args.out_rows, impacts)
    print(f"  wrote_report: {args.out_impact}")
    print(f"  wrote_rows: {args.out_rows}")
    return 0


if __name__ == "__main__":
    configure_standard_streams()
    raise SystemExit(main())
