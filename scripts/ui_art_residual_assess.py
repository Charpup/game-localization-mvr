#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Assess a UI-art residual triage slice against the full rerun baseline.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
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


def count_review_rows(path: Path) -> Dict[str, int]:
    rows, _ = read_csv(path)
    counts: Counter[str] = Counter()
    for row in rows:
        counts[str(row.get("ui_art_category") or "other_review")] += 1
    return dict(counts)


def row_map(path: Path) -> Dict[str, Dict[str, str]]:
    rows, _ = read_csv(path)
    return {str(row.get("string_id") or ""): row for row in rows}


def top_sources_from_hard(report: Dict[str, Any]) -> List[Tuple[str, int]]:
    counter: Counter[str] = Counter()
    for item in report.get("errors") or []:
        source = str(item.get("source") or "")
        if source:
            counter[source] += 1
    return counter.most_common(20)


def lane_metrics(candidate_rows: List[Dict[str, str]], review_rows: List[Dict[str, str]]) -> Dict[str, Any]:
    lane_by_id = {str(row.get("string_id") or ""): str(row.get("residual_lane") or "") for row in candidate_rows}
    by_lane: Dict[str, Counter] = defaultdict(Counter)
    for row in candidate_rows:
        lane = str(row.get("residual_lane") or "unknown")
        by_lane[lane]["candidate_rows"] += 1
        by_lane[lane][f"mode:{row.get('translation_mode') or 'llm'}"] += 1
    for row in review_rows:
        sid = str(row.get("string_id") or "")
        lane = lane_by_id.get(sid, "outside_slice")
        by_lane[lane]["remaining_review_rows"] += 1
        by_lane[lane][f"severity:{row.get('severity') or 'unknown'}"] += 1
        by_lane[lane][f"reason:{row.get('reason') or 'unknown'}"] += 1
    return {lane: dict(counter) for lane, counter in by_lane.items()}


