#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None


REPO_ROOT = Path(__file__).resolve().parent.parent


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_yaml_dict(path: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if yaml is None:
        return dict(default or {})
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = REPO_ROOT / file_path
    if not file_path.exists():
        return dict(default or {})
    try:
        loaded = yaml.safe_load(file_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return dict(default or {})
    return loaded if isinstance(loaded, dict) else dict(default or {})


def load_review_ticket_contract() -> Dict[str, Any]:
    return _load_yaml_dict("workflow/review_ticket_contract.yaml", {})


def load_feedback_log_contract() -> Dict[str, Any]:
    return _load_yaml_dict("workflow/feedback_log_contract.yaml", {})


def load_lifecycle_registry(path: str = "workflow/lifecycle_registry.yaml") -> Dict[str, Any]:
    return _load_yaml_dict(path, {"version": "1.0", "entries": []})


def read_json(path: str) -> Dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    return json.loads(file_path.read_text(encoding="utf-8"))


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            text = line.strip()
            if not text:
                continue
            payload = json.loads(text)
            if not isinstance(payload, dict):
                raise ValueError(f"Expected object at {path}:{line_no}")
            rows.append(payload)
    return rows


def write_json(path: str, payload: Dict[str, Any]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: str, rows: Iterable[Dict[str, Any]]) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def ensure_feedback_log(path: str) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if not file_path.exists():
        file_path.write_text("", encoding="utf-8")


def load_feedback_log(path: str) -> List[Dict[str, Any]]:
    ensure_feedback_log(path)
    return read_jsonl(path)


def _parse_reason_codes(raw: Any) -> List[str]:
    if isinstance(raw, list):
        return [str(item) for item in raw if str(item)]
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return [text]
    if isinstance(parsed, list):
        return [str(item) for item in parsed if str(item)]
    return [text]


def _priority_from_task(task: Dict[str, Any], row: Dict[str, Any]) -> str:
    risk_level = str(task.get("risk_level") or task.get("target_constraints", {}).get("risk_level") or "").lower()
    review_source = str(row.get("review_source") or "")
    if review_source in {"post_gate_blocked", "execution_failure"}:
        return "P0"
    if risk_level == "high":
        return "P1"
    return "P2"


def _normalize_review_status(value: Any) -> str:
    text = str(value or "").strip()
    if text in {"pending", "acknowledged", "in_review", "approved", "rejected", "superseded", "closed"}:
        return text
    if text in {"not_required", "review_handoff", "blocked", "failed", "updated", "skip", ""}:
        return "pending"
    return "pending"


def _ticket_string_id(row: Dict[str, Any], task: Dict[str, Any], index: int) -> str:
    string_id = str(row.get("string_id") or task.get("string_id") or "").strip()
    if string_id:
        return string_id
    review_source = str(row.get("review_source") or "manual_review").strip() or "manual_review"
    return f"system:{review_source}:{index}"


def _ticket_current_target(row: Dict[str, Any], task: Dict[str, Any]) -> str:
    current_target = str(row.get("current_target") or task.get("current_target") or "").strip()
    return current_target or "<none>"


def _ticket_content_class(task: Dict[str, Any]) -> str:
    return str(task.get("content_class") or task.get("target_constraints", {}).get("content_class") or "review_handoff")


def _ticket_risk_level(task: Dict[str, Any], row: Dict[str, Any]) -> str:
    review_source = str(row.get("review_source") or "")
    default_risk = "review"
    if review_source in {"post_gate_blocked", "execution_failure"}:
        default_risk = "high"
    return str(task.get("risk_level") or task.get("target_constraints", {}).get("risk_level") or default_risk)


def _review_ticket_missing(field: str, value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value == ""
    if field == "reason_codes" and isinstance(value, list):
        return False
    return value == []


def build_review_tickets(
    review_queue_rows: List[Dict[str, Any]],
    *,
    task_lookup: Optional[Dict[str, Dict[str, Any]]] = None,
    source_artifacts: Optional[Dict[str, str]] = None,
    default_locale: str = "ru-RU",
) -> List[Dict[str, Any]]:
    source_artifacts = source_artifacts or {}
    task_lookup = task_lookup or {}
    tickets: List[Dict[str, Any]] = []
    for index, row in enumerate(review_queue_rows, start=1):
        task = task_lookup.get(str(row.get("task_id") or ""), {})
        string_id = _ticket_string_id(row, task, index)
        review_source = str(row.get("review_source") or "manual_review")
        ticket = {
            "ticket_id": f"ticket:{row.get('task_id') or string_id}:{review_source or 'manual'}",
            "task_id": str(row.get("task_id") or ""),
            "string_id": string_id,
            "target_locale": str(task.get("target_locale") or default_locale),
            "ticket_type": "execution_failure" if review_source == "execution_failure" else (
                "gate_blocked" if review_source == "post_gate_blocked" else "manual_review"
            ),
            "priority": _priority_from_task(task, row),
            "review_owner": str(row.get("review_owner") or "human-linguist"),
            "review_status": _normalize_review_status(row.get("review_status")),
            "review_source": review_source,
            "queue_reason": str(row.get("queue_reason") or ""),
            "current_target": _ticket_current_target(row, task),
            "reason_codes": _parse_reason_codes(row.get("reason_codes")),
            "content_class": _ticket_content_class(task),
            "risk_level": _ticket_risk_level(task, row),
            "created_at": now_iso(),
            "source_artifacts": source_artifacts,
        }
        tickets.append(ticket)
    validate_review_tickets(tickets)
    return tickets


def validate_review_tickets(tickets: List[Dict[str, Any]]) -> None:
    contract = load_review_ticket_contract()
    required_fields = contract.get("required_fields", []) or []
    ticket_type_enum = set(contract.get("ticket_type_enum", []) or [])
    priority_enum = set(contract.get("priority_enum", []) or [])
    review_status_enum = set(contract.get("review_status_enum", []) or [])
    for ticket in tickets:
        missing = [field for field in required_fields if _review_ticket_missing(field, ticket.get(field))]
        if missing:
            raise ValueError(f"Review ticket missing required field(s): {', '.join(missing)}")
        if ticket_type_enum and ticket["ticket_type"] not in ticket_type_enum:
            raise ValueError(f"Unsupported review ticket type: {ticket['ticket_type']}")
        if priority_enum and ticket["priority"] not in priority_enum:
            raise ValueError(f"Unsupported review ticket priority: {ticket['priority']}")
        if review_status_enum and ticket["review_status"] not in review_status_enum:
            raise ValueError(f"Unsupported review ticket status: {ticket['review_status']}")


def append_feedback_entries(path: str, entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    existing = load_feedback_log(path)
    contract = load_feedback_log_contract()
    required_fields = contract.get("required_fields", []) or []
    decision_enum = set(contract.get("decision_enum", []) or [])
    normalized: List[Dict[str, Any]] = []
    for entry in entries:
        payload = dict(entry)
        payload.setdefault("feedback_id", f"feedback:{payload.get('ticket_id') or payload.get('string_id') or 'unknown'}:{len(existing) + len(normalized) + 1}")
        payload.setdefault("created_at", now_iso())
        missing = [field for field in required_fields if payload.get(field) in (None, "", [])]
        if missing:
            raise ValueError(f"Feedback entry missing required field(s): {', '.join(missing)}")
        if decision_enum and str(payload.get("decision") or "") not in decision_enum:
            raise ValueError(f"Unsupported feedback decision: {payload.get('decision')}")
        normalized.append(payload)
    write_jsonl(path, [*existing, *normalized])
    return normalized


def build_kpi_report(
    *,
    scope: str,
    manifest: Dict[str, Any],
    review_tickets: List[Dict[str, Any]],
    feedback_logs: List[Dict[str, Any]],
    runtime_governance: Optional[Dict[str, Any]] = None,
    lifecycle_registry: Optional[Dict[str, Any]] = None,
    metrics_payload: Optional[Dict[str, Any]] = None,
    extra_sources: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    runtime_governance = runtime_governance or {}
    lifecycle_registry = lifecycle_registry or {"entries": []}
    metrics_payload = metrics_payload or {}
    extra_sources = extra_sources or {}

    execution = manifest.get("execution", {}) or {}
    task_outcomes = manifest.get("task_outcomes", {}) or {}
    total_tasks = sum(int(value) for value in (task_outcomes.get("counts_by_execution_status", {}) or {}).values())
    if not total_tasks:
        total_tasks = int(execution.get("updated", 0)) + int(execution.get("review_handoff", 0)) + int(execution.get("blocked", 0))

    pending_statuses = {"pending", "acknowledged", "in_review"}
    pending_review_tickets = sum(1 for ticket in review_tickets if str(ticket.get("review_status") or "") in pending_statuses)
    feedback_entries = len(feedback_logs)
    feedback_closure_rate = round(feedback_entries / len(review_tickets), 4) if review_tickets else 0.0
    manual_intervention_rate = round(len(review_tickets) / total_tasks, 4) if total_tasks else 0.0

    by_source: Dict[str, int] = {}
    by_locale: Dict[str, int] = {}
    for ticket in review_tickets:
        source = str(ticket.get("review_source") or "unknown")
        locale = str(ticket.get("target_locale") or "unknown")
        by_source[source] = by_source.get(source, 0) + 1
        by_locale[locale] = by_locale.get(locale, 0) + 1

    deprecated_asset_usage_count = sum(
        1
        for asset in (runtime_governance.get("asset_statuses", {}) or {}).values()
        if str(asset.get("status") or "") in {"deprecated", "superseded"}
    )

    return {
        "generated_at": now_iso(),
        "scope": scope,
        "runtime_summary": {
            "overall_status": str(manifest.get("overall_status") or manifest.get("status") or ""),
            "total_tasks": total_tasks,
            "updated_count": int(execution.get("updated", 0)),
            "review_handoff_count": len(review_tickets),
        },
        "review_summary": {
            "total_review_tickets": len(review_tickets),
            "pending_review_tickets": pending_review_tickets,
            "manual_intervention_rate": manual_intervention_rate,
            "feedback_entries": feedback_entries,
            "feedback_closure_rate": feedback_closure_rate,
            "by_source": by_source,
            "by_locale": by_locale,
        },
        "lifecycle_summary": {
            "registry_path": extra_sources.get("lifecycle_registry_path") or "",
            "checked_assets": runtime_governance.get("asset_statuses", {}),
            "deprecated_asset_usage_count": deprecated_asset_usage_count,
        },
        "metrics_sources": {
            "metrics_summary": metrics_payload.get("summary", {}),
            "extra_sources": extra_sources,
        },
        "trend_signals": {
            "review_queue_growth": len(review_tickets),
            "feedback_closure_gap": max(len(review_tickets) - feedback_entries, 0),
        },
        "ticket_counts": {
            "total": len(review_tickets),
            "pending": pending_review_tickets,
        },
        "feedback_counts": {
            "total": feedback_entries,
            "closed": feedback_entries,
        },
        "intervention_rate": {
            "ticket_count": len(review_tickets),
            "review_queue_count": len(review_tickets),
        },
        "review_backlog": {
            "pending_tickets": pending_review_tickets,
            "pending_review_queue_rows": len(review_tickets),
        },
    }
