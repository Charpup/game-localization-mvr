#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ui_art_length_review.py

Review zh-CN -> ru-RU UI art output against strict per-row limits.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional


UI_ART_POLICY_TABLE = {
    "badge_micro_1c": {"hard_floor": 4, "review_floor": 6},
    "badge_micro_2c": {"hard_floor": 6, "review_floor": 8},
    "label_generic_short": {"hard_floor": 8, "review_floor": 10, "review_ratio": 2.5},
    "title_name_short": {"hard_floor": 10, "review_floor": 12, "review_ratio": 2.5},
    "promo_short": {"hard_floor": 10, "review_floor": 12, "review_ratio": 2.6},
    "item_skill_name": {"hard_floor": 10, "hard_ratio": 2.6, "review_floor": 12, "review_ratio": 3.0},
    "slogan_long": {"hard_floor": 10, "hard_ratio": 2.6, "review_floor": 12, "review_ratio": 3.2},
    "other_review": {"hard_floor": 10, "review_floor": 14, "review_ratio": 2.6},
}
PROMO_BANNED_EXPANSIONS = ("превью", "выбор", "ниндзя")
WORD_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9]+", re.UNICODE)


def _parse_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _count_visual_lines(text: str) -> int:
    if not text:
        return 1
    return max(1, len(re.split(r"(?:\\n|\n)", text)))


def _build_length_policy(row: Dict[str, str]) -> Dict[str, int | str | bool]:
    category = str(row.get("ui_art_category") or "other_review").strip() or "other_review"
    spec = UI_ART_POLICY_TABLE.get(category, UI_ART_POLICY_TABLE["other_review"])
    source_len = _parse_int(row.get("source_len_clean", "0") or "0")
    placeholder_budget = _parse_int(row.get("placeholder_budget", "0") or "0")
    base_target = _parse_int(row.get("max_len_target", "0") or "0")
    base_review = _parse_int(row.get("max_len_review_limit", "0") or "0")
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
        "source_lines": _count_visual_lines(row.get("source_zh", "") or ""),
        "compact_rule": str(row.get("compact_rule") or ""),
        "compact_term": str(row.get("ui_art_compact_term") or "").strip(),
        "compact_mapping_status": str(row.get("compact_mapping_status") or ""),
        "strategy_hint": str(row.get("ui_art_strategy_hint") or "").strip(),
    }


def _contains_promo_expansion(text: str) -> bool:
    normalized = str(text or "").lower()
    return any(term in normalized for term in PROMO_BANNED_EXPANSIONS)


def _content_word_count(text: str) -> int:
    words = [token for token in WORD_RE.findall(text or "") if not token.isdigit()]
    return len(words)


