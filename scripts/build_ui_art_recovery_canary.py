#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build a deterministic stratified UI-art recovery canary sample from a prepared batch CSV.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

DEFAULT_SEED = 42
TARGET_TOTAL = 220
CATEGORY_QUOTAS = {
    "badge_micro_1c": 30,
    "badge_micro_2c": 30,
    "label_generic_short": 45,
    "title_name_short": 45,
    "promo_short": 30,
    "item_skill_name": 20,
    "slogan_long": 20,
}
PRIORITY_TERMS = [
    "挑战",
    "排行",
    "排行榜",
    "商店",
    "支援",
    "胜",
    "败",
    "域",
    "图鉴",
    "重生",
    "兑换",
    "修罗模式",
    "首充",
    "充值",
    "返利",
    "特惠",
    "福利",
    "礼包",
    "赠礼",
    "奖励预览",
]
PRIMARY_BACKFILL = ["label_generic_short", "title_name_short"]
SECONDARY_BACKFILL = ["promo_short", "item_skill_name", "badge_micro_1c", "slogan_long"]


def read_csv(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default


def _priority_rank(source_text: str, priority_terms: List[str]) -> Tuple[int, int]:
    if source_text in priority_terms:
        return (0, priority_terms.index(source_text))
    return (1, len(priority_terms) + 1)


def candidate_sort_key(row: Dict[str, str], priority_terms: List[str]) -> Tuple[int, int, str, str, str]:
    priority_group, priority_rank = _priority_rank(str(row.get("source_zh") or ""), priority_terms)
    return (
        priority_group,
        priority_rank,
        str(row.get("source_zh") or ""),
        str(row.get("source_string_id") or ""),
        str(row.get("working_string_id") or row.get("string_id") or ""),
    )


def original_order_key(row: Dict[str, str]) -> Tuple[int, str]:
    return (
        _safe_int(str(row.get("batch_row_id") or "0"), 0),
        str(row.get("working_string_id") or row.get("string_id") or ""),
    )


def select_rows(
    rows: List[Dict[str, str]],
    *,
    target_total: int = TARGET_TOTAL,
    category_quotas: Dict[str, int] | None = None,
    priority_terms: List[str] | None = None,
    primary_backfill: List[str] | None = None,
    secondary_backfill: List[str] | None = None,
    seed: int = DEFAULT_SEED,
) -> Tuple[List[Dict[str, str]], Dict]:
    category_quotas = dict(category_quotas or CATEGORY_QUOTAS)
    priority_terms = list(priority_terms or PRIORITY_TERMS)
    primary_backfill = list(primary_backfill or PRIMARY_BACKFILL)
    secondary_backfill = list(secondary_backfill or SECONDARY_BACKFILL)
    ready_rows = [row for row in rows if str(row.get("status") or "") == "ready"]
    by_category: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in ready_rows:
        by_category[str(row.get("ui_art_category") or "other_review")].append(row)

    for category in by_category:
        by_category[category] = sorted(by_category[category], key=lambda row: candidate_sort_key(row, priority_terms))

    selected_ids = set()
    selected_rows: List[Dict[str, str]] = []
    target_shortfalls: Dict[str, int] = {}
    actual_counts: Counter[str] = Counter()
    prioritized_hits: Counter[str] = Counter()

    def _take_from_category(category: str, limit: int) -> int:
        taken = 0
        for row in by_category.get(category, []):
            row_id = str(row.get("working_string_id") or row.get("string_id") or "")
            if not row_id or row_id in selected_ids:
                continue
            selected_ids.add(row_id)
            selected_rows.append(row)
            actual_counts[category] += 1
            src = str(row.get("source_zh") or "")
            if src in priority_terms:
                prioritized_hits[src] += 1
            taken += 1
            if taken >= limit:
                break
        return taken

    for category, quota in category_quotas.items():
        taken = _take_from_category(category, quota)
        if taken < quota:
            target_shortfalls[category] = quota - taken

    shortage = target_total - len(selected_rows)

    def _backfill(order: List[str], shortage_left: int) -> int:
        if shortage_left <= 0:
            return shortage_left
        while shortage_left > 0:
            progressed = False
            for category in order:
                taken = _take_from_category(category, 1)
                if taken:
                    shortage_left -= 1
                    progressed = True
                    if shortage_left <= 0:
                        break
            if not progressed:
                break
        return shortage_left

    shortage = _backfill(primary_backfill, shortage)
    shortage = _backfill(secondary_backfill, shortage)
    if shortage > 0:
        remaining_categories = [category for category in sorted(by_category) if category not in primary_backfill + secondary_backfill]
        shortage = _backfill(remaining_categories, shortage)

    selected_rows = sorted(selected_rows, key=original_order_key)
    manifest = {
        "seed": seed,
        "target_total": target_total,
        "selected_total": len(selected_rows),
        "shortage_after_backfill": shortage,
        "target_quotas": category_quotas,
        "actual_category_counts": dict(actual_counts),
        "category_shortfalls": target_shortfalls,
        "backfill_policy": {
            "primary": primary_backfill,
            "secondary": secondary_backfill,
        },
        "priority_terms": priority_terms,
        "priority_term_hits": dict(prioritized_hits),
        "selected_row_ids": [str(row.get("working_string_id") or row.get("string_id") or "") for row in selected_rows],
        "selected_source_ids": [str(row.get("source_string_id") or "") for row in selected_rows],
    }
    return selected_rows, manifest


def parse_json_arg(raw: str, fallback):
    if not raw:
        return fallback
    return json.loads(raw)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build a stratified UI-art recovery canary sample.")
    ap.add_argument("--input", required=True, help="Prepared full-source CSV path")
    ap.add_argument("--output", required=True, help="Prepared canary CSV path")
    ap.add_argument("--manifest", required=True, help="Canary manifest JSON path")
    ap.add_argument("--target-total", type=int, default=TARGET_TOTAL)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--quotas-json", default="")
    ap.add_argument("--priority-terms-json", default="")
    ap.add_argument("--primary-backfill-json", default="")
    ap.add_argument("--secondary-backfill-json", default="")
    args = ap.parse_args()

    input_path = Path(args.input)
    rows, fieldnames = read_csv(input_path)
    selected_rows, manifest = select_rows(
        rows,
        target_total=args.target_total,
        category_quotas=parse_json_arg(args.quotas_json, CATEGORY_QUOTAS),
        priority_terms=parse_json_arg(args.priority_terms_json, PRIORITY_TERMS),
        primary_backfill=parse_json_arg(args.primary_backfill_json, PRIMARY_BACKFILL),
        secondary_backfill=parse_json_arg(args.secondary_backfill_json, SECONDARY_BACKFILL),
        seed=args.seed,
    )

    if manifest["selected_total"] != args.target_total:
        raise SystemExit(f"Failed to build exact {args.target_total}-row canary; selected {manifest['selected_total']}.")

    write_csv(Path(args.output), selected_rows, fieldnames)
    manifest["source_path"] = str(input_path.resolve())
    manifest["output_path"] = str(Path(args.output).resolve())
    write_json(Path(args.manifest), manifest)
    print(f"[OK] Wrote {manifest['selected_total']} canary row(s) -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
