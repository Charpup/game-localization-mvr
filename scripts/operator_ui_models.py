#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""View models and artifact helpers for the Phase 5 runtime shell."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from scripts.operator_control_plane import derive_operator_artifacts


TEXT_SUFFIXES = {".log", ".txt", ".md", ".py", ".yaml", ".yml", ".csv"}
JSON_SUFFIXES = {".json", ".jsonl"}
WORKSPACE_CARD_STATUSES = {"all", "open", "closed"}
WORKSPACE_CASE_STATUSES = {"all", "open"}
WORKSPACE_CASE_LANES = {"all", "act", "review", "watch", "done"}
WORKSPACE_CARD_PRIORITIES = {"P0", "P1", "P2"}
WORKSPACE_CARD_TYPES = {"review_ticket", "runtime_alert", "governance_drift", "kpi_watch", "decision_required"}


@dataclass
class ArtifactRecord:
    key: str
    path: str
    exists: bool
    kind: str
    source: str
    size_bytes: int = 0
    previewable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "path": self.path,
            "exists": self.exists,
            "kind": self.kind,
            "source": self.source,
            "size_bytes": self.size_bytes,
            "previewable": self.previewable,
        }


@dataclass
class VerifySummary:
    status: str
    overall: str
    issue_count: int
    qa_rows: List[str]
    exists: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "overall": self.overall,
            "issue_count": self.issue_count,
            "qa_rows": list(self.qa_rows),
            "exists": self.exists,
        }


@dataclass
class IssueSummary:
    total: int
    by_severity: Dict[str, int]
    by_stage: Dict[str, int]
    top: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total,
            "by_severity": dict(self.by_severity),
            "by_stage": dict(self.by_stage),
            "top": list(self.top),
        }


@dataclass
class RunStageView:
    name: str
    status: str
    required: bool
    files: List[Dict[str, Any]]
    missing_required_files: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "required": self.required,
            "files": list(self.files),
            "missing_required_files": list(self.missing_required_files),
        }


@dataclass
class RunSummary:
    run_id: str
    run_dir: str
    manifest_path: str
    overall_status: str
    manifest_status: str
    verify_mode: str
    target_lang: str
    started_at: str
    stage_counts: Dict[str, int]
    issue_count: int
    warning_count: int
    pending: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "run_dir": self.run_dir,
            "manifest_path": self.manifest_path,
            "overall_status": self.overall_status,
            "manifest_status": self.manifest_status,
            "verify_mode": self.verify_mode,
            "target_lang": self.target_lang,
            "started_at": self.started_at,
            "stage_counts": dict(self.stage_counts),
            "issue_count": self.issue_count,
            "warning_count": self.warning_count,
            "pending": self.pending,
        }


@dataclass
class RunDetail:
    run_id: str
    run_dir: str
    manifest_path: str
    overall_status: str
    manifest_status: str
    verify_mode: str
    target_lang: str
    started_at: str
    input_csv: str
    row_checks: Dict[str, Any]
    stages: List[RunStageView]
    verify: VerifySummary
    issue_summary: IssueSummary
    artifacts: Dict[str, ArtifactRecord]
    allowed_artifact_keys: List[str]
    pending: bool = False
    command: List[str] | None = None
    pid: Optional[int] = None

    @property
    def stage_counts(self) -> Dict[str, int]:
        return dict(Counter(stage.status for stage in self.stages))

    @property
    def issue_count(self) -> int:
        return self.issue_summary.total

    @property
    def warning_count(self) -> int:
        return sum(
            count for severity, count in self.issue_summary.by_severity.items() if severity not in {"P0", "P1"}
        )

    def to_summary(self) -> RunSummary:
        return RunSummary(
            run_id=self.run_id,
            run_dir=self.run_dir,
            manifest_path=self.manifest_path,
            overall_status=self.overall_status,
            manifest_status=self.manifest_status,
            verify_mode=self.verify_mode,
            target_lang=self.target_lang,
            started_at=self.started_at,
            stage_counts=self.stage_counts,
            issue_count=self.issue_count,
            warning_count=self.warning_count,
            pending=self.pending,
        )

    def to_dict(self) -> Dict[str, Any]:
        data = self.to_summary().to_dict()
        data.update(
            {
                "input_csv": self.input_csv,
                "row_checks": dict(self.row_checks),
                "stages": [stage.to_dict() for stage in self.stages],
                "verify": self.verify.to_dict(),
                "issue_summary": self.issue_summary.to_dict(),
                "artifacts": [artifact.to_dict() for artifact in self.artifacts.values()],
                "allowed_artifact_keys": list(self.allowed_artifact_keys),
                "pending": self.pending,
                "command": list(self.command or []),
                "pid": self.pid,
            }
        )
        return data