def _category_reason(category: str, severity: str, line_overflow: bool, compact_issue: str = "") -> str:
    if line_overflow:
        return "line_budget_overflow"
    if compact_issue:
        return compact_issue
    if severity == "warning":
        return f"{category}_near_limit"
    return f"{category}_overflow"


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def classify_row(row: Dict[str, str], source_col: str, target_col: str) -> Optional[Dict[str, str]]:
    source_text = row.get(source_col, "") or ""
    target_text = row.get(target_col, "") or ""
    if not source_text.strip() or not target_text.strip():
        return None

    source_len = int(row.get("source_len_clean", "0") or len(source_text))
    target_len = len(target_text)
    policy = _build_length_policy(row)
    max_len_target = int(policy["target_limit"] or 0)
    max_len_review_limit = int(policy["review_limit"] or 0)
    ratio = round(target_len / source_len, 2) if source_len else 0.0
    target_lines = _count_visual_lines(target_text)
    strategy_hint = str(policy.get("strategy_hint") or "")
    line_overflow = (
        str(policy["category"]) == "slogan_long"
        and strategy_hint in {"", "headline_multiline"}
        and target_lines > int(policy["source_lines"] or 1)
    )
    compact_issue = ""
    if str(policy["compact_rule"]) == "dictionary_only":
        if str(policy["compact_mapping_status"]) == "manual_review_required":
            compact_issue = "compact_mapping_missing"
        elif str(policy["compact_term"]) and target_text.strip() != str(policy["compact_term"]):
            compact_issue = "compact_term_miss"
    elif strategy_hint == "promo_exact_head" and str(policy["compact_term"]) and target_text.strip() != str(policy["compact_term"]):
        compact_issue = "compact_term_miss"
    elif strategy_hint == "promo_compound_pack" and _contains_promo_expansion(target_text):
        compact_issue = "promo_expansion_forbidden"
    elif (
        str(policy["category"]) == "item_skill_name"
        and str(policy["compact_term"])
        and target_text.strip() != str(policy["compact_term"])
        and _content_word_count(target_text) > 2
    ):
        compact_issue = "compact_term_miss"
    elif str(policy["category"]).startswith("badge_micro_") and target_len > max_len_target:
        compact_issue = "compact_mapping_missing"

    if str(policy["compact_term"]) and target_text.strip() == str(policy["compact_term"]) and (
        str(policy["compact_rule"]) == "dictionary_only" or strategy_hint in {"promo_exact_head", "headline_nameplate"}
    ):
        return None

    if line_overflow:
        severity = "critical"
        reason = _category_reason(str(policy["category"]), "critical", True)
        recommendation = "preserve_source_line_budget_before_rerun"
    elif compact_issue:
        severity = "critical" if max_len_review_limit and target_len > max_len_review_limit else "major"
        reason = _category_reason(str(policy["category"]), severity, False, compact_issue)
        recommendation = (
            "send_to_manual_queue_until_compact_mapping_is_approved"
            if compact_issue == "compact_mapping_missing"
            else "replace_with_approved_compact_term"
        )
    elif max_len_review_limit and target_len > max_len_review_limit:
        severity = "critical"
        reason = "headline_budget_overflow" if strategy_hint.startswith("headline_") else _category_reason(str(policy["category"]), severity, False)
        recommendation = "shorten_ru_or_send_to_human_review"
    elif max_len_target and target_len > max_len_target:
        severity = "major"
        reason = "headline_budget_overflow" if strategy_hint.startswith("headline_") else _category_reason(str(policy["category"]), severity, False)
        recommendation = "shorten_ru_or_send_to_human_review"
    elif max_len_target and target_len >= max(1, int(max_len_target * 0.95)):
        severity = "warning"
        reason = _category_reason(str(policy["category"]), severity, False)
        recommendation = "prefer_compact_variant_on_next_pass"
    else:
        return None

    return {
        "string_id": str(row.get("string_id") or row.get("id") or ""),
        "source_string_id": str(row.get("source_string_id") or ""),
        "batch_row_id": str(row.get("batch_row_id") or ""),
        "source_zh": source_text,
        "target_text": target_text,
        "source_len_clean": str(source_len),
        "target_len": str(target_len),
        "max_len_target": str(max_len_target),
        "max_len_review_limit": str(max_len_review_limit),
        "length_ratio": f"{ratio:.2f}",
        "severity": severity,
        "reason": reason,
        "ui_art_category": str(policy["category"]),
        "category_reason": reason,
        "module_tag": row.get("module_tag", ""),
        "recommendation": recommendation,
    }


def build_summary(findings: List[Dict[str, str]]) -> dict:
    counts = {"warning": 0, "major": 0, "critical": 0}
    for finding in findings:
        counts[finding["severity"]] = counts.get(finding["severity"], 0) + 1
    return {
        "review_queue_total": len(findings),
        "severity_counts": counts,
        "critical_ids": [item["string_id"] for item in findings if item["severity"] == "critical"],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a length-focused review queue for UI art translations.")
    ap.add_argument("--input", required=True, help="Translated or repaired CSV path")
    ap.add_argument("--output", required=True, help="Review queue CSV path")
    ap.add_argument("--report", required=True, help="JSON summary path")
    ap.add_argument("--source-col", default="source_zh")
    ap.add_argument("--target-col", default="target_text")
    args = ap.parse_args()

    rows = read_csv(Path(args.input))
    findings = []
    for row in rows:
        finding = classify_row(row, args.source_col, args.target_col)
        if finding:
            findings.append(finding)

    fieldnames = [
        "string_id",
        "source_string_id",
        "batch_row_id",
        "source_zh",
        "target_text",
        "source_len_clean",
        "target_len",
        "max_len_target",
        "max_len_review_limit",
        "length_ratio",
        "severity",
        "reason",
        "ui_art_category",
        "category_reason",
        "module_tag",
        "recommendation",
    ]
    write_csv(Path(args.output), findings, fieldnames)
    write_json(Path(args.report), build_summary(findings))
    print(f"[OK] Wrote {len(findings)} UI art review row(s) -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
