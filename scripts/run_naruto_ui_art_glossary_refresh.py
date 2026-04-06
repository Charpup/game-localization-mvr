#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_naruto_ui_art_glossary_refresh.py

Orchestrate workbook-driven glossary extraction, merged glossary compilation,
typed glossary delta, incremental refresh, review CSV rebuild, and glossary
autopromote for the Naruto RU UI-art residual v2 slice.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import yaml


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKBOOK = Path(
    r"D:\Document\Dropbox\Dropbox\Txt\Jobs\渡鸦工坊 - RavenCraft\P-产品\3-3D 火影\俄文版\L-本地化\R-俄罗斯\3D 火影俄文-交接产物\3D 火影项目_俄文_本地化接力校对_2026.03.23.xlsx"
)
DEFAULT_BASE_SLICE_DIR = REPO_ROOT / (
    "data/incoming/naruto_ui_art_ru_20260404/runs/"
    "ui_art_full_rerun_20260404_run01/residual_triage_20260405_slice01/"
    "residual_v2_20260405_slice02"
)
DEFAULT_RUN_DIR = DEFAULT_BASE_SLICE_DIR / "glossary_refresh_20260406_run01"
DEFAULT_MERGED_APPROVED = REPO_ROOT / "glossary/zhCN_ruRU/project_naruto_ui_art_workbook_refresh_approved.yaml"
DEFAULT_COMPILED_GLOSSARY = REPO_ROOT / "glossary/compiled_naruto_ui_art_workbook_refresh.yaml"
DEFAULT_LIFECYCLE_REGISTRY = REPO_ROOT / "workflow/lifecycle_registry.yaml"
DEFAULT_STYLE_GUIDE = REPO_ROOT / "workflow/style_guide.md"
DEFAULT_STYLE_PROFILE = REPO_ROOT / "workflow/style_profile.generated.yaml"
DEFAULT_PLACEHOLDER_SCHEMA = REPO_ROOT / "workflow/placeholder_schema.yaml"
DEFAULT_FORBIDDEN_PATTERNS = REPO_ROOT / "workflow/forbidden_patterns.txt"
DEFAULT_ENV_PS1 = REPO_ROOT / ".env.ps1"
DEFAULT_TARGET_LOCALE = "ru-RU"
REGISTRY_GLOSSARY_ASSET = "glossary/compiled_naruto_ui_art_workbook_refresh.yaml"
KNOWN_SCOPES = {"project", "ip", "genre", "base"}

ENV_ASSIGN_RE = re.compile(r"^\$env:(?P<key>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<value>.+?)\s*$")
JOIN_PATH_RE = re.compile(r"^\(Join-Path \$PSScriptRoot ['\"](?P<name>[^'\"]+)['\"]\)$")