@dataclass
class WorkspaceCardView:
    card_id: str
    run_id: str
    card_type: str
    priority: str
    status: str
    title: str
    summary: str
    target_locale: str
    recommended_actions: List[str]
    artifact_refs: Dict[str, str]
    evidence_refs: List[str]
    adr_refs: List[str]
    owner: str
    started_at: str
    overall_status: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "card_id": self.card_id,
            "run_id": self.run_id,
            "card_type": self.card_type,
            "priority": self.priority,
            "status": self.status,
            "title": self.title,
            "summary": self.summary,
            "target_locale": self.target_locale,
            "recommended_actions": list(self.recommended_actions),
            "artifact_refs": dict(self.artifact_refs),
            "evidence_refs": list(self.evidence_refs),
            "adr_refs": list(self.adr_refs),
            "owner": self.owner,
            "started_at": self.started_at,
            "overall_status": self.overall_status,
        }


@dataclass
class WorkspaceOverview:
    open_card_count: int
    open_case_count: int
    runs_with_open_cards: int
    open_review_tickets: int
    runs_with_drift: int
    runtime_health_counts: Dict[str, int]
    case_counts_by_lane: Dict[str, int]
    recent_runs: List[RunSummary]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "open_card_count": self.open_card_count,
            "open_case_count": self.open_case_count,
            "runs_with_open_cards": self.runs_with_open_cards,
            "open_review_tickets": self.open_review_tickets,
            "runs_with_drift": self.runs_with_drift,
            "runtime_health_counts": dict(self.runtime_health_counts),
            "case_counts_by_lane": dict(self.case_counts_by_lane),
            "recent_runs": [run.to_dict() for run in self.recent_runs],
        }


@dataclass
class WorkspaceCaseView:
    case_id: str
    run_id: str
    lane: str
    status: str
    priority: str
    headline: str
    summary: str
    target_locale: str
    runtime_status: str
    open_card_count: int
    card_type_counts: Dict[str, int]
    next_action: str
    started_at: str
    has_persisted_operator_artifacts: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "run_id": self.run_id,
            "lane": self.lane,
            "status": self.status,
            "priority": self.priority,
            "headline": self.headline,
            "summary": self.summary,
            "target_locale": self.target_locale,
            "runtime_status": self.runtime_status,
            "open_card_count": self.open_card_count,
            "card_type_counts": dict(self.card_type_counts),
            "next_action": self.next_action,
            "started_at": self.started_at,
            "has_persisted_operator_artifacts": self.has_persisted_operator_artifacts,
        }


@dataclass
class WorkspaceRunDetail:
    run_id: str
    operator_summary: Dict[str, Any]
    cards: List[WorkspaceCardView]
    review_workload: Dict[str, Any]
    kpi_snapshot: Dict[str, Any]
    governance_drift: Dict[str, Any]
    decision_context: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "operator_summary": dict(self.operator_summary),
            "cards": [card.to_dict() for card in self.cards],
            "review_workload": dict(self.review_workload),
            "kpi_snapshot": dict(self.kpi_snapshot),
            "governance_drift": dict(self.governance_drift),
            "decision_context": dict(self.decision_context),
        }


def _read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            parsed = json.loads(line)
            if isinstance(parsed, dict):
                rows.append(parsed)
    except Exception:
        return []
    return rows


def _infer_repo_root(manifest_path: Path) -> Path:
    current = manifest_path.resolve().parent
    for parent in [current] + list(current.parents):
        if parent.name == "data":
            return parent.parent
    return manifest_path.resolve().parents[1]


def _resolve_path(raw_path: str, repo_root: Path, run_dir: Path) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return candidate
    repo_candidate = repo_root / candidate
    if repo_candidate.exists():
        return repo_candidate
    return run_dir / candidate