def make_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# UI Art Residual Triage Assessment",
        "",
        f"- Base rerun: `{payload['inputs']['base_run_dir']}`",
        f"- Slice dir: `{payload['inputs']['slice_dir']}`",
        "",
        "## Headline Delta",
        f"- hard QA: `{payload['deltas']['hard_total_before']} -> {payload['deltas']['hard_total_after']}`",
        f"- soft hard-gate: `{payload['deltas']['soft_gate_before']} -> {payload['deltas']['soft_gate_after']}`",
        "",
        "## Category Review Rows",
        "| Category | Before | After |",
        "|---|---:|---:|",
    ]
    for category in ("badge_micro_1c", "promo_short", "item_skill_name", "slogan_long"):
        before = payload["category_review_rows"]["before"].get(category, 0)
        after = payload["category_review_rows"]["after"].get(category, 0)
        lines.append(f"| {category} | {before} | {after} |")

    lines.extend(
        [
            "",
            "## Acceptance",
            "```json",
            json.dumps(payload["acceptance"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## Lane Metrics",
            "```json",
            json.dumps(payload["lane_metrics"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## Remaining Soft Hard-Gate Top Sources",
            "```json",
            json.dumps(payload["remaining_soft_hard_gate_top_sources"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## Remaining Hard-QA Top Sources",
            "```json",
            json.dumps(payload["remaining_hard_top_sources"], ensure_ascii=False, indent=2),
            "```",
        ]
    )
    return "\n".join(lines) + "\n"


def build_assessment(base_run_dir: Path, slice_dir: Path) -> Dict[str, Any]:
    base_run_dir = Path(base_run_dir)
    slice_dir = Path(slice_dir)

    base_assessment = read_json(base_run_dir / "ui_art_full_rerun_assessment.json")
    base_qa = read_json(base_run_dir / "ui_art_qa_hard_report.json")
    slice_qa = read_json(slice_dir / "ui_art_qa_hard_report.json")
    base_soft = read_json(base_run_dir / "ui_art_soft_qa_report.json")
    slice_soft = read_json(slice_dir / "ui_art_soft_qa_report.json")
    translated_map = row_map(slice_dir / "ui_art_translated_repaired.csv")
    candidate_rows, _ = read_csv(slice_dir / "ui_art_residual_candidates.csv")
    review_rows, _ = read_csv(slice_dir / "ui_art_residual_review_queue.csv")
    manual_rows, _ = read_csv(slice_dir / "ui_art_residual_manual_queue_seed.csv")

    before_category = {
        "badge_micro_1c": 0,
        "promo_short": int(((base_assessment.get("family_residuals") or {}).get("promo_short") or {}).get("rerun_review_rows", 0)),
        "item_skill_name": int(((base_assessment.get("family_residuals") or {}).get("item_skill_name") or {}).get("rerun_review_rows", 0)),
        "slogan_long": int(((base_assessment.get("family_residuals") or {}).get("slogan_long") or {}).get("rerun_review_rows", 0)),
    }
    before_category["badge_micro_1c"] = int((base_qa.get("error_counts") or {}).get("compact_mapping_missing", 0))
    after_category = count_review_rows(slice_dir / "ui_art_residual_review_queue.csv")

    hard_before = int(sum(int(v) for v in (base_qa.get("error_counts") or {}).values()))
    hard_after = int(sum(int(v) for v in (slice_qa.get("error_counts") or {}).values()))
    soft_before = len(((base_soft.get("hard_gate") or {}).get("violations") or []))
    soft_after = len(((slice_soft.get("hard_gate") or {}).get("violations") or []))
    after_compact_missing = int((slice_qa.get("error_counts") or {}).get("compact_mapping_missing", 0))

    slogan_reason_counts = Counter()
    for row in review_rows:
        if str(row.get("ui_art_category") or "") == "slogan_long":
            slogan_reason_counts[str(row.get("reason") or "unknown")] += 1

    acceptance = {
        "hard_total_lte_650": hard_after <= 650,
        "soft_hard_gate_lte_500": soft_after <= 500,
        "badge_micro_1c_compact_mapping_missing_zero": after_compact_missing == 0,
        "promo_short_review_rows_lte_15": int(after_category.get("promo_short", 0)) <= 15,
        "item_skill_name_review_rows_lte_90": int(after_category.get("item_skill_name", 0)) <= 90,
        "slogan_long_review_rows_lte_60": int(after_category.get("slogan_long", 0)) <= 60,
        "slogan_long_remaining_are_budget_types": set(slogan_reason_counts.keys()).issubset({"headline_budget_overflow", "line_budget_overflow"}),
    }
    acceptance["all_pass"] = all(acceptance.values())

    return {
        "inputs": {
            "base_run_dir": str(base_run_dir),
            "slice_dir": str(slice_dir),
        },
        "deltas": {
            "hard_total_before": hard_before,
            "hard_total_after": hard_after,
            "soft_gate_before": soft_before,
            "soft_gate_after": soft_after,
            "manual_seed_rows": len(manual_rows),
            "candidate_rows": len(candidate_rows),
        },
        "category_review_rows": {
            "before": before_category,
            "after": after_category,
        },
        "lane_metrics": lane_metrics(candidate_rows, review_rows),
        "remaining_soft_hard_gate_top_sources": Counter(
            str((translated_map.get(str(item.get("string_id") or ""), {}) or {}).get("source_zh") or "")
            for item in ((slice_soft.get("hard_gate") or {}).get("violations") or [])
            if str((translated_map.get(str(item.get("string_id") or ""), {}) or {}).get("source_zh") or "")
        ).most_common(20),
        "remaining_hard_top_sources": top_sources_from_hard(slice_qa),
        "acceptance": acceptance,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Assess a UI-art residual triage slice.")
    ap.add_argument("--base-run-dir", required=True)
    ap.add_argument("--slice-dir", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args()

    payload = build_assessment(Path(args.base_run_dir), Path(args.slice_dir))
    write_json(Path(args.out_json), payload)
    Path(args.out_md).write_text(make_markdown(payload), encoding="utf-8")
    print(f"[OK] Residual assessment -> {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
