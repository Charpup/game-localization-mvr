#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Milestone E incremental task generator and refresh executor."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from qa_hard import QAHardValidator
from runtime_adapter import batch_llm_call
from translate_llm import (
    build_glossary_summary,
    build_system_prompt_factory,
    build_user_prompt,
    derive_target_key,
    load_glossary,
    load_style_profile as load_translate_style_profile,
    tokens_signature,
)
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
from style_governance_runtime import evaluate_runtime_governance, format_runtime_governance_issues


TASK_REQUIRED_FIELDS = [
    "task_id",
    "string_id",
    "task_type",
    "target_locale",
    "reason_codes",
    "trigger_change_ids",
    "depends_on_rules",
    "source_artifacts",
    "target_constraints",
    "placeholder_signature",
    "current_target",
    "expected_change_scope",
    "human_review_required",
    "review_owner",
    "review_status",
]
TASK_TYPE_TO_SCOPE = {
    "refresh": "term_only",
    "retranslate": "style_plus_term",
    "manual_review": "manual",
    "skip": "manual",
}
RECOMMENDED_ACTION_TO_TASK = {
    "auto_refresh": "refresh",
    "retranslate": "retranslate",
    "manual_review": "manual_review",
    "skip": "skip",
}
DELTA_ROW_REQUIRED_FIELDS = [
    "string_id",
    "source_zh",
    "current_target",
    "target_locale",
    "content_class",
    "risk_level",
    "delta_types",
    "reason_codes",
    "reason_text",
    "rule_refs",
    "placeholder_locked",
    "manual_review_required",
    "manual_review_reason",
    "recommended_action",
]
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


