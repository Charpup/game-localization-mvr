#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
restore_ui_art_delivery.py

Merge the translated working subset back onto the full prepared batch,
restore original source string_id values, and keep working ids for audit.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List


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


def _collect_fieldnames(prepared_rows: List[Dict[str, str]], translated_rows: List[Dict[str, str]]) -> List[str]:
    fieldnames: List[str] = []
    for rows in (prepared_rows, translated_rows):
        for row in rows:
            for key in row.keys():
                if key not in fieldnames:
                    fieldnames.append(key)
    if "working_string_id" not in fieldnames:
        insert_at = fieldnames.index("string_id") + 1 if "string_id" in fieldnames else 0
        fieldnames.insert(insert_at, "working_string_id")
    if "delivery_status" not in fieldnames:
        fieldnames.append("delivery_status")
    return fieldnames


def merge_rows(prepared_rows: List[Dict[str, str]], translated_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    translated_map = {str(row.get("string_id") or ""): row for row in translated_rows}
    merged_rows: List[Dict[str, str]] = []

    for prepared in prepared_rows:
        working_id = str(prepared.get("string_id") or prepared.get("working_string_id") or "")
        source_id = str(prepared.get("source_string_id") or "")
        translated = translated_map.get(working_id, {})
        merged = dict(prepared)
        merged.update(translated)
        merged["working_string_id"] = working_id or merged.get("working_string_id", "")
        merged["source_string_id"] = source_id
        merged["string_id"] = source_id
        if translated:
            merged["delivery_status"] = "translated"
        elif str(prepared.get("status") or "") == "skipped_empty":
            merged["delivery_status"] = "skipped_empty"
            for target_field in ("target", "target_text", "target_ru", "rehydrated_text"):
                if target_field in merged:
                    merged[target_field] = ""
        else:
            merged["delivery_status"] = "missing_translation"
        merged_rows.append(merged)

    return merged_rows


def build_summary(prepared_rows: List[Dict[str, str]], merged_rows: List[Dict[str, str]]) -> dict:
    delivery_status_counts: Dict[str, int] = {}
    for row in merged_rows:
        status = str(row.get("delivery_status") or "unknown")
        delivery_status_counts[status] = delivery_status_counts.get(status, 0) + 1
    return {
        "prepared_row_count": len(prepared_rows),
        "delivery_row_count": len(merged_rows),
        "delivery_status_counts": delivery_status_counts,
        "row_count_match": len(prepared_rows) == len(merged_rows),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Restore original string_id values for UI art delivery.")
    ap.add_argument("--prepared", required=True, help="Full prepared batch CSV")
    ap.add_argument("--translated", required=True, help="Translated/re-hydrated working subset CSV")
    ap.add_argument("--output", required=True, help="Final delivery CSV")
    ap.add_argument("--report", required=True, help="Delivery merge JSON report")
    args = ap.parse_args()

    prepared_rows = read_csv(Path(args.prepared))
    translated_rows = read_csv(Path(args.translated)) if Path(args.translated).exists() else []

    merged_rows = merge_rows(prepared_rows, translated_rows)
    fieldnames = _collect_fieldnames(prepared_rows, translated_rows)
    write_csv(Path(args.output), merged_rows, fieldnames)
    write_json(Path(args.report), build_summary(prepared_rows, merged_rows))
    print(f"[OK] Restored {len(merged_rows)} UI art delivery row(s) -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
