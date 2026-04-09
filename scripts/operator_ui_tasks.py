#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Human task workflow and delivery models for the operator UI."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from secrets import token_hex
from typing import Any, Dict, Iterable, List, Optional, Tuple

from scripts.operator_ui_models import (
    ArtifactRecord,
    RunDetail,
    WorkspaceCaseView,
    build_pending_run_detail,
    find_run_manifest,
    load_run_detail,
    load_workspace_cases,
)


TASK_STATUSES = {
    "draft",
    "queued",
    "running",
    "needs_user_action",
    "needs_operator_review",
    "ready_for_download",
    "failed",
}
TASK_ACTIONS = {
    "refresh_status",
    "open_monitor",
    "open_runtime",
    "view_deliveries",
    "rerun",
    "approve_delivery",
    "request_changes",
    "archive_task",
}
TASK_BUCKETS = {
    "all",
    "needs_your_action",
    "running",
    "waiting_on_ops",
    "ready_to_collect",
    "failed",
    "archived",
}
TASK_STATUS_ORDER = {
    "needs_user_action": 0,
    "needs_operator_review": 1,
    "failed": 2,
    "running": 3,
    "queued": 4,
    "ready_for_download": 5,
    "draft": 6,
}
TASK_BUCKET_ORDER = {
    "needs_your_action": 0,
    "running": 1,
    "waiting_on_ops": 2,
    "ready_to_collect": 3,
    "failed": 4,
    "archived": 5,
}
VISIBLE_DELIVERY_GROUPS = ["primary_output", "validation_report", "issue_summary", "supporting_files"]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _now().isoformat()


def _safe_filename(filename: str, fallback: str = "input.csv") -> str:
    clean = Path(filename or fallback).name.strip()
    return clean or fallback


def _task_store_root(repo_root: Path) -> Path:
    return repo_root / "data" / "operator_ui_tasks"


def _task_record_path(repo_root: Path, task_id: str) -> Path:
    return _task_store_root(repo_root) / task_id / "task.json"


def _upload_store_root(repo_root: Path) -> Path:
    return repo_root / "data" / "operator_ui_uploads"


def _upload_record_path(repo_root: Path, upload_id: str) -> Path:
    return _upload_store_root(repo_root) / upload_id / "upload.json"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def task_id_for_run(run_id: str) -> str:
    return f"task_{run_id}"


def generate_task_id(*, prefix: str = "task", now: Optional[datetime] = None, suffix: Optional[str] = None) -> str:
    stamp = (now or _now()).strftime("%Y%m%d_%H%M%S_%f")
    return f"{prefix}_{stamp}_{(suffix or token_hex(2)).strip().lower()}"


def generate_upload_id(*, now: Optional[datetime] = None, suffix: Optional[str] = None) -> str:
    return generate_task_id(prefix="upload", now=now, suffix=suffix)


def stage_task_upload(
    repo_root: Path | str,
    *,
    filename: str,
    content: bytes,
    upload_id: str = "",
    uploaded_at: str = "",
) -> Dict[str, Any]:
    repo_root_path = Path(repo_root)
    safe_name = _safe_filename(filename)
    if Path(safe_name).suffix.lower() != ".csv":
        raise ValueError("only CSV uploads are supported")
    created_at = uploaded_at or _iso_now()
    resolved_upload_id = upload_id.strip() or generate_upload_id()
    upload_dir = _upload_store_root(repo_root_path) / resolved_upload_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    staged_path = upload_dir / safe_name
    staged_path.write_bytes(content)
    payload = {
        "upload_id": resolved_upload_id,
        "original_filename": safe_name,
        "staged_path": str(staged_path),
        "size_bytes": len(content),
        "uploaded_at": created_at,
    }
    _write_json(_upload_record_path(repo_root_path, resolved_upload_id), payload)
    return payload


def load_task_upload(repo_root: Path | str, upload_id: str) -> Optional[Dict[str, Any]]:
    repo_root_path = Path(repo_root)
    payload = _read_json(_upload_record_path(repo_root_path, upload_id))
    return payload if payload.get("upload_id") else None


def _normalize_history(raw_history: Iterable[Any]) -> List[Dict[str, Any]]:
    history: List[Dict[str, Any]] = []
    for index, item in enumerate(list(raw_history or []), start=1):
        if not isinstance(item, dict):
            continue
        history.append(
            {
                "event_id": str(item.get("event_id") or f"event_{index:03d}"),
                "type": str(item.get("type") or "note").strip() or "note",
                "title": str(item.get("title") or "Task updated").strip() or "Task updated",
                "message": str(item.get("message") or "").strip(),
                "at": str(item.get("at") or item.get("created_at") or "").strip(),
                "metadata": dict(item.get("metadata") or {}),
            }
        )
    return history


