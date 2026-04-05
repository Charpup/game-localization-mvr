#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Compare a UI-art recovery canary run against the previous full live run on the same sampled rows.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

RELEVANT_HARD_TYPES = {
    "length_overflow",
    "compact_mapping_missing",
    "compact_term_miss",
    "line_budget_overflow",
    "headline_budget_overflow",
    "promo_expansion_forbidden",
}
INVARIANT_HARD_TYPES = {"token_mismatch", "tag_unbalanced", "forbidden_hit", "new_placeholder_found", "empty_translation"}


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


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


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


def choose_translation_path(run_dir: Path) -> Path:
    for name in ("ui_art_repaired_hard_v2.csv", "ui_art_repaired_hard.csv", "ui_art_translated.csv"):
        candidate = run_dir / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"No translation CSV found under {run_dir}")


def join_sample_with_translation(sample_rows: List[Dict[str, str]], translation_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    translation_map = {str(row.get("string_id") or ""): row for row in translation_rows}
    joined: List[Dict[str, str]] = []
    missing: List[str] = []
    for sample_row in sample_rows:
        sid = str(sample_row.get("string_id") or "")
        translated = translation_map.get(sid)
        if not translated:
            missing.append(sid)
            continue
        merged = dict(sample_row)
        for key, value in translated.items():
            if key == "string_id":
                continue
            merged[key] = value
        joined.append(merged)
    if missing:
        raise RuntimeError(f"Missing translated rows for sampled ids: {missing[:10]}")
    return joined


def run_qa_hard(
    python_exe: Path,
    input_csv: Path,
    placeholder_map: Path,
    schema: Path,
    forbidden: Path,
    report_path: Path,
) -> Dict[str, Any]:
    result = subprocess.run(
        [
            str(python_exe),
            "scripts/qa_hard.py",
            str(input_csv),
            str(placeholder_map),
            str(schema),
            str(forbidden),
            str(report_path),
        ],
        cwd=str(Path(__file__).resolve().parent.parent),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if not report_path.exists():
        raise RuntimeError(f"qa_hard compare run failed without report: {result.stderr}")
    return read_json(report_path)


def build_sample_maps(sample_rows: List[Dict[str, str]]) -> Tuple[Dict[str, str], Dict[str, str], Counter]:
    category_by_id = {}
    source_by_id = {}
    counts: Counter[str] = Counter()
    for row in sample_rows:
        sid = str(row.get("string_id") or "")
        category = str(row.get("ui_art_category") or "other_review")
        category_by_id[sid] = category
        source_by_id[sid] = str(row.get("source_zh") or "")
        counts[category] += 1
    return category_by_id, source_by_id, counts


def hard_metrics(report: Dict[str, Any], category_by_id: Dict[str, str], source_by_id: Dict[str, str], denominators: Counter) -> Dict[str, Any]:
    errors = report.get("errors") or []
    category_issue_counts: Dict[str, Counter] = defaultdict(Counter)
    category_severity_counts: Dict[str, Counter] = defaultdict(Counter)
    category_source_fail_counts: Dict[str, Counter] = defaultdict(Counter)
    failing_ids: Dict[str, set[str]] = defaultdict(set)
    invariant_counts: Counter[str] = Counter()

    for error in errors:
        sid = str(error.get("string_id") or "")
        category = category_by_id.get(sid, str(error.get("ui_art_category") or "other_review"))
        source_text = source_by_id.get(sid, str(error.get("source") or ""))
        issue_type = str(error.get("type") or "unknown")
        severity = str(error.get("severity") or "major")
        category_issue_counts[category][issue_type] += 1
        category_severity_counts[category][severity] += 1
        if issue_type in RELEVANT_HARD_TYPES:
            failing_ids[category].add(sid)
            if source_text:
                category_source_fail_counts[category][source_text] += 1
        if issue_type in INVARIANT_HARD_TYPES:
            invariant_counts[issue_type] += 1

    category_rates = {}
    for category, denominator in denominators.items():
        fail_count = len(failing_ids.get(category, set()))
        category_rates[category] = {
            "denominator": denominator,
            "hard_fail_rows": fail_count,
            "hard_fail_rate": round((fail_count / denominator) if denominator else 0.0, 4),
            "severity_counts": dict(category_severity_counts.get(category, Counter())),
            "issue_type_counts": dict(category_issue_counts.get(category, Counter())),
            "source_fail_counts": dict(category_source_fail_counts.get(category, Counter())),
        }
    return {
        "by_category": category_rates,
        "invariant_counts": dict(invariant_counts),
    }


def review_metrics(review_rows: List[Dict[str, str]], category_by_id: Dict[str, str]) -> Dict[str, Any]:
    totals: Dict[str, Counter] = defaultdict(Counter)
    for row in review_rows:
        sid = str(row.get("string_id") or "")
        category = category_by_id.get(sid, str(row.get("ui_art_category") or "other_review"))
        severity = str(row.get("severity") or "unknown")
        totals[category]["review_rows"] += 1
        totals[category][f"severity:{severity}"] += 1
    return {category: dict(counter) for category, counter in totals.items()}


def soft_metrics(tasks: List[Dict[str, Any]], category_by_id: Dict[str, str]) -> Dict[str, Any]:
    overall = Counter()
    by_category: Dict[str, Counter] = defaultdict(Counter)
    for task in tasks:
        sid = str(task.get("string_id") or task.get("id") or "")
        if sid == "system" or sid not in category_by_id:
            continue
        category = category_by_id[sid]
        issue_type = str(task.get("type") or task.get("issue_type") or "unknown")
        overall[issue_type] += 1
        by_category[category][issue_type] += 1
    return {
        "overall_issue_type_counts": dict(overall),
        "by_category_issue_type_counts": {category: dict(counter) for category, counter in by_category.items()},
    }


def evaluate_promotion(canary_hard: Dict[str, Any], baseline_hard: Dict[str, Any], profile: str = "recovery_canary_v1") -> Dict[str, Any]:
    canary_by_category = canary_hard["by_category"]
    baseline_by_category = baseline_hard["by_category"]

    def _rate(report: Dict[str, Any], category: str) -> float:
        return float(report.get(category, {}).get("hard_fail_rate", 0.0))

    badge_fail_rows = (
        int(canary_by_category.get("badge_micro_1c", {}).get("hard_fail_rows", 0))
        + int(canary_by_category.get("badge_micro_2c", {}).get("hard_fail_rows", 0))
    )
    badge_denominator = (
        int(canary_by_category.get("badge_micro_1c", {}).get("denominator", 0))
        + int(canary_by_category.get("badge_micro_2c", {}).get("denominator", 0))
    )
    badge_rate = (badge_fail_rows / badge_denominator) if badge_denominator else 0.0

    slogan_issues = canary_by_category.get("slogan_long", {}).get("issue_type_counts", {})
    line_budget = int(slogan_issues.get("line_budget_overflow", 0))
    other_slogan_types = {k: v for k, v in slogan_issues.items() if k != "line_budget_overflow"}
    slogan_rule_pass = (
        int(canary_by_category.get("slogan_long", {}).get("hard_fail_rows", 0)) == 0
        or (
            line_budget >= max(other_slogan_types.values(), default=0)
            and _rate(canary_by_category, "slogan_long") < _rate(baseline_by_category, "slogan_long")
        )
    )

    invariant_pass = True
    invariant_regressions = {}
    canary_invariants = canary_hard.get("invariant_counts", {})
    baseline_invariants = baseline_hard.get("invariant_counts", {})
    for issue_type in sorted(INVARIANT_HARD_TYPES):
        base_count = int(baseline_invariants.get(issue_type, 0))
        current_count = int(canary_invariants.get(issue_type, 0))
        if current_count > base_count:
            invariant_pass = False
            invariant_regressions[issue_type] = {"baseline": base_count, "canary": current_count}

    if profile == "focused_recovery_slice_v2":
        promo_source_counts = canary_by_category.get("promo_short", {}).get("source_fail_counts", {})
        slogan_issue_counts = canary_by_category.get("slogan_long", {}).get("issue_type_counts", {})
        allowed_slogan_types = {"headline_budget_overflow", "line_budget_overflow"}
        slogan_types_ok = all(issue_type in allowed_slogan_types for issue_type in slogan_issue_counts)
        thresholds = {
            "badge_micro_2c": int(canary_by_category.get("badge_micro_2c", {}).get("hard_fail_rows", 0)) == 0,
            "promo_short": _rate(canary_by_category, "promo_short") < 0.20,
            "promo_repeated_clusters": int(promo_source_counts.get("奖励预览", 0)) <= 1 and int(promo_source_counts.get("充值返利", 0)) <= 1,
            "item_skill_name": _rate(canary_by_category, "item_skill_name") < 0.45,
            "slogan_long": _rate(canary_by_category, "slogan_long") < 0.25 and slogan_types_ok,
            "badge_micro_1c_sentinel": _rate(canary_by_category, "badge_micro_1c") <= _rate(baseline_by_category, "badge_micro_1c"),
            "label_generic_short_sentinel": _rate(canary_by_category, "label_generic_short") <= _rate(baseline_by_category, "label_generic_short"),
            "title_name_short_sentinel": _rate(canary_by_category, "title_name_short") <= _rate(baseline_by_category, "title_name_short"),
            "hard_invariants": invariant_pass,
        }
        decision = "ready_for_full_rerun" if all(thresholds.values()) else "hold_full_rerun"
    else:
        thresholds = {
            "badge_micro_combined": badge_rate < 0.5,
            "label_generic_short": _rate(canary_by_category, "label_generic_short") < 0.35,
            "title_name_short": _rate(canary_by_category, "title_name_short") < 0.40,
            "slogan_long": slogan_rule_pass,
            "hard_invariants": invariant_pass,
        }
        decision = "pass_ready_for_full_rerun" if all(thresholds.values()) else "failed_hold_full_rerun"
    return {
        "profile": profile,
        "thresholds": thresholds,
        "badge_micro_combined_fail_rate": round(badge_rate, 4),
        "invariant_regressions": invariant_regressions,
        "decision": decision,
    }


def build_markdown_report(payload: Dict[str, Any]) -> str:
    lines = [
        "# UI Art Recovery Canary Comparison",
        "",
        f"- Decision: `{payload['promotion']['decision']}`",
        f"- Sample rows: `{payload['sample']['selected_total']}`",
        "",
        "## Threshold Check",
    ]
    for key, passed in payload["promotion"]["thresholds"].items():
        lines.append(f"- `{key}`: `{'pass' if passed else 'fail'}`")
    lines.extend(["", "## Category Hard-QA Rates", "| Category | Baseline | Canary |", "|---|---:|---:|"])
    for category in sorted(payload["baseline"]["hard"]["by_category"]):
        base_rate = payload["baseline"]["hard"]["by_category"][category]["hard_fail_rate"]
        canary_rate = payload["canary"]["hard"]["by_category"].get(category, {}).get("hard_fail_rate", 0.0)
        lines.append(f"| {category} | {base_rate:.2%} | {canary_rate:.2%} |")
    lines.extend(["", "## Review Queue Volume", "| Category | Baseline | Canary |", "|---|---:|---:|"])
    review_categories = sorted(set(payload["baseline"]["review_queue"]) | set(payload["canary"]["review_queue"]))
    for category in review_categories:
        base_count = int((payload["baseline"]["review_queue"].get(category) or {}).get("review_rows", 0))
        canary_count = int((payload["canary"]["review_queue"].get(category) or {}).get("review_rows", 0))
        lines.append(f"| {category} | {base_count} | {canary_count} |")
    lines.extend(
        [
            "",
            "## Soft-QA Mix",
            "Baseline overall issue counts:",
            "```json",
            json.dumps(payload["baseline"]["soft"]["overall_issue_type_counts"], ensure_ascii=False, indent=2),
            "```",
            "Canary overall issue counts:",
            "```json",
            json.dumps(payload["canary"]["soft"]["overall_issue_type_counts"], ensure_ascii=False, indent=2),
            "```",
        ]
    )
    if payload["promotion"]["invariant_regressions"]:
        lines.extend(["", "## Invariant Regressions", "```json", json.dumps(payload["promotion"]["invariant_regressions"], ensure_ascii=False, indent=2), "```"])
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare the UI-art recovery canary against the previous live run.")
    ap.add_argument("--sample-prepared", required=True)
    ap.add_argument("--baseline-run-dir", required=True)
    ap.add_argument("--canary-run-dir", required=True)
    ap.add_argument("--promotion-profile", default="recovery_canary_v1")
    ap.add_argument("--schema", default=str(Path(__file__).resolve().parent.parent / "workflow" / "placeholder_schema.yaml"))
    ap.add_argument("--forbidden-patterns", default=str(Path(__file__).resolve().parent.parent / "workflow" / "forbidden_patterns.txt"))
    ap.add_argument("--out-json", required=True)
    ap.add_argument("--out-md", required=True)
    args = ap.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    python_exe = repo_root / ".venv" / "Scripts" / "python.exe"
    sample_rows, sample_fields = read_csv(Path(args.sample_prepared))
    category_by_id, source_by_id, denominators = build_sample_maps(sample_rows)

    baseline_run_dir = Path(args.baseline_run_dir)
    canary_run_dir = Path(args.canary_run_dir)
    compare_tmp = canary_run_dir / "compare_tmp"
    compare_tmp.mkdir(parents=True, exist_ok=True)

    baseline_translation_rows, _ = read_csv(choose_translation_path(baseline_run_dir))
    canary_translation_rows, _ = read_csv(choose_translation_path(canary_run_dir))

    baseline_joined = join_sample_with_translation(sample_rows, baseline_translation_rows)
    canary_joined = join_sample_with_translation(sample_rows, canary_translation_rows)

    baseline_subset_csv = compare_tmp / "baseline_subset.csv"
    canary_subset_csv = compare_tmp / "canary_subset.csv"
    write_csv(baseline_subset_csv, baseline_joined, set(sample_fields) | set().union(*(row.keys() for row in baseline_joined)))
    write_csv(canary_subset_csv, canary_joined, set(sample_fields) | set().union(*(row.keys() for row in canary_joined)))

    baseline_hard_report = run_qa_hard(
        python_exe=python_exe,
        input_csv=baseline_subset_csv,
        placeholder_map=baseline_run_dir / "placeholder_map.json",
        schema=Path(args.schema),
        forbidden=Path(args.forbidden_patterns),
        report_path=compare_tmp / "baseline_qa_hard_report.json",
    )
    canary_hard_report = run_qa_hard(
        python_exe=python_exe,
        input_csv=canary_subset_csv,
        placeholder_map=canary_run_dir / "placeholder_map.json",
        schema=Path(args.schema),
        forbidden=Path(args.forbidden_patterns),
        report_path=compare_tmp / "canary_qa_hard_report.json",
    )

    baseline_review_rows = [row for row in read_csv(baseline_run_dir / "ui_art_review_queue.csv")[0] if str(row.get("string_id") or "") in category_by_id]
    canary_review_rows = [row for row in read_csv(canary_run_dir / "ui_art_review_queue.csv")[0] if str(row.get("string_id") or "") in category_by_id]
    baseline_soft_tasks = [task for task in read_jsonl(baseline_run_dir / "ui_art_soft_tasks.jsonl") if str(task.get("string_id") or "") in category_by_id]
    canary_soft_tasks = [task for task in read_jsonl(canary_run_dir / "ui_art_soft_tasks.jsonl") if str(task.get("string_id") or "") in category_by_id]

    payload = {
        "sample": read_json(Path(args.sample_prepared).with_suffix(".manifest.json")) if Path(args.sample_prepared).with_suffix(".manifest.json").exists() else {"selected_total": len(sample_rows)},
        "baseline": {
            "run_dir": str(baseline_run_dir),
            "hard": hard_metrics(baseline_hard_report, category_by_id, source_by_id, denominators),
            "review_queue": review_metrics(baseline_review_rows, category_by_id),
            "soft": soft_metrics(baseline_soft_tasks, category_by_id),
        },
        "canary": {
            "run_dir": str(canary_run_dir),
            "hard": hard_metrics(canary_hard_report, category_by_id, source_by_id, denominators),
            "review_queue": review_metrics(canary_review_rows, category_by_id),
            "soft": soft_metrics(canary_soft_tasks, category_by_id),
        },
    }
    payload["promotion"] = evaluate_promotion(payload["canary"]["hard"], payload["baseline"]["hard"], profile=args.promotion_profile)

    write_json(Path(args.out_json), payload)
    Path(args.out_md).write_text(build_markdown_report(payload), encoding="utf-8")
    print(f"[OK] Wrote canary comparison -> {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
