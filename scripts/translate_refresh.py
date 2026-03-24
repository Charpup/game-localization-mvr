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
    tokens_signature,
)


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
    "queue_reason",
    "execution_status",
    "reason_codes",
    "manual_review_reason",
    "current_target",
]


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


def build_initial_review_queue(tasks: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for task in tasks:
        if not task["human_review_required"]:
            continue
        rows.append(
            {
                "task_id": task["task_id"],
                "string_id": task["string_id"],
                "task_type": task["task_type"],
                "review_owner": task["review_owner"],
                "review_status": task["review_status"],
                "queue_reason": task.get("manual_review_reason") or task["task_type"],
                "execution_status": "pending_handoff",
                "reason_codes": json.dumps(task["reason_codes"], ensure_ascii=False),
                "manual_review_reason": task.get("manual_review_reason") or "",
                "current_target": task.get("current_target") or "",
            }
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
            style_profile=None,
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
    review_queue = build_initial_review_queue(tasks)
    execution_status: Dict[str, str] = {}
    failure_breakdown: Dict[str, str] = {}

    refresh_tasks = [task for task in tasks if task["task_type"] == "refresh"]
    retranslate_tasks = [task for task in tasks if task["task_type"] == "retranslate"]

    refresh_updates, refresh_failures = run_refresh_llm(refresh_tasks, model, style_text)
    retranslate_updates, retranslate_failures = run_retranslate_llm(
        retranslate_tasks,
        model,
        style_text,
        glossary_summaries_by_locale,
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
            execution_status[task["task_id"]] = "review_handoff"
            continue

        updated_text = update_map.get(task["string_id"])
        if not updated_text:
            row["refresh_status"] = "failed"
            row["refresh_task_type"] = task_type
            row["refresh_notes"] = failure_breakdown.get(task["string_id"], "execution_failed")
            execution_status[task["task_id"]] = "failed"
            review_queue.append(
                {
                    "task_id": task["task_id"],
                    "string_id": task["string_id"],
                    "task_type": task_type,
                    "review_owner": "human-linguist",
                    "review_status": "pending",
                    "queue_reason": failure_breakdown.get(task["string_id"], "execution_failed"),
                    "execution_status": "failed",
                    "reason_codes": json.dumps(task["reason_codes"], ensure_ascii=False),
                    "manual_review_reason": task.get("manual_review_reason") or "",
                    "current_target": task.get("current_target") or "",
                }
            )
            continue

        target_key = derive_target_key(str(task["target_locale"]))
        row[target_key] = updated_text
        row["target_text"] = updated_text
        row["target"] = updated_text
        row["refresh_status"] = "updated"
        row["refresh_task_type"] = task_type
        row["refresh_notes"] = ""
        execution_status[task["task_id"]] = "updated"

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
    qa_failed_ids = set(qa_gate["failed_string_ids"])
    for task in tasks:
        if task["string_id"] not in qa_failed_ids:
            continue
        review_queue.append(
            {
                "task_id": task["task_id"],
                "string_id": task["string_id"],
                "task_type": task["task_type"],
                "review_owner": "human-linguist",
                "review_status": "pending",
                "queue_reason": "qa_hard_failed",
                "execution_status": execution_status.get(task["task_id"], "unknown"),
                "reason_codes": json.dumps(task["reason_codes"], ensure_ascii=False),
                "manual_review_reason": task.get("manual_review_reason") or "",
                "current_target": task.get("current_target") or "",
            }
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

    row_count_gate = {
        "input_rows": len(translated_rows),
        "output_rows": len(rows),
        "passed": len(translated_rows) == len(rows),
    }
    gates_passed = row_count_gate["passed"] and placeholder_gate["passed"] and qa_gate["passed"]
    if gates_passed:
        Path(candidate_csv).replace(out_csv)

    manifest = {
        "generated_at": now_iso(),
        "mode": "execute",
        "task_counts": {
            "total": len(tasks),
            "by_type": {task_type: len([task for task in tasks if task["task_type"] == task_type]) for task_type in TASK_TYPE_TO_SCOPE},
        },
        "execution": {
            "updated": len([status for status in execution_status.values() if status == "updated"]),
            "review_handoff": len([status for status in execution_status.values() if status == "review_handoff"]),
            "failed": len([status for status in execution_status.values() if status == "failed"]),
            "skipped_direct_write": len([task for task in tasks if task["task_type"] in {"manual_review", "skip"}]),
            "failure_breakdown": failure_breakdown,
        },
        "artifacts": {
            "input_translated_csv": translated_csv_path,
            "candidate_output_csv": out_csv if gates_passed else candidate_csv,
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
        "review_handoff": {
            "queue_path": review_queue_path,
            "pending_count": len(deduped),
            "string_ids": [item["string_id"] for item in deduped],
        },
    }
    return rows, deduped, manifest


def build_generation_manifest(tasks: List[Dict[str, Any]], review_queue: List[Dict[str, str]]) -> Dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "mode": "generate_only",
        "task_counts": {
            "total": len(tasks),
            "by_type": {task_type: len([task for task in tasks if task["task_type"] == task_type]) for task_type in TASK_TYPE_TO_SCOPE},
        },
        "execution": {
            "updated": 0,
            "review_handoff": len(review_queue),
            "failed": 0,
            "skipped_direct_write": len([task for task in tasks if task["task_type"] in {"manual_review", "skip"}]),
            "failure_breakdown": {},
        },
        "post_gates": {
            "row_count_integrity": {"passed": True, "skipped": "generate_only"},
            "placeholder_signature_integrity": {"passed": True, "skipped": "generate_only"},
            "qa_hard": {"passed": True, "skipped": "generate_only"},
        },
        "review_handoff": {
            "queue_path": "",
            "pending_count": len(review_queue),
            "string_ids": [item["string_id"] for item in review_queue],
        },
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
    parser.add_argument("--target-locale", default="ru-RU")
    parser.add_argument("--tasks-out", default="data/incremental_tasks.jsonl")
    parser.add_argument("--review-queue", default="data/incremental_review_queue.csv")
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
        }
        tasks = generate_tasks(delta_rows, translated_rows, source_artifacts, glossary_maps_by_locale)

    task_locales = [str(task.get("target_locale") or args.target_locale) for task in tasks]
    _, glossary_summaries_by_locale = build_glossary_resources(args.glossary, task_locales)

    write_jsonl(args.tasks_out, tasks)
    review_queue = build_initial_review_queue(tasks)
    write_review_queue(args.review_queue, review_queue)

    if args.generate_only:
        manifest = build_generation_manifest(tasks, review_queue)
        manifest["review_handoff"]["queue_path"] = args.review_queue
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
        "failure_breakdown": args.failure_breakdown,
    }
    manifest["review_handoff"]["queue_path"] = args.review_queue
    manifest["review_handoff"]["pending_count"] = len(review_queue_rows)
    manifest["review_handoff"]["string_ids"] = [item["string_id"] for item in review_queue_rows]
    write_json(args.manifest, manifest)
    gates = manifest["post_gates"]
    if not gates["row_count_integrity"]["passed"]:
        return 1
    if not gates["placeholder_signature_integrity"]["passed"]:
        return 1
    if not gates["qa_hard"]["passed"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
