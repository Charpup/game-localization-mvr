#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build the focused 98-row UI-art recovery slice canary from:
- a freshly prepared full-source CSV
- the previously selected 220-row canary sample
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

TARGET_CATEGORIES = {"badge_micro_2c", "promo_short", "item_skill_name", "slogan_long"}
SENTINEL_COUNTS = {"badge_micro_1c": 5, "label_generic_short": 5, "title_name_short": 5}
EXPECTED_TOTAL = 98


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


def _order_key(row: Dict[str, str]) -> Tuple[int, str]:
    try:
        batch_row = int(float(str(row.get("batch_row_id") or "0")))
    except Exception:
        batch_row = 0
    return batch_row, str(row.get("working_string_id") or row.get("string_id") or "")


def select_rows(
    current_rows: List[Dict[str, str]],
    prior_canary_rows: List[Dict[str, str]],
    *,
    target_categories: set[str] | None = None,
    sentinel_counts: Dict[str, int] | None = None,
    expected_total: int = EXPECTED_TOTAL,
) -> Tuple[List[Dict[str, str]], Dict]:
    target_categories = set(target_categories or TARGET_CATEGORIES)
    sentinel_counts = dict(sentinel_counts or SENTINEL_COUNTS)
    current_by_id = {
        str(row.get("working_string_id") or row.get("string_id") or ""): row
        for row in current_rows
        if str(row.get("status") or "") == "ready"
    }
    prior_rows_sorted = sorted(prior_canary_rows, key=_order_key)

    selected_ids: List[str] = []
    target_selected: Counter[str] = Counter()
    sentinel_selected: Counter[str] = Counter()

    for row in prior_rows_sorted:
        working_id = str(row.get("working_string_id") or row.get("string_id") or "")
        prior_category = str(row.get("ui_art_category") or "other_review")
        if working_id not in current_by_id or working_id in selected_ids:
            continue
        if prior_category in target_categories:
            selected_ids.append(working_id)
            target_selected[prior_category] += 1

    for row in prior_rows_sorted:
        working_id = str(row.get("working_string_id") or row.get("string_id") or "")
        prior_category = str(row.get("ui_art_category") or "other_review")
        if working_id not in current_by_id or working_id in selected_ids:
            continue
        if prior_category in sentinel_counts and sentinel_selected[prior_category] < sentinel_counts[prior_category]:
            selected_ids.append(working_id)
            sentinel_selected[prior_category] += 1

    selected_rows = [current_by_id[row_id] for row_id in selected_ids]
    selected_rows = sorted(selected_rows, key=_order_key)
    manifest = {
        "selected_total": len(selected_rows),
        "target_categories": sorted(target_categories),
        "target_counts_from_prior_canary": dict(target_selected),
        "sentinel_counts": dict(sentinel_selected),
        "selected_row_ids": selected_ids,
        "selected_source_ids": [str(row.get("source_string_id") or "") for row in selected_rows],
        "actual_current_category_counts": dict(Counter(str(row.get("ui_art_category") or "other_review") for row in selected_rows)),
    }
    return selected_rows, manifest


def parse_json_arg(raw: str, fallback):
    if not raw:
        return fallback
    return json.loads(raw)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the focused UI-art recovery slice canary.")
    ap.add_argument("--prepared-full", required=True, help="Freshly prepared full-source CSV")
    ap.add_argument("--existing-canary", required=True, help="Previously selected 220-row canary prepared CSV")
    ap.add_argument("--output", required=True, help="Focused slice prepared CSV output")
    ap.add_argument("--manifest", required=True, help="Focused slice manifest JSON output")
    ap.add_argument("--target-categories-json", default="")
    ap.add_argument("--sentinel-counts-json", default="")
    ap.add_argument("--expected-total", type=int, default=EXPECTED_TOTAL)
    args = ap.parse_args()

    current_rows, fieldnames = read_csv(Path(args.prepared_full))
    prior_canary_rows, _ = read_csv(Path(args.existing_canary))
    selected_rows, manifest = select_rows(
        current_rows,
        prior_canary_rows,
        target_categories=set(parse_json_arg(args.target_categories_json, sorted(TARGET_CATEGORIES))),
        sentinel_counts=parse_json_arg(args.sentinel_counts_json, SENTINEL_COUNTS),
        expected_total=args.expected_total,
    )

    if len(selected_rows) != args.expected_total:
        raise SystemExit(f"Failed to build exact {args.expected_total}-row focused slice; selected {len(selected_rows)}")

    write_csv(Path(args.output), selected_rows, fieldnames)
    manifest["prepared_full"] = str(Path(args.prepared_full).resolve())
    manifest["existing_canary"] = str(Path(args.existing_canary).resolve())
    manifest["output"] = str(Path(args.output).resolve())
    write_json(Path(args.manifest), manifest)
    print(f"[OK] Wrote {len(selected_rows)} focused slice row(s) -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