def _artifact_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in JSON_SUFFIXES:
        return "json"
    if suffix in TEXT_SUFFIXES:
        return "text"
    return "binary"


def _is_previewable(path: Path) -> bool:
    return _artifact_kind(path) in {"json", "text"}


def _normalize_stage_status(raw_status: str, missing_required_files: List[str], required: bool) -> str:
    lowered = (raw_status or "").strip().lower()
    if lowered in {"fail", "failed", "error", "blocked"}:
        return "fail"
    if missing_required_files and required:
        return "fail"
    if lowered in {"warn", "warning"}:
        return "warn"
    if lowered in {"pass", "passed", "success", "ok"}:
        return "pass"
    if lowered in {"running", "in_progress", "pending"}:
        return "running"
    if missing_required_files:
        return "warn"
    return "unknown"


def _normalize_stage(stage: Dict[str, Any], repo_root: Path, run_dir: Path) -> RunStageView:
    files: List[Dict[str, Any]] = []
    missing_required_files: List[str] = []
    for item in stage.get("files", []) or []:
        raw_path = item.get("path") if isinstance(item, dict) else str(item)
        required = True if not isinstance(item, dict) else bool(item.get("required", True))
        resolved = _resolve_path(str(raw_path), repo_root, run_dir)
        exists = resolved.exists()
        files.append({"path": str(resolved), "required": required, "exists": exists})
        if required and not exists:
            missing_required_files.append(str(resolved))

    required = bool(stage.get("required", True))
    status = _normalize_stage_status(str(stage.get("status", "")), missing_required_files, required)
    return RunStageView(
        name=str(stage.get("name", "Unknown Stage")),
        status=status,
        required=required,
        files=files,
        missing_required_files=missing_required_files,
    )


def _first_candidate(candidates: Iterable[Path]) -> Path:
    for path in candidates:
        return path
    raise ValueError("expected at least one candidate path")


def _candidate_issue_paths(manifest: Dict[str, Any], repo_root: Path, run_dir: Path, run_id: str) -> Iterable[Path]:
    manifest_issue = str(manifest.get("issue_file", "")).strip()
    if manifest_issue:
        yield _resolve_path(manifest_issue, repo_root, run_dir)
    yield run_dir / "smoke_issues.json"
    yield repo_root / "reports" / f"smoke_issues_{run_id}.json"


def _candidate_verify_paths(manifest: Dict[str, Any], repo_root: Path, run_dir: Path, run_id: str) -> Iterable[Path]:
    artifacts = manifest.get("artifacts", {}) if isinstance(manifest.get("artifacts"), dict) else {}
    verify_path = str(artifacts.get("smoke_verify_report", "")).strip()
    if verify_path:
        yield _resolve_path(verify_path, repo_root, run_dir)
    yield run_dir / f"smoke_verify_{run_id}.json"
    yield repo_root / "reports" / f"smoke_verify_{run_id}.json"


def _pick_existing_path(candidates: Iterable[Path]) -> Optional[Path]:
    for path in candidates:
        if path.exists():
            return path
    return None


def _summarize_issues(issue_report: Dict[str, Any]) -> IssueSummary:
    issues = issue_report.get("issues", []) if isinstance(issue_report, dict) else []
    severity_counter: Counter[str] = Counter()
    stage_counter: Counter[str] = Counter()
    top: List[Dict[str, Any]] = []
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        severity = str(issue.get("severity", "UNKNOWN")).upper()
        stage = str(issue.get("stage", "unknown"))
        severity_counter[severity] += 1
        stage_counter[stage] += 1
        top.append(
            {
                "severity": severity,
                "stage": stage,
                "error_code": str(issue.get("error_code", "")),
                "suggestion": str(issue.get("suggestion") or issue.get("suggest") or ""),
            }
        )
    return IssueSummary(
        total=sum(severity_counter.values()),
        by_severity=dict(severity_counter),
        by_stage=dict(stage_counter),
        top=top[:10],
    )


def _summarize_verify(verify_report: Dict[str, Any], exists: bool) -> VerifySummary:
    if not isinstance(verify_report, dict) or not verify_report:
        return VerifySummary(status="UNKNOWN", overall="UNKNOWN", issue_count=0, qa_rows=[], exists=exists)
    return VerifySummary(
        status=str(verify_report.get("status", "UNKNOWN")),
        overall=str(verify_report.get("overall", verify_report.get("status", "UNKNOWN"))),
        issue_count=int(verify_report.get("issue_count", 0) or 0),
        qa_rows=list(verify_report.get("qa_rows", []) or []),
        exists=exists,
    )


