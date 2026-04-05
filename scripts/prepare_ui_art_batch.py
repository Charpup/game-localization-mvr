#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prepare_ui_art_batch.py

Prepare a zh-CN -> ru-RU UI art batch with strict length metadata.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


PLACEHOLDER_PATTERN = re.compile(r"\{[\d\w]+\}|%[sd]|\u003c[^>]+\u003e|\[.+?\]|【.+?】|⟦(?:PH|TAG)_\d+⟧")
DEFAULT_ENCODING_CANDIDATES = ("utf-8-sig", "utf-8", "gb18030", "gbk", "cp936")
SLOGAN_PUNCTUATION = tuple("，。！？：；、…")
PROMO_PACK_HINTS = (
    "自选箱",
    "自选礼包",
    "礼包",
)
PROMO_HINTS = (
    "首充",
    "充值",
    "返利",
    "特惠",
    "福利",
    "礼包",
    "赠礼",
    "奖励预览",
    "热销",
    "折扣",
    "直购",
    "优惠",
)
BADGE_EXACT_MAP = {
    "推荐": "Топ",
    "极品": "Эпик",
    "首充": "1-й дон.",
    "热销": "Хит",
    "特惠": "Спец.",
    "福利": "Бонус",
    "赠礼": "Дар",
    "限定": "Лимит",
    "新品": "Нов.",
}
PROMO_EXACT_MAP = {
    "奖励预览": "Нагр.",
    "充值返利": "Донат+",
    "今日充值": "Донат дня",
    "自选箱": "Пак",
    "自选礼包": "Пак",
}
ITEM_COMPACT_MAP = {
    "仙之试炼": "Сэн-тест",
    "仙人之力": "Сила Сэн.",
    "仙术铭刻": "Сэн-печ.",
    "仙术印记": "Сэн-знак",
}
HEADLINE_EXACT_MAP = {
    "人间道·灵魂吞噬": "Люд. путь·Погл. душ",
}
COMPACT_TERM_MAP = {
    "奖励": "Награды",
    "时装": "Скин",
    "头像框": "Рамка",
    "战令": "БП",
    "十连": "x10",
    "单抽": "x1",
    "榜单": "Топ",
    "设置": "Настр.",
    "折扣": "Скидка",
    "热销": "Хит",
    "秘卷": "Свиток",
    "挑战": "Чел.",
    "排行": "Топ",
    "排行榜": "Топ",
    "商店": "Шоп",
    "支援": "Сапп.",
    "胜": "Поб.",
    "败": "Пор.",
    "域": "Зона",
    "图鉴": "Кодекс",
    "重生": "Рес.",
    "兑换": "Обм.",
    "修罗模式": "Асура",
    "充值": "Донат",
    "返利": "Бонус",
    "特惠": "Спец.",
    "福利": "Бонус",
    "礼包": "Пак",
    "赠礼": "Дар",
    "奖励预览": "Нагр.",
    **BADGE_EXACT_MAP,
    **PROMO_EXACT_MAP,
    **ITEM_COMPACT_MAP,
    **HEADLINE_EXACT_MAP,
}
DICT_ONLY_CATEGORIES = {"badge_micro_1c", "badge_micro_2c"}
GENERIC_LABEL_TERMS = {
    "挑战",
    "排行",
    "排行榜",
    "榜单",
    "商店",
    "支援",
    "胜",
    "败",
    "域",
    "图鉴",
    "重生",
    "兑换",
    "修罗模式",
    "设置",
    "奖励",
    "时装",
    "头像框",
    "秘卷",
    "战令",
}
BADGE_TERMS_2C = {
    "热销",
    "特惠",
    "首充",
    "推荐",
    "限定",
    "新品",
    "极品",
    "福利",
    "赠礼",
    "胜利",
    "失败",
}
ITEM_SKILL_HINTS = (
    "之",
    "术",
    "卷",
    "刃",
    "玉",
    "魂",
    "符",
    "奥义",
    "查克拉",
    "元素",
    "战魂",
    "套装",
    "勾玉",
    "通灵",
)


