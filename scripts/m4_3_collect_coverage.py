#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collect M4-3 coverage matrix and issue hotspots from recent full smoke runs."""

from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


CORE_STAGES = [
    "Connectivity",
    "Normalize",
    "Translate",
    "QA Hard",
    "Rehydrate",
    "Smoke Verify",
]

STAGE_TO_SCRIPT = {
    "connectivity": "scripts/llm_ping.py",
    "normalize": "scripts/normalize_guard.py",
    "translate": "scripts/translate_llm.py",
    "qa hard": "scripts/qa_hard.py",
    "qa": "scripts/qa_hard.py",
    "rehydrate": "scripts/rehydrate_export.py",
    "smoke verify": "scripts/smoke_verify.py",
}


def _safe_load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _safe_load_jsonl(path: Path) -> List[dict]:
    if not path.exists():
        return []
    records: List[dict] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except Exception:
                continue
    return records


def _safe_write_jsonl(path: Path, records: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in records:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def _build_hotspot_summary(
    selected_run_dirs: List[str],
    selected_run_ids: List[str],
    hotspot_count: int,
) -> dict:
    return {
        "type": "summary",
        "report": "M4-3 issue hotspots (computed)",
        "selected_run_dirs": selected_run_dirs,
        "selected_run_ids": selected_run_ids,
        "hotspot_count": hotspot_count,
        "notes": [
            "Hotspots are grouped by (stage, error_code) across selected run set.",
            "A summary-only file indicates the collector ran successfully and found zero hotspots.",
        ],
    }


def _normalize_stage_name(stage_name: str) -> str:
    normalized = (stage_name or "").strip().lower()
    # strip "(en-US)" like suffix
    normalized = re.sub(r"\([^)]*\)", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return ""
    if "connect" in normalized:
        return "connectivity"
    if normalized.startswith("norm"):
        return "normalize"
    if normalized.startswith("trans"):
        return "translate"
    if normalized.startswith("qa"):
        return "qa hard"
    if normalized.startswith("rehyd"):
        return "rehydrate"
    if "verify" in normalized:
        return "smoke verify"
    return normalized


def _stage_to_script(stage_name: str) -> Optional[str]:
    if not stage_name:
        return None
    normalized = _normalize_stage_name(stage_name)
    return STAGE_TO_SCRIPT.get(normalized)


def _collect_runs(
    smoke_runs_dir: Path,
    prefix: str,
    run_window: int,
) -> List[Tuple[Path, dict]]:
    candidates = []
    for p in smoke_runs_dir.iterdir():
        if not p.is_dir():
            continue
        if not p.name.startswith(prefix):
            continue
        manifest_path = p / "run_manifest.json"
        if not manifest_path.exists():
            continue
        manifest = _safe_load_json(manifest_path)
        if not manifest:
            continue
        candidates.append((manifest_path, manifest))

    candidates.sort(key=lambda item: item[1].get("timestamp", ""), reverse=True)
    if len(candidates) <= run_window:
        return candidates
    return candidates[:run_window]


def _collect_issues_for_run(run_dir: Path, manifest: dict) -> List[dict]:
    all_issues: List[dict] = []

    # prefer explicit issue file if available
    issue_path = run_dir / "smoke_issues.json"
    explicit = manifest.get("issue_file")
    if explicit:
        candidate = Path(explicit)
        if not candidate.is_absolute():
            candidate = run_dir / candidate
        issue_data = _safe_load_json(candidate)
        if isinstance(issue_data, dict):
            issues = issue_data.get("issues", [])
            if isinstance(issues, list):
                all_issues.extend(issues)

    if issue_path.exists():
        issue_data = _safe_load_json(issue_path)
        issues = issue_data.get("issues", []) if isinstance(issue_data, dict) else []
        if isinstance(issues, list):
            all_issues.extend(issues)

    # include jsonl issues if any
    for path in run_dir.glob("smoke_issues*.jsonl"):
        all_issues.extend(_safe_load_jsonl(path))

    # de-duplicate conservatively by tuple(fields), keep last occurrence
    dedup: Dict[Tuple, dict] = {}
    for issue in all_issues:
        if not isinstance(issue, dict):
            continue
        context = issue.get("context", {})
        try:
            context_key = json.dumps(context, ensure_ascii=False, sort_keys=True)
        except Exception:
            context_key = str(context)
        key = (
            issue.get("run_id", ""),
            issue.get("stage", ""),
            issue.get("error_code", ""),
            issue.get("row", ""),
            issue.get("string_id", ""),
            context_key,
        )
        dedup[key] = issue
    issues = list(dedup.values())
    return _override_current_qa_warning_state(run_dir, manifest, issues)


def _resolve_run_artifact_path(run_dir: Path, manifest: dict, *keys: str) -> Optional[Path]:
    candidates = []
    for key in keys:
        value = manifest.get(key)
        if value:
            candidates.append(value)
        stage_artifacts = manifest.get("stage_artifacts", {})
        if isinstance(stage_artifacts, dict) and stage_artifacts.get(key):
            candidates.append(stage_artifacts.get(key))
        artifacts = manifest.get("artifacts", {})
        if isinstance(artifacts, dict) and artifacts.get(key):
            candidates.append(artifacts.get(key))

    for candidate in candidates:
        path = Path(str(candidate))
        if not path.is_absolute():
            path = run_dir / path
        if path.exists():
            return path
    return None


def _override_current_qa_warning_state(run_dir: Path, manifest: dict, issues: List[dict]) -> List[dict]:
    filtered = [
        issue for issue in issues
        if issue.get("error_code") not in {"QA_HARD_WARNINGS", "VERIFY_QA_WARNING"}
    ]

    qa_report_path = _resolve_run_artifact_path(run_dir, manifest, "qa_hard_report", "smoke_qa_hard_report")
    if not qa_report_path:
        return filtered

    qa_report = _safe_load_json(qa_report_path)
    if not qa_report:
        return filtered

    warning_total = int((qa_report.get("metadata", {}) or {}).get("total_warnings", 0))
    warning_policy = qa_report.get("warning_policy") or {}
    actionable_warning_total = int(warning_policy.get("actionable_warning_total", warning_total))

    if actionable_warning_total <= 0:
        return filtered

    run_id = manifest.get("run_id", run_dir.name)
    warning_counts = qa_report.get("warning_counts", {})
    warning_samples = (qa_report.get("warnings") or [])[:20]
    filtered.extend([
        {
            "run_id": run_id,
            "stage": "qa hard",
            "severity": "P2",
            "error_code": "QA_HARD_WARNINGS",
            "context": {
                "qa_report": str(qa_report_path),
                "total_warnings": warning_total,
                "actionable_warning_total": actionable_warning_total,
                "warning_counts": warning_counts,
                "warning_policy": warning_policy,
                "warning_samples": warning_samples,
            },
        },
        {
            "run_id": run_id,
            "stage": "smoke verify",
            "severity": "P2",
            "error_code": "VERIFY_QA_WARNING",
            "context": {
                "qa_report": str(qa_report_path),
                "total_warnings": warning_total,
                "actionable_warning_total": actionable_warning_total,
                "warning_counts": warning_counts,
                "warning_policy": warning_policy,
                "warning_samples": warning_samples,
            },
        },
    ])
    return filtered


def _severity_rank(sev: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2}.get(str(sev).upper(), 3)


def collect_coverage_and_hotspots(
    smoke_runs_dir: Path,
    run_prefix: str,
    run_window: int = 3,
):
    selected_runs = _collect_runs(smoke_runs_dir, run_prefix, run_window)
    selected_run_count = len(selected_runs)
    selected_run_ids = [manifest.get("run_id", manifest_path.parent.name) for manifest_path, manifest in selected_runs]
    selected_run_dirs = [str(manifest_path.parent) for manifest_path, _ in selected_runs]
    selected_run_ids_by_position = {rid: idx for idx, rid in enumerate(selected_run_ids)}

    touch_map: Dict[str, Dict[str, bool]] = {stage.lower(): {} for stage in CORE_STAGES}
    for manifest_path, manifest in selected_runs:
        run_id = manifest.get("run_id", manifest_path.parent.name)
        for stage in manifest.get("stages", []) or []:
            stage_name = _normalize_stage_name(stage.get("name", ""))
            if not stage_name:
                continue
            if stage_name == "translate" or stage_name.startswith("translate"):
                stage_key = "translate"
            elif stage_name == "qa hard":
                stage_key = "qa hard"
            elif stage_name == "smoke verify":
                stage_key = "smoke verify"
            elif stage_name == "connectivity":
                stage_key = "connectivity"
            elif stage_name == "normalize":
                stage_key = "normalize"
            elif stage_name == "rehydrate":
                stage_key = "rehydrate"
            else:
                stage_key = stage_name
            touch_map.setdefault(stage_key, {})[run_id] = True

    stage_coverage_records = []
    for stage_key in CORE_STAGES:
        key = stage_key.lower()
        if key == "qa hard":
            key = "qa hard"
        touched_runs = [run_id for run_id in selected_run_ids if run_id in touch_map.get(key, {})]
        touch_count = len(touched_runs)
        stage_coverage_records.append({
            "type": "stage_coverage",
            "stage": stage_key,
            "touch_count": touch_count,
            "touch_ratio": touch_count / max(1, selected_run_count),
            "touched_run_ids": touched_runs,
            "per_run": {run_id: bool(run_id in touch_map.get(key, {})) for run_id in selected_run_ids},
            "script": STAGE_TO_SCRIPT.get(key) or STAGE_TO_SCRIPT.get(key.replace("-", " ")),
            "core_stage": True,
        })

    issue_hotspots = defaultdict(lambda: {
        "run_ids": set(),
        "occurrences": 0,
        "first_seen_run_idx": None,
        "severity": "P3",
    })
    for manifest_path, manifest in selected_runs:
        run_id = manifest.get("run_id", manifest_path.parent.name)
        issues = _collect_issues_for_run(manifest_path.parent, manifest)
        for issue in issues:
            stage_name = _normalize_stage_name(issue.get("stage", ""))
            if not stage_name:
                continue
            error_code = issue.get("error_code", "UNKNOWN")
            key = (stage_name, error_code)
            rec = issue_hotspots[key]
            rec["occurrences"] += 1
            rec["run_ids"].add(run_id)
            idx = selected_run_ids_by_position.get(run_id, 1_000_000)
            if rec["first_seen_run_idx"] is None or idx < rec["first_seen_run_idx"]:
                rec["first_seen_run_idx"] = idx
                rec["first_seen_run_id"] = run_id
            run_sev = str(issue.get("severity", "P2")).upper()
            if _severity_rank(run_sev) < _severity_rank(rec["severity"]):
                rec["severity"] = run_sev

    issue_hotspot_records: List[dict] = []
    for (stage_name, error_code), rec in issue_hotspots.items():
        severity = rec["severity"]
        run_ids = sorted(rec["run_ids"])
        if severity == "P0":
            decision_hint = "BLOCK"
        elif severity in {"P1", "P2"}:
            decision_hint = "REWORK"
        else:
            decision_hint = "KEEP"
        issue_hotspot_records.append({
            "type": "stage_issue_hotspot",
            "stage": stage_name,
            "error_code": error_code,
            "severity": severity,
            "first_seen_run_id": rec.get("first_seen_run_id", run_ids[0] if run_ids else ""),
            "occurrences": rec["occurrences"],
            "run_ids": run_ids,
            "decision_hint": decision_hint,
        })

    issue_hotspot_records.sort(key=lambda item: (item["stage"], item["error_code"]))

    summary = {
        "type": "summary",
        "report": "M4-3 coverage matrix (computed)",
        "selected_run_dirs": selected_run_dirs,
        "selected_run_ids": selected_run_ids,
        "core_stage_assumption": "core stages by manifest names",
        "core_scripts": [
            STAGE_TO_SCRIPT.get(_normalize_stage_name(stage), "")
            for stage in CORE_STAGES
        ],
        "notes": [
            "Connectivity/normalize/translate/qa_hard/rehydrate/smoke_verify coverage from manifest stages.",
            "Issue hotspots are grouped by (stage, error_code) across selected run set.",
            "Run ordering follows manifest timestamp descending."
        ],
    }

    return summary, stage_coverage_records, issue_hotspot_records, selected_runs


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect M4-3 coverage matrix and issue hotspots."
    )
    repo_root = Path(__file__).resolve().parents[1]
    default_runs_dir = repo_root / "data" / "smoke_runs"
    parser.add_argument("--smoke-runs-dir", default=str(default_runs_dir))
    parser.add_argument("--run-prefix", default="manual_1000_full_")
    parser.add_argument("--run-window", type=int, default=3)
    parser.add_argument(
        "--coverage-out",
        default=str(default_runs_dir / "M4_3_coverage_report.jsonl"),
    )
    parser.add_argument(
        "--issue-hotspots-out",
        default=str(default_runs_dir / "M4_3_issue_hotspots.jsonl"),
    )

    args = parser.parse_args()
    smoke_runs_dir = Path(args.smoke_runs_dir)
    coverage_out = Path(args.coverage_out)
    hotspots_out = Path(args.issue_hotspots_out)

    summary, coverage, hotspots, _ = collect_coverage_and_hotspots(
        smoke_runs_dir=smoke_runs_dir,
        run_prefix=args.run_prefix,
        run_window=args.run_window,
    )
    records = [summary] + coverage
    _safe_write_jsonl(coverage_out, records)
    hotspot_records = hotspots or [
        _build_hotspot_summary(
            selected_run_dirs=summary.get("selected_run_dirs", []),
            selected_run_ids=summary.get("selected_run_ids", []),
            hotspot_count=0,
        )
    ]
    _safe_write_jsonl(hotspots_out, hotspot_records)

    print(f"OK Wrote coverage -> {coverage_out}")
    print(f"OK Wrote issue hotspots -> {hotspots_out}")
    print(f"Stats: Runs analyzed: {len(summary.get('selected_run_ids', []))}, "
          f"stage entries: {len(records)-1}, issue hotspots: {len(hotspots)}")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