def _derive_overall_status(
    manifest_status: str,
    stages: List[RunStageView],
    verify: VerifySummary,
    pending: bool = False,
) -> str:
    lowered_manifest = (manifest_status or "").strip().lower()
    verify_status = verify.status.upper()
    stage_statuses = [stage.status for stage in stages]

    if pending or lowered_manifest in {"running", "pending"}:
        return "running"
    if verify_status == "FAIL" or lowered_manifest in {"fail", "failed"} or "fail" in stage_statuses:
        return "fail"
    if verify_status == "WARN" or "warn" in stage_statuses:
        return "warn"
    if verify_status == "PASS":
        return "pass"
    if lowered_manifest in {"success", "pass", "completed"} and stage_statuses and all(status == "pass" for status in stage_statuses):
        return "pass"
    return "unknown"


def _build_artifact_records(
    manifest: Dict[str, Any],
    manifest_path: Path,
    verify_path: Path,
    issue_path: Path,
    repo_root: Path,
    run_dir: Path,
) -> Dict[str, ArtifactRecord]:
    artifact_index: Dict[str, ArtifactRecord] = {}

    def add_artifact(key: str, raw_path: str, source: str) -> None:
        resolved = _resolve_path(raw_path, repo_root, run_dir)
        exists = resolved.exists()
        artifact_index[key] = ArtifactRecord(
            key=key,
            path=str(resolved),
            exists=exists,
            kind=_artifact_kind(resolved),
            source=source,
            size_bytes=resolved.stat().st_size if exists else 0,
            previewable=_is_previewable(resolved),
        )

    add_artifact("run_manifest", str(manifest_path), "derived")

    artifacts = manifest.get("artifacts", {}) if isinstance(manifest.get("artifacts"), dict) else {}
    for key, value in artifacts.items():
        if isinstance(value, str) and value.strip():
            add_artifact(str(key), value, "manifest.artifacts")

    stage_artifacts = manifest.get("stage_artifacts", {}) if isinstance(manifest.get("stage_artifacts"), dict) else {}
    for key, value in stage_artifacts.items():
        if isinstance(value, str) and value.strip() and key not in artifact_index:
            add_artifact(str(key), value, "manifest.stage_artifacts")

    add_artifact("smoke_verify_report", str(verify_path), "derived")
    add_artifact("smoke_issues_report", str(issue_path), "derived")
    return artifact_index


def _list_manifest_paths(repo_root: Path) -> List[Path]:
    data_root = repo_root / "data"
    if not data_root.exists():
        return []
    return sorted(
        data_root.rglob("run_manifest.json"),
        key=lambda path: (
            str(_read_json(path).get("started_at", _read_json(path).get("timestamp", ""))),
            path.stat().st_mtime,
        ),
        reverse=True,
    )


def _operator_artifact_paths(repo_root: Path, run_id: str) -> tuple[Path, Path]:
    return (
        repo_root / "data" / "operator_cards" / run_id / "operator_cards.jsonl",
        repo_root / "data" / "operator_reports" / run_id / "operator_summary.json",
    )


def _load_or_derive_operator_payload(repo_root: Path, run_detail: RunDetail) -> Dict[str, Any]:
    cards_path, summary_path = _operator_artifact_paths(repo_root, run_detail.run_id)
    persisted_cards = _read_jsonl(cards_path)
    persisted_summary = _read_json(summary_path)
    if persisted_cards and isinstance(persisted_summary, dict) and persisted_summary:
        return {
            "run_id": run_detail.run_id,
            "cards_path": str(cards_path),
            "summary_json_path": str(summary_path),
            "summary_md_path": str(summary_path.with_suffix(".md")),
            "open_card_count": int(persisted_summary.get("open_operator_cards", 0) or 0),
            "report": persisted_summary,
            "cards": persisted_cards,
            "has_persisted_operator_artifacts": True,
        }
    payload = derive_operator_artifacts(run_dir=run_detail.run_dir, repo_root=repo_root)
    payload["has_persisted_operator_artifacts"] = False
    return payload


