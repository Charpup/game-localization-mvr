#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

from review_governance import (
    append_feedback_entries,
    build_kpi_report as build_kpi_report_v2,
    build_review_tickets as build_review_tickets_v2,
    load_feedback_log,
    load_lifecycle_registry as load_lifecycle_registry_v2,
    load_review_ticket_contract,
    write_json,
    write_jsonl,
)
from style_governance_runtime import (
    evaluate_runtime_governance,
    format_runtime_governance_issues,
)


REPO_ROOT = Path(__file__).resolve().parent.parent


class GovernanceError(RuntimeError):
    pass


def _load_yaml_dict(path: str) -> Dict[str, Any]:
    if yaml is None:
        return {}
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = REPO_ROOT / file_path
    if not file_path.exists():
        return {}
    payload = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _repo_relative(path: str) -> str:
    raw = Path(path)
    resolved = raw if raw.is_absolute() else (REPO_ROOT / raw).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _is_repo_managed(path: str) -> bool:
    raw = Path(path)
    resolved = raw if raw.is_absolute() else (REPO_ROOT / raw).resolve()
    try:
        resolved.relative_to(REPO_ROOT)
        return True
    except ValueError:
        return False


def _find_lifecycle_entry(asset_path: str, lifecycle_registry_path: str) -> Dict[str, Any]:
    registry = load_lifecycle_registry(lifecycle_registry_path)
    normalized = _repo_relative(asset_path)
    for entry in registry.get("entries", []) or []:
        if not isinstance(entry, dict):
            continue
        entry_path = _repo_relative(str(entry.get("asset_path") or ""))
        if entry_path == normalized:
            payload = dict(entry)
            if "asset_type" not in payload and payload.get("asset_kind"):
                payload["asset_type"] = payload["asset_kind"]
            if "path" not in payload and payload.get("asset_path"):
                payload["path"] = payload["asset_path"]
            return payload
    return {}


def load_style_profile(path: str) -> Dict[str, Any]:
    return _load_yaml_dict(path)


def load_lifecycle_registry(path: str = "workflow/lifecycle_registry.yaml") -> Dict[str, Any]:
    return load_lifecycle_registry_v2(path)