def _clean_task_record(record: Dict[str, Any]) -> Dict[str, Any]:
    linked_run_ids = [str(item).strip() for item in list(record.get("linked_run_ids", []) or []) if str(item).strip()]
    status = str(record.get("status", record.get("status_override", ""))).strip()
    if status not in TASK_STATUSES:
        status = "draft" if not linked_run_ids else "queued"
    input_mode = str(record.get("input_mode", "")).strip().lower()
    if input_mode not in {"upload", "path"}:
        input_mode = "upload" if str(record.get("upload_id", "")).strip() else "path"
    source_input = str(record.get("source_input", "")).strip()
    source_label = str(record.get("source_input_label", "")).strip() or (_safe_filename(source_input, "input.csv") if source_input else "")
    return {
        "task_id": str(record.get("task_id", "")).strip(),
        "task_type": str(record.get("task_type", "localization_job")).strip() or "localization_job",
        "title": str(record.get("title", "")).strip(),
        "summary": str(record.get("summary", "")).strip(),
        "input_mode": input_mode,
        "source_input": source_input,
        "source_input_label": source_label,
        "upload_id": str(record.get("upload_id", "")).strip(),
        "target_locale": str(record.get("target_locale", "")).strip(),
        "verify_mode": str(record.get("verify_mode", "")).strip(),
        "linked_run_ids": linked_run_ids,
        "created_at": str(record.get("created_at", "")).strip(),
        "updated_at": str(record.get("updated_at", "")).strip(),
        "status": status,
        "bundle_state": str(record.get("bundle_state", "")).strip(),
        "latest_feedback_note": str(record.get("latest_feedback_note", "")).strip(),
        "archived_at": str(record.get("archived_at", "")).strip(),
        "event_history": _normalize_history(record.get("event_history", [])),
        "first_user_action_at": str(record.get("first_user_action_at", "")).strip(),
        "approved_at": str(record.get("approved_at", "")).strip(),
        "request_changes_at": str(record.get("request_changes_at", "")).strip(),
        "downloaded_at": str(record.get("downloaded_at", "")).strip(),
        "bundle_summary": dict(record.get("bundle_summary") or {}),
    }


def load_human_task_record(repo_root: Path | str, task_id: str) -> Optional[Dict[str, Any]]:
    repo_root_path = Path(repo_root)
    record = _clean_task_record(_read_json(_task_record_path(repo_root_path, task_id)))
    return record if record["task_id"] else None


def load_human_task_records(repo_root: Path | str) -> List[Dict[str, Any]]:
    repo_root_path = Path(repo_root)
    root = _task_store_root(repo_root_path)
    if not root.exists():
        return []
    records: List[Dict[str, Any]] = []
    for path in sorted(root.rglob("task.json")):
        record = _clean_task_record(_read_json(path))
        if record["task_id"]:
            records.append(record)
    return records