def _priority_rank(priority: str) -> int:
    return {"P0": 0, "P1": 1, "P2": 2}.get(str(priority or "").upper(), 99)


def _status_rank(status: str) -> int:
    return {"open": 0, "closed": 1}.get(str(status or "").lower(), 99)


def _normalize_workspace_card(card: Dict[str, Any], run_detail: RunDetail) -> WorkspaceCardView:
    return WorkspaceCardView(
        card_id=str(card.get("card_id", "")),
        run_id=str(card.get("run_id", run_detail.run_id)),
        card_type=str(card.get("card_type", "")),
        priority=str(card.get("priority", "P2")),
        status=str(card.get("status", "open")),
        title=str(card.get("title", "")),
        summary=str(card.get("summary", "")),
        target_locale=str(card.get("target_locale", run_detail.target_lang or "unknown")),
        recommended_actions=list(card.get("recommended_actions", []) or []),
        artifact_refs={str(key): str(value) for key, value in dict(card.get("artifact_refs", {}) or {}).items()},
        evidence_refs=[str(item) for item in list(card.get("evidence_refs", []) or [])],
        adr_refs=[str(item) for item in list(card.get("adr_refs", []) or [])],
        owner=str(card.get("owner", "")),
        started_at=run_detail.started_at,
        overall_status=run_detail.overall_status,
    )


def _sorted_workspace_cards(cards: List[WorkspaceCardView]) -> List[WorkspaceCardView]:
    return sorted(
        cards,
        key=lambda card: (_status_rank(card.status), _priority_rank(card.priority), card.started_at, card.card_id),
    )


def _build_decision_context(cards: List[WorkspaceCardView], report: Dict[str, Any]) -> Dict[str, Any]:
    primary = _sorted_workspace_cards(cards)[0] if cards else None
    if primary is None:
        return {
            "card_id": "",
            "title": "No operator decision required",
            "summary": "This run currently has no operator cards requiring follow-up.",
            "recommended_actions": list(report.get("next_recommended_actions", []) or []),
            "artifact_refs": dict(report.get("artifact_refs", {}) or {}),
            "evidence_refs": list(report.get("evidence_refs", []) or []),
            "adr_refs": list(report.get("adr_refs", []) or []),
        }
    return {
        "card_id": primary.card_id,
        "title": primary.title,
        "summary": primary.summary,
        "recommended_actions": list(primary.recommended_actions),
        "artifact_refs": dict(primary.artifact_refs),
        "evidence_refs": list(primary.evidence_refs),
        "adr_refs": list(primary.adr_refs),
    }


def _workspace_case_cards(cards: List[WorkspaceCardView]) -> List[WorkspaceCardView]:
    open_cards = [card for card in cards if card.status == "open"]
    return open_cards or cards


def _workspace_case_primary_card(cards: List[WorkspaceCardView]) -> Optional[WorkspaceCardView]:
    relevant = _workspace_case_cards(cards)
    if not relevant:
        return None
    card_type_rank = {
        "runtime_alert": 0,
        "review_ticket": 1,
        "governance_drift": 2,
        "kpi_watch": 3,
        "decision_required": 4,
    }
    return sorted(
        relevant,
        key=lambda card: (
            card_type_rank.get(card.card_type, 99),
            _priority_rank(card.priority),
            _status_rank(card.status),
            card.card_id,
        ),
    )[0]


def _workspace_case_lane(cards: List[WorkspaceCardView], run_detail: RunDetail, report: Dict[str, Any]) -> str:
    open_cards = [card for card in cards if card.status == "open"]
    if not open_cards:
        return "done"
    if run_detail.overall_status in {"fail", "blocked"} or any(card.priority == "P0" for card in open_cards):
        return "act"
    pending_review_tickets = int(((report.get("open_review_workload") or {}).get("pending_review_tickets")) or 0)
    if pending_review_tickets > 0 or any(card.card_type == "review_ticket" for card in open_cards):
        return "review"
    return "watch"


def _workspace_case_summary(primary: WorkspaceCardView | None, report: Dict[str, Any], cards: List[WorkspaceCardView]) -> str:
    if primary and primary.summary:
        return primary.summary
    open_card_count = len([card for card in cards if card.status == "open"])
    if open_card_count:
        return f"{open_card_count} open operator signals require follow-up."
    return str((report.get("decision_context") or {}).get("summary") or "No open operator signals.")


