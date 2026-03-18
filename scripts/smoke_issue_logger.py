#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke issue logging helpers (JSON + JSONL)."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Union


def _to_payload_hash(payload: Optional[Any]) -> str:
    if payload is None:
        return ""
    try:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    except Exception:
        raw = repr(payload).encode("utf-8", errors="replace")
    return hashlib.sha1(raw).hexdigest()


def build_issue(
    run_id: str,
    stage: str,
    severity: str = "P2",
    model: str = "",
    error_code: str = "",
    trace_id: str = "",
    file: str = "",
    row: Union[str, int, None] = None,
    string_id: str = "",
    context: Optional[Dict[str, Any]] = None,
    suggest: str = "",
    payload: Optional[Any] = None
) -> Dict[str, Any]:
    """Build a normalized issue record."""
    safe_row: Union[str, int, None] = row
    if row is not None and isinstance(row, str) and str(row).strip().isdigit():
        try:
            safe_row = int(row)
        except ValueError:
            safe_row = row

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "stage": stage,
        "severity": severity,
        "model": model,
        "error_code": error_code,
        "trace_id": trace_id,
        "file": file,
        "row": safe_row,
        "string_id": string_id,
        "payload_hash": _to_payload_hash(payload),
        "context": context or {},
        "suggest": suggest,
        # Backward compatible key kept for existing consumers/tests.
        "suggestion": suggest,
    }


def append_issue(report_path: str, issue: Dict[str, Any]) -> None:
    """Append one issue to JSON report + JSONL trace."""
    report_path_obj = Path(report_path)
    report_path_obj.parent.mkdir(parents=True, exist_ok=True)

    # Load existing JSON report
    if report_path_obj.exists():
        try:
            with open(report_path_obj, "r", encoding="utf-8") as f:
                report = json.load(f)
        except Exception:
            report = {}
    else:
        report = {}

    if not isinstance(report, dict):
        report = {}

    if "issues" not in report or not isinstance(report["issues"], list):
        report["issues"] = []

    if "run_id" not in report and "run_id" in issue:
        report["run_id"] = issue["run_id"]

    report["updated_at"] = datetime.now(timezone.utc).isoformat()
    report["issues"].append(issue)

    with open(report_path_obj, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    jsonl_path = report_path_obj.with_suffix(report_path_obj.suffix + ".jsonl")
    with open(jsonl_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(issue, ensure_ascii=False) + os.linesep)