def _append_event(
    record: Dict[str, Any],
    *,
    event_type: str,
    title: str,
    message: str = "",
    at: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    resolved_at = at or _iso_now()
    history = list(record.get("event_history", []) or [])
    history.append(
        {
            "event_id": generate_task_id(prefix="event"),
            "type": event_type,
            "title": title,
            "message": message,
            "at": resolved_at,
            "metadata": dict(metadata or {}),
        }
    )
    record["event_history"] = history[-64:]
    record["updated_at"] = resolved_at


def _stamp_first_user_action(record: Dict[str, Any], *, at: str) -> None:
    if not record.get("first_user_action_at"):
        record["first_user_action_at"] = at


def create_human_task_record(
    repo_root: Path | str,
    *,
    title: str,
    source_input: str,
    target_locale: str,
    verify_mode: str,
    linked_run_id: str,
    created_at: str,
    task_id: str = "",
    task_type: str = "localization_job",
    input_mode: str = "path",
    source_input_label: str = "",
    upload_id: str = "",
) -> Dict[str, Any]:
    repo_root_path = Path(repo_root)
    resolved_task_id = task_id.strip() or generate_task_id()
    record = {
        "task_id": resolved_task_id,
        "task_type": task_type,
        "title": title.strip(),
        "summary": "",
        "input_mode": input_mode if input_mode in {"upload", "path"} else "path",
        "source_input": str(source_input).strip(),
        "source_input_label": source_input_label.strip() or _safe_filename(source_input, "input.csv"),
        "upload_id": upload_id.strip(),
        "target_locale": str(target_locale).strip(),
        "verify_mode": str(verify_mode).strip(),
        "linked_run_ids": [str(linked_run_id).strip()] if str(linked_run_id).strip() else [],
        "created_at": str(created_at).strip() or _iso_now(),
        "updated_at": str(created_at).strip() or _iso_now(),
        "status": "queued" if str(linked_run_id).strip() else "draft",
        "bundle_state": "",
        "latest_feedback_note": "",
        "archived_at": "",
        "event_history": [],
        "first_user_action_at": "",
        "approved_at": "",
        "request_changes_at": "",
        "downloaded_at": "",
        "bundle_summary": {},
    }
    _append_event(
        record,
        event_type="task_created",
        title="Task created",
        message="The localization task has been created.",
        at=record["created_at"],
        metadata={"input_mode": record["input_mode"], "source_input_label": record["source_input_label"]},
    )
    if record["linked_run_ids"]:
        _append_event(
            record,
            event_type="run_linked",
            title="Initial run started",
            message="The first pipeline run has been launched for this task.",
            at=record["created_at"],
            metadata={"run_id": record["linked_run_ids"][-1]},
        )
    _write_json(_task_record_path(repo_root_path, resolved_task_id), record)
    return _clean_task_record(record)


def append_human_task_run(repo_root: Path | str, task_id: str, *, run_id: str, updated_at: str, note: str = "") -> Dict[str, Any]:
    repo_root_path = Path(repo_root)
    record = load_human_task_record(repo_root_path, task_id)
    if record is None:
        raise FileNotFoundError(task_id)
    record["linked_run_ids"] = [*record["linked_run_ids"], run_id]
    record["status"] = "queued"
    record["bundle_state"] = ""
    record["approved_at"] = ""
    _append_event(
        record,
        event_type="run_linked",
        title="New run started",
        message=note or "A new pipeline run has been launched for this task.",
        at=updated_at,
        metadata={"run_id": run_id},
    )
    _write_json(_task_record_path(repo_root_path, task_id), record)
    return _clean_task_record(record)


def update_human_task_record(repo_root: Path | str, task_id: str, updater) -> Dict[str, Any]:
    repo_root_path = Path(repo_root)
    record = load_human_task_record(repo_root_path, task_id)
    if record is None:
        if task_id.startswith("task_"):
            run_id = task_id.removeprefix("task_")
            try:
                run_detail = load_run_detail(find_run_manifest(repo_root_path, run_id), repo_root=repo_root_path)
            except FileNotFoundError as exc:
                raise FileNotFoundError(task_id) from exc
            record = _synthetic_record_for_run(run_detail)
        else:
            raise FileNotFoundError(task_id)
    updater(record)
    _write_json(_task_record_path(repo_root_path, task_id), record)
    return _clean_task_record(record)


def mark_task_delivery_downloaded(repo_root: Path | str, task_id: str, *, delivery_id: str, at: str = "") -> Dict[str, Any]:
    resolved_at = at or _iso_now()

    def _updater(record: Dict[str, Any]) -> None:
        record["downloaded_at"] = resolved_at
        _stamp_first_user_action(record, at=resolved_at)
        _append_event(
            record,
            event_type="delivery_downloaded",
            title="Delivery downloaded",
            message="A delivery file was downloaded from the task package.",
            at=resolved_at,
            metadata={"delivery_id": delivery_id},
        )

    return update_human_task_record(repo_root, task_id, _updater)


def approve_human_task_delivery(repo_root: Path | str, task_id: str, *, delivery_id: str, at: str = "") -> Dict[str, Any]:
    resolved_at = at or _iso_now()

    def _updater(record: Dict[str, Any]) -> None:
        record["status"] = "ready_for_download"
        record["bundle_state"] = "approved"
        record["approved_at"] = resolved_at
        _stamp_first_user_action(record, at=resolved_at)
        _append_event(
            record,
            event_type="delivery_approved",
            title="Package approved",
            message="The current delivery package has been approved for collection.",
            at=resolved_at,
            metadata={"delivery_id": delivery_id},
        )

    return update_human_task_record(repo_root, task_id, _updater)


def archive_human_task(repo_root: Path | str, task_id: str, *, at: str = "") -> Dict[str, Any]:
    resolved_at = at or _iso_now()

    def _updater(record: Dict[str, Any]) -> None:
        record["archived_at"] = resolved_at
        _append_event(
            record,
            event_type="task_archived",
            title="Task archived",
            message="The task was archived from the active inbox.",
            at=resolved_at,
        )

    return update_human_task_record(repo_root, task_id, _updater)


def request_human_task_changes(
    repo_root: Path | str,
    task_id: str,
    *,
    note: str,
    at: str = "",
    new_run_id: str = "",
) -> Dict[str, Any]:
    resolved_at = at or _iso_now()

    def _updater(record: Dict[str, Any]) -> None:
        record["latest_feedback_note"] = note.strip()
        record["request_changes_at"] = resolved_at
        record["bundle_state"] = ""
        record["approved_at"] = ""
        _stamp_first_user_action(record, at=resolved_at)
        _append_event(
            record,
            event_type="changes_requested",
            title="Changes requested",
            message=note.strip(),
            at=resolved_at,
        )
        if new_run_id:
            record["status"] = "queued"
            record["linked_run_ids"] = [*record.get("linked_run_ids", []), new_run_id]
            _append_event(
                record,
                event_type="run_linked",
                title="Follow-up run started",
                message="A follow-up run was started after the requested changes.",
                at=resolved_at,
                metadata={"run_id": new_run_id},
            )
        else:
            record["status"] = "needs_operator_review"
            _append_event(
                record,
                event_type="ops_handoff",
                title="Escalated to Ops Monitor",
                message="Automatic rerun was unavailable, so the task was moved to Waiting on Ops.",
                at=resolved_at,
            )

    return update_human_task_record(repo_root, task_id, _updater)


@dataclass
class HumanArtifactView:
    artifact_key: str
    delivery_id: str
    label: str
    description: str
    kind: str
    primary_use: str
    group_id: str
    group_label: str
    openable: bool
    downloadable: bool
    source_run_id: str
    preview_url: str
    download_url: str
    technical_detail: bool = False
    path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_key": self.artifact_key,
            "delivery_id": self.delivery_id,
            "label": self.label,
            "description": self.description,
            "kind": self.kind,
            "primary_use": self.primary_use,
            "group_id": self.group_id,
            "group_label": self.group_label,
            "openable": self.openable,
            "downloadable": self.downloadable,
            "source_run_id": self.source_run_id,
            "preview_url": self.preview_url,
            "download_url": self.download_url,
            "technical_detail": self.technical_detail,
            "path": self.path,
        }


