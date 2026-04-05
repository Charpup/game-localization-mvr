#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Assess the final narrow residual-v2 slice against the repaired residual-v1 baseline.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_csv(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def count_category(rows: List[Dict[str, str]]) -> Dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        counts[str(row.get("ui_art_category") or "other_review")] += 1
    return dict(counts)


def blocking_title_length(rows: List[Dict[str, str]]) -> int:
    total = 0
    for row in rows:
        if str(row.get("ui_art_category") or "") != "title_name_short":
            continue
        if str(row.get("severity") or "") not in {"major", "critical"}:
            continue
        reason = str(row.get("reason") or "")
        if reason.startswith("title_name_short_") or reason == "headline_budget_overflow":
            total += 1
    return total


def markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# UI Art Residual V2 Assessment",
        "",
        f"- Base slice: `{payload['inputs']['base_slice_dir']}`",
        f"- V2 slice: `{payload['inputs']['v2_slice_dir']}`",
        "",
        "## Headline Delta",
        f"- hard QA: `{payload['deltas']['hard_total_before']} -> {payload['deltas']['hard_total_after']}`",
        f"- soft hard-gate: `{payload['deltas']['soft_gate_before']} -> {payload['deltas']['soft_gate_after']}`",
        f"- review queue: `{payload['deltas']['review_rows_before']} -> {payload['deltas']['review_rows_after']}`",
        "",
        "## Acceptance",
        "```json",
        json.dumps(payload["acceptance"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Manual Separation",
        "```json",
        json.dumps(payload["manual_separation"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Remaining Top Sources",
        "```json",
        json.dumps(payload["remaining_top_sources"], ensure_ascii=False, indent=2),
        "```",
    ]
    return "\n".join(lines) + "\n"


def build_assessment(base_slice_dir: Path, v2_slice_dir: Path) -> Dict[str, Any]:
    base_slice_dir = Path(base_slice_dir)
    v2_slice_dir = Path(v2_slice_dir)

    base_qa = read_json(base_slice_dir / "ui_art_qa_hard_report.json")
    v2_qa = read_json(v2_slice_dir / "ui_art_qa_hard_report.json")
    base_soft = read_json(base_slice_dir / "ui_art_soft_qa_report.json")
    v2_soft = read_json(v2_slice_dir / "ui_art_soft_qa_report.json")
    base_review, _ = read_csv(base_slice_dir / "ui_art_residual_review_queue.csv")
    v2_review, _ = read_csv(v2_slice_dir / "ui_art_residual_v2_review_queue_enriched.csv")
    manual_creative, _ = read_csv(v2_slice_dir / "ui_art_residual_v2_manual_creative_titles.csv")
    manual_ambiguity, _ = read_csv(v2_slice_dir / "ui_art_residual_v2_manual_ambiguity_terms.csv")
    v2_manifest = read_json(v2_slice_dir / "ui_art_residual_v2_manifest.json")

    hard_before = int(sum(int(v) for v in (base_qa.get("error_counts") or {}).values()))
    hard_after = int(sum(int(v) for v in (v2_qa.get("error_counts") or {}).values()))
    soft_before = len(((base_soft.get("hard_gate") or {}).get("violations") or []))
    soft_after = len(((v2_soft.get("hard_gate") or {}).get("violations") or []))
    before_title_block = blocking_title_length(base_review)
    after_title_block = blocking_title_length(v2_review)
    after_badge_missing = int((v2_qa.get("error_counts") or {}).get("compact_mapping_missing", 0))

    remaining_counter: Counter[str] = Counter()
    for item in (v2_qa.get("errors") or []):
        source = str(item.get("source") or "")
        if source:
            remaining_counter[source] += 1

    acceptance = {
        "soft_hard_gate_below_500": soft_after < 500,
        "badge_micro_1c_compact_mapping_missing_zero": after_badge_missing == 0,
        "title_name_short_blocking_length_reduced": after_title_block < before_title_block,
        "manual_only_queue_separated": (len(manual_creative) + len(manual_ambiguity)) > 0,
    }
    acceptance["all_pass"] = all(acceptance.values())

    return {
        "inputs": {
            "base_slice_dir": str(base_slice_dir),
            "v2_slice_dir": str(v2_slice_dir),
        },
        "deltas": {
            "hard_total_before": hard_before,
            "hard_total_after": hard_after,
            "soft_gate_before": soft_before,
            "soft_gate_after": soft_after,
            "review_rows_before": len(base_review),
            "review_rows_after": len(v2_review),
            "title_name_short_blocking_length_before": before_title_block,
            "title_name_short_blocking_length_after": after_title_block,
        },
        "category_review_rows": {
            "before": count_category(base_review),
            "after": count_category(v2_review),
        },
        "manual_separation": {
            "manual_creative_titles": len(manual_creative),
            "manual_ambiguity_terms": len(manual_ambiguity),
            "auto_fix_candidate_rows": int(v2_manifest.get("auto_fix_candidate_rows") or 0),
            "repair_input_rows": int(v2_manifest.get("repair_input_rows") or 0),
        },
        "remaining_top_sources": remaining_counter.most_common(20),
        "acceptance": acceptance,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Assess a UI-art residual-v2 slice.")
    ap.add_argument("--base-slice-dir", required=True)
    ap.add_argument("--v2-slice-dir", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args()

    payload = build_assessment(Path(args.base_slice_dir), Path(args.v2_slice_dir))
    write_json(Path(args.out_json), payload)
    Path(args.out_md).write_text(markdown(payload), encoding="utf-8")
    print(f"[OK] Residual V2 assessment -> {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