def detect_encoding(path: Path, candidates: Sequence[str] = DEFAULT_ENCODING_CANDIDATES) -> str:
    raw = path.read_bytes()
    for encoding in candidates:
        try:
            raw.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("auto", raw, 0, 1, f"unable to decode with candidates: {', '.join(candidates)}")


def read_csv(path: Path, input_encoding: str = "auto") -> tuple[List[Dict[str, str]], List[str], str]:
    encoding = detect_encoding(path) if input_encoding == "auto" else input_encoding
    with path.open("r", encoding=encoding, newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return rows, list(reader.fieldnames or []), encoding


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def fingerprint_file(path: Path) -> dict:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = path.stat()
    return {
        "path": str(path),
        "size_bytes": stat.st_size,
        "mtime_epoch": stat.st_mtime,
        "sha256": digest.hexdigest(),
    }


def clean_source_length(text: str) -> int:
    return len(PLACEHOLDER_PATTERN.sub("", text or "").strip())


def placeholder_budget(text: str) -> int:
    return sum(len(match.group(0)) for match in PLACEHOLDER_PATTERN.finditer(text or ""))


def infer_len_tier(source_len: int) -> str:
    if source_len <= 2:
        return "XS"
    if source_len <= 4:
        return "S"
    if source_len <= 8:
        return "M"
    return "L"


def normalize_source_text(text: str) -> str:
    stripped = PLACEHOLDER_PATTERN.sub("", text or "")
    return re.sub(r"\s+", "", stripped).strip()


def compact_term_for(source_text: str) -> str:
    return COMPACT_TERM_MAP.get(normalize_source_text(source_text), "")


def classify_ui_art_category(source_text: str, clean_len: int) -> str:
    normalized = normalize_source_text(source_text)
    if not normalized:
        return "other_review"
    if clean_len <= 1:
        return "badge_micro_1c"
    if clean_len == 2 and normalized in BADGE_TERMS_2C:
        return "badge_micro_2c"
    if any(hint in normalized for hint in PROMO_PACK_HINTS):
        return "promo_short"
    if "·" in (source_text or "") and "\n" not in (source_text or ""):
        return "slogan_long"
    if "\n" in (source_text or "") or clean_len >= 13:
        return "slogan_long"
    if any(hint in normalized for hint in PROMO_HINTS):
        return "promo_short"
    if normalized in GENERIC_LABEL_TERMS:
        return "label_generic_short"
    if any(hint in normalized for hint in ITEM_SKILL_HINTS):
        return "item_skill_name"
    if clean_len == 2:
        return "label_generic_short"
    if clean_len <= 8:
        return "title_name_short"
    if any(mark in normalized for mark in SLOGAN_PUNCTUATION) or clean_len >= 9:
        return "slogan_long"
    return "other_review"


def determine_ui_art_strategy_hint(source_text: str, category: str) -> str:
    normalized = normalize_source_text(source_text)
    if category == "badge_micro_2c":
        return "badge_exact_map"
    if category == "promo_short":
        if normalized in {"奖励预览", "充值返利", "今日充值"}:
            return "promo_exact_head"
        if any(hint in normalized for hint in PROMO_PACK_HINTS):
            return "promo_compound_pack"
        return "promo_exact_head"
    if category == "item_skill_name":
        return "item_compact_noun"
    if category == "slogan_long":
        if "·" in (source_text or "") and "\n" not in (source_text or ""):
            return "headline_nameplate"
        if "\n" in (source_text or ""):
            return "headline_multiline"
        return "headline_singleline"
    return ""


def determine_translation_mode(source_text: str, category: str, strategy_hint: str, compact_rule: str, compact_term: str) -> tuple[str, str]:
    normalized = normalize_source_text(source_text)
    if compact_rule == "dictionary_only" and compact_term:
        return ("prefill_exact", compact_term)
    if category == "promo_short" and strategy_hint == "promo_exact_head":
        target = PROMO_EXACT_MAP.get(normalized, "")
        return ("prefill_exact", target) if target else ("llm", "")
    if category == "item_skill_name" and compact_term:
        return ("prefill_exact", compact_term)
    if strategy_hint == "headline_nameplate" and compact_term:
        return ("prefill_exact", compact_term)
    return ("llm", "")


def build_working_string_id(row_index: int) -> str:
    return f"UIART_{row_index:06d}"


def prepare_rows(
    rows: List[Dict[str, str]],
    source_col: str,
    source_id_col: str,
    ratio: float,
    review_ratio: float,
    source_locale: str,
    target_locale: str,
    module_tag: str,
) -> List[Dict[str, str]]:
    prepared: List[Dict[str, str]] = []
    for row_index, row in enumerate(rows, start=1):
        row_out = dict(row)
        source_id = str(row.get(source_id_col) or "").strip()
        working_id = build_working_string_id(row_index)
        source_text = (row.get(source_col) or "").strip()
        clean_len = clean_source_length(source_text)
        placeholder_len = placeholder_budget(source_text)
        is_empty = not source_text

        if is_empty:
            max_len = 0
            review_limit = 0
            len_tier = "EMPTY"
            status = "skipped_empty"
        else:
            max_len = math.floor(clean_len * ratio) + placeholder_len
            review_limit = math.floor(clean_len * review_ratio) + placeholder_len
            len_tier = infer_len_tier(clean_len)
            status = "ready"
        ui_art_category = classify_ui_art_category(source_text, clean_len)
        strategy_hint = determine_ui_art_strategy_hint(source_text, ui_art_category)
        compact_term = compact_term_for(source_text)
        compact_rule = "dictionary_only" if ui_art_category in DICT_ONLY_CATEGORIES else "compact_preferred"
        compact_mapping_status = (
            "approved_available"
            if compact_term
            else ("manual_review_required" if ui_art_category in DICT_ONLY_CATEGORIES else "optional")
        )
        translation_mode, prefill_target_ru = determine_translation_mode(
            source_text,
            ui_art_category,
            strategy_hint,
            compact_rule,
            compact_term,
        )

        row_out["batch_row_id"] = str(row_index)
        row_out["source_string_id"] = source_id
        row_out["working_string_id"] = working_id
        row_out["string_id"] = working_id
        row_out["source_locale"] = source_locale
        row_out["target_locale"] = target_locale
        row_out["module_tag"] = module_tag
        row_out["module_confidence"] = "1.0"
        row_out["source_len_clean"] = str(clean_len)
        row_out["placeholder_budget"] = str(placeholder_len)
        row_out["max_len_target"] = str(max_len)
        row_out["max_len_review_limit"] = str(review_limit)
        row_out["len_tier"] = len_tier
        row_out["ui_art_category"] = ui_art_category
        row_out["ui_art_strategy_hint"] = strategy_hint
        row_out["ui_art_compact_term"] = compact_term
        row_out["compact_rule"] = compact_rule
        row_out["compact_mapping_status"] = compact_mapping_status
        row_out["translation_mode"] = translation_mode
        row_out["prefill_target_ru"] = prefill_target_ru
        row_out["length_policy"] = f"ui_art_ratio_{ratio:.1f}_review_{review_ratio:.1f}"
        row_out["status"] = status
        prepared.append(row_out)
    return prepared


def build_summary(rows: List[Dict[str, str]], ratio: float, review_ratio: float, module_tag: str) -> dict:
    ready_rows = [r for r in rows if r.get("status") == "ready"]
    source_ids = [str(r.get("source_string_id") or "").strip() for r in rows]
    source_id_counter = Counter(value for value in source_ids if value)
    duplicated = {key: count for key, count in source_id_counter.items() if count > 1}
    return {
        "batch_type": "naruto_ui_art_ru",
        "row_count": len(rows),
        "ready_rows": len(ready_rows),
        "empty_rows": len(rows) - len(ready_rows),
        "duplicate_source_id_count": len(duplicated),
        "duplicate_source_rows_total": sum(duplicated.values()),
        "duplicate_source_ids_preview": dict(list(sorted(duplicated.items()))[:20]),
        "module_tag": module_tag,
        "ui_art_category_counts": dict(Counter(r.get("ui_art_category", "other_review") for r in ready_rows)),
        "target_ratio": ratio,
        "review_ratio": review_ratio,
        "examples": [
            {
                "string_id": r.get("string_id", ""),
                "source_string_id": r.get("source_string_id", ""),
                "source_len_clean": int(r.get("source_len_clean", "0") or 0),
                "max_len_target": int(r.get("max_len_target", "0") or 0),
                "max_len_review_limit": int(r.get("max_len_review_limit", "0") or 0),
                "ui_art_category": r.get("ui_art_category", ""),
                "ui_art_compact_term": r.get("ui_art_compact_term", ""),
            }
            for r in ready_rows[:10]
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Prepare a UI art localization batch with strict RU length caps.")
    ap.add_argument("--input", required=True, help="Source CSV path")
    ap.add_argument("--output", help="Prepared CSV path")
    ap.add_argument("--report", help="JSON summary path")
    ap.add_argument("--output-dir", help="Output directory. If set, writes source_ui_art_prepared.csv and batch_manifest.json")
    ap.add_argument("--source-col", default="source_zh", help="Source text column name")
    ap.add_argument("--source-id-col", default="string_id", help="Original source id column name")
    ap.add_argument("--input-encoding", default="auto", help="Input encoding or auto")
    ap.add_argument("--source-locale", default="zh-CN")
    ap.add_argument("--target-locale", default="ru-RU")
    ap.add_argument("--module-tag", default="ui_art_label")
    ap.add_argument("--ratio", type=float, default=2.3, help="Target max length ratio")
    ap.add_argument("--review-ratio", type=float, default=2.5, help="Human review hard ratio")
    args = ap.parse_args()

    if not args.output_dir and (not args.output or not args.report):
        raise SystemExit("Provide either --output-dir or both --output and --report.")

    output_path = Path(args.output) if args.output else None
    report_path = Path(args.report) if args.report else None
    if args.output_dir:
        output_dir = Path(args.output_dir)
        output_path = output_path or (output_dir / "source_ui_art_prepared.csv")
        report_path = report_path or (output_dir / "batch_manifest.json")

    input_path = Path(args.input)
    rows, input_fieldnames, input_encoding = read_csv(input_path, input_encoding=args.input_encoding)
    if not input_fieldnames:
        raise SystemExit("Input CSV has no header.")

    prepared = prepare_rows(
        rows=rows,
        source_col=args.source_col,
        source_id_col=args.source_id_col,
        ratio=args.ratio,
        review_ratio=args.review_ratio,
        source_locale=args.source_locale,
        target_locale=args.target_locale,
        module_tag=args.module_tag,
    )

    fieldnames = list(input_fieldnames)
    for extra in [
        "batch_row_id",
        "source_string_id",
        "working_string_id",
        "source_locale",
        "target_locale",
        "module_tag",
        "module_confidence",
        "source_len_clean",
        "placeholder_budget",
        "max_len_target",
        "max_len_review_limit",
        "len_tier",
        "ui_art_category",
        "ui_art_strategy_hint",
        "ui_art_compact_term",
        "compact_rule",
        "compact_mapping_status",
        "translation_mode",
        "prefill_target_ru",
        "length_policy",
        "status",
    ]:
        if extra not in fieldnames:
            fieldnames.append(extra)

    assert output_path is not None
    assert report_path is not None

    write_csv(output_path, prepared, fieldnames)
    summary = build_summary(prepared, args.ratio, args.review_ratio, args.module_tag)
    summary["input_encoding"] = input_encoding
    summary["source_fingerprint"] = fingerprint_file(input_path)
    write_json(report_path, summary)
    print(f"[OK] Prepared {len(prepared)} UI art rows -> {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