@dataclass
class HumanTaskView:
    task_id: str
    task_type: str
    title: str
    summary: str
    why_it_matters: str
    linked_run_ids: List[str]
    linked_runs: List[Dict[str, Any]]
    status: str
    bucket: str
    current_step: str
    required_human_action: str
    allowed_actions: List[Dict[str, Any]]
    output_refs: List[HumanArtifactView]
    bundle_summary: Dict[str, Any]
    latest_run_id: str
    latest_run_status: str
    source_input: str
    source_input_label: str
    input_mode: str
    upload_id: str
    target_locale: str
    verify_mode: str
    started_at: str
    monitor_case_id: str = ""
    latest_feedback_note: str = ""
    archived_at: str = ""
    history: List[Dict[str, Any]] = field(default_factory=list)
    next_primary_action: str = ""
    metrics: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "task_type": self.task_type,
            "title": self.title,
            "summary": self.summary,
            "why_it_matters": self.why_it_matters,
            "linked_run_ids": list(self.linked_run_ids),
            "linked_runs": list(self.linked_runs),
            "status": self.status,
            "bucket": self.bucket,
            "current_step": self.current_step,
            "required_human_action": self.required_human_action,
            "allowed_actions": list(self.allowed_actions),
            "output_refs": [artifact.to_dict() for artifact in self.output_refs],
            "bundle_summary": dict(self.bundle_summary),
            "latest_run_id": self.latest_run_id,
            "latest_run_status": self.latest_run_status,
            "source_input": self.source_input,
            "source_input_label": self.source_input_label,
            "input_mode": self.input_mode,
            "upload_id": self.upload_id,
            "target_locale": self.target_locale,
            "verify_mode": self.verify_mode,
            "started_at": self.started_at,
            "monitor_case_id": self.monitor_case_id,
            "latest_feedback_note": self.latest_feedback_note,
            "archived_at": self.archived_at,
            "history": list(self.history),
            "next_primary_action": self.next_primary_action,
            "metrics": dict(self.metrics),
        }


@dataclass
class HumanTaskOverview:
    total: int
    counts_by_status: Dict[str, int]
    counts_by_bucket: Dict[str, int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "counts_by_status": dict(self.counts_by_status),
            "counts_by_bucket": dict(self.counts_by_bucket),
        }


def _load_run_detail_map(repo_root: Path, pending_runs: Optional[List[Dict[str, Any]]] = None) -> Dict[str, RunDetail]:
    run_details: Dict[str, RunDetail] = {}
    data_root = repo_root / "data"
    if data_root.exists():
        for manifest_path in data_root.rglob("run_manifest.json"):
            detail = load_run_detail(manifest_path, repo_root=repo_root)
            run_details[detail.run_id] = detail
    for payload in pending_runs or []:
        detail = build_pending_run_detail(payload)
        run_details.setdefault(detail.run_id, detail)
    return run_details


def _load_workspace_case_map(repo_root: Path) -> Dict[str, WorkspaceCaseView]:
    return {case.run_id: case for case in load_workspace_cases(repo_root, status="all", limit=10000)}


def _delivery_group_label(group_id: str) -> str:
    return {
        "primary_output": "Primary output",
        "validation_report": "Validation report",
        "issue_summary": "Issue summary",
        "supporting_files": "Supporting files",
    }.get(group_id, "Supporting files")


def _artifact_meta(artifact_key: str) -> Dict[str, Any]:
    mapping: Dict[str, Dict[str, Any]] = {
        "operator_summary_md": {
            "label": "Delivery summary",
            "description": "Human-readable summary for the localized delivery.",
            "primary_use": "Primary output",
            "group_id": "primary_output",
            "technical_detail": False,
            "priority": 0,
        },
        "smoke_verify_report": {
            "label": "Verification report",
            "description": "Quality check summary for the latest run.",
            "primary_use": "Quality review",
            "group_id": "validation_report",
            "technical_detail": False,
            "priority": 1,
        },
        "smoke_issues_report": {
            "label": "Issue summary",
            "description": "Structured issue list collected during verification.",
            "primary_use": "Risk review",
            "group_id": "issue_summary",
            "technical_detail": False,
            "priority": 2,
        },
        "operator_summary_json": {
            "label": "Structured delivery summary",
            "description": "Machine-readable summary exported for integrations or deeper inspection.",
            "primary_use": "Supporting file",
            "group_id": "supporting_files",
            "technical_detail": True,
            "priority": 6,
        },
        "run_manifest": {
            "label": "Execution manifest",
            "description": "Technical record of the run inputs, status, and generated artifacts.",
            "primary_use": "Technical details",
            "group_id": "supporting_files",
            "technical_detail": True,
            "priority": 7,
        },
        "smoke_verify_log": {
            "label": "Run log",
            "description": "Plain-text execution log for the selected run.",
            "primary_use": "Debugging",
            "group_id": "supporting_files",
            "technical_detail": True,
            "priority": 8,
        },
        "smoke_governance_kpi_json": {
            "label": "Governance snapshot",
            "description": "Governance and KPI signal snapshot for the run.",
            "primary_use": "Monitoring",
            "group_id": "supporting_files",
            "technical_detail": True,
            "priority": 9,
        },
        "smoke_review_tickets_jsonl": {
            "label": "Review queue",
            "description": "Queued human review tickets generated by this run.",
            "primary_use": "Review planning",
            "group_id": "supporting_files",
            "technical_detail": True,
            "priority": 10,
        },
        "smoke_feedback_log_jsonl": {
            "label": "Feedback log",
            "description": "Recorded review feedback attached to this run.",
            "primary_use": "Review history",
            "group_id": "supporting_files",
            "technical_detail": True,
            "priority": 11,
        },
        "operator_cards": {
            "label": "Operator cards",
            "description": "Operator-facing cards linked to the selected run.",
            "primary_use": "Technical details",
            "group_id": "supporting_files",
            "technical_detail": True,
            "priority": 12,
        },
    }
    if artifact_key in mapping:
        return dict(mapping[artifact_key])
    humanized = artifact_key.replace("_", " ").strip().title()
    technical = any(token in artifact_key for token in ["manifest", "log", "operator_", "governance", "ticket", "feedback"])
    return {
        "label": humanized,
        "description": f"{humanized} exported from the selected run.",
        "primary_use": "Supporting file",
        "group_id": "supporting_files",
        "technical_detail": technical,
        "priority": 40,
    }