def validate_style_governance_runtime(style_profile_path: str, *, lifecycle_registry_path: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    style_profile = load_translate_style_profile(style_profile_path)
    if not style_profile:
        raise GovernanceError(f"style profile missing or invalid: {style_profile_path}")
    if not _is_repo_managed(style_profile_path):
        return style_profile, {
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
    return style_profile, report


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
    csv_rows: List[Dict[str, str]] = []
    fieldnames = _review_ticket_fieldnames(tickets)
    for ticket in tickets:
        row: Dict[str, str] = {}
        for field in fieldnames:
            value = ticket.get(field)
            if isinstance(value, (list, dict)):
                row[field] = json.dumps(value, ensure_ascii=False)
            else:
                row[field] = "" if value is None else str(value)
        csv_rows.append(row)
    write_csv(csv_path, csv_rows, fieldnames)


def configure_standard_streams() -> None:
    if sys.platform != "win32":
        return
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
                continue
            buffer = getattr(stream, "buffer", None)
            if buffer is not None and not getattr(buffer, "closed", False):
                wrapped = io.TextIOWrapper(buffer, encoding="utf-8", errors="replace")
                setattr(sys, stream_name, wrapped)
        except Exception:
            continue


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path: str, payload: Dict[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_no}: {exc}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"Expected object in {path}:{line_no}")
            rows.append(payload)
    return rows


def write_jsonl(path: str, rows: Iterable[Dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_csv_rows(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: str, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_string_list(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item)]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return [str(item) for item in parsed if str(item)]
        except json.JSONDecodeError:
            pass
        return [text]
    return []


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def build_signature_payload(text: str) -> Dict[str, int]:
    return tokens_signature(text or "")


def normalize_task(raw: Dict[str, Any]) -> Dict[str, Any]:
    task = dict(raw)
    task["reason_codes"] = normalize_string_list(task.get("reason_codes"))
    task["trigger_change_ids"] = normalize_string_list(task.get("trigger_change_ids"))
    task["depends_on_rules"] = normalize_string_list(task.get("depends_on_rules"))
    task["human_review_required"] = normalize_bool(task.get("human_review_required"))
    task["placeholder_signature"] = task.get("placeholder_signature") or {}
    if not isinstance(task["placeholder_signature"], dict):
        raise ValueError(f"Task {task.get('task_id') or task.get('string_id') or '<unknown>'} has invalid placeholder_signature")
    source_artifacts = task.get("source_artifacts") or {}
    if not isinstance(source_artifacts, dict):
        raise ValueError(f"Task {task.get('task_id') or task.get('string_id') or '<unknown>'} has invalid source_artifacts")
    task["source_artifacts"] = source_artifacts
    target_constraints = task.get("target_constraints") or {}
    if not isinstance(target_constraints, dict):
        raise ValueError(f"Task {task.get('task_id') or task.get('string_id') or '<unknown>'} has invalid target_constraints")
    task["target_constraints"] = target_constraints
    task["execution_status"] = str(task.get("execution_status") or "").strip()
    task["final_status"] = str(task.get("final_status") or "").strip()
    task["status_reason"] = str(task.get("status_reason") or "").strip()
    return task


def validate_tasks(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for index, raw in enumerate(tasks, start=1):
        missing = [field for field in TASK_REQUIRED_FIELDS if field not in raw or raw.get(field) in (None, "", [])]
        if missing:
            identifier = raw.get("task_id") or raw.get("string_id") or f"line {index}"
            raise ValueError(f"Task contract violation for {identifier}: missing required field(s): {', '.join(missing)}")
        task = normalize_task(raw)
        if task["task_type"] not in TASK_TYPE_TO_SCOPE:
            raise ValueError(f"Task {task['task_id']} has unsupported task_type: {task['task_type']}")
        if task["task_type"] == "retranslate" and not str(task.get("source_text") or "").strip():
            raise ValueError(f"Task contract violation for {task['task_id']}: retranslate tasks require source_text")
        normalized.append(task)
    return normalized


def validate_delta_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for index, row in enumerate(rows, start=1):
        missing = [field for field in DELTA_ROW_REQUIRED_FIELDS if field not in row]
        if missing:
            raise ValueError(f"Delta row {index} missing required field(s): {', '.join(missing)}")
        row_copy = dict(row)
        row_copy["delta_types"] = normalize_string_list(row_copy.get("delta_types"))
        row_copy["reason_codes"] = normalize_string_list(row_copy.get("reason_codes"))
        row_copy["rule_refs"] = normalize_string_list(row_copy.get("rule_refs"))
        row_copy["placeholder_locked"] = normalize_bool(row_copy.get("placeholder_locked"))
        row_copy["manual_review_required"] = normalize_bool(row_copy.get("manual_review_required"))
        normalized.append(row_copy)
    return normalized


def load_delta_inputs(delta_rows_path: str, delta_report_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    report = read_json(delta_report_path) if delta_report_path else {}
    if not delta_rows_path:
        inferred_rows = str(report.get("row_impacts_path") or "").strip()
        if not inferred_rows:
            raise ValueError("Task generation requires --delta-rows or a delta report with row_impacts_path")
        delta_rows_path = inferred_rows
    return validate_delta_rows(read_jsonl(delta_rows_path)), report


def row_source_text(row: Dict[str, Any], fallback: str = "") -> str:
    return str(row.get("tokenized_zh") or row.get("source_zh") or fallback or "")


def build_glossary_index(glossary_path: str, target_locale: str) -> Tuple[Dict[str, str], str]:
    glossary_entries, _ = load_glossary(glossary_path, target_locale)
    approved = {entry.term_zh: entry.term_ru for entry in glossary_entries if entry.status == "approved"}
    return approved, build_glossary_summary(glossary_entries)


def build_glossary_resources(glossary_path: str, locales: Iterable[str]) -> Tuple[Dict[str, Dict[str, str]], Dict[str, str]]:
    locale_maps: Dict[str, Dict[str, str]] = {}
    locale_summaries: Dict[str, str] = {}
    for locale in sorted({str(item).strip() for item in locales if str(item).strip()}):
        locale_map, locale_summary = build_glossary_index(glossary_path, locale)
        locale_maps[locale] = locale_map
        locale_summaries[locale] = locale_summary
    return locale_maps, locale_summaries


def relevant_glossary_terms(source_text: str, glossary_map: Dict[str, str]) -> List[Dict[str, str]]:
    hints = []
    for term_zh, target_text in glossary_map.items():
        if term_zh and term_zh in source_text:
            hints.append({"term_zh": term_zh, "target_text": target_text})
    hints.sort(key=lambda item: item["term_zh"])
    return hints[:20]


def build_task(
    impact: Dict[str, Any],
    row: Dict[str, str],
    source_artifacts: Dict[str, str],
    glossary_map: Dict[str, str],
) -> Dict[str, Any]:
    action = str(impact["recommended_action"])
    task_type = RECOMMENDED_ACTION_TO_TASK.get(action)
    if not task_type:
        raise ValueError(f"Unsupported recommended_action for {impact['string_id']}: {action}")

    source_text = row_source_text(row, str(impact.get("source_zh") or ""))
    human_review_required = bool(impact["manual_review_required"]) or task_type in {"manual_review", "skip"}
    review_owner = "human-linguist" if human_review_required else "automation"
    review_status = "pending" if human_review_required else "not_required"
    task = {
        "task_id": f"{task_type}:{impact['string_id']}",
        "string_id": impact["string_id"],
        "task_type": task_type,
        "target_locale": impact["target_locale"],
        "reason_codes": normalize_string_list(impact.get("reason_codes")),
        "trigger_change_ids": normalize_string_list(impact.get("delta_types")),
        "depends_on_rules": normalize_string_list(impact.get("rule_refs")),
        "source_artifacts": source_artifacts,
        "target_constraints": {
            "content_class": impact["content_class"],
            "risk_level": impact["risk_level"],
            "placeholder_locked": bool(impact["placeholder_locked"]),
            "manual_review_reason": str(impact.get("manual_review_reason") or ""),
            "reason_text": str(impact.get("reason_text") or ""),
        },
        "placeholder_signature": build_signature_payload(source_text),
        "current_target": str(impact.get("current_target") or row.get("target_text") or ""),
        "expected_change_scope": TASK_TYPE_TO_SCOPE[task_type],
        "human_review_required": human_review_required,
        "review_owner": review_owner,
        "review_status": review_status,
        "source_text": source_text,
        "source_zh": str(row.get("source_zh") or impact.get("source_zh") or ""),
        "manual_review_reason": str(impact.get("manual_review_reason") or ""),
        "recommended_action": action,
        "content_class": impact["content_class"],
        "risk_level": impact["risk_level"],
        "relevant_glossary_terms": relevant_glossary_terms(source_text, glossary_map),
    }
    return task


def generate_tasks(
    delta_rows: List[Dict[str, Any]],
    translated_rows: List[Dict[str, str]],
    source_artifacts: Dict[str, str],
    glossary_maps_by_locale: Dict[str, Dict[str, str]],
) -> List[Dict[str, Any]]:
    rows_by_id = {str(row.get("string_id") or ""): row for row in translated_rows}
    tasks: List[Dict[str, Any]] = []
    for impact in delta_rows:
        string_id = str(impact["string_id"])
        row = rows_by_id.get(string_id)
        if row is None:
            raise ValueError(f"Impacted string_id {string_id} not found in translated CSV")
        locale = str(impact.get("target_locale") or "").strip()
        tasks.append(build_task(impact, row, source_artifacts, glossary_maps_by_locale.get(locale, {})))
    return validate_tasks(tasks)


def write_review_queue(path: str, rows: List[Dict[str, str]]) -> None:
    write_csv(path, rows, REVIEW_QUEUE_FIELDS)


def initial_task_status(task: Dict[str, Any]) -> Tuple[str, str, str]:
    if task["task_type"] in {"manual_review", "skip"}:
        reason = str(task.get("manual_review_reason") or task["task_type"])
        return "review_handoff", "review_handoff", reason
    return "pending", "pending", "awaiting_execution"


def apply_task_status(
    task: Dict[str, Any],
    execution_status: str,
    final_status: Optional[str] = None,
    status_reason: str = "",
) -> None:
    task["execution_status"] = execution_status
    task["final_status"] = final_status or execution_status
    task["status_reason"] = status_reason


def initialize_task_statuses(tasks: List[Dict[str, Any]]) -> None:
    for task in tasks:
        execution_status, final_status, status_reason = initial_task_status(task)
        apply_task_status(task, execution_status, final_status, status_reason)


def infer_review_source(task: Dict[str, Any]) -> str:
    final_status = str(task.get("final_status") or "")
    execution_status = str(task.get("execution_status") or "")
    if final_status == "blocked":
        return "post_gate_blocked"
    if execution_status == "failed":
        return "execution_failure"
    if final_status == "review_handoff":
        return "initial_manual_review"
    return ""


def build_review_queue_entry(
    task: Dict[str, Any],
    queue_reason: str,
    review_source: str,
    current_target: str,
) -> Dict[str, str]:
    review_status = str(task.get("review_status") or "pending")
    if review_status == "not_required":
        review_status = "pending"
    return {
        "task_id": task["task_id"],
        "string_id": task["string_id"],
        "task_type": task["task_type"],
        "review_owner": str(task.get("review_owner") or "human-linguist"),
        "review_status": review_status,
        "review_source": review_source,
        "queue_reason": queue_reason,
        "execution_status": str(task.get("execution_status") or ""),
        "final_status": str(task.get("final_status") or ""),
        "status_reason": str(task.get("status_reason") or queue_reason),
        "reason_codes": json.dumps(task["reason_codes"], ensure_ascii=False),
        "manual_review_reason": task.get("manual_review_reason") or "",
        "current_target": current_target,
    }


def build_initial_review_queue(tasks: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for task in tasks:
        if not task["human_review_required"]:
            continue
        rows.append(
            build_review_queue_entry(
                task=task,
                queue_reason=task.get("manual_review_reason") or task["task_type"],
                review_source="initial_manual_review",
                current_target=task.get("current_target") or "",
            )
        )
    return rows


def group_tasks_by_locale(tasks: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for task in tasks:
        locale = str(task.get("target_locale") or "").strip()
        if not locale:
            raise ValueError(f"Task {task.get('task_id') or task.get('string_id') or '<unknown>'} missing target_locale")
        grouped.setdefault(locale, []).append(task)
    return grouped


def build_refresh_system_prompt(style_text: str, target_locale: str) -> str:
    return (
        f"你是严谨的本地化增量刷新器（zh-CN -> {target_locale}）。\n"
        "任务：基于 source_zh、current_target 与 glossary_hints，只做最小必要改写。\n"
        "硬约束：\n"
        "- 必须保留所有占位符、tag、markup 的原始数量和顺序。\n"
        "- 不允许擅自扩写，不允许删除语义。\n"
        "- 如果当前译文已经满足要求，可直接返回原文。\n"
        "输出必须是 JSON：{\"items\":[{\"id\":\"...\",\"updated_target\":\"...\"}]}\n"
        f"style_guide:\n{style_text[:1500]}"
    )


def build_refresh_user_prompt(items: List[Dict[str, str]]) -> str:
    payload = []
    for item in items:
        payload.append(json.loads(item["source_text"]))
    return json.dumps(payload, ensure_ascii=False, indent=2)


def select_result_text(item: Dict[str, Any], target_key: str) -> str:
    for candidate in ("updated_target", target_key, "target_text", "target_ru", "updated_ru", "target"):
        value = str(item.get(candidate) or "").strip()
        if value:
            return value
    return ""


def run_refresh_llm(
    tasks: List[Dict[str, Any]],
    model: str,
    style_text: str,
) -> Tuple[Dict[str, str], Dict[str, str]]:
    if not tasks:
        return {}, {}
    updates: Dict[str, str] = {}
    failures: Dict[str, str] = {}
    for locale, locale_tasks in group_tasks_by_locale(tasks).items():
        llm_rows: List[Dict[str, str]] = []
        for task in locale_tasks:
            payload = {
                "id": task["string_id"],
                "source_zh": task.get("source_zh") or task.get("source_text") or "",
                "current_target": task.get("current_target") or "",
                "glossary_hints": task.get("relevant_glossary_terms") or [],
                "reason_codes": task.get("reason_codes") or [],
            }
            llm_rows.append({"id": task["string_id"], "source_text": json.dumps(payload, ensure_ascii=False)})

        results = batch_llm_call(
            step="translate_refresh_incremental",
            rows=llm_rows,
            model=model,
            system_prompt=build_refresh_system_prompt(style_text, locale),
            user_prompt_template=build_refresh_user_prompt,
            content_type="normal",
            retry=2,
            allow_fallback=True,
        )
        target_key = derive_target_key(locale)
        by_id = {task["string_id"]: task for task in locale_tasks}
        for result in results:
            string_id = str(result.get("id") or "")
            if not string_id or string_id not in by_id:
                continue
            candidate = select_result_text(result, target_key)
            if not candidate:
                failures[string_id] = "empty_llm_output"
                continue
            if tokens_signature(by_id[string_id]["source_text"]) != tokens_signature(candidate):
                failures[string_id] = "placeholder_signature_mismatch"
                continue
            updates[string_id] = candidate

        for task in locale_tasks:
            if task["string_id"] not in updates and task["string_id"] not in failures:
                failures[task["string_id"]] = "missing_llm_result"
    return updates, failures


def run_retranslate_llm(
    tasks: List[Dict[str, Any]],
    model: str,
    style_text: str,
    glossary_summaries_by_locale: Dict[str, str],
    style_profile: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, str], Dict[str, str]]:
    if not tasks:
        return {}, {}
    updates: Dict[str, str] = {}
    failures: Dict[str, str] = {}
    for locale, locale_tasks in group_tasks_by_locale(tasks).items():
        llm_rows = [{"id": task["string_id"], "source_text": task["source_text"]} for task in locale_tasks]
        target_key = derive_target_key(locale)
        system_prompt_builder = build_system_prompt_factory(
            style_guide=style_text,
            glossary_summary=glossary_summaries_by_locale.get(locale, ""),
            style_profile=style_profile,
            target_lang=locale,
            target_key=target_key,
        )
        results = batch_llm_call(
            step="translate_refresh_retranslate",
            rows=llm_rows,
            model=model,
            system_prompt=system_prompt_builder,
            user_prompt_template=build_user_prompt,
            content_type="normal",
            retry=2,
            allow_fallback=True,
        )
        by_id = {task["string_id"]: task for task in locale_tasks}
        for result in results:
            string_id = str(result.get("id") or result.get("string_id") or "")
            if not string_id or string_id not in by_id:
                continue
            candidate = select_result_text(result, target_key)
            if not candidate:
                failures[string_id] = "empty_llm_output"
                continue
            if tokens_signature(by_id[string_id]["source_text"]) != tokens_signature(candidate):
                failures[string_id] = "placeholder_signature_mismatch"
                continue
            updates[string_id] = candidate
        for task in locale_tasks:
            if task["string_id"] not in updates and task["string_id"] not in failures:
                failures[task["string_id"]] = "missing_llm_result"
    return updates, failures


def ensure_refresh_columns(rows: List[Dict[str, str]], tasks: List[Dict[str, Any]]) -> List[str]:
    fieldnames = list(rows[0].keys()) if rows else []
    locale_fields = set()
    for row in rows:
        locale = str(row.get("target_locale") or "").strip()
        if locale:
            locale_fields.add(derive_target_key(locale))
    for task in tasks:
        locale = str(task.get("target_locale") or "").strip()
        if locale:
            locale_fields.add(derive_target_key(locale))
    for field in list(locale_fields) + ["target_text", "target", "refresh_status", "refresh_task_type", "refresh_notes"]:
        if field not in fieldnames:
            fieldnames.append(field)
    return fieldnames


def pick_row_target_text(row: Dict[str, str]) -> str:
    locale = str(row.get("target_locale") or "").strip()
    candidates: List[str] = []
    if locale:
        candidates.append(derive_target_key(locale))
    candidates.extend(["target_text", "target", "target_ru"])
    seen = set()
    for field in candidates:
        if field in seen:
            continue
        seen.add(field)
        candidate = str(row.get(field) or "")
        if candidate:
            return candidate
    return ""


def build_gate_failure_reason(
    string_id: str,
    row_count_gate: Dict[str, Any],
    placeholder_failed_ids: Iterable[str],
    qa_failed_ids: Iterable[str],
) -> str:
    reasons: List[str] = []
    placeholder_failed_set = set(placeholder_failed_ids)
    qa_failed_set = set(qa_failed_ids)
    if not row_count_gate.get("passed", False):
        reasons.append("row_count_integrity_failed")
    if string_id in placeholder_failed_set:
        reasons.append("placeholder_signature_failed")
    if string_id in qa_failed_set:
        reasons.append("qa_hard_failed")
    return ";".join(reasons) or "post_gate_blocked"


def summarize_task_outcomes(tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
    counts_by_execution_status: Dict[str, int] = {}
    counts_by_final_status: Dict[str, int] = {}
    items: List[Dict[str, Any]] = []
    for task in tasks:
        execution_status = str(task.get("execution_status") or "")
        final_status = str(task.get("final_status") or "")
        counts_by_execution_status[execution_status] = counts_by_execution_status.get(execution_status, 0) + 1
        counts_by_final_status[final_status] = counts_by_final_status.get(final_status, 0) + 1
        items.append(
            {
                "task_id": task["task_id"],
                "string_id": task["string_id"],
                "task_type": task["task_type"],
                "execution_status": execution_status,
                "final_status": final_status,
                "status_reason": str(task.get("status_reason") or ""),
                "review_source": infer_review_source(task),
            }
        )
    return {
        "counts_by_execution_status": counts_by_execution_status,
        "counts_by_final_status": counts_by_final_status,
        "items": items,
    }


def derive_overall_status(tasks: List[Dict[str, Any]], gate_status: str = "passed") -> str:
    if gate_status == "blocked":
        return "blocked"
    if any(str(task.get("final_status") or "") == "blocked" for task in tasks):
        return "blocked"
    if any(str(task.get("execution_status") or "") == "failed" for task in tasks):
        return "failed"
    if any(str(task.get("final_status") or "") == "review_handoff" for task in tasks):
        return "review_handoff"
    if any(str(task.get("final_status") or "") == "updated" for task in tasks):
        return "updated"
    return "pending"


def build_gate_summary(
    row_count_gate: Dict[str, Any],
    placeholder_gate: Dict[str, Any],
    qa_gate: Dict[str, Any],
    blocked_task_ids: List[str],
    blocked_string_ids: List[str],
) -> Dict[str, Any]:
    failed_gates: List[str] = []
    if not row_count_gate.get("passed", False):
        failed_gates.append("row_count_integrity")
    if not placeholder_gate.get("passed", False):
        failed_gates.append("placeholder_signature_integrity")
    if not qa_gate.get("passed", False):
        failed_gates.append("qa_hard")
    return {
        "status": "blocked" if failed_gates else "passed",
        "failed_gates": failed_gates,
        "blocked_task_ids": blocked_task_ids,
        "blocked_string_ids": blocked_string_ids,
    }


def build_review_handoff_summary(review_queue: List[Dict[str, str]], queue_path: str) -> Dict[str, Any]:
    by_source: Dict[str, int] = {}
    for item in review_queue:
        source = str(item.get("review_source") or "unknown")
        by_source[source] = by_source.get(source, 0) + 1
    return {
        "queue_path": queue_path,
        "pending_count": len(review_queue),
        "string_ids": [item["string_id"] for item in review_queue],
        "by_source": by_source,
        "items": review_queue,
    }


def verify_placeholder_integrity(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    failing_ids: List[str] = []
    checked = 0
    for row in rows:
        string_id = str(row.get("string_id") or "")
        source_text = row_source_text(row)
        target_text = pick_row_target_text(row)
        if not source_text or not target_text:
            continue
        checked += 1
        if tokens_signature(source_text) != tokens_signature(target_text):
            failing_ids.append(string_id)
    return {
        "checked_rows": checked,
        "failed_string_ids": failing_ids,
        "passed": not failing_ids,
    }


def run_qa_hard_gate(
    translated_csv: str,
    placeholder_map: str,
    schema: str,
    forbidden: str,
    report_path: str,
) -> Dict[str, Any]:
    validator = QAHardValidator(
        translated_csv=translated_csv,
        placeholder_map=placeholder_map,
        schema_yaml=schema,
        forbidden_txt=forbidden,
        report_json=report_path,
    )
    passed = validator.run()
    report = read_json(report_path) if Path(report_path).exists() else {}
    return {
        "passed": passed,
        "report_path": report_path,
        "error_total": len(report.get("errors", [])),
        "warning_total": len(report.get("warnings", [])),
        "failed_string_ids": sorted({str(item.get("string_id") or "") for item in report.get("errors", []) if item.get("string_id")}),
    }


def staged_candidate_path(out_csv: str) -> str:
    requested = Path(out_csv)
    if requested.suffix:
        return str(requested.with_name(f"{requested.stem}.candidate{requested.suffix}"))
    return str(requested.with_name(f"{requested.name}.candidate"))


def execute_tasks(
    tasks: List[Dict[str, Any]],
    translated_rows: List[Dict[str, str]],
    translated_csv_path: str,
    out_csv: str,
    model: str,
    style_text: str,
    glossary_summaries_by_locale: Dict[str, str],
    style_profile: Optional[Dict[str, Any]],
    review_queue_path: str,
    failure_breakdown_path: str,
    placeholder_map: str,
    schema: str,
    forbidden: str,
    qa_report: str,
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], Dict[str, Any]]:
    rows = [dict(row) for row in translated_rows]
    rows_by_id = {str(row.get("string_id") or ""): row for row in rows}
    fieldnames = ensure_refresh_columns(rows, tasks)
    initialize_task_statuses(tasks)
    review_queue = build_initial_review_queue(tasks)
    failure_breakdown: Dict[str, str] = {}

    refresh_tasks = [task for task in tasks if task["task_type"] == "refresh"]
    retranslate_tasks = [task for task in tasks if task["task_type"] == "retranslate"]

    refresh_updates, refresh_failures = run_refresh_llm(refresh_tasks, model, style_text)
    retranslate_updates, retranslate_failures = run_retranslate_llm(
        retranslate_tasks,
        model,
        style_text,
        glossary_summaries_by_locale,
        style_profile,
    )

    for string_id, reason in {**refresh_failures, **retranslate_failures}.items():
        failure_breakdown[string_id] = reason

    update_map = {**refresh_updates, **retranslate_updates}

    for task in tasks:
        row = rows_by_id.get(task["string_id"])
        if row is None:
            raise ValueError(f"Task {task['task_id']} references missing row {task['string_id']}")

        task_type = task["task_type"]
        if task_type in {"manual_review", "skip"}:
            row["refresh_status"] = "review_handoff"
            row["refresh_task_type"] = task_type
            row["refresh_notes"] = task.get("manual_review_reason") or task_type
            apply_task_status(
                task,
                execution_status="review_handoff",
                final_status="review_handoff",
                status_reason=task.get("manual_review_reason") or task_type,
            )
            continue

        updated_text = update_map.get(task["string_id"])
        if not updated_text:
            row["refresh_status"] = "failed"
            row["refresh_task_type"] = task_type
            row["refresh_notes"] = failure_breakdown.get(task["string_id"], "execution_failed")
            apply_task_status(
                task,
                execution_status="failed",
                final_status="review_handoff",
                status_reason=failure_breakdown.get(task["string_id"], "execution_failed"),
            )
            review_queue.append(
                build_review_queue_entry(
                    task=task,
                    queue_reason=failure_breakdown.get(task["string_id"], "execution_failed"),
                    review_source="execution_failure",
                    current_target=task.get("current_target") or "",
                )
            )
            continue

        target_key = derive_target_key(str(task["target_locale"]))
        row[target_key] = updated_text
        row["target_text"] = updated_text
        row["target"] = updated_text
        row["refresh_status"] = "updated"
        row["refresh_task_type"] = task_type
        row["refresh_notes"] = ""
        apply_task_status(task, execution_status="updated", final_status="updated", status_reason="")

    candidate_csv = staged_candidate_path(out_csv)
    write_csv(candidate_csv, rows, fieldnames)
    placeholder_gate = verify_placeholder_integrity(rows)
    qa_gate = run_qa_hard_gate(candidate_csv, placeholder_map, schema, forbidden, qa_report)
    write_json(
        failure_breakdown_path,
        {
            "generated_at": now_iso(),
            "total_failed": len(failure_breakdown),
            "by_string_id": failure_breakdown,
        },
    )
    row_count_gate = {
        "input_rows": len(translated_rows),
        "output_rows": len(rows),
        "passed": len(translated_rows) == len(rows),
    }
    placeholder_failed_ids = set(placeholder_gate["failed_string_ids"])
    qa_failed_ids = set(qa_gate["failed_string_ids"])
    blocked_task_ids: List[str] = []
    blocked_string_ids: List[str] = []
    if not row_count_gate["passed"]:
        blocked_task_ids = [task["task_id"] for task in tasks]
        blocked_string_ids = [task["string_id"] for task in tasks]
    else:
        blocked_string_id_set = placeholder_failed_ids | qa_failed_ids
        for task in tasks:
            if task["string_id"] in blocked_string_id_set:
                blocked_task_ids.append(task["task_id"])
                blocked_string_ids.append(task["string_id"])

    for task in tasks:
        if task["task_id"] not in blocked_task_ids:
            continue
        status_reason = build_gate_failure_reason(
            task["string_id"],
            row_count_gate=row_count_gate,
            placeholder_failed_ids=placeholder_failed_ids,
            qa_failed_ids=qa_failed_ids,
        )
        apply_task_status(
            task,
            execution_status=str(task.get("execution_status") or "pending"),
            final_status="blocked",
            status_reason=status_reason,
        )
        row = rows_by_id.get(task["string_id"])
        if row is not None:
            row["refresh_status"] = "blocked"
            row["refresh_notes"] = status_reason
        review_queue.append(
            build_review_queue_entry(
                task=task,
                queue_reason=status_reason,
                review_source="post_gate_blocked",
                current_target=pick_row_target_text(row) if row is not None else task.get("current_target") or "",
            )
        )

    deduped: List[Dict[str, str]] = []
    seen = set()
    for item in review_queue:
        key = (item["task_id"], item["queue_reason"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    write_review_queue(review_queue_path, deduped)

    gates_passed = row_count_gate["passed"] and placeholder_gate["passed"] and qa_gate["passed"]
    execution_failed = any(str(task.get("execution_status") or "") == "failed" for task in tasks)
    promotion_allowed = gates_passed and not execution_failed
    if promotion_allowed:
        Path(candidate_csv).replace(out_csv)

    task_outcomes = summarize_task_outcomes(tasks)
    gate_summary = build_gate_summary(
        row_count_gate=row_count_gate,
        placeholder_gate=placeholder_gate,
        qa_gate=qa_gate,
        blocked_task_ids=blocked_task_ids,
        blocked_string_ids=blocked_string_ids,
    )
    manifest = {
        "generated_at": now_iso(),
        "mode": "execute",
        "overall_status": derive_overall_status(tasks, gate_status=gate_summary["status"]),
        "task_counts": {
            "total": len(tasks),
            "by_type": {task_type: len([task for task in tasks if task["task_type"] == task_type]) for task_type in TASK_TYPE_TO_SCOPE},
        },
        "execution": {
            "updated": len([task for task in tasks if task.get("execution_status") == "updated"]),
            "review_handoff": len([task for task in tasks if task.get("execution_status") == "review_handoff"]),
            "failed": len([task for task in tasks if task.get("execution_status") == "failed"]),
            "blocked": len([task for task in tasks if task.get("final_status") == "blocked"]),
            "skipped_direct_write": len([task for task in tasks if task["task_type"] in {"manual_review", "skip"}]),
            "failure_breakdown": failure_breakdown,
        },
        "task_outcomes": task_outcomes,
        "artifacts": {
            "input_translated_csv": translated_csv_path,
            "candidate_output_csv": out_csv if promotion_allowed else candidate_csv,
            "staged_candidate_csv": candidate_csv,
            "failure_breakdown_json": failure_breakdown_path,
            "review_queue_csv": review_queue_path,
            "qa_report_json": qa_report,
        },
        "post_gates": {
            "row_count_integrity": row_count_gate,
            "placeholder_signature_integrity": placeholder_gate,
            "qa_hard": qa_gate,
        },
        "gate_summary": gate_summary,
        "review_handoff": build_review_handoff_summary(deduped, review_queue_path),
    }
    return rows, deduped, manifest


def build_generation_manifest(tasks: List[Dict[str, Any]], review_queue: List[Dict[str, str]]) -> Dict[str, Any]:
    initialize_task_statuses(tasks)
    return {
        "generated_at": now_iso(),
        "mode": "generate_only",
        "overall_status": derive_overall_status(tasks, gate_status="skipped"),
        "task_counts": {
            "total": len(tasks),
            "by_type": {task_type: len([task for task in tasks if task["task_type"] == task_type]) for task_type in TASK_TYPE_TO_SCOPE},
        },
        "execution": {
            "updated": 0,
            "review_handoff": len([task for task in tasks if task.get("execution_status") == "review_handoff"]),
            "failed": 0,
            "blocked": 0,
            "skipped_direct_write": len([task for task in tasks if task["task_type"] in {"manual_review", "skip"}]),
            "failure_breakdown": {},
        },
        "task_outcomes": summarize_task_outcomes(tasks),
        "post_gates": {
            "row_count_integrity": {"passed": True, "skipped": "generate_only"},
            "placeholder_signature_integrity": {"passed": True, "skipped": "generate_only"},
            "qa_hard": {"passed": True, "skipped": "generate_only"},
        },
        "gate_summary": {
            "status": "skipped",
            "failed_gates": [],
            "blocked_task_ids": [],
            "blocked_string_ids": [],
        },
        "review_handoff": build_review_handoff_summary(review_queue, ""),
    }


def read_style_text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8").strip()


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Milestone E incremental refresh task executor")
    parser.add_argument("--delta-rows", default="", help="delta_rows.jsonl from typed delta engine")
    parser.add_argument("--delta-report", default="", help="delta_report.json from typed delta engine")
    parser.add_argument("--impact", default="", help="Legacy alias for --delta-report; does not recompute delta")
    parser.add_argument("--translated", required=True, help="Current translated CSV")
    parser.add_argument("--glossary", default="glossary/compiled.yaml")
    parser.add_argument("--style", required=True, help="Style guide markdown")
    parser.add_argument("--style-profile", default="data/style_profile.yaml", help="Governed style profile path")
    parser.add_argument("--lifecycle-registry", default="workflow/lifecycle_registry.yaml", help="Lifecycle registry for governed assets")
    parser.add_argument("--target-locale", default="ru-RU")
    parser.add_argument("--tasks-out", default="data/incremental_tasks.jsonl")
    parser.add_argument("--review-queue", default="data/incremental_review_queue.csv")
    parser.add_argument("--review-tickets", default="data/review_tickets.jsonl")
    parser.add_argument("--review-tickets-csv", default="data/review_tickets.csv")
    parser.add_argument("--feedback-log", default="data/review_feedback_log.jsonl")
    parser.add_argument("--kpi-report", default="data/language_governance_kpi.json")
    parser.add_argument("--manifest", default="data/incremental_refresh_manifest.json")
    parser.add_argument("--failure-breakdown", default="data/incremental_failure_breakdown.json")
    parser.add_argument("--out-csv", "--out_csv", dest="out_csv", default="data/refreshed.csv")
    parser.add_argument("--tasks-in", default="", help="Execute pre-generated incremental_tasks.jsonl")
    parser.add_argument("--generate-only", action="store_true")
    parser.add_argument("--placeholder-map", default="data/placeholder_map.json")
    parser.add_argument("--schema", default="workflow/placeholder_schema.yaml")
    parser.add_argument("--forbidden", default="workflow/forbidden_patterns.txt")
    parser.add_argument("--qa-report", default="data/qa_refresh_report.json")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    configure_standard_streams()
    args = parse_args(argv)
    delta_report_path = args.delta_report or args.impact

    if Path(args.translated).resolve() == Path(args.out_csv).resolve():
        raise ValueError("--out-csv must differ from --translated so executor does not overwrite canonical input in place")

    translated_rows = read_csv_rows(args.translated)
    if not translated_rows:
        raise ValueError(f"Translated CSV is empty: {args.translated}")

    try:
        style_profile, runtime_governance = validate_style_governance_runtime(
            args.style_profile,
            lifecycle_registry_path=args.lifecycle_registry,
        )
        validate_governed_asset(args.glossary, "glossary", lifecycle_registry_path=args.lifecycle_registry)
        validate_governed_asset(args.schema, "policy", lifecycle_registry_path=args.lifecycle_registry)
    except GovernanceError as exc:
        raise ValueError(f"Phase 3 governance gate failed: {exc}") from exc

    style_text = read_style_text(args.style)

    if args.tasks_in:
        tasks = validate_tasks(read_jsonl(args.tasks_in))
    else:
        delta_rows, report = load_delta_inputs(args.delta_rows, delta_report_path)
        task_locales = [str(row.get("target_locale") or args.target_locale) for row in delta_rows]
        glossary_maps_by_locale, _ = build_glossary_resources(args.glossary, task_locales)
        source_artifacts = {
            "delta_rows": args.delta_rows or str(report.get("row_impacts_path") or ""),
            "delta_report": delta_report_path,
            "translated_csv": args.translated,
            "glossary": args.glossary,
            "style": args.style,
            "style_profile": args.style_profile,
            "lifecycle_registry": args.lifecycle_registry,
        }
        tasks = generate_tasks(delta_rows, translated_rows, source_artifacts, glossary_maps_by_locale)

    task_locales = [str(task.get("target_locale") or args.target_locale) for task in tasks]
    _, glossary_summaries_by_locale = build_glossary_resources(args.glossary, task_locales)

    initialize_task_statuses(tasks)
    write_jsonl(args.tasks_out, tasks)
    review_queue = build_initial_review_queue(tasks)
    write_review_queue(args.review_queue, review_queue)
    ticket_source_artifacts = {
        "tasks_out": args.tasks_out,
        "review_queue": args.review_queue,
        "manifest": args.manifest,
        "style_profile": args.style_profile,
    }
    review_tickets = build_review_tickets(
        review_queue,
        task_lookup={str(task.get("task_id") or ""): task for task in tasks},
        source_artifacts=ticket_source_artifacts,
        default_locale=args.target_locale,
    )
    write_review_tickets(args.review_tickets, args.review_tickets_csv, review_tickets)
    ensure_feedback_log(args.feedback_log)
    feedback_logs = load_feedback_log(args.feedback_log)

    if args.generate_only:
        manifest = build_generation_manifest(tasks, review_queue)
        manifest["review_handoff"]["queue_path"] = args.review_queue
        manifest["runtime_governance"] = runtime_governance
        manifest["artifacts"] = {
            "review_tickets_jsonl": args.review_tickets,
            "review_tickets_csv": args.review_tickets_csv,
            "feedback_log_jsonl": args.feedback_log,
            "kpi_report_json": args.kpi_report,
        }
        governance_write_json(
            args.kpi_report,
            build_kpi_report(
                scope="translate_refresh_generate_only",
                manifest=manifest,
                review_tickets=review_tickets,
                feedback_logs=feedback_logs,
                runtime_governance=runtime_governance,
                lifecycle_registry=load_lifecycle_registry(args.lifecycle_registry),
                extra_sources={
                    "tasks_out": args.tasks_out,
                    "review_queue": args.review_queue,
                    "review_tickets": args.review_tickets,
                    "feedback_log": args.feedback_log,
                    "lifecycle_registry_path": args.lifecycle_registry,
                },
            ),
        )
        write_json(args.manifest, manifest)
        return 0

    _, review_queue_rows, manifest = execute_tasks(
        tasks=tasks,
        translated_rows=translated_rows,
        translated_csv_path=args.translated,
        out_csv=args.out_csv,
        model=args.model,
        style_text=style_text,
        glossary_summaries_by_locale=glossary_summaries_by_locale,
        style_profile=style_profile,
        review_queue_path=args.review_queue,
        failure_breakdown_path=args.failure_breakdown,
        placeholder_map=args.placeholder_map,
        schema=args.schema,
        forbidden=args.forbidden,
        qa_report=args.qa_report,
    )
    manifest["inputs"] = {
        "translated_csv": args.translated,
        "tasks_in": args.tasks_in,
        "tasks_out": args.tasks_out,
        "delta_report": delta_report_path,
        "glossary": args.glossary,
        "style": args.style,
        "style_profile": args.style_profile,
        "lifecycle_registry": args.lifecycle_registry,
        "failure_breakdown": args.failure_breakdown,
    }
    manifest["runtime_governance"] = runtime_governance
    manifest["review_handoff"]["queue_path"] = args.review_queue
    manifest["review_handoff"]["pending_count"] = len(review_queue_rows)
    manifest["review_handoff"]["string_ids"] = [item["string_id"] for item in review_queue_rows]
    manifest["review_handoff"]["items"] = review_queue_rows
    manifest["review_handoff"]["by_source"] = build_review_handoff_summary(review_queue_rows, args.review_queue)["by_source"]
    review_tickets = build_review_tickets(
        review_queue_rows,
        task_lookup={str(task.get("task_id") or ""): task for task in tasks},
        source_artifacts={
            "translated_csv": args.translated,
            "tasks_out": args.tasks_out,
            "review_queue": args.review_queue,
            "manifest": args.manifest,
            "style_profile": args.style_profile,
        },
        default_locale=args.target_locale,
    )
    write_review_tickets(args.review_tickets, args.review_tickets_csv, review_tickets)
    ensure_feedback_log(args.feedback_log)
    feedback_logs = load_feedback_log(args.feedback_log)
    governance_write_json(
        args.kpi_report,
        build_kpi_report(
            scope="translate_refresh_execute",
            manifest=manifest,
            review_tickets=review_tickets,
            feedback_logs=feedback_logs,
            runtime_governance=runtime_governance,
            lifecycle_registry=load_lifecycle_registry(args.lifecycle_registry),
            extra_sources={
                "translated_csv": args.translated,
                "tasks_out": args.tasks_out,
                "review_queue": args.review_queue,
                "review_tickets": args.review_tickets,
                "feedback_log": args.feedback_log,
                "lifecycle_registry_path": args.lifecycle_registry,
            },
        ),
    )
    manifest.setdefault("artifacts", {})
    manifest["artifacts"]["review_tickets_jsonl"] = args.review_tickets
    manifest["artifacts"]["review_tickets_csv"] = args.review_tickets_csv
    manifest["artifacts"]["feedback_log_jsonl"] = args.feedback_log
    manifest["artifacts"]["kpi_report_json"] = args.kpi_report
    write_jsonl(args.tasks_out, tasks)
    write_json(args.manifest, manifest)
    gates = manifest["post_gates"]
    if not gates["row_count_integrity"]["passed"]:
        return 1
    if not gates["placeholder_signature_integrity"]["passed"]:
        return 1
    if not gates["qa_hard"]["passed"]:
        return 1
    if manifest["execution"]["failed"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