def _workspace_case_next_action(primary: WorkspaceCardView | None, report: Dict[str, Any]) -> str:
    if primary and primary.recommended_actions:
        return str(primary.recommended_actions[0])
    report_actions = list(report.get("next_recommended_actions", []) or [])
    return str(report_actions[0]) if report_actions else ""


def _workspace_case_type_counts(cards: List[WorkspaceCardView]) -> Dict[str, int]:
    relevant = _workspace_case_cards(cards)
    counts: Counter[str] = Counter(card.card_type for card in relevant)
    return dict(counts)


def _build_workspace_case(run_detail: RunDetail, report: Dict[str, Any], cards: List[WorkspaceCardView], *, has_persisted_operator_artifacts: bool) -> Optional[WorkspaceCaseView]:
    if not cards:
        return None
    primary = _workspace_case_primary_card(cards)
    lane = _workspace_case_lane(cards, run_detail, report)
    status = "closed" if lane == "done" else "open"
    priority_source = _workspace_case_cards(cards)
    priority = sorted(priority_source, key=lambda card: _priority_rank(card.priority))[0].priority if priority_source else "P2"
    return WorkspaceCaseView(
        case_id=f"case:{run_detail.run_id}",
        run_id=run_detail.run_id,
        lane=lane,
        status=status,
        priority=priority,
        headline=primary.title if primary else run_detail.run_id,
        summary=_workspace_case_summary(primary, report, cards),
        target_locale=primary.target_locale if primary else (run_detail.target_lang or "unknown"),
        runtime_status=run_detail.overall_status,
        open_card_count=len([card for card in cards if card.status == "open"]),
        card_type_counts=_workspace_case_type_counts(cards),
        next_action=_workspace_case_next_action(primary, report),
        started_at=run_detail.started_at,
        has_persisted_operator_artifacts=has_persisted_operator_artifacts,
    )


def _validate_workspace_filters(status: str, card_type: str, priority: str) -> None:
    if status not in WORKSPACE_CARD_STATUSES:
        raise ValueError("status must be one of all/open/closed")
    if card_type and card_type not in WORKSPACE_CARD_TYPES:
        raise ValueError("card_type must be one of the operator_card contract enums")
    if priority and priority not in WORKSPACE_CARD_PRIORITIES:
        raise ValueError("priority must be one of P0/P1/P2")


def _validate_workspace_case_filters(status: str, lane: str) -> None:
    if status not in WORKSPACE_CASE_STATUSES:
        raise ValueError("status must be one of all/open")
    if lane not in WORKSPACE_CASE_LANES:
        raise ValueError("lane must be one of all/act/review/watch/done")


def load_workspace_run_detail(repo_root: Path | str, run_id: str) -> WorkspaceRunDetail:
    repo_root_path = Path(repo_root)
    run_detail = load_run_detail(find_run_manifest(repo_root_path, run_id), repo_root=repo_root_path)
    payload = _load_or_derive_operator_payload(repo_root_path, run_detail)
    cards = _sorted_workspace_cards([_normalize_workspace_card(card, run_detail) for card in payload["cards"]])
    report = dict(payload["report"])
    workspace = WorkspaceRunDetail(
        run_id=run_detail.run_id,
        operator_summary=report,
        cards=cards,
        review_workload=dict(report.get("open_review_workload", {}) or {}),
        kpi_snapshot=dict(report.get("kpi_snapshot", {}) or {}),
        governance_drift=dict(report.get("governance_drift_summary", {}) or {}),
        decision_context=_build_decision_context(cards, report),
    )
    return workspace