def _make_delivery_id(run_id: str, artifact_key: str) -> str:
    return f"{run_id}__{artifact_key}"


def build_human_artifact_views(run_detail: Optional[RunDetail], *, task_id: str = "") -> List[HumanArtifactView]:
    if run_detail is None:
        return []
    views: List[HumanArtifactView] = []
    for artifact_key in run_detail.allowed_artifact_keys:
        artifact = run_detail.artifacts.get(artifact_key)
        if artifact is None:
            continue
        meta = _artifact_meta(artifact.key)
        delivery_id = _make_delivery_id(run_detail.run_id, artifact.key)
        views.append(
            HumanArtifactView(
                artifact_key=artifact.key,
                delivery_id=delivery_id,
                label=str(meta["label"]),
                description=str(meta["description"]),
                kind=artifact.kind,
                primary_use=str(meta["primary_use"]),
                group_id=str(meta["group_id"]),
                group_label=_delivery_group_label(str(meta["group_id"])),
                openable=bool(artifact.previewable and artifact.exists),
                downloadable=bool(artifact.exists),
                source_run_id=run_detail.run_id,
                preview_url=f"/api/tasks/{task_id}/deliveries/{delivery_id}" if task_id else "",
                download_url=f"/api/tasks/{task_id}/deliveries/{delivery_id}/download" if task_id else "",
                technical_detail=bool(meta["technical_detail"]),
                path=artifact.path,
            )
        )
    return sorted(
        views,
        key=lambda item: (
            _artifact_meta(item.artifact_key)["priority"],
            item.label,
        ),
    )


def build_bundle_summary(deliveries: List[HumanArtifactView]) -> Dict[str, Any]:
    grouped: Dict[str, List[HumanArtifactView]] = {group_id: [] for group_id in VISIBLE_DELIVERY_GROUPS}
    technical_details: List[HumanArtifactView] = []
    for delivery in deliveries:
        if delivery.technical_detail:
            technical_details.append(delivery)
        else:
            grouped.setdefault(delivery.group_id, []).append(delivery)
    groups = [
        {
            "group_id": group_id,
            "label": _delivery_group_label(group_id),
            "items": [delivery.to_dict() for delivery in grouped.get(group_id, [])],
        }
        for group_id in VISIBLE_DELIVERY_GROUPS
        if grouped.get(group_id)
    ]
    primary_delivery = next((delivery for delivery in deliveries if delivery.downloadable and not delivery.technical_detail), None)
    return {
        "groups": groups,
        "technical_details": [delivery.to_dict() for delivery in technical_details],
        "primary_delivery_id": primary_delivery.delivery_id if primary_delivery else "",
        "counts": {
            "visible": sum(len(group["items"]) for group in groups),
            "technical": len(technical_details),
            "total": len(deliveries),
        },
    }


def _effective_task_status(
    run_detail: Optional[RunDetail],
    workspace_case: Optional[WorkspaceCaseView],
    record: Dict[str, Any],
) -> str:
    stored_status = str(record.get("status", "")).strip()
    if run_detail is None:
        return stored_status if stored_status in TASK_STATUSES else "draft"
    if run_detail.pending:
        pending_status = run_detail.overall_status.strip().lower()
        if pending_status in {"running", "pending"}:
            return "running"
        if pending_status in {"fail", "failed", "blocked"}:
            return "failed"
        return stored_status if stored_status in TASK_STATUSES else "queued"
    if run_detail.overall_status in {"running", "pending"}:
        return "running"
    if run_detail.overall_status in {"fail", "failed", "blocked"}:
        return "failed"
    if workspace_case and workspace_case.status == "open":
        return "needs_operator_review"
    if run_detail.overall_status == "warn":
        return "needs_operator_review"
    if run_detail.overall_status == "pass":
        if stored_status == "ready_for_download" or str(record.get("bundle_state", "")).strip() == "approved":
            return "ready_for_download"
        return "needs_user_action"
    return stored_status if stored_status in TASK_STATUSES else "running"


def _task_bucket(status: str, archived_at: str) -> str:
    if archived_at:
        return "archived"
    return {
        "needs_user_action": "needs_your_action",
        "queued": "running",
        "running": "running",
        "needs_operator_review": "waiting_on_ops",
        "ready_for_download": "ready_to_collect",
        "failed": "failed",
        "draft": "running",
    }.get(status, "running")


def _fallback_title(record: Dict[str, Any], run_detail: Optional[RunDetail]) -> str:
    if record.get("title"):
        return str(record["title"])
    if record.get("source_input_label"):
        return str(record["source_input_label"])
    source_input = str(record.get("source_input", "")).strip()
    if source_input:
        return Path(source_input).name
    if run_detail and run_detail.input_csv:
        return Path(run_detail.input_csv).name
    if run_detail:
        return run_detail.run_id
    return "New localization task"


