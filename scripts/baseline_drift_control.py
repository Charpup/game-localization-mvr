#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Milestone D baseline drift control for validation samples.

This script keeps a baseline validation snapshot and executes a deterministic
drift comparison gate. It supports:

1) create-baseline
   Build or register a validation sample snapshot and persist its manifest.

2) compare
   Rebuild or load a current sample, compare it against the baseline, write
drift reports, and fail when thresholds are exceeded.

3) run-ID aliases for milestones:
   plc_run_d_prepare / plc_run_d_full / plc_run_d_verify
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

try:
    from scripts.build_validation_set import (
        STRATA,
        calculate_sha256,
        classify_stratum,
        load_source_columns,
        load_source_data,
        stratified_sample,
        write_csv,
        write_meta,
    )
except ImportError:  # pragma: no cover
    from build_validation_set import (
        STRATA,
        calculate_sha256,
        classify_stratum,
        load_source_columns,
        load_source_data,
        stratified_sample,
        write_csv,
        write_meta,
    )


MANIFEST_VERSION = "baseline-drift-v1"
DEFAULT_RUN_RECORD_DIR = Path("docs/project_lifecycle/run_records")

DEFAULT_D_PREPARE_SOURCE = "output/test_30_repaired.csv"
DEFAULT_D_PREPARE_ROWS = 10
DEFAULT_D_PREPARE_SEED = 42
DEFAULT_D_PREPARE_SCOPE = "milestone_D_prepare"

DEFAULT_D_COMPARE_SOURCE = "output/test_30_repaired.csv"
DEFAULT_D_COMPARE_ROWS = 10
DEFAULT_D_COMPARE_SEED = 42
DEFAULT_D_COMPARE_MAX_ROW_CHURN_RATIO = 0.05
DEFAULT_D_COMPARE_MAX_STRATUM_DELTA = 2
DEFAULT_D_COMPARE_REQUIRE_SOURCE_MATCH = True
DEFAULT_D_COMPARE_REQUIRE_SAMPLE_CHECKSUM_MATCH = False
DEFAULT_D_COMPARE_SCOPE = "milestone_D_full"
DEFAULT_D_VERIFY_SCOPE = "milestone_D_verify"