def load_workspace_cases(
    repo_root: Path | str,
    *,
    status: str = "open",
    lane: str = "all",
    target_locale: str = "",
    query: str = "",
    limit: int = 50,
) -> List[WorkspaceCaseView]:
    _validate_workspace_case_filters(status, lane)
    repo_root_path = Path(repo_root)
    lowered_query = str(query or "").strip().lower()
    lowered_target_locale = str(target_locale or "").strip().lower()
    cases: List[WorkspaceCaseView] = []
    for manifest_path in _list_manifest_paths(repo_root_path):
        run_detail = load_run_detail(manifest_path, repo_root=repo_root_path)
        payload = _load_or_derive_operator_payload(repo_root_path, run_detail)
        cards = _sorted_workspace_cards([_normalize_workspace_card(card, run_detail) for card in payload["cards"]])
        case = _build_workspace_case(
            run_detail,
            dict(payload["report"]),
            cards,
            has_persisted_operator_artifacts=bool(payload.get("has_persisted_operator_artifacts")),
        )
        if case is None:
            continue
        if status == "open" and case.status != "open":
            continue
        if lane != "all" and case.lane != lane:
            continue
        if lowered_target_locale and case.target_locale.lower() != lowered_target_locale:
            continue
        if lowered_query:
            haystack = " ".join([case.run_id, case.headline, case.summary, case.target_locale]).lower()
            if lowered_query not in haystack:
                continue
        cases.append(case)
    return sorted(
        cases,
        key=lambda case: (
            0 if case.status == "open" else 1,
            {"act": 0, "review": 1, "watch": 2, "done": 3}.get(case.lane, 99),
            _priority_rank(case.priority),
            case.started_at,
            case.case_id,
        ),
    )[: max(limit, 0)]


def load_workspace_cards(
    repo_root: Path | str,
    *,
    status: str = "open",
    card_type: str = "",
    priority: str = "",
    target_locale: str = "",
    limit: int = 50,
) -> List[WorkspaceCardView]:
    _validate_workspace_filters(status, card_type, priority)
    repo_root_path = Path(repo_root)
    cards: List[WorkspaceCardView] = []
    for manifest_path in _list_manifest_paths(repo_root_path):
        run_detail = load_run_detail(manifest_path, repo_root=repo_root_path)
        payload = _load_or_derive_operator_payload(repo_root_path, run_detail)
        for raw_card in payload["cards"]:
            card = _normalize_workspace_card(raw_card, run_detail)
            if status != "all" and card.status != status:
                continue
            if card_type and card.card_type != card_type:
                continue
            if priority and card.priority != priority:
                continue
            if target_locale and card.target_locale != target_locale:
                continue
            cards.append(card)
    return _sorted_workspace_cards(cards)[: max(limit, 0)]


def load_workspace_overview(repo_root: Path | str, limit_runs: int = 10) -> WorkspaceOverview:
    repo_root_path = Path(repo_root)
    runtime_health_counts: Counter[str] = Counter()
    open_card_count = 0
    open_case_count = 0
    runs_with_open_cards = 0
    runs_with_drift = 0
    open_review_tickets = 0
    case_counts_by_lane: Counter[str] = Counter()
    for manifest_path in _list_manifest_paths(repo_root_path):
        run_detail = load_run_detail(manifest_path, repo_root=repo_root_path)
        runtime_health_counts[run_detail.overall_status] += 1
        payload = _load_or_derive_operator_payload(repo_root_path, run_detail)
        cards = [_normalize_workspace_card(card, run_detail) for card in payload["cards"]]
        open_cards = [card for card in cards if card.status == "open"]
        open_card_count += len(open_cards)
        if open_cards:
            runs_with_open_cards += 1
        if any(card.card_type == "governance_drift" and card.status == "open" for card in cards):
            runs_with_drift += 1
        open_review_tickets += sum(1 for card in open_cards if card.card_type == "review_ticket")
        case = _build_workspace_case(
            run_detail,
            dict(payload["report"]),
            _sorted_workspace_cards(cards),
            has_persisted_operator_artifacts=bool(payload.get("has_persisted_operator_artifacts")),
        )
        if case is not None:
            case_counts_by_lane[case.lane] += 1
            if case.status == "open":
                open_case_count += 1
    overview = WorkspaceOverview(
        open_card_count=open_card_count,
        open_case_count=open_case_count,
        runs_with_open_cards=runs_with_open_cards,
        open_review_tickets=open_review_tickets,
        runs_with_drift=runs_with_drift,
        runtime_health_counts=dict(runtime_health_counts),
        case_counts_by_lane=dict(case_counts_by_lane),
        recent_runs=load_run_summaries(repo_root_path, limit=limit_runs),
    )
    return overview