def _task_summary(status: str, title: str) -> str:
    if status == "queued":
        return f"{title} has been queued and is waiting for the pipeline to start."
    if status == "running":
        return f"{title} is currently moving through translation and verification."
    if status == "needs_user_action":
        return f"{title} finished running and is waiting for your delivery decision."
    if status == "needs_operator_review":
        return f"{title} produced signals that need an operator review before release."
    if status == "ready_for_download":
        return f"{title} has an approved package ready to inspect and collect."
    if status == "failed":
        return f"{title} failed before producing a trusted delivery package."
    return f"{title} is ready to be configured."


def _task_why_it_matters(status: str, workspace_case: Optional[WorkspaceCaseView]) -> str:
    if status == "queued":
        return "The task has been accepted and is waiting for runtime capacity."
    if status == "running":
        return "No human action is needed yet, but you can monitor progress or inspect the latest run."
    if status == "needs_user_action":
        return "The run finished cleanly enough for a human decision. Review the result package now to approve it or request changes."
    if status == "needs_operator_review":
        return workspace_case.next_action if workspace_case and workspace_case.next_action else "A human needs to inspect the flagged signals before this task can move forward."
    if status == "ready_for_download":
        return "The result package has been approved and is ready to collect."
    if status == "failed":
        return "The latest run stopped in a failure state and needs a rerun or expert diagnosis."
    return "Create the task to begin a localized delivery."


def _task_current_step(status: str) -> str:
    return {
        "draft": "Configure the task inputs and launch the first run.",
        "queued": "Queued for pipeline start.",
        "running": "Pipeline is processing rows and collecting validation signals.",
        "needs_user_action": "Review the package and decide whether to approve it or request changes.",
        "needs_operator_review": "Waiting for operator review and a release decision.",
        "ready_for_download": "The approved package is ready to inspect and download.",
        "failed": "Latest run failed and needs expert attention.",
    }.get(status, "Waiting for the next pipeline step.")


def _task_required_action(status: str) -> str:
    return {
        "draft": "Review the inputs, then start the task.",
        "queued": "Wait for the run to start or open the monitor if you need live visibility.",
        "running": "Check the monitor for live progress, or wait for a result package.",
        "needs_user_action": "Inspect the package, then approve it or request changes with a clear note.",
        "needs_operator_review": "Open the Ops Monitor to review the flagged case and decide whether to rerun.",
        "ready_for_download": "Open the package and download the files you need.",
        "failed": "Open Pro Runtime for diagnostics or rerun the task after fixing the input.",
    }.get(status, "Check the latest task status.")


def _task_actions(status: str, run_detail: Optional[RunDetail], deliveries: List[HumanArtifactView], record: Dict[str, Any]) -> List[Dict[str, Any]]:
    can_rerun = bool(record.get("source_input")) and bool(record.get("target_locale")) and bool(record.get("verify_mode"))
    actions: List[Dict[str, Any]] = []
    if status in {"queued", "running"}:
        actions.append({"action": "refresh_status", "primary": True})
        if run_detail is not None:
            actions.append({"action": "open_monitor", "primary": False})
            actions.append({"action": "open_runtime", "primary": False})
    elif status == "needs_user_action":
        if deliveries:
            actions.append({"action": "approve_delivery", "primary": True})
            actions.append({"action": "view_deliveries", "primary": False})
        actions.append({"action": "request_changes", "primary": False, "requires_note": True})
        if run_detail is not None:
            actions.append({"action": "open_monitor", "primary": False})
    elif status == "needs_operator_review":
        actions.append({"action": "open_monitor", "primary": True})
        if run_detail is not None:
            actions.append({"action": "open_runtime", "primary": False})
        if can_rerun:
            actions.append({"action": "rerun", "primary": False})
    elif status == "ready_for_download":
        if deliveries:
            actions.append({"action": "view_deliveries", "primary": True})
        actions.append({"action": "archive_task", "primary": False})
        actions.append({"action": "request_changes", "primary": False, "requires_note": True})
        if run_detail is not None:
            actions.append({"action": "open_monitor", "primary": False})
    elif status == "failed":
        if can_rerun:
            actions.append({"action": "rerun", "primary": True})
        if run_detail is not None:
            actions.append({"action": "open_runtime", "primary": not can_rerun})
            actions.append({"action": "open_monitor", "primary": False})
        actions.append({"action": "archive_task", "primary": False})
    else:
        actions.append({"action": "refresh_status", "primary": True})
    return actions


def _synthetic_record_for_run(run_detail: RunDetail) -> Dict[str, Any]:
    created_at = run_detail.started_at or _iso_now()
    return {
        "task_id": task_id_for_run(run_detail.run_id),
        "task_type": "localization_job",
        "title": "",
        "summary": "",
        "input_mode": "path",
        "source_input": run_detail.input_csv,
        "source_input_label": _safe_filename(run_detail.input_csv or run_detail.run_id, "input.csv"),
        "upload_id": "",
        "target_locale": run_detail.target_lang,
        "verify_mode": run_detail.verify_mode,
        "linked_run_ids": [run_detail.run_id],
        "created_at": created_at,
        "updated_at": created_at,
        "status": "queued",
        "bundle_state": "",
        "latest_feedback_note": "",
        "archived_at": "",
        "event_history": [
            {
                "event_id": "event_001",
                "type": "run_discovered",
                "title": "Discovered existing run",
                "message": "This task was reconstructed from an existing pipeline run.",
                "at": created_at,
                "metadata": {"run_id": run_detail.run_id},
            }
        ],
        "first_user_action_at": "",
        "approved_at": "",
        "request_changes_at": "",
        "downloaded_at": "",
        "bundle_summary": {},
    }


