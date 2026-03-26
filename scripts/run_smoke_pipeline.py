#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smoke Pipeline Orchestrator (E2E full pass with run manifest + issue record).

This script is designed for pragmatic smoke execution:
normalize -> translate -> qa_hard -> rehydrate -> verify
with optional target-language fallback (EN -> RU).
"""

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
    from scripts.smoke_issue_logger import append_issue, build_issue
except ImportError:  # pragma: no cover
    from smoke_issue_logger import append_issue, build_issue
try:
    from scripts.review_governance import (
        build_kpi_report,
        build_review_tickets,
        ensure_feedback_log,
        load_feedback_log,
        load_lifecycle_registry,
        load_review_ticket_contract,
        write_json as governance_write_json,
        write_jsonl as governance_write_jsonl,
    )
except ImportError:  # pragma: no cover
    from review_governance import (
        build_kpi_report,
        build_review_tickets,
        ensure_feedback_log,
        load_feedback_log,
        load_lifecycle_registry,
        load_review_ticket_contract,
        write_json as governance_write_json,
        write_jsonl as governance_write_jsonl,
    )
try:
    from scripts.style_governance_runtime import evaluate_runtime_governance, format_runtime_governance_issues
except ImportError:  # pragma: no cover
    from style_governance_runtime import evaluate_runtime_governance, format_runtime_governance_issues


REPO_ROOT = Path(__file__).resolve().parent.parent


class GovernanceError(RuntimeError):
    pass


def _repo_relative(path: str) -> str:
    raw = Path(path)
    resolved = raw if raw.is_absolute() else (REPO_ROOT / raw).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def _is_repo_managed(path: str) -> bool:
    try:
        (Path(path) if Path(path).is_absolute() else (REPO_ROOT / path).resolve()).relative_to(REPO_ROOT)
        return True
    except ValueError:
        return False


def _find_lifecycle_entry(asset_path: str, lifecycle_registry_path: str) -> Dict[str, Any]:
    registry = load_lifecycle_registry(lifecycle_registry_path)
    normalized = _repo_relative(asset_path)
    for entry in registry.get("entries", []) or []:
        if not isinstance(entry, dict):
            continue
        if _repo_relative(str(entry.get("asset_path") or "")) == normalized:
            return entry
    return {}


def validate_governed_asset(asset_path: str, asset_kind: str, *, lifecycle_registry_path: str) -> Dict[str, Any]:
    if not Path(asset_path).exists():
        raise GovernanceError(f"missing governed asset: {asset_path}")
    if not _is_repo_managed(asset_path):
        return {}
    entry = _find_lifecycle_entry(asset_path, lifecycle_registry_path)
    if not entry:
        raise GovernanceError(f"missing lifecycle registry entry for {_repo_relative(asset_path)}")
    expected_kind = "policy" if asset_kind in {"policy", "rubric"} else asset_kind
    actual_kind = str(entry.get("asset_kind") or "")
    if actual_kind != expected_kind:
        raise GovernanceError(
            f"lifecycle asset kind mismatch for {_repo_relative(asset_path)}: expected {expected_kind}, got {actual_kind}"
        )
    if str(entry.get("status") or "") != "approved":
        raise GovernanceError(f"governed asset is not approved: {_repo_relative(asset_path)}")
    return entry


def validate_style_governance_runtime(style_profile_path: str, *, lifecycle_registry_path: str) -> Dict[str, Any]:
    if not Path(style_profile_path).exists():
        raise GovernanceError(f"style profile missing or invalid: {style_profile_path}")
    if not _is_repo_managed(style_profile_path):
        return {
            "passed": True,
            "style_profile_path": str(style_profile_path),
            "asset_statuses": {},
            "issues": [],
        }
    report = evaluate_runtime_governance(
        style_profile_path=style_profile_path,
        lifecycle_registry_path=lifecycle_registry_path,
        policy_paths=["workflow/style_governance_contract.yaml"],
    )
    if not report["passed"]:
        raise GovernanceError(format_runtime_governance_issues(report))
    return report


def _review_ticket_fieldnames(tickets: List[Dict[str, Any]]) -> List[str]:
    required = list(load_review_ticket_contract().get("required_fields", []) or [])
    extras: List[str] = []
    for ticket in tickets:
        for key in ticket.keys():
            if key not in required and key not in extras:
                extras.append(key)
    return [*required, *extras]


def write_review_tickets(jsonl_path: str, csv_path: str, tickets: List[Dict[str, Any]]) -> None:
    governance_write_jsonl(jsonl_path, tickets)
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
    if not rows:
        rows = []
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


REVIEW_QUEUE_FIELDS = [
    "task_id",
    "string_id",
    "task_type",
    "review_owner",
    "review_status",
    "review_source",
    "queue_reason",
    "execution_status",
    "final_status",
    "status_reason",
    "reason_codes",
    "manual_review_reason",
    "current_target",
]


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _safe_stage_name(name: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name.lower().replace(" ", "_"))


def _run_step(cmd: list, log_path: Path, env: dict = None) -> subprocess.CompletedProcess:
    run_env = dict(os.environ)
    if env:
        run_env.update(env)

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"command: {cmd}\n")
        f.write(f"started: {datetime.now(timezone.utc).isoformat()}\n\n")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=run_env,
    )

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"returncode: {result.returncode}\n\n")
        f.write("---- STDOUT ----\n")
        f.write(result.stdout or "")
        f.write("\n---- STDERR ----\n")
        f.write(result.stderr or "")
    return result


def _derive_target_key(target_lang: str) -> str:
    if not target_lang:
        return "target_ru"
    norm = target_lang.split("-", 1)[0].strip().lower().replace("_", "")
    return f"target_{norm}" if norm else "target_ru"


def _count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return max(0, sum(1 for _ in csv.reader(f)) - 1)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _append_stage(
    manifest: dict,
    name: str,
    files: list,
    status: str,
    required: bool = True,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    normalized_files = []
    for item in files:
        if isinstance(item, dict):
            normalized_files.append({
                "path": str(item.get("path", "")),
                "required": bool(item.get("required", True)),
            })
            continue
        normalized_files.append({"path": str(item), "required": True})
    stage = {
        "name": name,
        "status": status,
        "required": required,
        "files": normalized_files,
    }
    if details:
        stage["details"] = details
    manifest["stages"].append(stage)


def _write_manifest(manifest_path: Path, manifest: dict) -> None:
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def _append_artifact(manifest: dict, name: str, path: Path) -> None:
    manifest.setdefault("artifacts", {})
    manifest["artifacts"][name] = str(path)


def _append_stage_artifact(manifest: dict, name: str, path: Path) -> None:
    manifest.setdefault("stage_artifacts", {})
    manifest["stage_artifacts"][name] = str(path)


def _set_manifest_artifact(manifest: dict, name: str, value: Any) -> None:
    manifest.setdefault("artifacts", {})
    manifest["artifacts"][name] = value


def _read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                rows.append(payload)
    return rows


def _read_csv_rows(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_review_queue(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REVIEW_QUEUE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _dedupe_review_queue(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    deduped: List[Dict[str, str]] = []
    seen = set()
    for row in rows:
        key = (row.get("task_id", ""), row.get("review_source", ""), row.get("status_reason", ""))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _build_review_queue_entry(
    *,
    string_id: str,
    review_source: str,
    queue_reason: str,
    current_target: str,
    task_type: str = "manual_review",
    execution_status: str = "review_handoff",
    final_status: str = "review_handoff",
    reason_codes: Optional[List[str]] = None,
    manual_review_reason: str = "",
) -> Dict[str, str]:
    status_reason = queue_reason or review_source
    return {
        "task_id": f"{task_type}:{string_id or review_source}",
        "string_id": string_id,
        "task_type": task_type,
        "review_owner": "human-linguist",
        "review_status": "pending",
        "review_source": review_source,
        "queue_reason": queue_reason or review_source,
        "execution_status": execution_status,
        "final_status": final_status,
        "status_reason": status_reason,
        "reason_codes": json.dumps(reason_codes or [], ensure_ascii=False),
        "manual_review_reason": manual_review_reason or queue_reason or review_source,
        "current_target": current_target,
    }


def _review_handoff_summary(rows: List[Dict[str, str]], queue_path: Path) -> Dict[str, Any]:
    by_source: Dict[str, int] = {}
    string_ids: List[str] = []
    for row in rows:
        source = str(row.get("review_source") or "")
        if source:
            by_source[source] = by_source.get(source, 0) + 1
        string_id = str(row.get("string_id") or "")
        if string_id:
            string_ids.append(string_id)
    return {
        "queue_path": str(queue_path),
        "pending_count": len(rows),
        "string_ids": sorted(dict.fromkeys(string_ids)),
        "by_source": by_source,
        "items": rows,
    }


def _normalize_review_ticket_queue_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    normalized: List[Dict[str, str]] = []
    for row in rows:
        item = dict(row)
        task_id = str(item.get("task_id") or "")
        review_source = str(item.get("review_source") or "manual_review")
        if not task_id:
            task_id = f"manual_review:{item.get('string_id') or review_source}"
            item["task_id"] = task_id
        if not str(item.get("string_id") or ""):
            item["string_id"] = str(task_id.split(":", 1)[-1] or review_source)
        if not str(item.get("review_status") or "") or str(item.get("review_status") or "") == "not_required":
            item["review_status"] = "pending"
        if not str(item.get("current_target") or ""):
            item["current_target"] = "[manual review required]"
        reason_codes = item.get("reason_codes")
        if isinstance(reason_codes, str):
            stripped = reason_codes.strip()
            if stripped in {"", "[]"}:
                item["reason_codes"] = json.dumps([review_source.upper()], ensure_ascii=False)
        elif not reason_codes:
            item["reason_codes"] = json.dumps([review_source.upper()], ensure_ascii=False)
        normalized.append(item)
    return normalized


def _build_review_ticket_task_lookup(rows: List[Dict[str, str]], target_locale: str) -> Dict[str, Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {}
    high_risk_sources = {"post_gate_blocked", "execution_failure", "soft_qa_hard_gate", "soft_repair_rollback"}
    for row in rows:
        task_id = str(row.get("task_id") or "")
        if not task_id:
            continue
        review_source = str(row.get("review_source") or "")
        risk_level = "high" if review_source in high_risk_sources else "medium"
        lookup[task_id] = {
            "task_id": task_id,
            "target_locale": target_locale,
            "content_class": "general",
            "risk_level": risk_level,
            "target_constraints": {
                "content_class": "general",
                "risk_level": risk_level,
            },
        }
    return lookup


def _extract_current_target(row: Dict[str, Any], fallback: str = "") -> str:
    preferred_keys = ["target_text", "target", "target_ru", "target_en"]
    dynamic_target_keys = [
        key for key in row.keys()
        if key.startswith("target_") and key not in preferred_keys
    ]
    for key in preferred_keys + sorted(dynamic_target_keys):
        value = str(row.get(key) or "")
        if value:
            return value
    return fallback


def _derive_overall_status(stages: List[Dict[str, Any]], gate_summary: Dict[str, Any], review_queue: List[Dict[str, str]]) -> str:
    if gate_summary.get("status") == "failed":
        return "failed"
    if gate_summary.get("status") == "blocked":
        return "blocked"
    if any(str(stage.get("status") or "") == "fail" and bool(stage.get("required", True)) for stage in stages):
        return "failed"
    if review_queue or any(str(stage.get("status") or "") == "warn" for stage in stages):
        return "warn"
    return "pass"


def _stage_status_counts(stages: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for stage in stages:
        status = str(stage.get("status") or "")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _qa_stage_status(returncode: int, has_errors: bool, actionable_warning_total: int) -> str:
    if returncode != 0 or has_errors:
        return "block"
    if actionable_warning_total > 0:
        return "warn"
    return "pass"


def _make_manifest(args: argparse.Namespace, run_id: str, input_csv: Path, run_dir: Path, issue_file: Path) -> dict:
    started = datetime.now(timezone.utc)
    return {
        "run_id": run_id,
        "timestamp": started.isoformat(),
        "manifest_version": "smoke-manifest-v1",
        "status_contract_version": "phase1-runtime-v1",
        "project": "game-localization-mvr",
        "run_dir": str(run_dir.resolve()),
        "input_csv": str(input_csv),
        "target_lang": args.target_lang,
        "target_key": _derive_target_key(args.target_lang),
        "fallback_target_lang": args.fallback_target_lang,
        "fallback_enabled": bool(args.enable_target_fallback),
        "verify_mode": args.verify_mode,
        "status": "running",
        "issue_file": str(issue_file),
        "artifacts": {
            "style_guide": args.style,
            "style_profile": args.style_profile,
            "lifecycle_registry": getattr(args, "lifecycle_registry", "workflow/lifecycle_registry.yaml"),
            "schema": args.schema,
            "forbidden_patterns": args.forbidden,
            "glossary": args.glossary,
            "soft_qa_rubric": getattr(args, "soft_qa_rubric", "workflow/soft_qa_rubric.yaml"),
            "model": args.model,
        },
        "delivery_columns": [],
        "normalize_options": {
            "source_lang": args.source_lang,
            "long_text_threshold": args.long_text_threshold,
        },
        "stage_artifacts": {},
        "row_counts": {
            "input": 0
        },
        "row_checks": {},
        "repair_cycles": {
            "hard": {"status": "skipped", "task_count": 0, "escalation_count": 0},
            "soft": {"status": "skipped", "task_count": 0, "escalation_count": 0},
        },
        "review_handoff": {
            "queue_path": "",
            "pending_count": 0,
            "string_ids": [],
            "by_source": {},
            "items": [],
        },
        "gate_summary": {
            "status": "running",
            "failed_gates": [],
            "blocking_stage": "",
        },
        "delivery_decision": {
            "selected_candidate_csv": "",
            "selected_candidate_stage": "",
            "rollback_used": False,
            "rollback_reason": "",
        },
        "stages": [],
        "started_at": started.isoformat()
    }


def _write_row_checks(manifest: dict, input_rows: int, translate_rows: int, final_rows: int) -> None:
    manifest["row_checks"] = {
        "input_rows": input_rows,
        "translate_rows": translate_rows,
        "final_rows": final_rows,
        "translate_delta": translate_rows - input_rows,
        "final_delta": final_rows - input_rows,
    }


def _resolve_style_profile_path(path: str) -> str:
    if path and path.strip():
        return path
    for candidate in ("workflow/style_profile.generated.yaml", "data/style_profile.yaml"):
        if Path(candidate).exists():
            return candidate
    return "workflow/style_profile.generated.yaml"


def _ensure_style_profile(path: str, log_path: Path) -> tuple[bool, str]:
    style_profile_path = Path(path)
    if style_profile_path.exists():
        return True, str(style_profile_path)

    questionnaire = Path("workflow/style_guide_questionnaire.md")
    if not questionnaire.exists():
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(f"style_profile_missing: {path}\n")
            f.write(f"questionnaire_missing: {questionnaire}\n")
        return False, str(style_profile_path)

    guide_output = Path("workflow/style_guide.generated.md")
    cmd = [
        sys.executable,
        "scripts/style_guide_bootstrap.py",
        "--questionnaire",
        str(questionnaire),
        "--guide-output",
        str(guide_output),
        "--profile-output",
        str(style_profile_path),
        "--dry-run",
    ]
    result = _run_step(cmd, log_path)
    return result.returncode == 0 and style_profile_path.exists(), str(style_profile_path)


def _issue_row_mismatch(run_id: str, issue_file: Path, stage: str, expected: int, actual: int, note: str) -> None:
    append_issue(str(issue_file), build_issue(
        run_id=run_id,
        stage=stage,
        severity="P0",
        error_code="ROW_COUNT_MISMATCH",
        context={
            "expected_rows": expected,
            "actual_rows": actual,
            "delta": actual - expected,
            "note": note,
        },
        suggest="检查输入/输出 CSV 行数一致性，避免丢行。"
    ))


def _run_metrics_stage(
    manifest: dict,
    run_id: str,
    run_dir: Path,
    issue_file: Path,
) -> None:
    metrics_log = run_dir / f"06_{_safe_stage_name('metrics')}.log"
    metrics_output_base = run_dir / "smoke_metrics_report"
    metrics_md = run_dir / "smoke_metrics_report.md"
    metrics_json = run_dir / "smoke_metrics_report.json"
    metrics_script = Path("scripts") / "metrics_aggregator.py"
    reports_dir = run_dir
    trace_path = run_dir / "llm_trace.jsonl"
    progress_logs = sorted(reports_dir.glob("*_progress.jsonl")) if reports_dir.exists() else []
    trace_exists = trace_path.exists()

    _append_stage(
        manifest,
        "Metrics",
        [
            {"path": str(metrics_md), "required": False},
            {"path": str(metrics_json), "required": False},
        ],
        "skip",
        required=False,
    )
    _append_stage_artifact(manifest, "metrics_log", metrics_log)
    _append_stage_artifact(manifest, "metrics_report_md", metrics_md)
    _append_stage_artifact(manifest, "metrics_report_json", metrics_json)
    _set_manifest_artifact(manifest, "metrics_report", [str(metrics_md), str(metrics_json)])
    _set_manifest_artifact(manifest, "metrics_report_json", str(metrics_json))
    manifest["metrics_status"] = {
        "stage": "metrics",
        "script": str(metrics_script),
        "reports_dir": str(reports_dir),
        "trace_path": str(trace_path),
        "progress_log_count": len(progress_logs),
        "trace_exists": trace_exists,
        "status": "skipped",
    }

    if not metrics_script.exists():
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="metrics",
            severity="P2",
            error_code="METRICS_SCRIPT_MISSING",
            context={"script": str(metrics_script)},
            suggest="恢复 metrics_aggregator.py 后再启用 smoke metrics。"
        ))
        return

    if not progress_logs:
        return

    metrics = _run_step([
        sys.executable, str(metrics_script),
        "--reports-dir", str(reports_dir),
        "--trace-path", str(trace_path),
        "--output", str(metrics_output_base),
        "--json",
    ], metrics_log)

    metrics_ok = metrics.returncode == 0 and metrics_md.exists() and metrics_json.exists()
    manifest["stages"][-1]["status"] = "pass" if metrics_ok else "warn"
    manifest["metrics_status"] = {
        "stage": "metrics",
        "script": str(metrics_script),
        "reports_dir": str(reports_dir),
        "trace_path": str(trace_path),
        "progress_log_count": len(progress_logs),
        "trace_exists": trace_exists,
        "status": "pass" if metrics_ok else "warn",
        "returncode": metrics.returncode,
        "log": str(metrics_log),
    }

    if not metrics_ok:
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="metrics",
            severity="P2",
            error_code="METRICS_STAGE_WARN",
            context={
                "script": str(metrics_script),
                "log": str(metrics_log),
                "returncode": metrics.returncode,
                "reports_dir": str(reports_dir),
                "trace_path": str(trace_path),
                "progress_log_count": len(progress_logs),
                "trace_exists": trace_exists,
                "output_md_exists": metrics_md.exists(),
                "output_json_exists": metrics_json.exists(),
            },
            suggest="检查 metrics 聚合输入日志与 trace 路径，但无需阻断 smoke 主链。"
        ))


def _read_rows_as_dict(path: Path, key_field: str) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8-sig", newline="") as f:
            rows = {}
            reader = csv.DictReader(f)
            for row in reader:
                rows[str(row.get(key_field, "")).strip()] = row
            return rows
    except Exception:
        return {}


def _resolve_target_columns(headers: List[str], preferred_key: str) -> List[str]:
    candidates = [preferred_key, "target_text", "target", "target_en", "target_ru", "target_zh", "rehydrated_text", "translated_text", "tokenized_target"]
    normalized_headers = [h for h in headers if h]
    seen = set()
    columns = []
    for c in candidates:
        if c in normalized_headers and c not in seen:
            columns.append(c)
            seen.add(c)
    return columns


def _append_symbol_regression_checks(
    run_id: str,
    issue_file: Path,
    input_csv_rows: Dict[str, Dict[str, str]],
    final_csv_rows: Dict[str, Dict[str, str]],
    final_csv_headers: List[str],
    active_target_key: str,
) -> None:
    symbol_rules = {
        "7390672": ["【", "】"],
        "22050006": ["\\n"],
    }
    target_columns = _resolve_target_columns(final_csv_headers, active_target_key)
    if not target_columns:
        return

    for sid, required in symbol_rules.items():
        source_row = input_csv_rows.get(str(sid), {})
        source_text = (source_row.get("source_zh") or source_row.get("source") or "")
        final_row = final_csv_rows.get(str(sid), {})

        if not source_row:
            append_issue(str(issue_file), build_issue(
                run_id=run_id,
                stage="verify",
                severity="P2",
                error_code="SYMBOL_GUARD_ROW_MISSING_SOURCE",
                context={"string_id": str(sid), "phase": "symbol_guard"},
                suggest="补齐输入源文件中该 string_id 的上下文后重跑。"
            ))
            continue

        if not final_row:
            append_issue(str(issue_file), build_issue(
                run_id=run_id,
                stage="verify",
                severity="P0",
                error_code="SYMBOL_GUARD_ROW_MISSING_FINAL",
                context={"string_id": str(sid), "phase": "symbol_guard"},
                suggest="检查 rehydrate 阶段是否丢失该行。"
            ))
            continue

        for ch in required:
            if ch not in source_text:
                continue

            # 目标列优先使用 target / target_text / target_en（兼容历史字段），
            # 并允许 rehydrated_text 作为保底列。
            candidate_columns = list(dict.fromkeys([
                "target",
                "target_text",
                "target_en",
                "target_ru",
                "rehydrated_text",
            ]))  # 去重且保序
            check_columns = [c for c in candidate_columns if c in target_columns or c in final_row]

            if not check_columns:
                continue

            if not any(ch in (final_row.get(c) or "") for c in check_columns):
                append_issue(str(issue_file), build_issue(
                    run_id=run_id,
                    stage="verify",
                    severity="P0",
                    error_code="SYMBOL_GUARD_MISSING",
                    context={
                        "string_id": str(sid),
                        "symbol": ch,
                        "missing_in_columns": check_columns,
                        "columns_checked": target_columns,
                        "phase": "symbol_guard",
                    },
                    suggest="检查 normalize->translate->qa_hard->rehydrate 的占位符与标点恢复链路。"
                ))


def _finalize_manifest(
    manifest: Dict[str, Any],
    *,
    run_manifest_path: Path,
    review_queue_path: Path,
    review_queue_rows: List[Dict[str, str]],
    gate_summary: Dict[str, Any],
    status_reason: str = "",
    passed_at: Optional[str] = None,
) -> None:
    deduped_review_rows = _dedupe_review_queue(review_queue_rows)
    _write_review_queue(review_queue_path, deduped_review_rows)
    manifest["review_handoff"] = _review_handoff_summary(deduped_review_rows, review_queue_path)
    manifest["gate_summary"] = gate_summary
    manifest["overall_status"] = _derive_overall_status(manifest.get("stages", []), gate_summary, deduped_review_rows)
    manifest["status"] = manifest["overall_status"]
    manifest["stage_status_counts"] = _stage_status_counts(manifest.get("stages", []))
    manifest["status_reason"] = status_reason
    if passed_at:
        manifest["passed_at"] = passed_at
    _write_manifest(run_manifest_path, manifest)


def run_pipeline(args: argparse.Namespace) -> int:
    if not getattr(args, "soft_qa_rubric", ""):
        args.soft_qa_rubric = "workflow/soft_qa_rubric.yaml"
    if not getattr(args, "lifecycle_registry", ""):
        args.lifecycle_registry = "workflow/lifecycle_registry.yaml"
    run_id = f"smoke_run_{_timestamp()}"
    run_dir = Path(args.run_dir or Path("data") / run_id)
    run_dir.mkdir(parents=True, exist_ok=True)
    issue_file = run_dir / "smoke_issues.json"
    issue_file.parent.mkdir(parents=True, exist_ok=True)

    input_csv = Path(args.input).resolve()
    draft_csv = run_dir / "smoke_draft.csv"
    placeholder_map = run_dir / "smoke_placeholder_map.json"
    translated_csv = run_dir / "smoke_translated.csv"
    qa_hard_report = run_dir / "smoke_qa_hard_report.json"
    repaired_hard_csv = run_dir / "smoke_repaired_hard.csv"
    qa_hard_recheck_report = run_dir / "smoke_qa_hard_recheck_report.json"
    qa_soft_report = run_dir / "smoke_qa_soft_report.json"
    qa_soft_tasks = run_dir / "smoke_repair_tasks.jsonl"
    repaired_soft_csv = run_dir / "smoke_repaired_soft.csv"
    qa_hard_post_soft_report = run_dir / "smoke_qa_hard_post_soft_report.json"
    review_queue_path = run_dir / "smoke_review_queue.csv"
    review_tickets_jsonl = run_dir / "smoke_review_tickets.jsonl"
    review_tickets_csv = run_dir / "smoke_review_tickets.csv"
    feedback_log_jsonl = run_dir / "smoke_review_feedback_log.jsonl"
    kpi_report_json = run_dir / "smoke_language_governance_kpi.json"
    final_csv = run_dir / "smoke_final_export.csv"
    run_manifest_path = run_dir / "run_manifest.json"

    manifest = _make_manifest(args, run_id, input_csv, run_dir, issue_file)
    manifest["review_handoff"]["queue_path"] = str(review_queue_path)
    _append_artifact(manifest, "smoke_review_queue", review_queue_path)
    _append_artifact(manifest, "smoke_review_tickets_jsonl", review_tickets_jsonl)
    _append_artifact(manifest, "smoke_review_tickets_csv", review_tickets_csv)
    _append_artifact(manifest, "smoke_feedback_log_jsonl", feedback_log_jsonl)
    _append_artifact(manifest, "smoke_governance_kpi_json", kpi_report_json)
    review_queue_rows: List[Dict[str, str]] = []
    candidate_csv: Optional[Path] = None
    candidate_stage = ""
    runtime_governance: Dict[str, Any] = {
        "passed": True,
        "style_profile_path": str(args.style_profile or ""),
        "asset_statuses": {},
        "issues": [],
    }

    def finish_failed(stage_name: str, reason: str, *, failed_gate: str = "", code: int = 1) -> int:
        manifest["delivery_decision"]["selected_candidate_csv"] = str(candidate_csv) if candidate_csv else ""
        manifest["delivery_decision"]["selected_candidate_stage"] = candidate_stage
        _finalize_manifest(
            manifest,
            run_manifest_path=run_manifest_path,
            review_queue_path=review_queue_path,
            review_queue_rows=review_queue_rows,
            gate_summary={
                "status": "failed",
                "failed_gates": [failed_gate] if failed_gate else [],
                "blocking_stage": stage_name,
            },
            status_reason=reason,
        )
        return code

    def finish_blocked(stage_name: str, reason: str, *, failed_gates: List[str], code: int = 1) -> int:
        manifest["delivery_decision"]["selected_candidate_csv"] = str(candidate_csv) if candidate_csv else ""
        manifest["delivery_decision"]["selected_candidate_stage"] = candidate_stage
        _finalize_manifest(
            manifest,
            run_manifest_path=run_manifest_path,
            review_queue_path=review_queue_path,
            review_queue_rows=review_queue_rows,
            gate_summary={
                "status": "blocked",
                "failed_gates": failed_gates,
                "blocking_stage": stage_name,
            },
            status_reason=reason,
        )
        return code

    def append_escalation_rows(
        escalation_rows: List[Dict[str, str]],
        *,
        review_source: str,
        current_rows_map: Dict[str, Dict[str, str]],
        final_status: str = "review_handoff",
        queue_reason: str = "",
    ) -> None:
        for escalation in escalation_rows:
            string_id = str(escalation.get("string_id") or "")
            current_target = ""
            if string_id:
                current_row = current_rows_map.get(string_id) or {}
                current_target = _extract_current_target(current_row)
            review_queue_rows.append(
                _build_review_queue_entry(
                    string_id=string_id,
                    review_source=review_source,
                    queue_reason=queue_reason or str(escalation.get("suggested_action") or escalation.get("issues_summary") or review_source),
                    current_target=current_target,
                    execution_status="review_handoff" if final_status != "blocked" else "updated",
                    final_status=final_status,
                    manual_review_reason=str(escalation.get("suggested_action") or queue_reason or review_source),
                )
            )

    def append_qa_error_rows(
        report: Dict[str, Any],
        *,
        review_source: str,
        current_rows_map: Dict[str, Dict[str, str]],
        queue_reason: str,
        final_status: str = "blocked",
    ) -> None:
        for error in report.get("errors", []) or []:
            string_id = str(error.get("string_id") or "")
            if not string_id:
                continue
            current_row = current_rows_map.get(string_id) or {}
            current_target = _extract_current_target(
                current_row,
                fallback=str(error.get("current_translation") or ""),
            )
            reason_codes = [str(error.get("type") or "")] if error.get("type") else []
            review_queue_rows.append(
                _build_review_queue_entry(
                    string_id=string_id,
                    review_source=review_source,
                    queue_reason=queue_reason,
                    current_target=current_target,
                    execution_status="review_handoff" if final_status != "blocked" else "updated",
                    final_status=final_status,
                    reason_codes=reason_codes,
                    manual_review_reason=queue_reason,
                )
            )

    if not input_csv.exists():
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="normalize",
            severity="P0",
            error_code="INPUT_MISSING",
            context={"input_csv": str(input_csv)},
            suggest="检查输入 CSV 是否存在。"
        ))
        print(f"Missing input: {input_csv}")
        return finish_failed("normalize", "input_missing", failed_gate="input")

    input_row_count = _count_csv_rows(input_csv)
    manifest["row_counts"]["input"] = input_row_count

    style_profile_log = run_dir / f"00a_{_safe_stage_name('style_profile_bootstrap')}.log"
    args.style_profile = _resolve_style_profile_path(args.style_profile)
    style_profile_ready, resolved_style_profile = _ensure_style_profile(args.style_profile, style_profile_log)
    args.style_profile = resolved_style_profile
    manifest["artifacts"]["style_profile"] = args.style_profile
    _append_stage_artifact(manifest, "style_profile_log", style_profile_log)
    _append_stage_artifact(manifest, "style_profile", Path(args.style_profile))
    if not style_profile_ready:
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="style_profile_bootstrap",
            severity="P0",
            error_code="STYLE_PROFILE_MISSING",
            context={"style_profile": args.style_profile, "log": str(style_profile_log)},
            suggest="通过 scripts/style_guide_bootstrap.py 生成 style profile 后再重试。"
        ))
        return finish_failed("style_profile_bootstrap", "style_profile_missing", failed_gate="style_profile")
    try:
        lifecycle_registry_path = getattr(args, "lifecycle_registry", "workflow/lifecycle_registry.yaml")
        runtime_governance = validate_style_governance_runtime(
            args.style_profile,
            lifecycle_registry_path=lifecycle_registry_path,
        )
        validate_governed_asset(args.glossary, "glossary", lifecycle_registry_path=lifecycle_registry_path)
        validate_governed_asset(args.soft_qa_rubric, "rubric", lifecycle_registry_path=lifecycle_registry_path)
        validate_governed_asset(args.schema, "policy", lifecycle_registry_path=lifecycle_registry_path)
    except GovernanceError as exc:
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="style_governance_gate",
            severity="P0",
            error_code="STYLE_GOVERNANCE_GATE_FAIL",
            context={"style_profile": args.style_profile, "error": str(exc)},
            suggest="修复 style governance / lifecycle registry 后重试。",
        ))
        return finish_failed("style_governance_gate", "style_governance_gate_failed", failed_gate="style_governance")
    manifest["runtime_governance"] = runtime_governance

    # 0) connectivity
    ping_log = run_dir / f"00_{_safe_stage_name('connectivity')}.log"
    ping = _run_step([sys.executable, "scripts/llm_ping.py"], ping_log)
    ping_ok = ping.returncode == 0
    _append_stage(manifest, "Connectivity", [ping_log], "pass" if ping_ok else "fail")
    _append_artifact(manifest, "smoke_connectivity_log", ping_log)
    _append_stage_artifact(manifest, "smoke_connectivity_log", ping_log)
    if not ping_ok:
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="connectivity",
            severity="P0",
            error_code="LLM_CONNECTIVITY_FAIL",
            context={"log": str(ping_log), "returncode": ping.returncode, "stdout": ping.stdout[-200:]},
            suggest="先修复 LLM 凭证与 base_url，然后重试。"
        ))
        return finish_failed("connectivity", "llm_connectivity_fail", failed_gate="connectivity")

    # 1) normalize
    normalize_log = run_dir / f"01_{_safe_stage_name('normalize')}.log"
    normalize = _run_step([
        sys.executable, "scripts/normalize_guard.py",
        str(input_csv),
        str(draft_csv),
        str(placeholder_map),
        args.schema,
        "--long-text-threshold", str(args.long_text_threshold),
        "--source-lang", args.source_lang,
    ], normalize_log)
    normalize_ok = normalize.returncode == 0
    _append_stage(manifest, "Normalize", [draft_csv, placeholder_map], "pass" if normalize_ok else "fail")
    _append_artifact(manifest, "smoke_draft_csv", draft_csv)
    _append_artifact(manifest, "smoke_placeholder_map", placeholder_map)
    _append_stage_artifact(manifest, "normalize_log", normalize_log)
    _append_stage_artifact(manifest, "draft_csv", draft_csv)
    if not normalize_ok:
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="normalize",
            severity="P0",
            error_code="NORMALIZE_FAIL",
            context={"log": str(normalize_log), "returncode": normalize.returncode},
            suggest="检查输入 CSV 的列字段与占位符格式。"
        ))
        return finish_failed("normalize", "normalize_fail", failed_gate="normalize")

    # 2) translate (EN preferred, RU fallback)
    translation_log = run_dir / f"02_{_safe_stage_name('translate')}.log"
    active_target = args.target_lang
    used_fallback = False
    target_cmd = [
        sys.executable, "scripts/translate_llm.py",
        "--input", str(draft_csv),
        "--output", str(translated_csv),
        "--style", args.style,
        "--glossary", args.glossary,
        "--style-profile", args.style_profile,
        "--lifecycle-registry", lifecycle_registry_path,
        "--target-lang", active_target,
        "--target-key", _derive_target_key(active_target),
        "--model", args.model,
        "--checkpoint", str(run_dir / "smoke_translate_checkpoint.json")
    ]

    metrics_env = {
        "LLM_TRACE_PATH": str(run_dir / "llm_trace.jsonl"),
    }
    translate = _run_step(target_cmd, translation_log, env=metrics_env)
    if translate.returncode != 0 and active_target != "ru-RU" and args.enable_target_fallback:
        # fallback to ru-RU once when EN route fails
        used_fallback = True
        translation_log = run_dir / f"02_{_safe_stage_name('translate_fallback')}.log"
        active_target = args.fallback_target_lang or "ru-RU"
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="translate",
            severity="P1",
            error_code="TARGET_LANG_FALLBACK_TRIGGERED",
            context={"primary_target": args.target_lang, "fallback_target": active_target},
            suggest="使用目标语言回退策略，保持 pipeline 可继续。"
        ))
        target_cmd = [
            sys.executable, "scripts/translate_llm.py",
            "--input", str(draft_csv),
            "--output", str(translated_csv),
            "--style", args.style,
            "--glossary", args.glossary,
            "--style-profile", args.style_profile,
            "--lifecycle-registry", lifecycle_registry_path,
            "--target-lang", active_target,
            "--target-key", _derive_target_key(active_target),
            "--model", args.model,
            "--checkpoint", str(run_dir / "smoke_translate_checkpoint.json")
        ]
        translate = _run_step(target_cmd, translation_log, env=metrics_env)
        manifest["fallback_used"] = True
        manifest["fallback_from"] = args.target_lang
        manifest["fallback_to"] = active_target

    translate_ok = translate.returncode == 0
    _append_stage(manifest, f"Translate ({active_target})", [translated_csv], "pass" if translate_ok else "fail")
    _append_artifact(manifest, "smoke_translate_log", translation_log)
    _append_artifact(manifest, "smoke_translated_csv", translated_csv)
    _append_stage_artifact(manifest, "translate_log", translation_log)
    _append_stage_artifact(manifest, "translated_csv", translated_csv)
    manifest["target_lang_effective"] = active_target
    manifest["target_key_effective"] = _derive_target_key(active_target)
    manifest["translate_log"] = str(translation_log)
    manifest["used_fallback"] = bool(used_fallback)
    if not translate_ok:
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="translate",
            severity="P0",
            error_code="TRANSLATE_FAIL",
            context={"log": str(translation_log), "returncode": translate.returncode, "target_lang": active_target},
            suggest="检查模型是否可用、输出字段格式和网络连通。"
        ))
        return finish_failed("translate", "translate_fail", failed_gate="translate")

    candidate_csv = translated_csv
    candidate_stage = "translate"

    # 3) QA hard
    qa_log = run_dir / f"03_{_safe_stage_name('qa_hard')}.log"
    qa = _run_step([
        sys.executable, "scripts/qa_hard.py",
        str(translated_csv),
        str(placeholder_map),
        args.schema,
        args.forbidden,
        str(qa_hard_report),
    ], qa_log)
    qa_report = _read_json(qa_hard_report)
    qa_has_errors = bool(qa_report.get("has_errors"))
    qa_warning_total = int((qa_report.get("metadata", {}) or {}).get("total_warnings", 0))
    qa_warning_policy = qa_report.get("warning_policy") or {}
    qa_actionable_warning_total = int(qa_warning_policy.get("actionable_warning_total", qa_warning_total))
    qa_warning_samples = (qa_report.get("warnings") or [])[:50]
    qa_warning_counts = qa_report.get("warning_counts", {})
    qa_stage_status = _qa_stage_status(qa.returncode, qa_has_errors, qa_actionable_warning_total)
    if qa_stage_status == "block":
        qa_stage_status = "warn"
    _append_stage(
        manifest,
        "QA Hard",
        [qa_hard_report],
        qa_stage_status,
        details={
            "errors": int((qa_report.get("metadata", {}) or {}).get("total_errors", 0)),
            "warnings": qa_warning_total,
            "actionable_warning_total": qa_actionable_warning_total,
            "recovery_path": "repair_hard" if (qa.returncode != 0 or qa_has_errors) else "not_needed",
        },
    )
    _append_artifact(manifest, "smoke_qa_hard_report", qa_hard_report)
    _append_artifact(manifest, "smoke_qa_hard_log", qa_log)
    _append_stage_artifact(manifest, "qa_hard_report", qa_hard_report)
    _append_stage_artifact(manifest, "qa_hard_log", qa_log)
    manifest["qa_hard_report"] = str(qa_hard_report)
    if qa_has_errors:
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="qa_hard",
            severity="P0",
            error_code="QA_HARD_FAIL",
            context={
                "report": str(qa_hard_report),
                "total_errors": qa_report.get("metadata", {}).get("total_errors", 0),
                "error_counts": qa_report.get("error_counts", {}),
            },
            suggest="修复硬性规则问题（token/标签/禁用词）后重试。"
        ))
    elif qa_actionable_warning_total > 0:
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="qa_hard",
            severity="P2",
            error_code="QA_HARD_WARNINGS",
            context={
                "report": str(qa_hard_report),
                "total_warnings": qa_warning_total,
                "actionable_warning_total": qa_actionable_warning_total,
                "warning_counts": qa_warning_counts,
                "warning_samples": qa_warning_samples,
                "warning_policy": qa_warning_policy,
            },
            suggest="留意软告警趋势，必要时在 normalize/数据侧修正，再决定是否允许。"
        ))
    if qa.returncode != 0 and not qa_has_errors:
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="qa_hard",
            severity="P0",
            error_code="QA_HARD_FAIL",
            context={"log": str(qa_log), "returncode": qa.returncode},
            suggest="修复硬性规则问题（token/标签/禁用词）后重试。"
        ))

    if qa.returncode != 0 or qa_has_errors:
        repair_hard_dir = run_dir / "repair_reports" / "hard"
        repair_hard_log = run_dir / f"03b_{_safe_stage_name('repair_hard')}.log"
        repair_hard = _run_step([
            sys.executable,
            "scripts/repair_loop.py",
            "--input", str(translated_csv),
            "--tasks", str(qa_hard_report),
            "--output", str(repaired_hard_csv),
            "--output-dir", str(repair_hard_dir),
            "--qa-type", "hard",
            "--target-lang", active_target,
        ], repair_hard_log)
        hard_stats_path = repair_hard_dir / "repair_hard_stats.json"
        hard_escalation_path = repair_hard_dir / "escalated_hard_qa.csv"
        hard_escalations = _read_csv_rows(hard_escalation_path)
        hard_stats = _read_json(hard_stats_path)
        hard_repair_ok = repair_hard.returncode == 0 and repaired_hard_csv.exists()
        manifest["repair_cycles"]["hard"] = {
            "status": "completed" if hard_repair_ok else "failed",
            "task_count": int(hard_stats.get("total_tasks", len(qa_report.get("errors", []) or []))),
            "repaired": int(hard_stats.get("repaired", 0)),
            "escalation_count": len(hard_escalations),
            "stats_path": str(hard_stats_path),
            "escalation_path": str(hard_escalation_path),
            "log": str(repair_hard_log),
        }
        _append_stage(
            manifest,
            "Repair Hard",
            [
                repaired_hard_csv,
                {"path": str(hard_stats_path), "required": False},
                {"path": str(hard_escalation_path), "required": False},
            ],
            "pass" if hard_repair_ok else "fail",
            details={
                "task_count": manifest["repair_cycles"]["hard"]["task_count"],
                "repaired": manifest["repair_cycles"]["hard"]["repaired"],
                "escalation_count": len(hard_escalations),
            },
        )
        _append_artifact(manifest, "smoke_repaired_hard_csv", repaired_hard_csv)
        _append_stage_artifact(manifest, "repair_hard_log", repair_hard_log)
        _append_stage_artifact(manifest, "repair_hard_stats", hard_stats_path)
        _append_stage_artifact(manifest, "repair_hard_escalations", hard_escalation_path)
        if not hard_repair_ok:
            append_issue(str(issue_file), build_issue(
                run_id=run_id,
                stage="repair_hard",
                severity="P0",
                error_code="REPAIR_HARD_FAIL",
                context={"log": str(repair_hard_log), "returncode": repair_hard.returncode},
                suggest="检查 repair_loop hard 输出与修复配置后重试。"
            ))
            return finish_failed("repair_hard", "repair_hard_fail", failed_gate="repair_hard")

        candidate_csv = repaired_hard_csv
        candidate_stage = "repair_hard"
        qa_hard_recheck_log = run_dir / f"03c_{_safe_stage_name('qa_hard_recheck')}.log"
        qa_hard_recheck = _run_step([
            sys.executable, "scripts/qa_hard.py",
            str(candidate_csv),
            str(placeholder_map),
            args.schema,
            args.forbidden,
            str(qa_hard_recheck_report),
        ], qa_hard_recheck_log)
        qa_hard_recheck_payload = _read_json(qa_hard_recheck_report)
        qa_hard_recheck_has_errors = bool(qa_hard_recheck_payload.get("has_errors"))
        qa_hard_recheck_warning_total = int((qa_hard_recheck_payload.get("metadata", {}) or {}).get("total_warnings", 0))
        qa_hard_recheck_warning_policy = qa_hard_recheck_payload.get("warning_policy") or {}
        qa_hard_recheck_actionable_warning_total = int(
            qa_hard_recheck_warning_policy.get("actionable_warning_total", qa_hard_recheck_warning_total)
        )
        _append_stage(
            manifest,
            "QA Hard Recheck",
            [qa_hard_recheck_report],
            _qa_stage_status(
                qa_hard_recheck.returncode,
                qa_hard_recheck_has_errors,
                qa_hard_recheck_actionable_warning_total,
            ),
            details={
                "errors": int((qa_hard_recheck_payload.get("metadata", {}) or {}).get("total_errors", 0)),
                "warnings": qa_hard_recheck_warning_total,
                "actionable_warning_total": qa_hard_recheck_actionable_warning_total,
            },
        )
        _append_stage_artifact(manifest, "qa_hard_recheck_report", qa_hard_recheck_report)
        _append_stage_artifact(manifest, "qa_hard_recheck_log", qa_hard_recheck_log)
        if qa_hard_recheck.returncode != 0 or qa_hard_recheck_has_errors:
            repaired_rows_map = _read_rows_as_dict(candidate_csv, "string_id")
            append_escalation_rows(
                hard_escalations,
                review_source="repair_hard_escalation",
                current_rows_map=repaired_rows_map,
                final_status="blocked",
                queue_reason="repair_hard_escalated",
            )
            append_qa_error_rows(
                qa_hard_recheck_payload,
                review_source="qa_hard_recheck_blocked",
                current_rows_map=repaired_rows_map,
                queue_reason="qa_hard_failed_after_repair",
                final_status="blocked",
            )
            append_issue(str(issue_file), build_issue(
                run_id=run_id,
                stage="qa_hard_recheck",
                severity="P0",
                error_code="QA_HARD_RECHECK_FAIL",
                context={
                    "report": str(qa_hard_recheck_report),
                    "log": str(qa_hard_recheck_log),
                    "total_errors": (qa_hard_recheck_payload.get("metadata", {}) or {}).get("total_errors", 0),
                },
                suggest="硬修复后仍有硬性错误，改为人工复核处理。"
            ))
            return finish_blocked("qa_hard_recheck", "qa_hard_failed_after_repair", failed_gates=["qa_hard"])

    # 4) soft QA -> repair loop (soft) with rollback-safe promotion
    soft_qa_log = run_dir / f"04_{_safe_stage_name('soft_qa')}.log"
    soft_qa = _run_step([
        sys.executable,
        "scripts/soft_qa_llm.py",
        str(candidate_csv),
        args.style,
        args.glossary,
        args.soft_qa_rubric,
        "--style-profile", args.style_profile,
        "--lifecycle-registry", lifecycle_registry_path,
        "--out_report", str(qa_soft_report),
        "--out_tasks", str(qa_soft_tasks),
    ], soft_qa_log)
    soft_qa_payload = _read_json(qa_soft_report)
    soft_qa_tasks = _read_jsonl(qa_soft_tasks)
    soft_findings = bool(soft_qa_payload.get("has_findings")) or bool(soft_qa_tasks)
    soft_gate_status = str((soft_qa_payload.get("hard_gate") or {}).get("status") or "")
    soft_hard_gate_triggered = soft_qa.returncode == 2 or soft_gate_status == "fail"
    soft_stage_status = "pass"
    if soft_qa.returncode not in (0, 2):
        soft_stage_status = "warn"
    elif soft_findings or soft_hard_gate_triggered:
        soft_stage_status = "warn"
    _append_stage(
        manifest,
        "Soft QA",
        [
            qa_soft_report,
            {"path": str(qa_soft_tasks), "required": False},
        ],
        soft_stage_status,
        details={
            "returncode": soft_qa.returncode,
            "has_findings": soft_findings,
            "hard_gate_status": soft_gate_status or ("fail" if soft_hard_gate_triggered else "pass"),
            "task_count": len(soft_qa_tasks),
        },
    )
    _append_artifact(manifest, "smoke_qa_soft_report", qa_soft_report)
    _append_artifact(manifest, "smoke_qa_soft_tasks", qa_soft_tasks)
    _append_stage_artifact(manifest, "soft_qa_log", soft_qa_log)
    _append_stage_artifact(manifest, "soft_qa_report", qa_soft_report)
    _append_stage_artifact(manifest, "soft_qa_tasks", qa_soft_tasks)
    if soft_qa.returncode not in (0, 2):
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="soft_qa",
            severity="P1",
            error_code="SOFT_QA_EXECUTION_FAIL",
            context={"log": str(soft_qa_log), "returncode": soft_qa.returncode},
            suggest="检查 soft QA 模型调用与 rubric 配置；当前交付将回退为人工复核。"
        ))
        review_queue_rows.append(
            _build_review_queue_entry(
                string_id="",
                review_source="soft_qa_execution_failure",
                queue_reason="soft_qa_execution_failed",
                current_target="",
                execution_status="failed",
                final_status="review_handoff",
                manual_review_reason="soft_qa_execution_failed",
            )
        )
    if soft_hard_gate_triggered and not soft_qa_tasks:
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="soft_qa",
            severity="P1",
            error_code="SOFT_QA_HARD_GATE_NO_TASKS",
            context={
                "report": str(qa_soft_report),
                "log": str(soft_qa_log),
                "returncode": soft_qa.returncode,
                "hard_gate_status": soft_gate_status or "fail",
            },
            suggest="soft QA 触发硬门禁但没有生成 repair 任务，改为人工复核后再决定是否继续交付。"
        ))
        review_queue_rows.append(
            _build_review_queue_entry(
                string_id="",
                review_source="soft_qa_hard_gate",
                queue_reason="soft_qa_hard_gate_no_tasks",
                current_target="",
                execution_status="review_handoff",
                final_status="review_handoff",
                manual_review_reason="soft_qa_hard_gate_no_tasks",
            )
        )

    if soft_findings and soft_qa_tasks:
        repair_soft_dir = run_dir / "repair_reports" / "soft"
        repair_soft_log = run_dir / f"04b_{_safe_stage_name('repair_soft')}.log"
        repair_soft = _run_step([
            sys.executable,
            "scripts/repair_loop.py",
            "--input", str(candidate_csv),
            "--tasks", str(qa_soft_tasks),
            "--output", str(repaired_soft_csv),
            "--output-dir", str(repair_soft_dir),
            "--qa-type", "soft",
            "--target-lang", active_target,
        ], repair_soft_log)
        soft_stats_path = repair_soft_dir / "repair_soft_stats.json"
        soft_escalation_path = repair_soft_dir / "escalated_soft_qa.csv"
        soft_escalations = _read_csv_rows(soft_escalation_path)
        soft_stats = _read_json(soft_stats_path)
        soft_repair_ok = repair_soft.returncode == 0 and repaired_soft_csv.exists()
        manifest["repair_cycles"]["soft"] = {
            "status": "completed" if soft_repair_ok else "failed",
            "task_count": int(soft_stats.get("total_tasks", len(soft_qa_tasks))),
            "repaired": int(soft_stats.get("repaired", 0)),
            "escalation_count": len(soft_escalations),
            "stats_path": str(soft_stats_path),
            "escalation_path": str(soft_escalation_path),
            "log": str(repair_soft_log),
        }
        _append_stage(
            manifest,
            "Repair Soft",
            [
                repaired_soft_csv,
                {"path": str(soft_stats_path), "required": False},
                {"path": str(soft_escalation_path), "required": False},
            ],
            "pass" if soft_repair_ok else "warn",
            details={
                "task_count": manifest["repair_cycles"]["soft"]["task_count"],
                "repaired": manifest["repair_cycles"]["soft"]["repaired"],
                "escalation_count": len(soft_escalations),
            },
        )
        _append_stage_artifact(manifest, "repair_soft_log", repair_soft_log)
        _append_stage_artifact(manifest, "repair_soft_stats", soft_stats_path)
        _append_stage_artifact(manifest, "repair_soft_escalations", soft_escalation_path)
        if not soft_repair_ok:
            append_issue(str(issue_file), build_issue(
                run_id=run_id,
                stage="repair_soft",
                severity="P1",
                error_code="REPAIR_SOFT_FAIL",
                context={"log": str(repair_soft_log), "returncode": repair_soft.returncode},
                suggest="保持硬规则安全候选输出，并将 soft 问题转人工复核。"
            ))
            current_rows_map = _read_rows_as_dict(candidate_csv, "string_id")
            for task in soft_qa_tasks:
                string_id = str(task.get("string_id") or "")
                current_row = current_rows_map.get(string_id) or {}
                review_queue_rows.append(
                    _build_review_queue_entry(
                        string_id=string_id,
                        review_source="soft_repair_execution_failure",
                        queue_reason="soft_repair_execution_failed",
                        current_target=_extract_current_target(current_row),
                        execution_status="failed",
                        final_status="review_handoff",
                        reason_codes=[str(task.get("type") or "")] if task.get("type") else [],
                        manual_review_reason="soft_repair_execution_failed",
                    )
                )
        else:
            qa_hard_post_soft_log = run_dir / f"04c_{_safe_stage_name('qa_hard_post_soft')}.log"
            qa_hard_post_soft = _run_step([
                sys.executable, "scripts/qa_hard.py",
                str(repaired_soft_csv),
                str(placeholder_map),
                args.schema,
                args.forbidden,
                str(qa_hard_post_soft_report),
            ], qa_hard_post_soft_log)
            qa_hard_post_soft_payload = _read_json(qa_hard_post_soft_report)
            qa_hard_post_soft_has_errors = bool(qa_hard_post_soft_payload.get("has_errors"))
            qa_hard_post_soft_warning_total = int((qa_hard_post_soft_payload.get("metadata", {}) or {}).get("total_warnings", 0))
            qa_hard_post_soft_warning_policy = qa_hard_post_soft_payload.get("warning_policy") or {}
            qa_hard_post_soft_actionable_warning_total = int(
                qa_hard_post_soft_warning_policy.get("actionable_warning_total", qa_hard_post_soft_warning_total)
            )
            _append_stage(
                manifest,
                "QA Hard Post Soft",
                [qa_hard_post_soft_report],
                _qa_stage_status(
                    qa_hard_post_soft.returncode,
                    qa_hard_post_soft_has_errors,
                    qa_hard_post_soft_actionable_warning_total,
                ),
                details={
                    "errors": int((qa_hard_post_soft_payload.get("metadata", {}) or {}).get("total_errors", 0)),
                    "warnings": qa_hard_post_soft_warning_total,
                    "actionable_warning_total": qa_hard_post_soft_actionable_warning_total,
                },
            )
            _append_stage_artifact(manifest, "qa_hard_post_soft_report", qa_hard_post_soft_report)
            _append_stage_artifact(manifest, "qa_hard_post_soft_log", qa_hard_post_soft_log)
            if qa_hard_post_soft.returncode != 0 or qa_hard_post_soft_has_errors:
                current_rows_map = _read_rows_as_dict(candidate_csv, "string_id")
                append_escalation_rows(
                    soft_escalations,
                    review_source="repair_soft_escalation",
                    current_rows_map=current_rows_map,
                    queue_reason="repair_soft_escalated",
                )
                append_qa_error_rows(
                    qa_hard_post_soft_payload,
                    review_source="soft_repair_rollback",
                    current_rows_map=current_rows_map,
                    queue_reason="qa_hard_failed_after_soft_repair",
                    final_status="review_handoff",
                )
                append_issue(str(issue_file), build_issue(
                    run_id=run_id,
                    stage="qa_hard_post_soft",
                    severity="P1",
                    error_code="SOFT_REPAIR_ROLLBACK",
                    context={
                        "report": str(qa_hard_post_soft_report),
                        "log": str(qa_hard_post_soft_log),
                        "rollback_to": str(candidate_csv),
                    },
                    suggest="soft repair 破坏了硬规则，已回滚到上一个硬规则安全候选。"
                ))
                manifest["delivery_decision"]["rollback_used"] = True
                manifest["delivery_decision"]["rollback_reason"] = "soft_repair_failed_hard_gate"
            else:
                candidate_csv = repaired_soft_csv
                candidate_stage = "repair_soft"
                current_rows_map = _read_rows_as_dict(candidate_csv, "string_id")
                append_escalation_rows(
                    soft_escalations,
                    review_source="repair_soft_escalation",
                    current_rows_map=current_rows_map,
                    queue_reason="repair_soft_escalated",
                )
    else:
        manifest["repair_cycles"]["soft"] = {
            "status": "skipped",
            "task_count": len(soft_qa_tasks),
            "escalation_count": 0,
        }

    manifest["delivery_decision"]["selected_candidate_csv"] = str(candidate_csv)
    manifest["delivery_decision"]["selected_candidate_stage"] = candidate_stage

    # 5) rehydrate export
    rehydrate_log = run_dir / f"05_{_safe_stage_name('rehydrate')}.log"
    rehydrate = _run_step([
        sys.executable, "scripts/rehydrate_export.py",
        str(candidate_csv),
        str(placeholder_map),
        str(final_csv),
        "--target-lang", active_target
    ], rehydrate_log)
    _append_stage(manifest, "Rehydrate", [final_csv], "pass" if rehydrate.returncode == 0 else "fail")
    _append_artifact(manifest, "smoke_final_csv", final_csv)
    _append_artifact(manifest, "smoke_rehydrate_log", rehydrate_log)
    _append_stage_artifact(manifest, "final_csv", final_csv)
    _append_stage_artifact(manifest, "rehydrate_log", rehydrate_log)
    manifest["final_csv"] = str(final_csv)
    manifest["output_target_lang"] = active_target
    manifest["output_target_key"] = _derive_target_key(active_target)
    if rehydrate.returncode != 0:
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="rehydrate",
            severity="P0",
            error_code="REHYDRATE_FAIL",
            context={"log": str(rehydrate_log), "returncode": rehydrate.returncode, "target_lang": active_target},
            suggest="检查 placeholder 映射完整性和输出列定义。"
        ))
        return finish_failed("rehydrate", "rehydrate_fail", failed_gate="rehydrate")

    # 6) row count integrity checks
    translated_rows = _count_csv_rows(translated_csv)
    candidate_rows = _count_csv_rows(candidate_csv)
    final_rows = _count_csv_rows(final_csv)
    input_rows_map = _read_rows_as_dict(input_csv, "string_id")
    final_rows_map = _read_rows_as_dict(final_csv, "string_id")
    final_headers = []
    if final_csv.exists():
        with open(final_csv, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            final_headers = next(reader, []) or []
    _write_row_checks(manifest, input_row_count, translated_rows, final_rows)
    manifest["row_checks"]["candidate_rows"] = candidate_rows
    manifest["row_checks"]["candidate_delta"] = candidate_rows - input_row_count
    _append_symbol_regression_checks(
        run_id=run_id,
        issue_file=issue_file,
        input_csv_rows=input_rows_map,
        final_csv_rows=final_rows_map,
        final_csv_headers=final_headers,
        active_target_key=manifest["target_key_effective"],
    )
    # 标记本次交付主消费列，优先使用 rehydrated_text，再回退历史列。
    manifest["delivery_columns"] = _resolve_target_columns(
        final_headers,
        manifest["target_key_effective"]
    )
    if "rehydrated_text" in final_headers and "rehydrated_text" not in manifest["delivery_columns"]:
        manifest["delivery_columns"].insert(0, "rehydrated_text")
    if manifest["target_key_effective"] in final_headers and manifest["target_key_effective"] not in manifest["delivery_columns"]:
        manifest["delivery_columns"].append(manifest["target_key_effective"])
    if "target" in final_headers and "target" not in manifest["delivery_columns"]:
        manifest["delivery_columns"].append("target")
    if "target_text" in final_headers and "target_text" not in manifest["delivery_columns"]:
        manifest["delivery_columns"].append("target_text")
    if translated_rows != input_row_count:
        _issue_row_mismatch(run_id, issue_file, "translate", input_row_count, translated_rows, "translate output row count mismatch")
        return finish_blocked("row_count_integrity", "translate_row_count_mismatch", failed_gates=["row_count_integrity"])
    if candidate_rows != input_row_count:
        _issue_row_mismatch(run_id, issue_file, candidate_stage or "candidate", input_row_count, candidate_rows, "candidate output row count mismatch")
        return finish_blocked("row_count_integrity", "candidate_row_count_mismatch", failed_gates=["row_count_integrity"])
    if final_rows != input_row_count:
        _issue_row_mismatch(run_id, issue_file, "rehydrate", input_row_count, final_rows, "final output row count mismatch")
        return finish_blocked("row_count_integrity", "final_row_count_mismatch", failed_gates=["row_count_integrity"])

    # 7) metrics (non-blocking observability)
    _run_metrics_stage(
        manifest=manifest,
        run_id=run_id,
        run_dir=run_dir,
        issue_file=issue_file,
    )

    # 8) verify (manifest-driven)
    verify_log = run_dir / f"99_{_safe_stage_name('smoke_verify')}.log"
    manifest["final_file"] = str(final_csv)
    manifest["stage_artifacts"].update({
        "final_target_lang": active_target,
    })
    _append_stage_artifact(manifest, "verify_input", final_csv)
    _append_artifact(manifest, "smoke_manifest", run_manifest_path)
    _append_artifact(manifest, "smoke_verify_log", verify_log)
    deduped_review_queue = _normalize_review_ticket_queue_rows(_dedupe_review_queue(review_queue_rows))
    _write_review_queue(review_queue_path, deduped_review_queue)
    ensure_feedback_log(str(feedback_log_jsonl))
    feedback_logs = load_feedback_log(str(feedback_log_jsonl))
    review_tickets = build_review_tickets(
        deduped_review_queue,
        task_lookup=_build_review_ticket_task_lookup(deduped_review_queue, active_target),
        source_artifacts={
            "run_manifest": str(run_manifest_path),
            "review_queue": str(review_queue_path),
            "style_profile": args.style_profile,
        },
        default_locale=active_target,
    )
    write_review_tickets(str(review_tickets_jsonl), str(review_tickets_csv), review_tickets)
    governance_write_json(
        str(kpi_report_json),
        build_kpi_report(
            scope="smoke_pipeline",
            manifest=manifest,
            review_tickets=review_tickets,
            feedback_logs=feedback_logs,
            runtime_governance=runtime_governance,
            lifecycle_registry=load_lifecycle_registry(getattr(args, "lifecycle_registry", "workflow/lifecycle_registry.yaml")),
            metrics_payload=_read_json(run_dir / "smoke_metrics_report.json"),
            extra_sources={
                "run_manifest": str(run_manifest_path),
                "review_queue": str(review_queue_path),
                "review_tickets": str(review_tickets_jsonl),
                "feedback_log": str(feedback_log_jsonl),
                "metrics_report_json": str(run_dir / "smoke_metrics_report.json"),
                "lifecycle_registry_path": getattr(args, "lifecycle_registry", "workflow/lifecycle_registry.yaml"),
            },
        ),
    )
    manifest.setdefault("artifacts", {})
    manifest["artifacts"]["smoke_review_tickets_jsonl"] = str(review_tickets_jsonl)
    manifest["artifacts"]["smoke_review_tickets_csv"] = str(review_tickets_csv)
    manifest["artifacts"]["smoke_feedback_log_jsonl"] = str(feedback_log_jsonl)
    manifest["artifacts"]["smoke_governance_kpi_json"] = str(kpi_report_json)
    _write_manifest(run_manifest_path, manifest)

    verify = _run_step([
        sys.executable, "scripts/smoke_verify.py",
        "--manifest", str(run_manifest_path),
        "--mode", args.verify_mode,
        "--issue-file", str(issue_file),
    ], verify_log)
    _append_stage(manifest, "Smoke Verify", [verify_log], "pass" if verify.returncode == 0 else "block")
    if verify.returncode != 0:
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="smoke_verify",
            severity="P1",
            error_code="SMOKE_VERIFY_FAIL",
            context={"log": str(verify_log), "returncode": verify.returncode},
            suggest="修复被阻断项后复跑 verify。"
        ))
        return finish_blocked("smoke_verify", "smoke_verify_blocked", failed_gates=["smoke_verify"], code=verify.returncode)

    passed_at = datetime.now(timezone.utc).isoformat()
    manifest["stage_artifacts"]["final_file"] = str(final_csv)
    manifest["pipeline_completion"] = {
        "status": "completed",
        "completed_at": passed_at,
        "notes": "Pipeline finished with unified phase-1 quality closure semantics."
    }
    _finalize_manifest(
        manifest,
        run_manifest_path=run_manifest_path,
        review_queue_path=review_queue_path,
        review_queue_rows=review_queue_rows,
        gate_summary={
            "status": "passed",
            "failed_gates": [],
            "blocking_stage": "",
        },
        status_reason="pipeline_completed",
        passed_at=passed_at,
    )
    return 0


def main():
    parser = argparse.ArgumentParser(description="Run smoke pipeline")
    parser.add_argument("--input", required=True, help="Input CSV path")
    parser.add_argument("--run-dir", default="", help="Custom run output directory")
    parser.add_argument("--target-lang", default="ru-RU", help="Primary target language, e.g. en-US")
    parser.add_argument("--fallback-target-lang", default="ru-RU", help="Fallback target language")
    parser.add_argument("--disable-target-fallback", action="store_true", help="Disable EN→RU fallback")
    parser.add_argument("--verify-mode", choices=["preflight", "full"], default="full", help="Smoke verify mode")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001", help="Translation model")
    parser.add_argument("--style", default="workflow/style_guide.md", help="Style guide path")
    parser.add_argument("--style-profile", default="", help="Style profile path. Defaults to tracked authority candidates and auto-bootstrap.")
    parser.add_argument("--lifecycle-registry", default="workflow/lifecycle_registry.yaml", help="Lifecycle registry for governed assets.")
    parser.add_argument("--glossary", default="glossary/compiled.yaml", help="Glossary path")
    parser.add_argument("--soft-qa-rubric", default="workflow/soft_qa_rubric.yaml", help="Soft QA rubric path")
    parser.add_argument("--schema", default="workflow/placeholder_schema.yaml", help="Placeholder schema path")
    parser.add_argument("--forbidden", default="workflow/forbidden_patterns.txt", help="Forbidden patterns path")
    parser.add_argument("--source-lang", default="zh-CN", help="Source language for normalization (default: zh-CN)")
    parser.add_argument(
        "--long-text-threshold",
        type=int,
        default=200,
        help="Rows with source_zh length >= threshold are treated as long text.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        help="Compatibility option: log level for command output (currently not used by pipeline internals).",
    )
    args = parser.parse_args()

    args.enable_target_fallback = not args.disable_target_fallback

    code = run_pipeline(args)
    raise SystemExit(code)


if __name__ == "__main__":
    main()