def find_run_manifest(repo_root: Path | str, run_id: str) -> Path:
    repo_root_path = Path(repo_root)
    data_root = repo_root_path / "data"
    for manifest_path in data_root.rglob("run_manifest.json"):
        manifest = _read_json(manifest_path)
        if str(manifest.get("run_id", manifest_path.parent.name)) == run_id:
            return manifest_path
    raise FileNotFoundError(run_id)


def load_run_detail(manifest_path: Path | str, repo_root: Path | str | None = None) -> RunDetail:
    manifest_path = Path(manifest_path)
    repo_root_path = Path(repo_root) if repo_root is not None else _infer_repo_root(manifest_path)
    manifest = _read_json(manifest_path)
    run_id = str(manifest.get("run_id", manifest_path.parent.name))
    run_dir = _resolve_path(str(manifest.get("run_dir", manifest_path.parent)), repo_root_path, manifest_path.parent)

    stages = [_normalize_stage(stage, repo_root_path, run_dir) for stage in manifest.get("stages", []) or []]

    verify_candidates = list(_candidate_verify_paths(manifest, repo_root_path, run_dir, run_id))
    issue_candidates = list(_candidate_issue_paths(manifest, repo_root_path, run_dir, run_id))
    verify_path = _pick_existing_path(verify_candidates) or _first_candidate(verify_candidates)
    issue_path = _pick_existing_path(issue_candidates) or _first_candidate(issue_candidates)

    verify = _summarize_verify(_read_json(verify_path), verify_path.exists())
    issue_summary = _summarize_issues(_read_json(issue_path) if issue_path.exists() else {})
    artifacts = _build_artifact_records(manifest, manifest_path, verify_path, issue_path, repo_root_path, run_dir)

    return RunDetail(
        run_id=run_id,
        run_dir=str(run_dir),
        manifest_path=str(manifest_path),
        overall_status=_derive_overall_status(str(manifest.get("status", "")), stages, verify),
        manifest_status=str(manifest.get("status", "")),
        verify_mode=str(manifest.get("verify_mode", "")),
        target_lang=str(manifest.get("target_lang", "")),
        started_at=str(manifest.get("started_at", manifest.get("timestamp", ""))),
        input_csv=str(manifest.get("input_csv", "")),
        row_checks=manifest.get("row_checks", {}) if isinstance(manifest.get("row_checks"), dict) else {},
        stages=stages,
        verify=verify,
        issue_summary=issue_summary,
        artifacts=artifacts,
        allowed_artifact_keys=sorted(artifacts.keys()),
    )


def build_pending_run_detail(pending_run: Dict[str, Any]) -> RunDetail:
    return RunDetail(
        run_id=str(pending_run.get("run_id", "")),
        run_dir=str(pending_run.get("run_dir", "")),
        manifest_path="",
        overall_status=str(pending_run.get("status", "running")),
        manifest_status=str(pending_run.get("status", "running")),
        verify_mode=str(pending_run.get("verify_mode", "")),
        target_lang=str(pending_run.get("target_lang", "")),
        started_at=str(pending_run.get("started_at", "")),
        input_csv=str(pending_run.get("input_csv", pending_run.get("input", ""))),
        row_checks={},
        stages=[],
        verify=VerifySummary(status="PENDING", overall="PENDING", issue_count=0, qa_rows=[], exists=False),
        issue_summary=IssueSummary(total=0, by_severity={}, by_stage={}, top=[]),
        artifacts={},
        allowed_artifact_keys=[],
        pending=True,
        command=list(pending_run.get("command", [])),
        pid=pending_run.get("pid"),
    )


def load_run_summaries(repo_root: Path | str, limit: int = 10) -> List[RunSummary]:
    repo_root_path = Path(repo_root)
    data_root = repo_root_path / "data"
    if not data_root.exists():
        return []

    manifests = sorted(
        data_root.rglob("run_manifest.json"),
        key=lambda path: (
            str(_read_json(path).get("started_at", _read_json(path).get("timestamp", ""))),
            path.stat().st_mtime,
        ),
        reverse=True,
    )

    summaries: List[RunSummary] = []
    for manifest_path in manifests[: max(limit, 0)]:
        summaries.append(load_run_detail(manifest_path, repo_root=repo_root_path).to_summary())
    return summaries


def list_run_summaries(repo_root: Path | str, limit: int = 10) -> List[RunSummary]:
    return load_run_summaries(repo_root, limit=limit)