def _linked_runs_payload(record: Dict[str, Any], run_map: Dict[str, RunDetail]) -> List[Dict[str, Any]]:
    payload: List[Dict[str, Any]] = []
    for run_id in reversed(list(record.get("linked_run_ids", []) or [])):
        detail = run_map.get(run_id)
        payload.append(
            {
                "run_id": run_id,
                "status": detail.overall_status if detail is not None else "unknown",
                "started_at": detail.started_at if detail is not None else "",
                "pending": bool(detail.pending) if detail is not None else False,
                "target_locale": detail.target_lang if detail is not None else str(record.get("target_locale", "")),
            }
        )
    return payload


def _task_metrics(record: Dict[str, Any]) -> Dict[str, str]:
    return {
        "created_at": str(record.get("created_at", "")),
        "first_user_action_at": str(record.get("first_user_action_at", "")),
        "approved_at": str(record.get("approved_at", "")),
        "request_changes_at": str(record.get("request_changes_at", "")),
        "downloaded_at": str(record.get("downloaded_at", "")),
    }


def build_human_task_view(
    record: Dict[str, Any],
    run_detail: Optional[RunDetail],
    workspace_case: Optional[WorkspaceCaseView],
    *,
    run_map: Optional[Dict[str, RunDetail]] = None,
) -> HumanTaskView:
    title = _fallback_title(record, run_detail)
    status = _effective_task_status(run_detail, workspace_case, record)
    bucket = _task_bucket(status, str(record.get("archived_at", "")))
    deliveries = build_human_artifact_views(run_detail, task_id=str(record.get("task_id", "")))
    bundle_summary = build_bundle_summary(deliveries)
    actions = _task_actions(status, run_detail, deliveries, record)
    return HumanTaskView(
        task_id=str(record.get("task_id", "")),
        task_type=str(record.get("task_type", "localization_job")) or "localization_job",
        title=title,
        summary=str(record.get("summary", "")).strip() or _task_summary(status, title),
        why_it_matters=_task_why_it_matters(status, workspace_case),
        linked_run_ids=[str(item) for item in list(record.get("linked_run_ids", []) or [])],
        linked_runs=_linked_runs_payload(record, run_map or {}),
        status=status,
        bucket=bucket,
        current_step=_task_current_step(status),
        required_human_action=_task_required_action(status),
        allowed_actions=actions,
        output_refs=deliveries,
        bundle_summary=bundle_summary,
        latest_run_id=run_detail.run_id if run_detail is not None else "",
        latest_run_status=run_detail.overall_status if run_detail is not None else "draft",
        source_input=str(record.get("source_input", "")).strip() or (run_detail.input_csv if run_detail else ""),
        source_input_label=str(record.get("source_input_label", "")).strip() or title,
        input_mode=str(record.get("input_mode", "path")),
        upload_id=str(record.get("upload_id", "")),
        target_locale=str(record.get("target_locale", "")).strip() or (run_detail.target_lang if run_detail else ""),
        verify_mode=str(record.get("verify_mode", "")).strip() or (run_detail.verify_mode if run_detail else ""),
        started_at=str(record.get("created_at") or record.get("updated_at") or (run_detail.started_at if run_detail else "")),
        monitor_case_id=workspace_case.case_id if workspace_case is not None else "",
        latest_feedback_note=str(record.get("latest_feedback_note", "")).strip(),
        archived_at=str(record.get("archived_at", "")).strip(),
        history=list(record.get("event_history", [])),
        next_primary_action=next((item["action"] for item in actions if item.get("primary")), ""),
        metrics=_task_metrics(record),
    )


def _build_all_task_views(repo_root: Path, pending_runs: Optional[List[Dict[str, Any]]] = None) -> List[HumanTaskView]:
    run_map = _load_run_detail_map(repo_root, pending_runs=pending_runs)
    case_map = _load_workspace_case_map(repo_root)
    records = load_human_task_records(repo_root)
    tasks: List[HumanTaskView] = []
    consumed_run_ids: set[str] = set()

    for record in records:
        linked_run_ids = [str(item) for item in list(record.get("linked_run_ids", []) or [])]
        latest_run_id = linked_run_ids[-1] if linked_run_ids else ""
        run_detail = run_map.get(latest_run_id) if latest_run_id else None
        tasks.append(build_human_task_view(record, run_detail, case_map.get(latest_run_id), run_map=run_map))
        consumed_run_ids.update(linked_run_ids)

    for run_id, run_detail in run_map.items():
        if run_id in consumed_run_ids:
            continue
        tasks.append(
            build_human_task_view(
                _synthetic_record_for_run(run_detail),
                run_detail,
                case_map.get(run_id),
                run_map=run_map,
            )
        )

    return sorted(
        tasks,
        key=lambda task: (
            TASK_BUCKET_ORDER.get(task.bucket, 99),
            TASK_STATUS_ORDER.get(task.status, 99),
            task.started_at,
            task.task_id,
        ),
    )


def _task_matches_query(task: HumanTaskView, query: str) -> bool:
    lowered = query.strip().lower()
    if not lowered:
        return True
    haystack = " ".join(
        [
            task.task_id,
            task.title,
            task.summary,
            task.why_it_matters,
            task.target_locale,
            task.source_input_label,
            task.latest_feedback_note,
            " ".join(task.linked_run_ids),
        ]
    ).lower()
    return lowered in haystack


