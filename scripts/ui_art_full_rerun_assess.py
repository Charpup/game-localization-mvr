#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Assess a full UI-art rerun against:
- the original failed full run
- the focused recovery slice anchor

The output is meant to drive residual triage after a full rerun completes.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


TARGET_FAMILIES = (
    "badge_micro_2c",
    "promo_short",
    "item_skill_name",
    "slogan_long",
)
NOISE_TYPES = {"terminology", "style_contract", "compact_mapping_missing", "compact_term_miss"}
TRUE_RESIDUAL_TYPES = {
    "length",
    "placeholder",
    "ambiguity_high_risk",
    "mistranslation",
    "line_budget_overflow",
    "headline_budget_overflow",
    "promo_expansion_forbidden",
}


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_csv(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    items: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def count_review_queue(path: Path, row_map: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    rows = read_csv(path)[0] if path.exists() else []
    by_category: Dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        sid = str(row.get("string_id") or "")
        prepared = row_map.get(sid, {})
        category = str(row.get("ui_art_category") or prepared.get("ui_art_category") or "other_review")
        severity = str(row.get("severity") or "unknown")
        by_category[category]["review_rows"] += 1
        by_category[category][f"severity:{severity}"] += 1
    return {category: dict(counter) for category, counter in by_category.items()}


def load_prepare_maps(prepared_csv: Path) -> Tuple[Dict[str, Dict[str, str]], Counter]:
    rows, _ = read_csv(prepared_csv)
    by_id = {str(row.get("string_id") or ""): row for row in rows}
    counts: Counter[str] = Counter()
    for row in rows:
        if str(row.get("status") or "") != "ready":
            continue
        counts[str(row.get("ui_art_category") or "other_review")] += 1
    return by_id, counts


def load_run_summary(manifest: Dict[str, Any], run_dir: Path) -> Dict[str, Any]:
    summary = dict(manifest.get("final_summary") or {})
    if "hard_qa_recheck_errors" not in summary and "hard_qa_initial_errors" not in summary:
        qa_recheck = read_json(run_dir / "ui_art_qa_hard_report_recheck.json")
        qa_primary = read_json(run_dir / "ui_art_qa_hard_report.json")
        qa_report = qa_recheck or qa_primary
        error_counts = dict(qa_report.get("error_counts") or {})
        total_errors = int(sum(int(value) for value in error_counts.values())) if error_counts else int(qa_report.get("metadata", {}).get("total_errors", 0) or 0)
        if qa_recheck:
            summary["hard_qa_recheck_errors"] = total_errors
            summary["hard_qa_recheck_error_counts"] = error_counts
        else:
            summary["hard_qa_initial_errors"] = total_errors
            summary["hard_qa_initial_error_counts"] = error_counts
    if "review_queue_total" not in summary:
        review_report = read_json(run_dir / "ui_art_review_queue.json")
        summary["review_queue_total"] = int(review_report.get("review_queue_total", 0) or 0)
    if "soft_qa_major" not in summary:
        soft_report = read_json(run_dir / "ui_art_soft_qa_report.json")
        summary["soft_qa_major"] = int(((soft_report.get("summary") or {}).get("major")) or 0)
    return summary


def read_focused_anchor_compare(focused_run_dir: Path) -> Dict[str, Any]:
    candidates = [
        focused_run_dir / "ui_art_recovery_slice2_compare.json",
        focused_run_dir / "ui_art_canary_compare.json",
        focused_run_dir / "ui_art_compare.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return read_json(candidate)
    fallback = sorted(focused_run_dir.glob("*compare*.json"))
    return read_json(fallback[0]) if fallback else {}


def classify_soft_item(item: Dict[str, Any], row: Dict[str, str]) -> str:
    issue_type = str(item.get("type") or item.get("issue_type") or "unknown")
    if issue_type in TRUE_RESIDUAL_TYPES:
        return "true_residual"
    if issue_type in NOISE_TYPES:
        if (
            str(row.get("translation_mode") or "") == "prefill_exact"
            or str(row.get("prefill_target_ru") or "")
            or str(row.get("ui_art_compact_term") or "")
            or str(row.get("compact_mapping_status") or "") == "approved_available"
        ):
            return "compact_policy_noise"
    return "mixed_review"


def soft_task_metrics(tasks: List[Dict[str, Any]], row_map: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    overall = Counter()
    bucket_counts = Counter()
    bucket_type_counts: Dict[str, Counter] = defaultdict(Counter)
    bucket_source_counts: Dict[str, Counter] = defaultdict(Counter)
    category_type_counts: Dict[str, Counter] = defaultdict(Counter)

    for task in tasks:
        sid = str(task.get("string_id") or task.get("id") or "")
        row = row_map.get(sid)
        if not row:
            continue
        issue_type = str(task.get("type") or task.get("issue_type") or "unknown")
        category = str(row.get("ui_art_category") or "other_review")
        source = str(row.get("source_zh") or "")
        bucket = classify_soft_item(task, row)
        overall[issue_type] += 1
        bucket_counts[bucket] += 1
        bucket_type_counts[bucket][issue_type] += 1
        if source:
            bucket_source_counts[bucket][source] += 1
        category_type_counts[category][issue_type] += 1

    return {
        "overall_issue_type_counts": dict(overall),
        "bucket_counts": dict(bucket_counts),
        "bucket_type_counts": {bucket: dict(counter) for bucket, counter in bucket_type_counts.items()},
        "bucket_top_sources": {
            bucket: counter.most_common(15) for bucket, counter in bucket_source_counts.items()
        },
        "by_category_issue_type_counts": {category: dict(counter) for category, counter in category_type_counts.items()},
    }


def hard_gate_metrics(soft_report: Dict[str, Any], row_map: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    violations = ((soft_report.get("hard_gate") or {}).get("violations") or []) if soft_report else []
    type_counts = Counter()
    source_counts = Counter()
    bucket_counts = Counter()
    bucket_type_counts: Dict[str, Counter] = defaultdict(Counter)

    for item in violations:
        sid = str(item.get("string_id") or "")
        row = row_map.get(sid, {})
        issue_type = str(item.get("type") or "unknown")
        source = str(row.get("source_zh") or "")
        bucket = classify_soft_item(item, row)
        type_counts[issue_type] += 1
        bucket_counts[bucket] += 1
        bucket_type_counts[bucket][issue_type] += 1
        if source:
            source_counts[source] += 1

    return {
        "violation_count": len(violations),
        "type_counts": dict(type_counts),
        "top_sources": source_counts.most_common(20),
        "bucket_counts": dict(bucket_counts),
        "bucket_type_counts": {bucket: dict(counter) for bucket, counter in bucket_type_counts.items()},
    }


def family_review_table(
    baseline_review: Dict[str, Any],
    rerun_review: Dict[str, Any],
    rerun_denominators: Counter,
    focused_anchor: Dict[str, Any],
) -> Dict[str, Any]:
    table = {}
    focused_by_category = ((focused_anchor.get("canary") or {}).get("hard") or {}).get("by_category", {})
    for family in TARGET_FAMILIES:
        base = baseline_review.get(family, {})
        rerun = rerun_review.get(family, {})
        denominator = int(rerun_denominators.get(family, 0))
        rerun_rows = int(rerun.get("review_rows", 0))
        table[family] = {
            "baseline_review_rows": int(base.get("review_rows", 0)),
            "rerun_review_rows": rerun_rows,
            "rerun_review_rate": round((rerun_rows / denominator) if denominator else 0.0, 4),
            "rerun_severity_counts": {
                key: int(value) for key, value in rerun.items() if key.startswith("severity:")
            },
            "focused_anchor_hard_fail_rate": float((focused_by_category.get(family) or {}).get("hard_fail_rate", 0.0)),
        }
    return table


def make_markdown(payload: Dict[str, Any]) -> str:
    lines = [
        "# UI Art Full Rerun Assessment",
        "",
        f"- Baseline full run: `{payload['inputs']['baseline_run_id']}`",
        f"- Focused anchor: `{payload['inputs']['focused_run_id']}`",
        f"- Full rerun: `{payload['inputs']['rerun_run_id']}`",
        "",
        "## Full-Run Delta",
        f"- hard QA total: `{payload['full_run_delta']['baseline_hard_total']} -> {payload['full_run_delta']['rerun_hard_total']}`",
        f"- review queue total: `{payload['full_run_delta']['baseline_review_total']} -> {payload['full_run_delta']['rerun_review_total']}`",
        f"- soft QA major: `{payload['full_run_delta']['baseline_soft_major']} -> {payload['full_run_delta']['rerun_soft_major']}`",
        "",
        "## Hard-QA Types",
        "```json",
        json.dumps(payload["full_run_delta"]["hard_type_counts"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Family Residuals",
        "| Family | Focused Anchor Hard Fail | Baseline Review Rows | Rerun Review Rows | Rerun Review Rate |",
        "|---|---:|---:|---:|---:|",
    ]
    for family, metrics in payload["family_residuals"].items():
        lines.append(
            f"| {family} | {metrics['focused_anchor_hard_fail_rate']:.2%} | {metrics['baseline_review_rows']} | {metrics['rerun_review_rows']} | {metrics['rerun_review_rate']:.2%} |"
        )
    lines.extend(
        [
            "",
            "## Soft-QA Overall Issue Mix",
            "```json",
            json.dumps(payload["soft_qa"]["overall_issue_type_counts"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## Hard-Gate Violations",
            "```json",
            json.dumps(payload["soft_qa"]["hard_gate"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## Noise Split",
            "```json",
            json.dumps(payload["soft_qa"]["noise_split"], ensure_ascii=False, indent=2),
            "```",
            "",
            "## Assessment Notes",
        ]
    )
    for note in payload["assessment_notes"]:
        lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


def build_assessment(
    baseline_run_dir: Path,
    focused_run_dir: Path,
    rerun_run_dir: Path,
) -> Dict[str, Any]:
    baseline_manifest = read_json(baseline_run_dir / "run_manifest.json")
    focused_manifest = read_json(focused_run_dir / "run_manifest.json")
    rerun_manifest = read_json(rerun_run_dir / "run_manifest.json")
    focused_compare = read_focused_anchor_compare(focused_run_dir)

    baseline_prepare = baseline_run_dir / "source_ui_art_prepared.csv"
    rerun_prepare = rerun_run_dir / "source_ui_art_prepared.csv"
    baseline_row_map, _ = load_prepare_maps(baseline_prepare)
    rerun_row_map, rerun_denominators = load_prepare_maps(rerun_prepare)

    baseline_classify_map = dict(rerun_row_map)
    baseline_classify_map.update(
        {sid: row for sid, row in baseline_row_map.items() if str(row.get("ui_art_category") or "")}
    )
    baseline_review = count_review_queue(baseline_run_dir / "ui_art_review_queue.csv", baseline_classify_map)
    rerun_review = count_review_queue(rerun_run_dir / "ui_art_review_queue.csv", rerun_row_map)

    rerun_soft_tasks = read_jsonl(rerun_run_dir / "ui_art_soft_tasks.jsonl")
    rerun_soft_report = read_json(rerun_run_dir / "ui_art_soft_qa_report.json")
    rerun_soft_metrics = soft_task_metrics(rerun_soft_tasks, rerun_row_map)
    hard_gate = hard_gate_metrics(rerun_soft_report, rerun_row_map)

    baseline_summary = load_run_summary(baseline_manifest, baseline_run_dir)
    rerun_summary = load_run_summary(rerun_manifest, rerun_run_dir)
    hard_type_counts = {
        "baseline": dict(baseline_summary.get("hard_qa_recheck_error_counts") or baseline_summary.get("hard_qa_initial_error_counts") or {}),
        "rerun": dict(rerun_summary.get("hard_qa_recheck_error_counts") or rerun_summary.get("hard_qa_initial_error_counts") or {}),
    }

    noise_split = {
        "compact_policy_noise": {
            "task_count": int(rerun_soft_metrics["bucket_counts"].get("compact_policy_noise", 0)),
            "violation_count": int(hard_gate["bucket_counts"].get("compact_policy_noise", 0)),
            "type_counts": rerun_soft_metrics["bucket_type_counts"].get("compact_policy_noise", {}),
            "top_sources": rerun_soft_metrics["bucket_top_sources"].get("compact_policy_noise", []),
        },
        "true_residual": {
            "task_count": int(rerun_soft_metrics["bucket_counts"].get("true_residual", 0)),
            "violation_count": int(hard_gate["bucket_counts"].get("true_residual", 0)),
            "type_counts": rerun_soft_metrics["bucket_type_counts"].get("true_residual", {}),
            "top_sources": rerun_soft_metrics["bucket_top_sources"].get("true_residual", []),
        },
        "mixed_review": {
            "task_count": int(rerun_soft_metrics["bucket_counts"].get("mixed_review", 0)),
            "violation_count": int(hard_gate["bucket_counts"].get("mixed_review", 0)),
            "type_counts": rerun_soft_metrics["bucket_type_counts"].get("mixed_review", {}),
            "top_sources": rerun_soft_metrics["bucket_top_sources"].get("mixed_review", []),
        },
    }

    notes = []
    if noise_split["compact_policy_noise"]["violation_count"] >= noise_split["true_residual"]["violation_count"]:
        notes.append("Soft-QA hard-gate violations are now dominated by compact-policy noise rather than true residual defects.")
    else:
        notes.append("Soft-QA hard-gate violations still contain a meaningful true-residual component; residual triage should prioritize those rows first.")
    if int(rerun_summary.get("review_queue_total", 0)) < int(baseline_summary.get("review_queue_total", 0)):
        notes.append("Review queue volume is lower than the original failed full run, which confirms the focused strategy scaled beyond the canary.")
    for family in TARGET_FAMILIES:
        family_rows = (rerun_review.get(family) or {}).get("review_rows", 0)
        if family_rows:
            notes.append(f"{family} still has {family_rows} review rows in the full rerun output.")

    return {
        "inputs": {
            "baseline_run_id": str(baseline_manifest.get("run_id") or baseline_run_dir.name),
            "focused_run_id": str(focused_manifest.get("run_id") or focused_run_dir.name),
            "rerun_run_id": str(rerun_manifest.get("run_id") or rerun_run_dir.name),
        },
        "full_run_delta": {
            "baseline_hard_total": int(baseline_summary.get("hard_qa_recheck_errors", 0) or baseline_summary.get("hard_qa_initial_errors", 0) or 0),
            "rerun_hard_total": int(rerun_summary.get("hard_qa_recheck_errors", 0) or rerun_summary.get("hard_qa_initial_errors", 0) or 0),
            "baseline_review_total": int(baseline_summary.get("review_queue_total", 0) or 0),
            "rerun_review_total": int(rerun_summary.get("review_queue_total", 0) or 0),
            "baseline_soft_major": int(baseline_summary.get("soft_qa_major", 0) or 0),
            "rerun_soft_major": int(rerun_summary.get("soft_qa_major", 0) or 0),
            "hard_type_counts": hard_type_counts,
        },
        "family_residuals": family_review_table(baseline_review, rerun_review, rerun_denominators, focused_compare),
        "soft_qa": {
            "overall_issue_type_counts": rerun_soft_metrics["overall_issue_type_counts"],
            "hard_gate": hard_gate,
            "noise_split": noise_split,
        },
        "assessment_notes": notes,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Assess a full UI-art rerun against the baseline full run and focused anchor.")
    ap.add_argument("--baseline-run-dir", required=True)
    ap.add_argument("--focused-run-dir", required=True)
    ap.add_argument("--rerun-run-dir", required=True)
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args()

    payload = build_assessment(
        baseline_run_dir=Path(args.baseline_run_dir),
        focused_run_dir=Path(args.focused_run_dir),
        rerun_run_dir=Path(args.rerun_run_dir),
    )
    write_json(Path(args.out_json), payload)
    Path(args.out_md).write_text(make_markdown(payload), encoding="utf-8")
    print(f"[OK] Wrote full rerun assessment -> {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
