#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""View models and artifact helpers for the Phase 5 runtime shell."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


TEXT_SUFFIXES = {".log", ".txt", ".md", ".py", ".yaml", ".yml", ".csv"}
JSON_SUFFIXES = {".json", ".jsonl"}


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


def _read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return {}


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