def validate_style_governance_runtime(
    style_profile_path: str,
    *,
    lifecycle_registry_path: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    profile = load_style_profile(style_profile_path)
    if not profile:
        raise GovernanceError(f"style profile missing or invalid: {style_profile_path}")
    effective_registry_path = lifecycle_registry_path or "workflow/lifecycle_registry.yaml"
    report = evaluate_runtime_governance(
        style_profile_path=style_profile_path,
        lifecycle_registry_path=effective_registry_path,
        policy_paths=["workflow/style_governance_contract.yaml"],
    )
    if not report.get("passed"):
        raise GovernanceError(format_runtime_governance_issues(report))
    lifecycle_entry = _find_lifecycle_entry(style_profile_path, effective_registry_path)
    if lifecycle_registry_path and not lifecycle_entry:
        raise GovernanceError(f"missing lifecycle entry for {_repo_relative(style_profile_path)}")
    return profile, lifecycle_entry


def validate_governed_asset(asset_path: str, asset_type: str, *, lifecycle_registry_path: Optional[str] = None) -> Dict[str, Any]:
    asset = Path(asset_path)
    if not asset.exists():
        raise GovernanceError(f"missing governed asset: {asset_path}")
    effective_registry_path = lifecycle_registry_path or "workflow/lifecycle_registry.yaml"
    entry = _find_lifecycle_entry(asset_path, effective_registry_path)
    if not entry:
        if _is_repo_managed(asset_path):
            raise GovernanceError(f"missing lifecycle registry entry for {_repo_relative(asset_path)}")
        if asset.is_absolute():
            return {}
        return {}
    expected_type = "policy" if asset_type in {"policy", "rubric"} else asset_type
    actual_type = str(entry.get("asset_type") or entry.get("asset_kind") or "")
    if actual_type != expected_type:
        raise GovernanceError(
            f"lifecycle asset type mismatch for {_repo_relative(asset_path)}: expected {expected_type}, got {actual_type}"
        )
    if str(entry.get("status") or "") != "approved":
        raise GovernanceError(f"governed asset is not approved: {_repo_relative(asset_path)}")
    return entry


def _review_ticket_fieldnames(tickets: List[Dict[str, Any]]) -> List[str]:
    required = list(load_review_ticket_contract().get("required_fields", []) or [])
    extras: List[str] = []
    for ticket in tickets:
        for key in ticket.keys():
            if key not in required and key not in extras:
                extras.append(key)
    return [*required, *extras]


def write_review_tickets(jsonl_path: str, csv_path: str, tickets: List[Dict[str, Any]]) -> None:
    write_jsonl(jsonl_path, tickets)
    fieldnames = _review_ticket_fieldnames(tickets)
    rows: List[Dict[str, str]] = []
    for ticket in tickets:
        row: Dict[str, str] = {}
        for field in fieldnames:
            value = ticket.get(field)
            if isinstance(value, (list, dict)):
                row[field] = json.dumps(value, ensure_ascii=False)
            else:
                row[field] = "" if value is None else str(value)
        rows.append(row)
    target = Path(csv_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def build_review_tickets(tasks: List[Dict[str, Any]], review_queue: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    task_lookup = {str(task.get("task_id") or ""): task for task in tasks}
    source_artifacts = dict(tasks[0].get("source_artifacts") or {}) if tasks else {}
    default_locale = str(tasks[0].get("target_locale") or "ru-RU") if tasks else "ru-RU"
    return build_review_tickets_v2(
        review_queue,
        task_lookup=task_lookup,
        source_artifacts=source_artifacts,
        default_locale=default_locale,
    )


def build_review_tickets_from_queue(
    review_queue: List[Dict[str, Any]],
    *,
    target_locale: str,
    source_artifacts: Dict[str, Any],
) -> List[Dict[str, Any]]:
    return build_review_tickets_v2(
        review_queue,
        task_lookup={},
        source_artifacts={str(key): str(value) for key, value in source_artifacts.items()},
        default_locale=target_locale,
    )


def append_feedback_log(
    *,
    input_path: str,
    output_path: str,
    feedback_source: str,
) -> List[Dict[str, Any]]:
    source = Path(input_path)
    rows: List[Dict[str, Any]] = []
    if source.suffix.lower() == ".csv":
        with source.open("r", encoding="utf-8-sig", newline="") as fh:
            rows = list(csv.DictReader(fh))
    else:
        with source.open("r", encoding="utf-8") as fh:
            for line_no, line in enumerate(fh, start=1):
                text = line.strip()
                if not text:
                    continue
                payload = json.loads(text)
                if not isinstance(payload, dict):
                    raise ValueError(f"Expected object at {input_path}:{line_no}")
                rows.append(payload)

    decision_map = {
        "accepted": "approve",
        "approve": "approve",
        "rejected": "reject",
        "reject": "reject",
        "revised": "request_retranslate",
        "request_retranslate": "request_retranslate",
        "request_refresh": "request_refresh",
        "ignore": "ignore",
        "supersede": "supersede",
    }
    entries: List[Dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        entries.append(
            {
                "feedback_id": f"feedback:{row.get('ticket_id') or row.get('task_id') or index}",
                "ticket_id": str(row.get("ticket_id") or row.get("task_id") or ""),
                "string_id": str(row.get("string_id") or ""),
                "target_locale": str(row.get("target_locale") or ""),
                "decision": decision_map.get(str(row.get("decision") or "").strip(), str(row.get("decision") or "ignore")),
                "reviewer": str(row.get("reviewer") or row.get("review_owner") or "human-linguist"),
                "notes": str(row.get("notes") or row.get("review_reason") or row.get("manual_review_reason") or ""),
                "updated_target": str(row.get("updated_target") or ""),
                "source_artifact": feedback_source,
            }
        )
    return append_feedback_entries(output_path, entries)


def build_kpi_report(
    *,
    run_id: str,
    target_locale: str,
    source_artifacts: Dict[str, Any],
    review_tickets: List[Dict[str, Any]],
    feedback_log: List[Dict[str, Any]],
    review_queue: List[Dict[str, Any]],
    lifecycle_registry_path: str = "workflow/lifecycle_registry.yaml",
) -> Dict[str, Any]:
    manifest = {
        "status": "review_handoff" if review_tickets else "pass",
        "execution": {
            "updated": 0,
            "review_handoff": len(review_tickets),
            "blocked": 0,
        },
        "task_outcomes": {
            "counts_by_execution_status": {
                "review_handoff": len(review_tickets),
            }
        },
    }
    return build_kpi_report_v2(
        scope="language_governance",
        manifest=manifest,
        review_tickets=review_tickets,
        feedback_logs=feedback_log,
        lifecycle_registry=load_lifecycle_registry(lifecycle_registry_path),
        extra_sources={
            "run_id": run_id,
            "target_locale": target_locale,
            "review_queue": source_artifacts.get("review_queue") or "",
            "lifecycle_registry_path": lifecycle_registry_path,
            **{str(key): value for key, value in source_artifacts.items()},
        },
        metrics_payload={"review_queue_count": len(review_queue)},
    )


__all__ = [
    "GovernanceError",
    "append_feedback_log",
    "build_kpi_report",
    "build_review_tickets",
    "build_review_tickets_from_queue",
    "load_feedback_log",
    "load_lifecycle_registry",
    "load_style_profile",
    "validate_governed_asset",
    "validate_style_governance_runtime",
    "write_json",
    "write_jsonl",
    "write_review_tickets",
]