PLC_PRESETS: Dict[str, Dict[str, Any]] = {
    "plc_run_d_prepare": {
        "mode": "create_baseline",
        "run_scope": DEFAULT_D_PREPARE_SCOPE,
        "name": "plc_run_d_prepare",
        "output_dir": "data/baselines",
        "source": DEFAULT_D_PREPARE_SOURCE,
        "rows": DEFAULT_D_PREPARE_ROWS,
        "seed": DEFAULT_D_PREPARE_SEED,
        "default_next_scope": "milestone_D_full",
    },
    "plc_run_d_full": {
        "mode": "compare",
        "run_scope": DEFAULT_D_COMPARE_SCOPE,
        "baseline_manifest": "data/baselines/plc_run_d_prepare/plc_run_d_prepare",
        "source": DEFAULT_D_COMPARE_SOURCE,
        "rows": DEFAULT_D_COMPARE_ROWS,
        "seed": DEFAULT_D_COMPARE_SEED,
        "max_row_churn_ratio": DEFAULT_D_COMPARE_MAX_ROW_CHURN_RATIO,
        "max_stratum_delta": DEFAULT_D_COMPARE_MAX_STRATUM_DELTA,
        "require_source_match": DEFAULT_D_COMPARE_REQUIRE_SOURCE_MATCH,
        "require_sample_checksum_match": DEFAULT_D_COMPARE_REQUIRE_SAMPLE_CHECKSUM_MATCH,
        "default_next_scope": "milestone_E_prepare",
        "output_dir": None,
    },
    "plc_run_d_verify": {
        "mode": "compare",
        "run_scope": DEFAULT_D_VERIFY_SCOPE,
        "baseline_manifest": "data/baselines/plc_run_d_prepare/plc_run_d_prepare",
        "source": DEFAULT_D_COMPARE_SOURCE,
        "rows": DEFAULT_D_COMPARE_ROWS,
        "seed": DEFAULT_D_COMPARE_SEED,
        "max_row_churn_ratio": DEFAULT_D_COMPARE_MAX_ROW_CHURN_RATIO,
        "max_stratum_delta": DEFAULT_D_COMPARE_MAX_STRATUM_DELTA,
        "require_source_match": DEFAULT_D_COMPARE_REQUIRE_SOURCE_MATCH,
        "require_sample_checksum_match": DEFAULT_D_COMPARE_REQUIRE_SAMPLE_CHECKSUM_MATCH,
        "default_next_scope": "milestone_E_prepare",
        "output_dir": None,
    },
}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def normalize_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name.strip())


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    ensure_parent(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def resolve_input_source(path_hint: str) -> Path:
    raw = Path(path_hint).resolve()
    if raw.exists():
        return raw
    fallback_candidates = [
        Path("test_30_repaired.csv"),
        Path("data/test_30_repaired.csv"),
        Path("output/test_30_repaired.csv"),
    ]
    for candidate in fallback_candidates:
        candidate = candidate.resolve()
        if candidate.exists():
            return candidate
    return raw


def write_text(path: Path, content: str) -> None:
    ensure_parent(path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def row_ids_from_csv(path: Path) -> List[str]:
    ids: List[str] = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = str(row.get("string_id", "")).strip()
            if sid:
                ids.append(sid)
    return ids


def load_rows_with_strata(path: Path) -> Tuple[List[Dict[str, str]], Dict[str, int]]:
    rows = load_source_data(str(path))
    counts: Dict[str, int] = {stratum: 0 for stratum in STRATA}
    for row in rows:
        counts[classify_stratum(row)] += 1
    return rows, counts


def hash_row_ids(row_ids: Sequence[str]) -> str:
    digest = hashlib.sha256()
    for sid in sorted(row_ids):
        digest.update(sid.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def build_snapshot_signature(
    *,
    source: Path,
    source_sha256: str,
    sample_sha256: str,
    seed: int,
    target_rows: int,
    row_ids: Sequence[str],
    stratum_distribution: Dict[str, int],
    input_columns: Sequence[str] | None = None,
    output_columns: Sequence[str] | None = None,
) -> str:
    payload = {
        "source": str(source.resolve()),
        "source_sha256": source_sha256,
        "sample_sha256": sample_sha256,
        "seed": int(seed),
        "target_rows": int(target_rows),
        "actual_rows": len(row_ids),
        "row_ids_hash": hash_row_ids(row_ids),
        "stratum_distribution": {
            stratum: int(stratum_distribution.get(stratum, 0)) for stratum in STRATA
        },
        "input_columns": list(input_columns or []),
        "output_columns": list(output_columns or []),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def build_drift_signature(added: Sequence[str], removed: Sequence[str]) -> str:
    payload = {
        "added": sorted(added),
        "removed": sorted(removed),
        "added_count": len(added),
        "removed_count": len(removed),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _next_scope(run_id: str, run_scope: str) -> str:
    preset_next = PLC_PRESETS.get(run_id, {}).get("default_next_scope", "")
    if preset_next:
        return preset_next
    if run_scope.endswith("_prepare"):
        return run_scope.replace("_prepare", "_full")
    if run_scope.endswith("_full"):
        return run_scope.replace("_full", "_verify")
    return ""


def _owner() -> str:
    return (
        os.getenv("GIT_AUTHOR_NAME")
        or os.getenv("USER")
        or os.getenv("USERNAME")
        or "Codex"
    )


def _resolve_run_record_dir(args: argparse.Namespace) -> Path:
    custom = str(getattr(args, "run_manifest_dir", "")).strip()
    if custom:
        return Path(custom).resolve()
    now = datetime.now().astimezone()
    return (
        DEFAULT_RUN_RECORD_DIR.resolve()
        / now.strftime("%Y-%m")
        / now.strftime("%Y-%m-%d")
    )


def _run_record_paths(args: argparse.Namespace, run_id: str) -> Tuple[Path, Path, Path, Path]:
    base = _resolve_run_record_dir(args)
    run_id_safe = normalize_name(run_id)
    return (
        base / f"run_manifest_{run_id_safe}.json",
        base / f"run_issue_{run_id_safe}.md",
        base / f"run_verify_{run_id_safe}.md",
        base / f"input_manifest_{run_id_safe}.json",
    )


def _relative_path(path: Path) -> str:
    cwd = Path.cwd().resolve()
    candidate = path.resolve()
    try:
        return str(candidate.relative_to(cwd))
    except Exception:
        return str(candidate)


def _stringify_scalar(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _stringify_scalar(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_stringify_scalar(v) for v in value]
    return str(value)


def _normalized_run_args(args: argparse.Namespace) -> Dict[str, Any]:
    payload = {key: _stringify_scalar(value) for key, value in vars(args).items()}
    payload["baseline_data_path"] = str(Path(str(args.source)).resolve())
    payload["sample_limit"] = int(getattr(args, "rows", DEFAULT_D_PREPARE_ROWS))
    payload["row_limit"] = int(getattr(args, "rows", DEFAULT_D_PREPARE_ROWS))
    if hasattr(args, "max_row_churn_ratio"):
        payload["max_row_churn_ratio"] = float(getattr(args, "max_row_churn_ratio"))
    return payload


def _build_decision_refs(
    *,
    run_id: str,
    run_scope: str,
    blockers: Sequence[str],
    metrics: Dict[str, Any] | None = None,
) -> List[str]:
    refs = [
        f"triadev:{run_scope}",
        f"plc:{run_id}",
        "artifact:scripts/baseline_drift_control.py",
    ]
    metrics = metrics or {}
    if metrics.get("baseline_snapshot_signature"):
        refs.append(f"signature:baseline:{metrics['baseline_snapshot_signature']}")
    if metrics.get("current_snapshot_signature"):
        refs.append(f"signature:current:{metrics['current_snapshot_signature']}")
    if metrics.get("drift_signature"):
        refs.append(f"signature:drift:{metrics['drift_signature']}")
    if blockers:
        refs.extend(f"gate:blocker:{item}" for item in blockers)
    return refs


def _sorted_artifacts(artifacts: Sequence[Path]) -> List[str]:
    ordered: List[str] = []
    for path in artifacts:
        p = Path(path)
        if not p.exists():
            continue
        item = _relative_path(p)
        if item not in ordered:
            ordered.append(item)
    return ordered


def _resolve_manifest_path(spec: str | Path) -> Path:
    path = Path(spec).resolve()
    if path.is_dir():
        direct_manifest = path / "baseline_manifest.json"
        if direct_manifest.exists():
            path = direct_manifest
        else:
            nested = list(path.glob("**/baseline_manifest.json"))
            if nested:
                path = nested[0].resolve()
    if not path.exists():
        raise FileNotFoundError(f"Missing baseline manifest: {path}")
    return path

def _extract_manifest_ids(manifest: Dict[str, Any]) -> Tuple[List[str], Dict[str, int], str, str]:
    sample = manifest.get("sample", {})
    row_ids = sample.get("row_ids")
    if not row_ids:
        sample_path = sample.get("path")
        if not sample_path:
            raise ValueError("Baseline manifest missing sample.path")
        row_ids = row_ids_from_csv(Path(sample_path))
    row_ids = [str(i) for i in row_ids]

    stratum_distribution = sample.get("stratum_distribution", {})
    stratum_distribution = {
        stratum: int(stratum_distribution.get(stratum, 0)) for stratum in STRATA
    }
    baseline_snapshot_signature = sample.get("snapshot_signature", "")
    if not baseline_snapshot_signature:
        baseline_snapshot_signature = sample.get("snapshot_signature_from_rows", "")
    return row_ids, stratum_distribution, baseline_snapshot_signature, sample.get("source", {}).get("path", "")


def _write_baseline_report(path: Path, manifest: Dict[str, Any]) -> None:
    sample = manifest.get("sample", {})
    lines = [
        "# Baseline Manifest Report",
        "",
        f"- Baseline Name: {manifest.get('baseline_name')}",
        f"- Generated At: {manifest.get('created_at')}",
        f"- Source: {manifest.get('source', {}).get('path')}",
        f"- Source SHA256: {manifest.get('source', {}).get('sha256')}",
        f"- Sample Path: {sample.get('path')}",
        f"- Sample SHA256: {sample.get('sha256')}",
        f"- Rows: {sample.get('rows')}",
        f"- Seed: {sample.get('seed')}",
        f"- Target Rows: {sample.get('target_rows')}",
        f"- Snapshot Signature: {sample.get('snapshot_signature', '')}",
        "",
        "## Row IDs Hash",
        f"- {sample.get('row_ids_hash', '')}",
        "",
        "## Stratum Distribution",
        "| Stratum | Count |",
        "|---|---:|",
    ]
    for stratum in STRATA:
        lines.append(f"| {stratum} | {sample.get('stratum_distribution', {}).get(stratum, 0)} |")
    write_text(path, "\n".join(lines) + "\n")


def _write_drift_report(path: Path, summary: Dict[str, Any]) -> None:
    s = summary.get("summary", {})
    thresholds = summary.get("thresholds", {})
    drift_signature = summary.get("drift_signature", "")
    base_sig = summary.get("baseline_snapshot_signature", "")
    cur_sig = summary.get("current_snapshot_signature", "")

    lines = [
        "# Drift Report",
        "",
        f"- Baseline Name: {s.get('baseline_name')}",
        f"- Generated At: {now_iso()}",
        f"- Baseline Manifest: {summary.get('baseline_manifest')}",
        f"- Current Manifest: {summary.get('current_manifest')}",
        "- Drift Numeric Report:",
        f"  - baseline_snapshot_signature: `{base_sig}`",
        f"  - current_snapshot_signature: `{cur_sig}`",
        f"  - drift_signature: `{drift_signature}`",
        f"- Row Churn Ratio: {s.get('row_churn_ratio', 0):.4f}",
        f"- Overlap Ratio: {s.get('overlap_ratio', 0):.4f}",
        f"- Added Rows: {s.get('added_count', 0)}",
        f"- Removed Rows: {s.get('removed_count', 0)}",
        f"- Changed Count: {s.get('changed_count', 0)}",
        f"- Max Stratum Delta: {s.get('max_stratum_delta', 0)}",
        f"- Threshold Failures: {'; '.join(summary.get('threshold_failures', [])) or 'none'}",
        "",
        "## Thresholds",
        f"- max_row_churn_ratio: {thresholds.get('max_row_churn_ratio')}",
        f"- max_stratum_delta: {thresholds.get('max_stratum_delta')}",
        f"- require_source_match: {thresholds.get('require_source_match')}",
        f"- require_sample_checksum_match: {thresholds.get('require_sample_checksum_match')}",
        "",
        "## Source SHA Status",
        f"- baseline: {s.get('source_sha_changed', False)}",
        f"- sample: {s.get('sample_sha_changed', False)}",
        "",
        "## Stratum Delta",
        "| Stratum | Baseline | Current | Delta |",
        "|---|---:|---:|---:|",
    ]
    for stratum in STRATA:
        entry = summary.get("stratum_deltas", {}).get(stratum, {})
        lines.append(
            f"| {stratum} | {entry.get('baseline', 0)} | {entry.get('current', 0)} | {entry.get('delta', 0)} |"
        )
    write_text(path, "\n".join(lines) + "\n")


def load_or_generate_sample(
    *,
    source: Path,
    sample_csv: Path | None,
    rows: int,
    seed: int,
    working_dir: Path,
    force: bool,
) -> Tuple[Path, Path, Dict[str, int], List[str], List[str], List[str]]:
    input_columns = load_source_columns(str(source))

    if sample_csv:
        sample_csv = sample_csv.resolve()
        if not sample_csv.exists():
            raise FileNotFoundError(f"Sample CSV not found: {sample_csv}")

        if sample_csv.suffix.lower() != ".csv":
            raise ValueError(f"Expected a CSV path for --sample-csv: {sample_csv}")

        meta_path = sample_csv.with_suffix(".meta.json")
        _, stratum_distribution = load_rows_with_strata(sample_csv)
        return sample_csv, meta_path, stratum_distribution, input_columns, [str(col) for col in load_source_columns(str(source))], row_ids_from_csv(sample_csv)

    source_rows = load_source_data(str(source))
    selected, stratum_counts = stratified_sample(source_rows, rows, seed)
    sample_csv = working_dir / f"validation_{rows}_baseline.csv"
    meta_path = working_dir / f"validation_{rows}_baseline.meta.json"

    if (sample_csv.exists() or meta_path.exists()) and not force:
        raise FileExistsError(
            f"Baseline sample already exists in {working_dir}. Use --force to overwrite."
        )

    write_csv(selected, str(sample_csv), fieldnames=input_columns)
    write_meta(
        str(sample_csv),
        stratum_counts,
        seed,
        str(source),
        rows,
        str(meta_path),
        input_columns=input_columns,
        output_columns=input_columns,
    )
    return sample_csv, meta_path, stratum_counts, input_columns, [str(col) for col in load_source_columns(str(source))], row_ids_from_csv(sample_csv)


def build_baseline_manifest(
    *,
    baseline_name: str,
    source: Path,
    sample_path: Path,
    meta_path: Path,
    rows: int,
    seed: int,
    stratum_distribution: Dict[str, int],
    input_columns: Sequence[str],
    output_columns: Sequence[str],
    row_ids: Sequence[str],
) -> Dict[str, Any]:
    sample_sha = calculate_sha256(str(sample_path))
    source_sha = calculate_sha256(str(source))
    signature = build_snapshot_signature(
        source=source,
        source_sha256=source_sha,
        sample_sha256=sample_sha,
        seed=seed,
        target_rows=rows,
        row_ids=row_ids,
        stratum_distribution=stratum_distribution,
        input_columns=input_columns,
        output_columns=output_columns,
    )

    return {
        "manifest_version": MANIFEST_VERSION,
        "baseline_name": baseline_name,
        "created_at": now_iso(),
        "baseline_data_path": str(source.resolve()),
        "sample_limit": int(rows),
        "source": {
            "path": str(source.resolve()),
            "sha256": source_sha,
        },
        "sample": {
            "path": str(sample_path.resolve()),
            "meta_path": str(meta_path.resolve()),
            "sha256": sample_sha,
            "rows": len(row_ids),
            "target_rows": rows,
            "seed": int(seed),
            "row_ids_hash": hash_row_ids(row_ids),
            "row_ids": [str(x) for x in row_ids],
            "input_columns": [str(x) for x in input_columns],
            "output_columns": [str(x) for x in output_columns],
            "stratum_distribution": {
                stratum: int(stratum_distribution.get(stratum, 0)) for stratum in STRATA
            },
            "snapshot_signature": signature,
        },
        "evidence": {
            "baseline_manifest_ready": True,
            "sample_ready": True,
            "snapshot_signature": signature,
        },
    }


def build_current_manifest(
    *,
    baseline_manifest_path: Path,
    source: Path,
    sample_path: Path,
    meta_path: Path,
    rows: int,
    seed: int,
    stratum_distribution: Dict[str, int],
    input_columns: Sequence[str],
    output_columns: Sequence[str],
    row_ids: Sequence[str],
) -> Dict[str, Any]:
    sample_sha = calculate_sha256(str(sample_path))
    source_sha = calculate_sha256(str(source))
    signature = build_snapshot_signature(
        source=source,
        source_sha256=source_sha,
        sample_sha256=sample_sha,
        seed=seed,
        target_rows=rows,
        row_ids=row_ids,
        stratum_distribution=stratum_distribution,
        input_columns=input_columns,
        output_columns=output_columns,
    )
    return {
        "manifest_version": MANIFEST_VERSION,
        "baseline_manifest": str(baseline_manifest_path),
        "created_at": now_iso(),
        "baseline_data_path": str(source.resolve()),
        "sample_limit": int(rows),
        "source": {
            "path": str(source.resolve()),
            "sha256": source_sha,
        },
        "sample": {
            "path": str(sample_path.resolve()),
            "meta_path": str(meta_path.resolve()),
            "sha256": sample_sha,
            "rows": len(row_ids),
            "target_rows": rows,
            "seed": int(seed),
            "row_ids_hash": hash_row_ids(row_ids),
            "row_ids": [str(x) for x in row_ids],
            "input_columns": [str(x) for x in input_columns],
            "output_columns": [str(x) for x in output_columns],
            "stratum_distribution": {
                stratum: int(stratum_distribution.get(stratum, 0)) for stratum in STRATA
            },
            "snapshot_signature": signature,
        },
        "evidence": {
            "current_manifest_ready": True,
            "sample_ready": True,
            "snapshot_signature": signature,
        },
    }

def compare_manifest(
    baseline_manifest_path: Path,
    current_manifest: Dict[str, Any],
    baseline_name: str,
    *,
    max_row_churn_ratio: float,
    max_stratum_delta: int,
    require_source_match: bool,
    require_sample_checksum_match: bool,
) -> Dict[str, Any]:
    baseline_manifest = read_json(baseline_manifest_path)
    baseline_sample = baseline_manifest.get("sample", {})
    baseline_rows, baseline_strata, _, _ = _extract_manifest_ids(baseline_manifest)

    current_sample = current_manifest.get("sample", {})
    current_rows, current_strata, _, _ = _extract_manifest_ids(current_manifest)

    baseline_set = set(str(x) for x in baseline_rows)
    current_set = set(str(x) for x in current_rows)

    added = sorted(current_set - baseline_set)
    removed = sorted(baseline_set - current_set)
    common = sorted(current_set & baseline_set)

    changed_count = 0
    total_baseline = len(baseline_set)
    row_churn_ratio = ((len(added) + len(removed)) / total_baseline) if total_baseline else 1.0
    overlap_ratio = (len(common) / total_baseline) if total_baseline else 0.0

    stratum_deltas: Dict[str, Dict[str, int]] = {}
    max_delta = 0
    for stratum in STRATA:
        b = int(baseline_strata.get(stratum, 0))
        c = int(current_strata.get(stratum, 0))
        delta = c - b
        stratum_deltas[stratum] = {"baseline": b, "current": c, "delta": delta}
        max_delta = max(max_delta, abs(delta))

    baseline_snapshot_signature = baseline_sample.get("snapshot_signature", "")
    if not baseline_snapshot_signature:
        baseline_snapshot_signature = build_snapshot_signature(
            source=Path(baseline_manifest["source"]["path"]),
            source_sha256=baseline_manifest["source"]["sha256"],
            sample_sha256=baseline_sample.get("sha256", ""),
            seed=int(baseline_sample.get("seed", 0)),
            target_rows=int(baseline_sample.get("target_rows", 0)),
            row_ids=baseline_rows,
            stratum_distribution={stratum: int(baseline_strata.get(stratum, 0)) for stratum in STRATA},
            input_columns=baseline_sample.get("input_columns", []),
            output_columns=baseline_sample.get("output_columns", []),
        )

    current_snapshot_signature = current_sample.get("snapshot_signature", "")
    if not current_snapshot_signature:
        current_snapshot_signature = build_snapshot_signature(
            source=Path(current_manifest["source"]["path"]),
            source_sha256=current_manifest["source"]["sha256"],
            sample_sha256=current_sample.get("sha256", ""),
            seed=int(current_sample.get("seed", 0)),
            target_rows=int(current_sample.get("target_rows", 0)),
            row_ids=current_rows,
            stratum_distribution={stratum: int(current_strata.get(stratum, 0)) for stratum in STRATA},
            input_columns=current_sample.get("input_columns", []),
            output_columns=current_sample.get("output_columns", []),
        )

    drift_signature = build_drift_signature(added, removed)
    threshold_failures: List[str] = []

    source_sha_changed = baseline_manifest.get("source", {}).get("sha256") != current_manifest.get("source", {}).get("sha256")
    sample_sha_changed = baseline_sample.get("sha256") != current_sample.get("sha256")

    if require_source_match and source_sha_changed:
        threshold_failures.append(
            f"STEP1_DRIFT_SOURCE_SHA: baseline source changed ({baseline_manifest['source']['sha256']} -> {current_manifest['source']['sha256']})"
        )

    if require_sample_checksum_match and sample_sha_changed:
        threshold_failures.append(
            f"STEP1_DRIFT_SAMPLE_SHA: baseline sample changed ({baseline_sample.get('sha256')} -> {current_sample.get('sha256')})"
        )

    if row_churn_ratio > max_row_churn_ratio:
        threshold_failures.append(
            f"STEP1_DRIFT_ROW_CHURN: row_churn_ratio={row_churn_ratio:.6f} > {max_row_churn_ratio}"
        )

    if max_delta > max_stratum_delta:
        threshold_failures.append(
            f"STEP1_DRIFT_STRATUM: max_stratum_delta={max_delta} > {max_stratum_delta}"
        )

    if len(baseline_rows) != len(current_rows):
        threshold_failures.append(
            f"STEP1_DRIFT_ROW_COUNT: baseline_rows={len(baseline_rows)} current_rows={len(current_rows)}"
        )

    return {
        "manifest_version": MANIFEST_VERSION,
        "baseline_manifest": str(baseline_manifest_path),
        "current_manifest": str(Path(current_manifest["sample"]["meta_path"]).with_name("current_manifest.json")),
        "baseline_data_path": str(Path(baseline_manifest.get("source", {}).get("path", "")).resolve()),
        "sample_limit": int(current_sample.get("target_rows", 0)),
        "summary": {
            "baseline_rows": len(baseline_rows),
            "current_rows": len(current_rows),
            "baseline_name": baseline_name,
            "added": added,
            "removed": removed,
            "common": common,
            "added_count": len(added),
            "removed_count": len(removed),
            "changed_count": changed_count,
            "row_churn_ratio": row_churn_ratio,
            "overlap_ratio": overlap_ratio,
            "source_sha_changed": source_sha_changed,
            "sample_sha_changed": sample_sha_changed,
            "baseline_sample_sha256": baseline_sample.get("sha256"),
            "current_sample_sha256": current_sample.get("sha256"),
            "max_stratum_delta": max_delta,
            "baseline_snapshot_signature": baseline_snapshot_signature,
            "current_snapshot_signature": current_snapshot_signature,
            "drift_signature": drift_signature,
        },
        "stratum_deltas": stratum_deltas,
        "thresholds": {
            "max_row_churn_ratio": max_row_churn_ratio,
            "max_stratum_delta": max_stratum_delta,
            "require_source_match": bool(require_source_match),
            "require_sample_checksum_match": bool(require_sample_checksum_match),
        },
        "threshold_failures": threshold_failures,
        "drift_signature": drift_signature,
        "baseline_snapshot_signature": baseline_snapshot_signature,
        "current_snapshot_signature": current_snapshot_signature,
        "evidence": {
            "drift_report_ready": True,
            "current_manifest_ready": True,
            "threshold_failures": list(threshold_failures),
            "gate_result": "pass" if not threshold_failures else "fail",
        },
    }


def _write_diff_rows_csv(path: Path, added: Sequence[str], removed: Sequence[str]) -> None:
    ensure_parent(path)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["string_id", "diff_type"])
        for sid in added:
            writer.writerow([sid, "added"])
        for sid in removed:
            writer.writerow([sid, "removed"])


def write_run_issue(
    report_path: Path,
    *,
    run_id: str,
    run_scope: str,
    status: str,
    blockers: Sequence[str],
    metrics: Dict[str, Any],
    completed_checks: Sequence[str] | None = None,
    pending_checks: Sequence[str] | None = None,
) -> None:
    completed_checks = list(completed_checks or [])
    pending_checks = list(pending_checks or [])
    lines = [
        f"# run_issue_{run_id}",
        "",
        f"- run_id: {run_id}",
        f"- run_scope: {run_scope}",
        f"- severity_summary: {status}",
        f"- blockers: {list(blockers)}",
        "- completed_checks:",
    ]
    if completed_checks:
        for item in completed_checks:
            lines.append(f"  - {item}")
    else:
        lines.append("  - []")

    lines.extend([
        "- pending_checks:",
    ])
    if pending_checks:
        for item in pending_checks:
            lines.append(f"  - {item}")
    else:
        lines.append("  - []")

    lines.extend([
        "- run_d_metrics:",
        f"  - baseline_name: {metrics.get('baseline_name', '-')}",
        f"  - row_churn_ratio: {metrics.get('row_churn_ratio', '-')}",
        f"  - max_stratum_delta: {metrics.get('max_stratum_delta', '-')}",
        f"  - baseline_snapshot_signature: `{metrics.get('baseline_snapshot_signature', '')}`",
        f"  - current_snapshot_signature: `{metrics.get('current_snapshot_signature', '')}`",
        f"  - drift_signature: `{metrics.get('drift_signature', '')}`",
    ])
    if metrics.get("threshold_failures"):
        lines.extend(["- threshold_failures:"])
        for item in metrics["threshold_failures"]:
            lines.append(f"  - {item}")
    else:
        lines.append("- threshold_failures: []")

    lines.extend([
        f"- evidence_ready: {str(not bool(blockers)).lower()}",
        "- note: 基线与漂移控制闭环已按脚本流程落盘，run_manifest/run_issue/run_verify 已就绪。",
    ])
    write_text(report_path, "\n".join(lines) + "\n")


def write_run_verify(
    report_path: Path,
    *,
    run_id: str,
    run_scope: str,
    status: str,
    verify_cmds: Sequence[str],
) -> None:
    lines = [
        f"# run_verify_{run_id}",
        "",
        f"- run_id: {run_id}",
        f"- run_scope: {run_scope}",
        "- do_now:",
        f"  - [{'x' if status == 'pass' else ' '}] baseline_drift_control 流程执行完成",
        "- acceptance_criteria:",
        "  - baseline_manifest 与 drift 报告产出且可读",
        "  - 关键阈值失败项可追溯到 run_issue/run_manifest",
        f"- result: {status}",
        "- verification_cmds:",
    ]
    if verify_cmds:
        for cmd in verify_cmds:
            lines.append(f"  - `{cmd}`")
    else:
        lines.append("  - []")
    lines.append("- evidence_ready: true")
    write_text(report_path, "\n".join(lines) + "\n")

def write_run_record(
    args: argparse.Namespace,
    *,
    run_id: str,
    run_scope: str,
    status: str,
    blockers: Sequence[str],
    decision_refs: Sequence[str],
    artifacts: Sequence[Path],
    start_ts: str,
    finished_ts: str,
    input_manifest_path: Path,
    run_issue_path: Path,
    run_verify_path: Path,
) -> Tuple[Path, Path, Path, Path]:
    manifest_path, issue_default, verify_default, input_default = _run_record_paths(args, run_id)

    # keep caller-chosen concrete issue/verify filenames
    issue_path = run_issue_path
    verify_path = run_verify_path
    input_path = input_manifest_path
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "run_id": run_id,
        "run_scope": run_scope,
        "status": status,
        "started_at": start_ts,
        "finished_at": finished_ts,
        "owner": _owner(),
        "input_manifest": _relative_path(input_path),
        "issue_report_path": _relative_path(issue_path),
        "verify_report_path": _relative_path(verify_path),
        "artifacts": _sorted_artifacts(artifacts),
        "blockers": list(blockers),
        "decision_refs": list(decision_refs),
        "evidence_ready": not bool(blockers),
        "gate_result": "pass" if status == "pass" else "fail",
        "evidence": {
            "input_manifest_path": _relative_path(input_path),
            "issue_report_path": _relative_path(issue_path),
            "verify_report_path": _relative_path(verify_path),
            "artifact_count": len(_sorted_artifacts(artifacts)),
        },
        "next_step_owner": _owner(),
        "next_step_scope": _next_scope(run_id, run_scope),
    }
    write_json(manifest_path, manifest)
    return manifest_path, issue_path, verify_path, input_path


def execute_create_baseline(args: argparse.Namespace) -> int:
    started = now_iso()
    run_id = str(args.run_id)
    baseline_name = str(args.name or run_id)
    baseline_root = Path(args.output_dir).resolve() / normalize_name(baseline_name)
    source = resolve_input_source(args.source)

    sample_csv, meta_path, stratum_distribution, input_columns, output_columns, row_ids = load_or_generate_sample(
        source=source,
        sample_csv=None,
        rows=int(args.rows),
        seed=int(args.seed),
        working_dir=baseline_root,
        force=bool(args.force),
    )

    manifest = build_baseline_manifest(
        baseline_name=baseline_name,
        source=source,
        sample_path=sample_csv,
        meta_path=meta_path,
        rows=int(args.rows),
        seed=int(args.seed),
        stratum_distribution=stratum_distribution,
        input_columns=input_columns,
        output_columns=output_columns,
        row_ids=row_ids,
    )

    baseline_manifest_path = baseline_root / "baseline_manifest.json"
    baseline_report_path = baseline_root / "baseline_report.md"
    write_json(baseline_manifest_path, manifest)
    _write_baseline_report(baseline_report_path, manifest)

    status = "pass"
    run_scope = str(args.run_scope or PLC_PRESETS.get(run_id, {}).get("run_scope", DEFAULT_D_PREPARE_SCOPE))
    record_dir = _resolve_run_record_dir(args)
    issue_path = record_dir / f"run_issue_{normalize_name(run_id)}.md"
    verify_path = record_dir / f"run_verify_{normalize_name(run_id)}.md"
    input_path = record_dir / f"input_manifest_{normalize_name(run_id)}.json"

    write_json(
        input_path,
        {
            "manifest_version": MANIFEST_VERSION,
            "run_id": run_id,
            "run_scope": run_scope,
            "command": "create-baseline",
            "generated_at": now_iso(),
            "args": _normalized_run_args(args),
            "baseline_data_path": str(source),
            "sample_limit": int(args.rows),
            "evidence_contract": {
                "requires_run_manifest": True,
                "requires_run_issue": True,
                "requires_run_verify": True,
            },
        },
    )

    write_run_issue(
        issue_path,
        run_id=run_id,
        run_scope=run_scope,
        status=status,
        blockers=[],
        metrics={
            "baseline_name": baseline_name,
            "baseline_snapshot_signature": manifest["sample"]["snapshot_signature"],
        },
        completed_checks=[
            f"D0 建立 baseline 基线快照 `{baseline_name}`",
            "D1 生成 baseline_manifest.json 与 baseline_report.md",
            f"D2 采样文件: {sample_csv}",
        ],
    )

    write_run_verify(
        verify_path,
        run_id=run_id,
        run_scope=run_scope,
        status=status,
        verify_cmds=[
            f"python scripts/baseline_drift_control.py create-baseline --name {baseline_name} --source {source} --rows {args.rows} --seed {args.seed}",
            f"python scripts/baseline_drift_control.py compare --baseline-manifest {baseline_manifest_path} --source {source} --rows {args.rows} --seed {args.seed}",
        ],
    )

    manifest_path, _, _, _ = write_run_record(
        args,
        run_id=run_id,
        run_scope=run_scope,
        status=status,
        blockers=[],
        decision_refs=_build_decision_refs(
            run_id=run_id,
            run_scope=run_scope,
            blockers=[],
            metrics={
                "baseline_snapshot_signature": manifest["sample"]["snapshot_signature"],
            },
        ),
        artifacts=[
            Path("scripts/baseline_drift_control.py"),
            baseline_manifest_path,
            baseline_report_path,
            sample_csv,
            meta_path,
        ],
        start_ts=started,
        finished_ts=now_iso(),
        input_manifest_path=input_path,
        run_issue_path=issue_path,
        run_verify_path=verify_path,
    )

    print(f"Prepared baseline: {baseline_manifest_path}")
    print(f"Run manifest: {manifest_path}")
    return 0


def execute_compare(args: argparse.Namespace) -> int:
    started = now_iso()
    run_id = str(args.run_id)
    baseline_manifest_path = _resolve_manifest_path(args.baseline_manifest)
    baseline_manifest = read_json(baseline_manifest_path)
    baseline_name = str(args.name or baseline_manifest.get("baseline_name", "baseline"))
    source = resolve_input_source(args.source)

    if args.output_dir:
        output_dir = Path(args.output_dir).resolve()
    else:
        output_dir = baseline_manifest_path.parent / "compare"
    output_dir.mkdir(parents=True, exist_ok=True)

    sample_csv, meta_path, stratum_distribution, input_columns, output_columns, row_ids = load_or_generate_sample(
        source=source,
        sample_csv=Path(args.sample_csv).resolve() if args.sample_csv else None,
        rows=int(args.rows),
        seed=int(args.seed),
        working_dir=output_dir,
        force=bool(args.force),
    )

    current_manifest = build_current_manifest(
        baseline_manifest_path=baseline_manifest_path,
        source=source,
        sample_path=sample_csv,
        meta_path=meta_path,
        rows=int(args.rows),
        seed=int(args.seed),
        stratum_distribution=stratum_distribution,
        input_columns=input_columns,
        output_columns=output_columns,
        row_ids=row_ids,
    )

    current_manifest_path = output_dir / "current_manifest.json"
    write_json(current_manifest_path, current_manifest)

    drift_summary = compare_manifest(
        baseline_manifest_path,
        current_manifest,
        baseline_name,
        max_row_churn_ratio=float(args.max_row_churn_ratio),
        max_stratum_delta=int(args.max_stratum_delta),
        require_source_match=bool(args.require_source_match),
        require_sample_checksum_match=bool(args.require_sample_checksum_match),
    )

    drift_summary_path = output_dir / "drift_summary.json"
    drift_report_path = output_dir / "drift_report.md"
    drift_diff_path = output_dir / "drift_diff_rows.csv"
    write_json(drift_summary_path, drift_summary)
    _write_drift_report(drift_report_path, drift_summary)
    _write_diff_rows_csv(
        drift_diff_path,
        drift_summary["summary"].get("added", []),
        drift_summary["summary"].get("removed", []),
    )

    status = "pass" if not drift_summary.get("threshold_failures") else "fail"
    blockers: List[str] = list(drift_summary.get("threshold_failures", []))
    run_scope = str(args.run_scope or PLC_PRESETS.get(run_id, {}).get("run_scope", DEFAULT_D_COMPARE_SCOPE))
    record_dir = _resolve_run_record_dir(args)
    issue_path = record_dir / f"run_issue_{normalize_name(run_id)}.md"
    verify_path = record_dir / f"run_verify_{normalize_name(run_id)}.md"
    input_path = record_dir / f"input_manifest_{normalize_name(run_id)}.json"
    write_json(
        input_path,
        {
            "manifest_version": MANIFEST_VERSION,
            "run_id": run_id,
            "run_scope": run_scope,
            "command": "compare",
            "generated_at": now_iso(),
            "args": _normalized_run_args(args),
            "baseline_data_path": str(source),
            "sample_limit": int(args.rows),
            "evidence_contract": {
                "requires_run_manifest": True,
                "requires_run_issue": True,
                "requires_run_verify": True,
                "requires_drift_report": True,
            },
        },
    )

    completed = [
        f"比较当前样本与基线 `{baseline_name}`",
        "drift_summary 与 drift_report 已写入",
        "drift_diff_rows.csv 已产出",
    ]
    pending = [
        "D8 漂移阈值未达标需修正采样定义",
    ] if status != "pass" else []
    write_run_issue(
        issue_path,
        run_id=run_id,
        run_scope=run_scope,
        status=status,
        blockers=blockers,
        metrics=drift_summary["summary"],
        completed_checks=completed,
        pending_checks=pending,
    )

    write_run_verify(
        verify_path,
        run_id=run_id,
        run_scope=run_scope,
        status=status,
        verify_cmds=[
            f"python scripts/baseline_drift_control.py compare --baseline-manifest {baseline_manifest_path} --source {args.source} --rows {args.rows} --seed {args.seed} --max-row-churn-ratio {args.max_row_churn_ratio} --max-stratum-delta {args.max_stratum_delta}",
            f"cat {drift_summary_path}",
        ],
    )

    manifest_path, _, _, _ = write_run_record(
        args,
        run_id=run_id,
        run_scope=run_scope,
        status=status,
        blockers=blockers,
        decision_refs=_build_decision_refs(
            run_id=run_id,
            run_scope=run_scope,
            blockers=blockers,
            metrics=drift_summary["summary"],
        ),
        artifacts=[
            Path("scripts/baseline_drift_control.py"),
            baseline_manifest_path,
            current_manifest_path,
            drift_summary_path,
            drift_report_path,
            drift_diff_path,
        ],
        start_ts=started,
        finished_ts=now_iso(),
        input_manifest_path=input_path,
        run_issue_path=issue_path,
        run_verify_path=verify_path,
    )

    print(f"Compared against baseline: {baseline_manifest_path}")
    print(f"drift_signature: {drift_summary['summary'].get('drift_signature')}")
    print(f"Run manifest: {manifest_path}")
    print(f"status: {status}")
    return 0 if status == "pass" else 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Baseline drift control for milestone D."
    )
    parser.add_argument("--run-manifest-dir", default="", help="Directory for run record artifacts")
    parser.add_argument("--owner", default=_owner(), help="Run owner")

    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create-baseline", help="Build baseline snapshot")
    create.add_argument("--name", required=True, help="Baseline name and target directory name")
    create.add_argument("--source", default=DEFAULT_D_PREPARE_SOURCE)
    create.add_argument("--rows", type=int, default=DEFAULT_D_PREPARE_ROWS)
    create.add_argument("--seed", type=int, default=DEFAULT_D_PREPARE_SEED)
    create.add_argument("--output-dir", default="data/baselines")
    create.add_argument("--force", action="store_true")
    create.add_argument("--run-scope", default=DEFAULT_D_PREPARE_SCOPE)
    create.set_defaults(mode="create_baseline", run_id="plc_run_d_prepare")

    compare = sub.add_parser("compare", help="Compare baseline with current sample")
    compare.add_argument("--baseline-manifest", required=True)
    compare.add_argument("--source", default=DEFAULT_D_COMPARE_SOURCE)
    compare.add_argument("--name")
    compare.add_argument("--rows", type=int, default=DEFAULT_D_COMPARE_ROWS)
    compare.add_argument("--seed", type=int, default=DEFAULT_D_COMPARE_SEED)
    compare.add_argument("--max-row-churn-ratio", type=float, default=DEFAULT_D_COMPARE_MAX_ROW_CHURN_RATIO)
    compare.add_argument("--max-stratum-delta", type=int, default=DEFAULT_D_COMPARE_MAX_STRATUM_DELTA)
    compare.add_argument(
        "--require-source-match",
        dest="require_source_match",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_D_COMPARE_REQUIRE_SOURCE_MATCH,
    )
    compare.add_argument(
        "--require-sample-checksum-match",
        dest="require_sample_checksum_match",
        action=argparse.BooleanOptionalAction,
        default=DEFAULT_D_COMPARE_REQUIRE_SAMPLE_CHECKSUM_MATCH,
    )
    compare.add_argument("--sample-csv")
    compare.add_argument("--output-dir")
    compare.add_argument("--force", action="store_true")
    compare.add_argument("--run-scope", default=DEFAULT_D_COMPARE_SCOPE)
    compare.set_defaults(mode="compare", run_id="plc_run_d_full")

    for run_id, preset in PLC_PRESETS.items():
        if preset["mode"] == "create_baseline":
            p = sub.add_parser(run_id, help=f"PLC preset: {run_id}")
            p.add_argument("--name", default=preset.get("name"))
            p.add_argument("--source", default=preset.get("source", DEFAULT_D_PREPARE_SOURCE))
            p.add_argument("--rows", type=int, default=preset.get("rows", DEFAULT_D_PREPARE_ROWS))
            p.add_argument("--seed", type=int, default=preset.get("seed", DEFAULT_D_PREPARE_SEED))
            p.add_argument("--output-dir", default=preset.get("output_dir", "data/baselines"))
            p.add_argument("--force", action="store_true")
            p.add_argument("--run-scope", default=preset.get("run_scope", DEFAULT_D_PREPARE_SCOPE))
            p.set_defaults(mode="create_baseline", run_id=run_id)
            continue

        p = sub.add_parser(run_id, help=f"PLC preset: {run_id}")
        p.add_argument("--baseline-manifest", default=preset.get("baseline_manifest"))
        p.add_argument("--name")
        p.add_argument("--source", default=preset.get("source", DEFAULT_D_COMPARE_SOURCE))
        p.add_argument("--rows", type=int, default=preset.get("rows", DEFAULT_D_COMPARE_ROWS))
        p.add_argument("--seed", type=int, default=preset.get("seed", DEFAULT_D_COMPARE_SEED))
        p.add_argument("--max-row-churn-ratio", type=float, default=preset.get("max_row_churn_ratio", DEFAULT_D_COMPARE_MAX_ROW_CHURN_RATIO))
        p.add_argument("--max-stratum-delta", type=int, default=preset.get("max_stratum_delta", DEFAULT_D_COMPARE_MAX_STRATUM_DELTA))
        p.add_argument(
            "--require-source-match",
            dest="require_source_match",
            action=argparse.BooleanOptionalAction,
            default=preset.get("require_source_match", DEFAULT_D_COMPARE_REQUIRE_SOURCE_MATCH),
        )
        p.add_argument(
            "--require-sample-checksum-match",
            dest="require_sample_checksum_match",
            action=argparse.BooleanOptionalAction,
            default=preset.get("require_sample_checksum_match", DEFAULT_D_COMPARE_REQUIRE_SAMPLE_CHECKSUM_MATCH),
        )
        p.add_argument("--sample-csv")
        p.add_argument("--output-dir", default=preset.get("output_dir"))
        p.add_argument("--force", action="store_true")
        p.add_argument("--run-scope", default=preset.get("run_scope", DEFAULT_D_COMPARE_SCOPE))
        p.set_defaults(mode="compare", run_id=run_id)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    if args.mode == "create_baseline":
        return execute_create_baseline(args)
    if args.mode == "compare":
        return execute_compare(args)
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