def configure_streams() -> None:
    if sys.platform != "win32" or os.getenv("PYTEST_CURRENT_TEST"):
        return
    import io

    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def dump_yaml(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(payload, fh, allow_unicode=True, sort_keys=False, default_flow_style=False)


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_csv_rows(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: Iterable[Dict[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def parse_ps1_value(raw_value: str, base_dir: Path) -> str:
    text = raw_value.strip()
    join_match = JOIN_PATH_RE.match(text)
    if join_match:
        return str((base_dir / join_match.group("name")).resolve())
    if (text.startswith("'") and text.endswith("'")) or (text.startswith('"') and text.endswith('"')):
        return text[1:-1]
    return text


def load_env_from_ps1(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not path.exists():
        return env
    base_dir = path.resolve().parent
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = ENV_ASSIGN_RE.match(line)
        if not match:
            continue
        env[match.group("key")] = parse_ps1_value(match.group("value"), base_dir)
    return env


def run_checked(command: Sequence[str], *, env: Dict[str, str], cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        list(command),
        cwd=str(cwd),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            f"cwd: {cwd}\n"
            f"cmd: {command}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    return proc


def run_captured(command: Sequence[str], *, env: Dict[str, str], cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=str(cwd),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    )


def extract_ru_target(entry: Dict[str, Any], target_locale: str = DEFAULT_TARGET_LOCALE) -> str:
    targets = entry.get("targets") or {}
    if isinstance(targets, dict):
        resolved = str(targets.get(target_locale) or "").strip()
        if resolved:
            return resolved
    return str(entry.get("term_ru") or "").strip()


def normalize_scope(value: Any, fallback: str) -> str:
    scope = str(value or "").strip().lower()
    if scope in KNOWN_SCOPES:
        return scope
    fallback_scope = str(fallback or "").strip().lower()
    return fallback_scope if fallback_scope in KNOWN_SCOPES else "base"


def add_scope(entries: Iterable[Dict[str, Any]], scope: str, source_tag: str) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for item in entries:
        term_zh = str(item.get("term_zh") or "").strip()
        term_ru = extract_ru_target(item)
        if not term_zh or not term_ru:
            continue
        note = str(item.get("note") or item.get("notes") or "").strip()
        normalized: Dict[str, Any] = {
            "term_zh": term_zh,
            "term_ru": term_ru,
            "status": str(item.get("status") or "approved").strip() or "approved",
            "scope": normalize_scope(item.get("scope"), scope),
            "note": note,
            "source_tag": source_tag,
        }
        if item.get("approved_at"):
            normalized["approved_at"] = item["approved_at"]
        output.append(normalized)
    return output


def add_compiled_compat(entries: Iterable[Dict[str, Any]], source_tag: str) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    for item in entries:
        term_zh = str(item.get("term_zh") or "").strip()
        term_ru = extract_ru_target(item)
        if not term_zh or not term_ru:
            continue
        note_parts = [str(item.get("note") or item.get("notes") or "").strip(), "compat_seed_from_old_compiled"]
        normalized: Dict[str, Any] = {
            "term_zh": term_zh,
            "term_ru": term_ru,
            "status": "approved",
            # Preserve residual-v2 runtime coverage as the refresh baseline.
            "scope": "ip",
            "note": "; ".join(part for part in note_parts if part),
            "source_tag": source_tag,
        }
        if item.get("approved_at"):
            normalized["approved_at"] = item["approved_at"]
        output.append(normalized)
    return output


def filter_missing_terms(
    entries: Iterable[Dict[str, Any]],
    existing_terms: Iterable[str],
) -> List[Dict[str, Any]]:
    seen_terms = {str(term or "").strip() for term in existing_terms if str(term or "").strip()}
    output: List[Dict[str, Any]] = []
    for entry in entries:
        term_zh = str(entry.get("term_zh") or "").strip()
        if not term_zh or term_zh in seen_terms:
            continue
        output.append(entry)
    return output


def dedupe_entries(entries: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for entry in entries:
        key = (
            str(entry.get("term_zh") or "").strip(),
            str(entry.get("term_ru") or "").strip(),
            str(entry.get("scope") or "").strip(),
            str(entry.get("status") or "").strip(),
        )
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def build_merged_approved(
    *,
    base_glossary: Path,
    patch_glossary: Path,
    compat_glossary: Optional[Path],
    runtime_glossary: Path,
    out_path: Path,
) -> Dict[str, Any]:
    base_entries = add_scope(load_yaml(base_glossary).get("entries", []), "base", repo_relative(base_glossary))
    patch_entries = add_scope(load_yaml(patch_glossary).get("entries", []), "ip", repo_relative(patch_glossary))
    compat_entries = []
    if compat_glossary:
        compat_entries = filter_missing_terms(
            add_compiled_compat(
                load_yaml(compat_glossary).get("entries", []),
                repo_relative(compat_glossary),
            ),
            [
                *(str(entry.get("term_zh") or "").strip() for entry in base_entries),
                *(str(entry.get("term_zh") or "").strip() for entry in patch_entries),
            ],
        )
    runtime_entries = add_scope(load_yaml(runtime_glossary).get("entries", []), "project", repo_relative(runtime_glossary))
    compat_entries = filter_missing_terms(
        compat_entries,
        [str(entry.get("term_zh") or "").strip() for entry in runtime_entries],
    )

    # Preserve only the old compiled coverage that is absent from the explicit
    # approved/patch/runtime layers, so patch/runtime keep ownership on ties.
    merged_entries = dedupe_entries([*base_entries, *patch_entries, *runtime_entries, *compat_entries])
    source_paths = [
        repo_relative(base_glossary),
        repo_relative(patch_glossary),
    ]
    if compat_glossary:
        source_paths.append(repo_relative(compat_glossary))
    source_paths.append(repo_relative(runtime_glossary))
    payload = {
        "meta": {
            "type": "approved",
            "language_pair": "zh-CN->ru-RU",
            "source": source_paths,
            "count": len(merged_entries),
            "compat_seed_entry_count": len(compat_entries),
        },
        "entries": merged_entries,
    }
    dump_yaml(out_path, payload)
    return payload


def load_glossary_map(path: Path) -> Dict[str, str]:
    data = load_yaml(path)
    mapping: Dict[str, str] = {}
    for item in data.get("entries", []):
        term_zh = str(item.get("term_zh") or "").strip()
        term_ru = extract_ru_target(item)
        if term_zh and term_ru:
            mapping[term_zh] = term_ru
    return mapping


def build_review_csv(full_csv: Path, out_csv: Path) -> None:
    rows = read_csv_rows(full_csv)
    review_rows = []
    for row in rows:
        target_ru = str(row.get("target_text") or row.get("target_ru") or row.get("target") or "").strip()
        review_rows.append(
            {
                "string_id": str(row.get("string_id") or "").strip(),
                "source_zh": str(row.get("source_zh") or "").strip(),
                "target_ru": target_ru,
            }
        )
    write_csv(out_csv, review_rows, ["string_id", "source_zh", "target_ru"])


def build_changed_rows(
    *,
    before_csv: Path,
    after_csv: Path,
    focus_glossary: Dict[str, str],
    out_changed_csv: Path,
    out_hit_csv: Path,
) -> Tuple[int, int]:
    before_rows = {str(row.get("string_id") or ""): row for row in read_csv_rows(before_csv)}
    after_rows = {str(row.get("string_id") or ""): row for row in read_csv_rows(after_csv)}
    changed_rows: List[Dict[str, Any]] = []
    hit_rows: List[Dict[str, Any]] = []
    for string_id, after in after_rows.items():
        before = before_rows.get(string_id, {})
        source_zh = str(after.get("source_zh") or "").strip()
        before_target = str(before.get("target_text") or before.get("target_ru") or before.get("target") or "").strip()
        after_target = str(after.get("target_text") or after.get("target_ru") or after.get("target") or "").strip()
        glossary_target = focus_glossary.get(source_zh, "")
        changed = before_target != after_target
        if changed:
            changed_rows.append(
                {
                    "string_id": string_id,
                    "source_zh": source_zh,
                    "before_target": before_target,
                    "after_target": after_target,
                    "glossary_target": glossary_target,
                    "glossary_hit": "yes" if glossary_target else "no",
                }
            )
        if glossary_target:
            hit_rows.append(
                {
                    "string_id": string_id,
                    "source_zh": source_zh,
                    "before_target": before_target,
                    "after_target": after_target,
                    "glossary_target": glossary_target,
                    "matches_glossary_target": "yes" if after_target == glossary_target else "no",
                    "changed": "yes" if changed else "no",
                }
            )

    write_csv(
        out_changed_csv,
        changed_rows,
        ["string_id", "source_zh", "before_target", "after_target", "glossary_target", "glossary_hit"],
    )
    write_csv(
        out_hit_csv,
        hit_rows,
        ["string_id", "source_zh", "before_target", "after_target", "glossary_target", "matches_glossary_target", "changed"],
    )
    return len(changed_rows), len(hit_rows)


def read_jsonl_rows(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def write_jsonl_rows(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def summarize_impacts(rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    by_locale: Dict[str, int] = {}
    by_content_class: Dict[str, int] = {}
    actions = set()
    for row in rows:
        locale = str(row.get("target_locale") or DEFAULT_TARGET_LOCALE).strip() or DEFAULT_TARGET_LOCALE
        content_class = str(row.get("content_class") or "general").strip() or "general"
        by_locale[locale] = by_locale.get(locale, 0) + 1
        by_content_class[content_class] = by_content_class.get(content_class, 0) + 1
        actions.add(str(row.get("recommended_action") or "").strip())
    if "manual_review" in actions:
        rerun_scope = "manual_review_required"
    elif "retranslate" in actions:
        rerun_scope = "retranslate_rows"
    elif "auto_refresh" in actions:
        rerun_scope = "auto_refresh_candidates"
    else:
        rerun_scope = "no_op"
    return {
        "impacted_rows_total": len(rows),
        "impacted_rows_by_locale": by_locale,
        "impacted_rows_by_content_class": by_content_class,
        "recommended_rerun_scope": rerun_scope,
        "impact_set": [str(row.get("string_id") or "").strip() for row in rows if str(row.get("string_id") or "").strip()],
    }


def normalize_focus_key(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def filter_runtime_safe_delta_rows(
    *,
    raw_report_path: Path,
    raw_rows_path: Path,
    focus_glossary_path: Path,
    filtered_report_path: Path,
    filtered_rows_path: Path,
) -> Dict[str, Any]:
    raw_report = load_json(raw_report_path)
    raw_rows = read_jsonl_rows(raw_rows_path)
    focus_map = load_glossary_map(focus_glossary_path)
    focus_terms = set(focus_map)
    filtered_rows = [
        row
        for row in raw_rows
        if str(row.get("source_zh") or "").strip() in focus_terms
    ]
    write_jsonl_rows(filtered_rows_path, filtered_rows)
    filtered_report = dict(raw_report)
    filtered_report.update(summarize_impacts(filtered_rows))
    filtered_report["row_impacts_path"] = str(filtered_rows_path)
    filtered_report["runtime_safe_exact_match_filter"] = {
        "enabled": True,
        "focus_term_count": len(focus_terms),
        "raw_impacted_rows_total": int(raw_report.get("impacted_rows_total") or 0),
        "filtered_impacted_rows_total": len(filtered_rows),
        "source_report_path": str(raw_report_path),
        "source_rows_path": str(raw_rows_path),
    }
    dump_json(filtered_report_path, filtered_report)
    return filtered_report


def filter_execute_tasks_by_focus_glossary(
    *,
    tasks_path: Path,
    focus_glossary_path: Path,
    out_path: Path,
) -> Dict[str, Any]:
    focus_keys = {normalize_focus_key(term) for term in load_glossary_map(focus_glossary_path).keys() if normalize_focus_key(term)}
    input_tasks = read_jsonl_rows(tasks_path)
    filtered_tasks = [
        task
        for task in input_tasks
        if normalize_focus_key(task.get("source_zh") or task.get("source_text") or "") in focus_keys
    ]
    write_jsonl_rows(out_path, filtered_tasks)
    return {
        "focus_term_count": len(focus_keys),
        "input_task_count": len(input_tasks),
        "filtered_task_count": len(filtered_tasks),
        "filtered_tasks_path": str(out_path),
    }


def staged_candidate_path(out_csv: Path) -> Path:
    if out_csv.suffix:
        return out_csv.with_name(f"{out_csv.stem}.candidate{out_csv.suffix}")
    return out_csv.with_name(f"{out_csv.name}.candidate")


def run_qa_hard_report(
    *,
    python_executable: str,
    translated_csv: Path,
    placeholder_map: Path,
    schema: Path,
    forbidden: Path,
    report_path: Path,
    env: Dict[str, str],
) -> subprocess.CompletedProcess[str]:
    return run_captured(
        [
            python_executable,
            str(REPO_ROOT / "scripts/qa_hard.py"),
            str(translated_csv),
            str(placeholder_map),
            str(schema),
            str(forbidden),
            str(report_path),
        ],
        env=env,
    )


def qa_error_keys(path: Path) -> set[Tuple[str, str, str]]:
    payload = load_json(path)
    keys: set[Tuple[str, str, str]] = set()
    for item in payload.get("errors", []):
        if not isinstance(item, dict):
            continue
        keys.add(
            (
                str(item.get("string_id") or ""),
                str(item.get("type") or ""),
                str(item.get("detail") or ""),
            )
        )
    return keys


def maybe_accept_baseline_qa(
    *,
    python_executable: str,
    base_full_csv: Path,
    refreshed_full_csv: Path,
    refreshed_manifest: Path,
    refreshed_qa_report: Path,
    placeholder_map: Path,
    placeholder_schema: Path,
    forbidden_patterns: Path,
    baseline_qa_report: Path,
    env: Dict[str, str],
) -> Dict[str, Any]:
    execute_manifest = load_json(refreshed_manifest)
    candidate_csv = staged_candidate_path(refreshed_full_csv)
    baseline_proc = run_qa_hard_report(
        python_executable=python_executable,
        translated_csv=base_full_csv,
        placeholder_map=placeholder_map,
        schema=placeholder_schema,
        forbidden=forbidden_patterns,
        report_path=baseline_qa_report,
        env=env,
    )
    if not candidate_csv.exists() or not refreshed_qa_report.exists():
        return {
            "accepted": False,
            "reason": "missing_candidate_or_qa_report",
            "baseline_qa_returncode": baseline_proc.returncode,
        }
    execution = execute_manifest.get("execution") or {}
    post_gates = execute_manifest.get("post_gates") or {}
    row_count_passed = bool(((post_gates.get("row_count_integrity") or {}).get("passed")))
    placeholder_passed = bool(((post_gates.get("placeholder_signature_integrity") or {}).get("passed")))
    execution_failed = int(execution.get("failed") or 0)
    candidate_errors = qa_error_keys(refreshed_qa_report)
    baseline_errors = qa_error_keys(baseline_qa_report)
    new_errors = candidate_errors - baseline_errors
    accepted = row_count_passed and placeholder_passed and execution_failed == 0 and not new_errors
    if accepted:
        candidate_csv.replace(refreshed_full_csv)
    return {
        "accepted": accepted,
        "reason": "no_new_qa_errors_vs_baseline" if accepted else "baseline_qa_regression_or_execution_failure",
        "baseline_qa_returncode": baseline_proc.returncode,
        "baseline_error_count": len(baseline_errors),
        "candidate_error_count": len(candidate_errors),
        "new_error_count": len(new_errors),
        "new_errors_sample": [list(item) for item in sorted(new_errors)[:20]],
    }


def load_proposals_count(path: Path) -> int:
    data = load_yaml(path)
    proposals = data.get("proposals") or data.get("entries") or []
    return len(proposals) if isinstance(proposals, list) else 0


def ensure_registry_entry(path: Path) -> None:
    registry = load_yaml(path)
    for entry in registry.get("entries", []):
        if str(entry.get("asset_path") or "").strip() == REGISTRY_GLOSSARY_ASSET:
            return
    raise RuntimeError(f"Lifecycle registry missing required glossary asset: {REGISTRY_GLOSSARY_ASSET}")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Naruto UI-art workbook glossary refresh workflow")
    parser.add_argument("--python", default=sys.executable, help="Python executable for subprocess steps")
    parser.add_argument("--env-ps1", default=str(DEFAULT_ENV_PS1), help="PowerShell env file with LLM_BASE_URL / key file")
    parser.add_argument("--workbook", default=str(DEFAULT_WORKBOOK), help="Reviewed workbook path")
    parser.add_argument("--base-slice-dir", default=str(DEFAULT_BASE_SLICE_DIR), help="Residual v2 base slice directory")
    parser.add_argument("--out-dir", default=str(DEFAULT_RUN_DIR), help="Derived run output directory")
    parser.add_argument("--merged-approved", default=str(DEFAULT_MERGED_APPROVED), help="Merged approved glossary output")
    parser.add_argument("--compiled-glossary", default=str(DEFAULT_COMPILED_GLOSSARY), help="Compiled glossary output")
    parser.add_argument("--style", default=str(DEFAULT_STYLE_GUIDE), help="Style guide markdown")
    parser.add_argument("--style-profile", default=str(DEFAULT_STYLE_PROFILE), help="Governed style profile")
    parser.add_argument("--placeholder-map", default="", help="Placeholder map for QA hard gate")
    parser.add_argument("--placeholder-schema", default=str(DEFAULT_PLACEHOLDER_SCHEMA), help="Placeholder schema path")
    parser.add_argument("--forbidden-patterns", default=str(DEFAULT_FORBIDDEN_PATTERNS), help="Forbidden patterns list")
    parser.add_argument("--lifecycle-registry", default=str(DEFAULT_LIFECYCLE_REGISTRY), help="Lifecycle registry path")
    parser.add_argument("--target-locale", default=DEFAULT_TARGET_LOCALE)
    parser.add_argument("--max-generate-review-handoff", type=int, default=0)
    parser.add_argument("--max-generate-blocked", type=int, default=0)
    parser.add_argument("--stop-after-generate-only", action="store_true")
    parser.add_argument("--model", default="", help="Optional translate_refresh model override")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    configure_streams()
    args = parse_args(argv)

    base_slice_dir = Path(args.base_slice_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    run_root_dir = base_slice_dir.parents[1] if len(base_slice_dir.parents) > 1 else base_slice_dir.parent

    base_full_csv = base_slice_dir / "ui_art_delivery_repaired_v2.csv"
    old_compiled_glossary = base_slice_dir / "glossary_ui_art_residual_v2_compiled.yaml"
    patch_glossary = base_slice_dir / "ui_art_residual_v2_patch_glossary.yaml"
    placeholder_map = Path(args.placeholder_map) if args.placeholder_map else run_root_dir / "placeholder_map.json"
    workbook_out_dir = out_dir / "workbook_glossary"
    workbook_full_resolved = workbook_out_dir / "full_resolved.yaml"
    workbook_focus_resolved = workbook_out_dir / "ui_art_focus_resolved.yaml"
    workbook_stats = workbook_out_dir / "stats.json"
    generate_tasks = out_dir / "translate_refresh_generate_tasks.jsonl"
    generate_review_queue = out_dir / "translate_refresh_generate_review_queue.csv"
    generate_review_tickets = out_dir / "translate_refresh_generate_review_tickets.jsonl"
    generate_review_tickets_csv = out_dir / "translate_refresh_generate_review_tickets.csv"
    feedback_log = out_dir / "translate_refresh_feedback_log.jsonl"
    generate_kpi_report = out_dir / "translate_refresh_generate_kpi.json"
    generate_manifest = out_dir / "translate_refresh_generate_manifest.json"
    delta_report_full = out_dir / "glossary_delta_report_full.json"
    delta_rows_full = out_dir / "glossary_delta_rows_full.jsonl"
    delta_report = out_dir / "glossary_delta_report.json"
    delta_rows = out_dir / "glossary_delta_rows.jsonl"
    refreshed_full_csv = out_dir / "ui_art_delivery_repaired_v2_glossary_refreshed.csv"
    refreshed_review_csv = out_dir / "ui_art_delivery_repaired_v2_review_glossary_refreshed.csv"
    execute_tasks_in = out_dir / "translate_refresh_execute_tasks_input.filtered.jsonl"
    refreshed_manifest = out_dir / "translate_refresh_execute_manifest.json"
    refreshed_tasks = out_dir / "translate_refresh_execute_tasks.jsonl"
    refreshed_review_queue = out_dir / "translate_refresh_execute_review_queue.csv"
    refreshed_review_tickets = out_dir / "translate_refresh_execute_review_tickets.jsonl"
    refreshed_review_tickets_csv = out_dir / "translate_refresh_execute_review_tickets.csv"
    refreshed_kpi_report = out_dir / "translate_refresh_execute_kpi.json"
    refreshed_failure_breakdown = out_dir / "translate_refresh_execute_failure_breakdown.json"
    refreshed_qa_report = out_dir / "translate_refresh_execute_qa_report.json"
    baseline_qa_report = out_dir / "ui_art_delivery_repaired_v2_baseline_qa_report.json"
    changed_rows_csv = out_dir / "ui_art_glossary_refresh_changed_rows.csv"
    glossary_hit_rows_csv = out_dir / "ui_art_glossary_refresh_glossary_hit_rows.csv"
    autopromote_proposals = out_dir / "glossary_autopromote_proposals.yaml"
    autopromote_patch = out_dir / "glossary_autopromote_patch.yaml"
    run_manifest = out_dir / "run_manifest.json"

    env = os.environ.copy()
    env.update(load_env_from_ps1(Path(args.env_ps1)))
    env.setdefault("PYTHONIOENCODING", "utf-8")

    ensure_registry_entry(Path(args.lifecycle_registry))

    run_checked([args.python, str(REPO_ROOT / "scripts/llm_ping.py")], env=env)

    run_checked(
        [
            args.python,
            str(REPO_ROOT / "scripts/build_reviewed_workbook_glossary.py"),
            "--workbook",
            str(Path(args.workbook)),
            "--target-csv",
            str(base_full_csv),
            "--out-dir",
            str(workbook_out_dir),
        ],
        env=env,
    )

    merged_payload = build_merged_approved(
        base_glossary=REPO_ROOT / "glossary/approved.yaml",
        patch_glossary=patch_glossary,
        compat_glossary=old_compiled_glossary,
        runtime_glossary=workbook_focus_resolved,
        out_path=Path(args.merged_approved),
    )

    run_checked(
        [
            args.python,
            str(REPO_ROOT / "scripts/glossary_compile.py"),
            "--approved",
            str(Path(args.merged_approved)),
            "--out_compiled",
            str(Path(args.compiled_glossary)),
            "--language_pair",
            "zh-CN->ru-RU",
            "--franchise",
            "naruto",
            "--resolve_by_scope",
        ],
        env=env,
    )

    run_checked(
        [
            args.python,
            str(REPO_ROOT / "scripts/glossary_delta.py"),
            "--old",
            str(old_compiled_glossary),
            "--new",
            str(Path(args.compiled_glossary)),
            "--source_csv",
            str(base_full_csv),
            "--out_impact",
            str(delta_report_full),
            "--out_rows",
            str(delta_rows_full),
            "--target-locale",
            args.target_locale,
        ],
        env=env,
    )
    delta_payload = filter_runtime_safe_delta_rows(
        raw_report_path=delta_report_full,
        raw_rows_path=delta_rows_full,
        focus_glossary_path=workbook_focus_resolved,
        filtered_report_path=delta_report,
        filtered_rows_path=delta_rows,
    )

    generate_cmd = [
        args.python,
        str(REPO_ROOT / "scripts/translate_refresh.py"),
        "--delta-rows",
        str(delta_rows),
        "--translated",
        str(base_full_csv),
        "--glossary",
        str(Path(args.compiled_glossary)),
        "--style",
        str(Path(args.style)),
        "--style-profile",
        str(Path(args.style_profile)),
        "--lifecycle-registry",
        str(Path(args.lifecycle_registry)),
        "--tasks-out",
        str(generate_tasks),
        "--review-queue",
        str(generate_review_queue),
        "--review-tickets",
        str(generate_review_tickets),
        "--review-tickets-csv",
        str(generate_review_tickets_csv),
        "--feedback-log",
        str(feedback_log),
        "--kpi-report",
        str(generate_kpi_report),
        "--manifest",
        str(generate_manifest),
        "--generate-only",
    ]
    if args.model:
        generate_cmd.extend(["--model", args.model])
    run_checked(generate_cmd, env=env)

    generate_payload = load_json(generate_manifest)
    review_handoff_count = int((generate_payload.get("review_handoff") or {}).get("pending_count") or 0)
    blocked_count = int((generate_payload.get("execution") or {}).get("blocked") or 0)
    if review_handoff_count > args.max_generate_review_handoff or blocked_count > args.max_generate_blocked:
        raise RuntimeError(
            "Generate-only safety stop triggered: "
            f"review_handoff={review_handoff_count}, blocked={blocked_count}"
        )

    if args.stop_after_generate_only:
        dump_json(
            run_manifest,
            {
                "mode": "generate_only_stop",
                "out_dir": str(out_dir),
                "workbook_stats": load_json(workbook_stats),
                "merged_approved_entry_count": len(merged_payload.get("entries", [])),
                "delta_report": delta_payload,
                "generate_manifest": generate_payload,
            },
        )
        return 0

    execute_task_filter = filter_execute_tasks_by_focus_glossary(
        tasks_path=generate_tasks,
        focus_glossary_path=workbook_focus_resolved,
        out_path=execute_tasks_in,
    )
    if int(execute_task_filter.get("filtered_task_count") or 0) <= 0:
        raise RuntimeError(f"No runtime-safe execute tasks after focus filter: {execute_task_filter}")

    execute_cmd = [
        args.python,
        str(REPO_ROOT / "scripts/translate_refresh.py"),
        "--tasks-in",
        str(execute_tasks_in),
        "--translated",
        str(base_full_csv),
        "--glossary",
        str(Path(args.compiled_glossary)),
        "--style",
        str(Path(args.style)),
        "--style-profile",
        str(Path(args.style_profile)),
        "--lifecycle-registry",
        str(Path(args.lifecycle_registry)),
        "--tasks-out",
        str(refreshed_tasks),
        "--review-queue",
        str(refreshed_review_queue),
        "--review-tickets",
        str(refreshed_review_tickets),
        "--review-tickets-csv",
        str(refreshed_review_tickets_csv),
        "--feedback-log",
        str(feedback_log),
        "--kpi-report",
        str(refreshed_kpi_report),
        "--manifest",
        str(refreshed_manifest),
        "--failure-breakdown",
        str(refreshed_failure_breakdown),
        "--qa-report",
        str(refreshed_qa_report),
        "--out-csv",
        str(refreshed_full_csv),
        "--placeholder-map",
        str(placeholder_map),
        "--schema",
        str(Path(args.placeholder_schema)),
        "--forbidden",
        str(Path(args.forbidden_patterns)),
    ]
    if args.model:
        execute_cmd.extend(["--model", args.model])
    qa_acceptance: Dict[str, Any] = {"accepted": True, "reason": "translate_refresh_execute_passed"}
    try:
        run_checked(execute_cmd, env=env)
    except RuntimeError as exc:
        qa_acceptance = maybe_accept_baseline_qa(
            python_executable=args.python,
            base_full_csv=base_full_csv,
            refreshed_full_csv=refreshed_full_csv,
            refreshed_manifest=refreshed_manifest,
            refreshed_qa_report=refreshed_qa_report,
            placeholder_map=placeholder_map,
            placeholder_schema=Path(args.placeholder_schema),
            forbidden_patterns=Path(args.forbidden_patterns),
            baseline_qa_report=baseline_qa_report,
            env=env,
        )
        if not qa_acceptance.get("accepted"):
            raise RuntimeError(f"{exc}\nBaseline QA acceptance failed: {json.dumps(qa_acceptance, ensure_ascii=False, indent=2)}") from exc

    build_review_csv(refreshed_full_csv, refreshed_review_csv)
    focus_map = load_glossary_map(workbook_focus_resolved)
    changed_count, hit_count = build_changed_rows(
        before_csv=base_full_csv,
        after_csv=refreshed_full_csv,
        focus_glossary=focus_map,
        out_changed_csv=changed_rows_csv,
        out_hit_csv=glossary_hit_rows_csv,
    )

    run_checked(
        [
            args.python,
            str(REPO_ROOT / "scripts/glossary_autopromote.py"),
            "--before",
            str(base_full_csv),
            "--after",
            str(refreshed_full_csv),
            "--style",
            str(Path(args.style)),
            "--style-profile",
            str(Path(args.style_profile)),
            "--glossary",
            str(Path(args.compiled_glossary)),
            "--scope",
            "project_naruto_ui_art_workbook_refresh",
            "--out_proposals",
            str(autopromote_proposals),
            "--out_patch",
            str(autopromote_patch),
        ],
        env=env,
    )

    execution_payload = load_json(refreshed_manifest)
    workbook_stats_payload = load_json(workbook_stats)
    autopromote_count = load_proposals_count(autopromote_proposals)
    run_summary = {
        "mode": "completed",
        "out_dir": str(out_dir),
        "inputs": {
            "workbook": str(Path(args.workbook)),
            "base_full_csv": str(base_full_csv),
            "old_compiled_glossary": str(old_compiled_glossary),
            "patch_glossary": str(patch_glossary),
            "style": str(Path(args.style)),
            "style_profile": str(Path(args.style_profile)),
            "placeholder_map": str(placeholder_map),
            "placeholder_schema": str(Path(args.placeholder_schema)),
            "forbidden_patterns": str(Path(args.forbidden_patterns)),
            "lifecycle_registry": str(Path(args.lifecycle_registry)),
        },
        "artifacts": {
            "workbook_full_resolved": str(workbook_full_resolved),
            "workbook_focus_resolved": str(workbook_focus_resolved),
            "merged_approved": str(Path(args.merged_approved)),
            "compiled_glossary": str(Path(args.compiled_glossary)),
            "delta_report_full": str(delta_report_full),
            "delta_rows_full": str(delta_rows_full),
            "delta_report": str(delta_report),
            "delta_rows": str(delta_rows),
            "generate_manifest": str(generate_manifest),
            "execute_tasks_input_filtered": str(execute_tasks_in),
            "refreshed_full_csv": str(refreshed_full_csv),
            "refreshed_review_csv": str(refreshed_review_csv),
            "changed_rows_csv": str(changed_rows_csv),
            "glossary_hit_rows_csv": str(glossary_hit_rows_csv),
            "autopromote_proposals": str(autopromote_proposals),
            "autopromote_patch": str(autopromote_patch),
        },
        "summary": {
            "workbook_stats": workbook_stats_payload,
            "merged_approved_entry_count": len(merged_payload.get("entries", [])),
            "delta_impacted_rows_total": int(delta_payload.get("impacted_rows_total") or 0),
            "generate_review_handoff_count": review_handoff_count,
            "execute_task_filter": execute_task_filter,
            "execute_updated_count": int((execution_payload.get("execution") or {}).get("updated") or 0),
            "execute_review_handoff_count": int((execution_payload.get("execution") or {}).get("review_handoff") or 0),
            "qa_hard_passed": bool((((execution_payload.get("post_gates") or {}).get("qa_hard") or {}).get("passed"))),
            "baseline_qa_acceptance": qa_acceptance,
            "changed_rows_count": changed_count,
            "glossary_hit_rows_count": hit_count,
            "autopromote_proposals_count": autopromote_count,
        },
        "generate_manifest": generate_payload,
        "execute_manifest": execution_payload,
        "delta_report": delta_payload,
    }
    dump_json(run_manifest, run_summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