def _filter_tasks(
    tasks: List[HumanTaskView],
    *,
    status: str = "",
    bucket: str = "",
    query: str = "",
    include_archived: bool = False,
) -> List[HumanTaskView]:
    filtered = tasks
    if not include_archived:
        filtered = [task for task in filtered if task.bucket != "archived"]
    if status:
        filtered = [task for task in filtered if task.status == status]
    if bucket and bucket != "all":
        filtered = [task for task in filtered if task.bucket == bucket]
    if query:
        filtered = [task for task in filtered if _task_matches_query(task, query)]
    return filtered


def load_human_task_summaries(
    repo_root: Path | str,
    *,
    pending_runs: Optional[List[Dict[str, Any]]] = None,
    limit: int = 25,
    status: str = "",
    bucket: str = "",
    query: str = "",
    include_archived: bool = False,
) -> List[HumanTaskView]:
    repo_root_path = Path(repo_root)
    tasks = _build_all_task_views(repo_root_path, pending_runs=pending_runs)
    filtered = _filter_tasks(tasks, status=status, bucket=bucket, query=query, include_archived=include_archived)
    return filtered[: max(limit, 0)]


def load_human_task_overview(
    repo_root: Path | str,
    *,
    pending_runs: Optional[List[Dict[str, Any]]] = None,
    limit: Optional[int] = None,
) -> HumanTaskOverview:
    repo_root_path = Path(repo_root)
    all_tasks = _build_all_task_views(repo_root_path, pending_runs=pending_runs)
    active_tasks = [task for task in all_tasks if task.bucket != "archived"]
    counts_by_status = dict(Counter(task.status for task in active_tasks))
    counts_by_bucket = dict(Counter(task.bucket for task in all_tasks))
    return HumanTaskOverview(total=len(active_tasks), counts_by_status=counts_by_status, counts_by_bucket=counts_by_bucket)


def _legacy_task_from_id(repo_root: Path, task_id: str, pending_runs: Optional[List[Dict[str, Any]]] = None) -> Optional[HumanTaskView]:
    if not task_id.startswith("task_"):
        return None
    run_id = task_id.removeprefix("task_")
    run_map = _load_run_detail_map(repo_root, pending_runs=pending_runs)
    run_detail = run_map.get(run_id)
    if run_detail is None:
        try:
            run_detail = load_run_detail(find_run_manifest(repo_root, run_id), repo_root=repo_root)
        except FileNotFoundError:
            return None
    case_map = _load_workspace_case_map(repo_root)
    return build_human_task_view(_synthetic_record_for_run(run_detail), run_detail, case_map.get(run_id), run_map=run_map)


def _load_task_context(
    repo_root: Path,
    task_id: str,
    *,
    pending_runs: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[Dict[str, Any], Optional[RunDetail], Optional[WorkspaceCaseView], Dict[str, RunDetail]]:
    record = load_human_task_record(repo_root, task_id)
    run_map = _load_run_detail_map(repo_root, pending_runs=pending_runs)
    case_map = _load_workspace_case_map(repo_root)
    if record is None:
        task = _legacy_task_from_id(repo_root, task_id, pending_runs=pending_runs)
        if task is None:
            raise FileNotFoundError(task_id)
        synthetic = _synthetic_record_for_run(run_map[task.latest_run_id])
        return synthetic, run_map.get(task.latest_run_id), case_map.get(task.latest_run_id), run_map
    linked_run_ids = [str(item) for item in list(record.get("linked_run_ids", []) or [])]
    latest_run_id = linked_run_ids[-1] if linked_run_ids else ""
    return record, run_map.get(latest_run_id) if latest_run_id else None, case_map.get(latest_run_id), run_map


def load_human_task_detail(repo_root: Path | str, task_id: str, *, pending_runs: Optional[List[Dict[str, Any]]] = None) -> HumanTaskView:
    repo_root_path = Path(repo_root)
    record, run_detail, workspace_case, run_map = _load_task_context(repo_root_path, task_id, pending_runs=pending_runs)
    return build_human_task_view(record, run_detail, workspace_case, run_map=run_map)


def load_human_task_deliveries(
    repo_root: Path | str,
    task_id: str,
    *,
    pending_runs: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    task = load_human_task_detail(repo_root, task_id, pending_runs=pending_runs)
    return {
        "task_id": task_id,
        "deliveries": [delivery.to_dict() for delivery in task.output_refs],
        "bundle_summary": dict(task.bundle_summary),
    }


def resolve_human_task_delivery(
    repo_root: Path | str,
    task_id: str,
    delivery_id: str,
    *,
    pending_runs: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[HumanTaskView, HumanArtifactView, ArtifactRecord]:
    repo_root_path = Path(repo_root)
    record, run_detail, workspace_case, run_map = _load_task_context(repo_root_path, task_id, pending_runs=pending_runs)
    task = build_human_task_view(record, run_detail, workspace_case, run_map=run_map)
    delivery = next((item for item in task.output_refs if item.delivery_id == delivery_id), None)
    if delivery is None or run_detail is None:
        raise FileNotFoundError(delivery_id)
    artifact = run_detail.artifacts.get(delivery.artifact_key)
    if artifact is None:
        raise FileNotFoundError(delivery_id)
    return task, delivery, artifact
