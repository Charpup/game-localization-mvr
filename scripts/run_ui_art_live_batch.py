#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run a serial UI-art zh-CN -> ru-RU live batch inside a dedicated run dir.

This wrapper keeps the retained localization chain intact while adding:
- source encoding normalization at prep time
- unique working string_id generation for duplicate-heavy batches
- process preflight and resumable run-dir management
- final original-id restoration for delivery
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from scripts.prepare_ui_art_batch import fingerprint_file
except ImportError:  # pragma: no cover
    from prepare_ui_art_batch import fingerprint_file


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BATCH_ROOT = REPO_ROOT / "data" / "incoming" / "ui_art_batch"
SCRIPT_PATH = Path(__file__).resolve()
PYTHON_EXE = REPO_ROOT / ".venv" / "Scripts" / "python.exe"
RELEVANT_SCRIPTS = (
    "translate_llm.py",
    "soft_qa_llm.py",
    "repair_loop.py",
    "llm_ping.py",
)
DEFERRED_UI_ART_REVIEW_ERROR_TYPES = {
    "length_overflow",
    "compact_mapping_missing",
    "compact_term_miss",
    "line_budget_overflow",
    "headline_budget_overflow",
    "promo_expansion_forbidden",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def make_run_id(prefix: str = "ui_art_live") -> str:
    return f"{prefix}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_csv(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


PREPARED_INPUT_REQUIRED_FIELDS = {
    "string_id",
    "working_string_id",
    "source_string_id",
    "ui_art_category",
    "max_len_target",
    "max_len_review_limit",
    "status",
}


def ensure_python() -> Path:
    if PYTHON_EXE.exists():
        return PYTHON_EXE
    return Path(sys.executable)


def build_paths(batch_root: Path, run_dir: Path) -> Dict[str, Path]:
    return {
        "input": batch_root / "source_ui_art.csv",
        "run_dir": run_dir,
        "logs_dir": run_dir / "logs",
        "manifest": run_dir / "run_manifest.json",
        "prepare_csv": run_dir / "source_ui_art_prepared.csv",
        "prepare_report": run_dir / "source_ui_art_prepare_report.json",
        "live_ready_csv": run_dir / "source_ui_art_live_ready.csv",
        "glossary": run_dir / "glossary_ui_art_compiled.yaml",
        "glossary_lock": run_dir / "glossary_ui_art_compiled.lock.json",
        "probe_input": run_dir / "probe_input.csv",
        "probe_output": run_dir / "probe_output.csv",
        "probe_checkpoint": run_dir / "probe_translate_checkpoint.json",
        "model_selection": run_dir / "model_selection.json",
        "draft_csv": run_dir / "ui_art_draft.csv",
        "placeholder_map": run_dir / "placeholder_map.json",
        "translated_csv": run_dir / "ui_art_translated.csv",
        "translate_checkpoint": run_dir / "translate_checkpoint.json",
        "qa_report": run_dir / "ui_art_qa_hard_report.json",
        "qa_actionable_tasks": run_dir / "ui_art_qa_hard_actionable.json",
        "repair_output": run_dir / "ui_art_repaired_hard.csv",
        "repair_dir": run_dir / "repair_reports" / "hard",
        "qa_recheck_report": run_dir / "ui_art_qa_hard_report_recheck.json",
        "soft_report": run_dir / "ui_art_soft_qa_report.json",
        "soft_tasks": run_dir / "ui_art_soft_tasks.jsonl",
        "soft_checkpoint": run_dir / "soft_qa_checkpoint.json",
        "review_queue": run_dir / "ui_art_review_queue.csv",
        "review_report": run_dir / "ui_art_review_queue.json",
        "final_export": run_dir / "ui_art_final_export.csv",
        "delivery_csv": run_dir / "ui_art_delivery.csv",
        "delivery_report": run_dir / "ui_art_delivery_report.json",
        "repair_config": run_dir / "repair_config_live.yaml",
    }


def manifest_for(
    run_id: str,
    batch_root: Path,
    run_dir: Path,
    source_fingerprint: Dict[str, Any],
    batch_type: str = "ui_art_live",
) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "route": "plc + triadev",
        "batch_type": batch_type,
        "batch_root": str(batch_root),
        "run_dir": str(run_dir),
        "source_fingerprint": source_fingerprint,
        "status": "initialized",
        "started_at": utc_now(),
        "updated_at": utc_now(),
        "chosen_model": "",
        "stages": [],
    }


def upsert_stage(manifest: Dict[str, Any], stage_name: str, status: str, **details: Any) -> None:
    stages = manifest.setdefault("stages", [])
    payload = {"name": stage_name, "status": status, "updated_at": utc_now()}
    payload.update(details)
    for idx, existing in enumerate(stages):
        if existing.get("name") == stage_name:
            stages[idx] = payload
            break
    else:
        stages.append(payload)
    manifest["updated_at"] = utc_now()
    manifest["status"] = status if stage_name == "overall" else manifest.get("status", status)


def list_python_processes() -> List[Dict[str, Any]]:
    if os.name != "nt":
        return []

    command = (
        "Get-CimInstance Win32_Process "
        "| Where-Object { $_.Name -like 'python*' } "
        "| Select-Object ProcessId, Name, CommandLine "
        "| ConvertTo-Json -Compress"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(REPO_ROOT),
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []


def find_active_batch_processes(batch_root: Path, run_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    batch_marker = str(batch_root).lower()
    run_marker = str(run_dir).lower() if run_dir else ""
    active: List[Dict[str, Any]] = []
    for proc in list_python_processes():
        pid = int(proc.get("ProcessId") or 0)
        if pid == os.getpid():
            continue
        command_line = str(proc.get("CommandLine") or "")
        lower = command_line.lower()
        if batch_marker not in lower and (not run_marker or run_marker not in lower):
            continue
        if not any(marker.lower() in lower for marker in RELEVANT_SCRIPTS):
            continue
        active.append({"pid": pid, "command_line": command_line})
    return active


def choose_run_dir(run_root: Path, source_fingerprint: Dict[str, Any], requested_run_id: str = "") -> Tuple[Path, str]:
    run_root.mkdir(parents=True, exist_ok=True)
    if requested_run_id:
        run_dir = run_root / requested_run_id
        return run_dir, "resume" if run_dir.exists() else "new"

    candidates = sorted((path for path in run_root.iterdir() if path.is_dir()), key=lambda item: item.name, reverse=True)
    source_sha = str(source_fingerprint.get("sha256") or "")
    for candidate in candidates:
        report = read_json(candidate / "source_ui_art_prepare_report.json")
        report_sha = str(((report.get("source_fingerprint") or {}).get("sha256")) or "")
        if report_sha and report_sha == source_sha:
            return candidate, "resume"
    return run_root / make_run_id(), "new"


def run_step(cmd: List[str], log_path: Path, env: Optional[Dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as fh:
        fh.write(f"command: {cmd}\n")
        fh.write(f"started_at: {utc_now()}\n\n")

    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)

    result = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=merged_env,
    )

    with log_path.open("a", encoding="utf-8") as fh:
        fh.write(f"returncode: {result.returncode}\n\n")
        fh.write("---- STDOUT ----\n")
        fh.write(result.stdout or "")
        fh.write("\n---- STDERR ----\n")
        fh.write(result.stderr or "")
    return result


def require_success(result: subprocess.CompletedProcess[str], stage_name: str) -> None:
    if result.returncode != 0:
        raise RuntimeError(f"{stage_name} failed with exit code {result.returncode}")


def require_report(result: subprocess.CompletedProcess[str], stage_name: str, report_path: Path) -> None:
    if report_path.exists():
        return
    if result.returncode != 0:
        raise RuntimeError(f"{stage_name} failed with exit code {result.returncode} and no report was written")
    raise RuntimeError(f"{stage_name} completed without writing report: {report_path}")


def require_soft_qa_result(result: subprocess.CompletedProcess[str], report_path: Path) -> Dict[str, Any]:
    require_report(result, "soft_qa", report_path)
    if result.returncode not in (0, 2):
        raise RuntimeError(f"soft_qa failed with unexpected exit code {result.returncode}")
    return read_json(report_path)


def is_prepared_ui_art_input(input_path: Path) -> bool:
    try:
        _, fieldnames = read_csv(input_path)
    except Exception:
        return False
    return PREPARED_INPUT_REQUIRED_FIELDS.issubset(set(fieldnames))


def summarize_prepared_rows(
    prepared_csv: Path,
    module_tag: str = "ui_art_label",
    batch_type: str = "ui_art",
) -> Dict[str, Any]:
    rows, _ = read_csv(prepared_csv)
    ready_rows = [row for row in rows if str(row.get("status") or "") == "ready"]
    return {
        "batch_type": batch_type,
        "row_count": len(rows),
        "ready_rows": len(ready_rows),
        "empty_rows": len(rows) - len(ready_rows),
        "module_tag": module_tag,
        "source_fingerprint": fingerprint_file(prepared_csv),
        "ui_art_category_counts": {
            category: sum(1 for row in ready_rows if str(row.get("ui_art_category") or "") == category)
            for category in sorted({str(row.get("ui_art_category") or "") for row in ready_rows})
        },
    }


def write_live_ready_csv(prepared_csv: Path, live_ready_csv: Path) -> Dict[str, int]:
    rows, fieldnames = read_csv(prepared_csv)
    live_rows = [row for row in rows if str(row.get("status") or "") == "ready"]
    write_csv(live_ready_csv, live_rows, fieldnames)
    return {"prepared_rows": len(rows), "live_ready_rows": len(live_rows), "skipped_rows": len(rows) - len(live_rows)}


def reconcile_translate_resume(output_csv: Path, checkpoint_path: Path) -> Dict[str, int]:
    if not output_csv.exists():
        return {"rows": 0, "deduped_rows": 0, "checkpoint_ids": 0}

    rows, fieldnames = read_csv(output_csv)
    seen: set[str] = set()
    unique_rows: List[Dict[str, str]] = []
    for row in rows:
        string_id = str(row.get("string_id") or "")
        if not string_id or string_id in seen:
            continue
        seen.add(string_id)
        unique_rows.append(row)

    if len(unique_rows) != len(rows):
        write_csv(output_csv, unique_rows, fieldnames)

    write_json(checkpoint_path, {"done_ids": list(seen)})
    return {"rows": len(rows), "deduped_rows": len(unique_rows), "checkpoint_ids": len(seen)}


def qa_report_has_errors(report_path: Path) -> bool:
    report = read_json(report_path)
    if not report:
        return False
    if report.get("has_errors") is True:
        return True
    return bool(report.get("errors"))


def qa_report_errors(report_path: Path) -> List[Dict[str, Any]]:
    report = read_json(report_path)
    errors = report.get("errors") or []
    if isinstance(errors, list):
        return errors
    return []


def build_actionable_hard_tasks(report_path: Path, output_path: Path) -> Dict[str, int]:
    report = read_json(report_path)
    errors = qa_report_errors(report_path)
    actionable = [
        error for error in errors if str(error.get("type") or "") not in DEFERRED_UI_ART_REVIEW_ERROR_TYPES
    ]
    payload = dict(report)
    payload["errors"] = actionable
    payload["has_errors"] = bool(actionable)
    counts: Dict[str, int] = {}
    for error in actionable:
        error_type = str(error.get("type") or "unknown")
        counts[error_type] = counts.get(error_type, 0) + 1
    payload["error_counts"] = counts
    write_json(output_path, payload)
    return {"actionable_errors": len(actionable), "deferred_review_errors": len(errors) - len(actionable)}


def blocking_errors_remain(report_path: Path) -> bool:
    return any(
        str(error.get("type") or "") not in DEFERRED_UI_ART_REVIEW_ERROR_TYPES
        for error in qa_report_errors(report_path)
    )


def current_translation_path(paths: Dict[str, Path]) -> Path:
    if (
        paths["qa_recheck_report"].exists()
        and not blocking_errors_remain(paths["qa_recheck_report"])
        and paths["repair_output"].exists()
    ):
        return paths["repair_output"]
    return paths["translated_csv"]


def choose_model_from_probe(
    python_exe: Path,
    paths: Dict[str, Path],
    style_path: Path,
    glossary_path: Path,
    style_profile_path: Path,
    probe_size: int,
) -> str:
    if paths["model_selection"].exists():
        cached = read_json(paths["model_selection"])
        chosen = str(cached.get("chosen_model") or "")
        if chosen:
            return chosen

    rows, fieldnames = read_csv(paths["live_ready_csv"])
    sample_rows = rows[:probe_size]
    if not sample_rows:
        raise RuntimeError("No live-ready rows available for model probe.")
    write_csv(paths["probe_input"], sample_rows, fieldnames)

    candidates = ["claude-haiku-4-5-20251001", "gpt-4.1-mini"]
    probe_results: List[Dict[str, Any]] = []
    for model in candidates:
        for path in (paths["probe_output"], paths["probe_checkpoint"]):
            if path.exists():
                path.unlink()
        result = run_step(
            [
                str(python_exe),
                "scripts/translate_llm.py",
                "--input",
                str(paths["probe_input"]),
                "--output",
                str(paths["probe_output"]),
                "--checkpoint",
                str(paths["probe_checkpoint"]),
                "--model",
                model,
                "--style",
                str(style_path),
                "--glossary",
                str(glossary_path),
                "--style-profile",
                str(style_profile_path),
                "--target-lang",
                "ru-RU",
            ],
            paths["logs_dir"] / f"probe_{model.replace('.', '_')}.log",
        )
        output_rows = read_csv(paths["probe_output"])[0] if paths["probe_output"].exists() else []
        success = result.returncode == 0 and len(output_rows) == len(sample_rows)
        probe_results.append({"model": model, "returncode": result.returncode, "output_rows": len(output_rows), "success": success})
        if success:
            write_json(paths["model_selection"], {"chosen_model": model, "probes": probe_results})
            return model

    write_json(paths["model_selection"], {"chosen_model": "", "probes": probe_results})
    raise RuntimeError("No probe model succeeded for this provider.")


def maybe_write_repair_config(paths: Dict[str, Path], chosen_model: str) -> Optional[Path]:
    if chosen_model.startswith("claude-"):
        return None
    payload = (
        "repair_loop:\n"
        "  max_rounds: 1\n"
        "  rounds:\n"
        "    1:\n"
        f"      model: {chosen_model}\n"
        "      prompt_variant: standard\n"
    )
    paths["repair_config"].write_text(payload, encoding="utf-8")
    return paths["repair_config"]


def ensure_required_env() -> None:
    missing = [name for name in ("LLM_BASE_URL", "LLM_API_KEY") if not os.environ.get(name)]
    if missing:
        raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")


def resolve_approved_glossaries(extra_glossaries: Iterable[str]) -> List[str]:
    approved = ["glossary/approved.yaml"]
    for candidate in extra_glossaries:
        text = str(candidate or "").strip()
        if text and text not in approved:
            approved.append(text)
    return approved


def run_pipeline(args: argparse.Namespace) -> int:
    python_exe = ensure_python()
    batch_root = Path(args.batch_root).resolve()
    input_path = Path(args.input).resolve() if args.input else (batch_root / "source_ui_art.csv")
    source_fingerprint = fingerprint_file(input_path)
    run_root = batch_root / "runs"
    run_dir, mode = choose_run_dir(run_root, source_fingerprint, requested_run_id=args.run_id)
    paths = build_paths(batch_root, run_dir)

    active = find_active_batch_processes(batch_root, run_dir=run_dir)
    if active:
        print("WARN: Active batch-related Python process detected. Refusing to start a second run.")
        print(json.dumps(active, ensure_ascii=False, indent=2))
        return 2

    run_dir.mkdir(parents=True, exist_ok=True)
    paths["logs_dir"].mkdir(parents=True, exist_ok=True)

    manifest = read_json(paths["manifest"]) or manifest_for(
        run_dir.name,
        batch_root,
        run_dir,
        source_fingerprint,
        batch_type=args.batch_type,
    )
    manifest["source_fingerprint"] = source_fingerprint
    manifest["resume_mode"] = mode
    manifest["batch_type"] = args.batch_type
    write_json(paths["manifest"], manifest)

    style_path = Path(args.style).resolve()
    style_profile_path = Path(args.style_profile).resolve()
    schema_path = Path(args.schema).resolve()
    forbidden_path = Path(args.forbidden_patterns).resolve()

    if not paths["prepare_csv"].exists() or read_json(paths["prepare_report"]).get("source_fingerprint", {}).get("sha256") != source_fingerprint.get("sha256"):
        upsert_stage(manifest, "prepare", "running", output=str(paths["prepare_csv"]))
        write_json(paths["manifest"], manifest)
        if is_prepared_ui_art_input(input_path):
            if input_path.resolve() != paths["prepare_csv"].resolve():
                shutil.copy2(input_path, paths["prepare_csv"])
            prepare_summary = summarize_prepared_rows(paths["prepare_csv"], batch_type=args.prepared_batch_type)
            prepare_summary["input_mode"] = "prepared_input"
            prepare_summary["source_fingerprint"] = source_fingerprint
            write_json(paths["prepare_report"], prepare_summary)
            with (paths["logs_dir"] / "01_prepare.log").open("w", encoding="utf-8") as fh:
                fh.write("mode: prepared_input\n")
                fh.write(f"source: {input_path}\n")
                fh.write(f"copied_to: {paths['prepare_csv']}\n")
            upsert_stage(manifest, "prepare", "completed", report=str(paths["prepare_report"]), input_mode="prepared_input")
        else:
            result = run_step(
                [
                    str(python_exe),
                    "scripts/prepare_ui_art_batch.py",
                    "--input",
                    str(input_path),
                    "--output",
                    str(paths["prepare_csv"]),
                    "--report",
                    str(paths["prepare_report"]),
                ],
                paths["logs_dir"] / "01_prepare.log",
            )
            require_success(result, "prepare")
            upsert_stage(manifest, "prepare", "completed", report=str(paths["prepare_report"]), input_mode="raw_input")
        write_json(paths["manifest"], manifest)

    ready_stats = write_live_ready_csv(paths["prepare_csv"], paths["live_ready_csv"])
    upsert_stage(manifest, "live_ready", "completed", **ready_stats)
    write_json(paths["manifest"], manifest)

    approved_glossaries = resolve_approved_glossaries(args.approved_glossary or [])
    if not paths["glossary"].exists():
        upsert_stage(manifest, "glossary_compile", "running", output=str(paths["glossary"]))
        write_json(paths["manifest"], manifest)
        glossary_cmd = [str(python_exe), "scripts/glossary_compile.py"]
        for approved in approved_glossaries:
            glossary_cmd.extend(["--approved", approved])
        glossary_cmd.extend(
            [
                "--out_compiled",
                str(paths["glossary"]),
                "--language_pair",
                "zh-CN->ru-RU",
                "--franchise",
                args.franchise,
                "--resolve_by_scope",
            ]
        )
        result = run_step(
            glossary_cmd,
            paths["logs_dir"] / "02_glossary_compile.log",
        )
        require_success(result, "glossary_compile")
        upsert_stage(manifest, "glossary_compile", "completed", output=str(paths["glossary"]))
        write_json(paths["manifest"], manifest)

    ensure_required_env()
    if not any(stage.get("name") == "llm_ping" and stage.get("status") == "completed" for stage in manifest.get("stages", [])):
        upsert_stage(manifest, "llm_ping", "running")
        write_json(paths["manifest"], manifest)
        result = run_step([str(python_exe), "scripts/llm_ping.py"], paths["logs_dir"] / "03_llm_ping.log")
        require_success(result, "llm_ping")
        upsert_stage(manifest, "llm_ping", "completed")
        write_json(paths["manifest"], manifest)

    chosen_model = args.model or choose_model_from_probe(
        python_exe=python_exe,
        paths=paths,
        style_path=style_path,
        glossary_path=paths["glossary"],
        style_profile_path=style_profile_path,
        probe_size=args.probe_size,
    )
    manifest["chosen_model"] = chosen_model
    write_json(paths["manifest"], manifest)

    if not paths["draft_csv"].exists() or not paths["placeholder_map"].exists():
        upsert_stage(manifest, "normalize_guard", "running")
        write_json(paths["manifest"], manifest)
        result = run_step(
            [
                str(python_exe),
                "scripts/normalize_guard.py",
                str(paths["live_ready_csv"]),
                str(paths["draft_csv"]),
                str(paths["placeholder_map"]),
                str(schema_path),
                "--source-lang",
                "zh-CN",
            ],
            paths["logs_dir"] / "04_normalize_guard.log",
        )
        require_success(result, "normalize_guard")
        upsert_stage(manifest, "normalize_guard", "completed")
        write_json(paths["manifest"], manifest)

    if not paths["qa_report"].exists():
        if paths["translated_csv"].exists() or paths["translate_checkpoint"].exists():
            reconcile = reconcile_translate_resume(paths["translated_csv"], paths["translate_checkpoint"])
            upsert_stage(manifest, "translate_reconcile", "completed", **reconcile)
            write_json(paths["manifest"], manifest)

        upsert_stage(manifest, "translate_llm", "running", model=chosen_model)
        write_json(paths["manifest"], manifest)
        result = run_step(
            [
                str(python_exe),
                "scripts/translate_llm.py",
                "--input",
                str(paths["draft_csv"]),
                "--output",
                str(paths["translated_csv"]),
                "--checkpoint",
                str(paths["translate_checkpoint"]),
                "--model",
                chosen_model,
                "--style",
                str(style_path),
                "--glossary",
                str(paths["glossary"]),
                "--style-profile",
                str(style_profile_path),
                "--target-lang",
                "ru-RU",
            ],
            paths["logs_dir"] / "05_translate.log",
        )
        require_success(result, "translate_llm")
        upsert_stage(manifest, "translate_llm", "completed", output=str(paths["translated_csv"]), checkpoint=str(paths["translate_checkpoint"]))
        write_json(paths["manifest"], manifest)

        upsert_stage(manifest, "qa_hard", "running")
        write_json(paths["manifest"], manifest)
        result = run_step(
            [
                str(python_exe),
                "scripts/qa_hard.py",
                str(paths["translated_csv"]),
                str(paths["placeholder_map"]),
                str(schema_path),
                str(forbidden_path),
                str(paths["qa_report"]),
            ],
            paths["logs_dir"] / "06_qa_hard.log",
        )
        require_report(result, "qa_hard", paths["qa_report"])
        upsert_stage(manifest, "qa_hard", "completed", report=str(paths["qa_report"]), returncode=result.returncode)
        write_json(paths["manifest"], manifest)

    if qa_report_has_errors(paths["qa_report"]):
        actionable_stats = build_actionable_hard_tasks(paths["qa_report"], paths["qa_actionable_tasks"])
        if actionable_stats["actionable_errors"] > 0:
            repair_config = maybe_write_repair_config(paths, chosen_model)
            upsert_stage(
                manifest,
                "repair_hard",
                "running",
                config=str(repair_config or "config/repair_config.yaml"),
                actionable_errors=actionable_stats["actionable_errors"],
                deferred_review_errors=actionable_stats["deferred_review_errors"],
            )
            write_json(paths["manifest"], manifest)
            if paths["repair_dir"].exists() and not (paths["repair_dir"] / "repair_DONE").exists():
                shutil.rmtree(paths["repair_dir"], ignore_errors=True)
            cmd = [
                str(python_exe),
                "scripts/repair_loop.py",
                "--input",
                str(paths["translated_csv"]),
                "--tasks",
                str(paths["qa_actionable_tasks"]),
                "--output",
                str(paths["repair_output"]),
                "--output-dir",
                str(paths["repair_dir"]),
                "--qa-type",
                "hard",
                "--target-lang",
                "ru-RU",
            ]
            if repair_config:
                cmd.extend(["--config", str(repair_config)])
            result = run_step(cmd, paths["logs_dir"] / "07_repair_hard.log")
            require_success(result, "repair_hard")
            upsert_stage(
                manifest,
                "repair_hard",
                "completed",
                output=str(paths["repair_output"]),
                actionable_errors=actionable_stats["actionable_errors"],
                deferred_review_errors=actionable_stats["deferred_review_errors"],
            )
            write_json(paths["manifest"], manifest)

            upsert_stage(manifest, "qa_hard_recheck", "running")
            write_json(paths["manifest"], manifest)
            result = run_step(
                [
                    str(python_exe),
                    "scripts/qa_hard.py",
                    str(paths["repair_output"]),
                    str(paths["placeholder_map"]),
                    str(schema_path),
                    str(forbidden_path),
                    str(paths["qa_recheck_report"]),
                ],
                paths["logs_dir"] / "08_qa_hard_recheck.log",
            )
            require_report(result, "qa_hard_recheck", paths["qa_recheck_report"])
            if blocking_errors_remain(paths["qa_recheck_report"]):
                raise RuntimeError("qa_hard still reports blocking hard errors after repair_hard.")
            upsert_stage(
                manifest,
                "qa_hard_recheck",
                "completed",
                report=str(paths["qa_recheck_report"]),
                returncode=result.returncode,
            )
            write_json(paths["manifest"], manifest)
        else:
            if paths["qa_recheck_report"].exists() and not blocking_errors_remain(paths["qa_recheck_report"]):
                upsert_stage(
                    manifest,
                    "qa_hard_recheck",
                    "completed",
                    report=str(paths["qa_recheck_report"]),
                    returncode=1,
                    reused_existing_report=True,
                )
            upsert_stage(
                manifest,
                "repair_hard",
                "skipped",
                reason="only_deferred_review_errors",
                deferred_review_errors=actionable_stats["deferred_review_errors"],
            )
            write_json(paths["manifest"], manifest)

    translation_for_review = current_translation_path(paths)

    if not paths["soft_report"].exists():
        soft_cmd = [
            str(python_exe),
            "scripts/soft_qa_llm.py",
            str(translation_for_review),
            str(style_path),
            str(paths["glossary"]),
            "workflow/soft_qa_rubric.yaml",
            "--style-profile",
            str(style_profile_path),
            "--model",
            chosen_model,
            "--out_report",
            str(paths["soft_report"]),
            "--out_tasks",
            str(paths["soft_tasks"]),
        ]
        if paths["soft_checkpoint"].exists():
            soft_cmd.append("--resume")
        upsert_stage(manifest, "soft_qa", "running", resume=paths["soft_checkpoint"].exists())
        write_json(paths["manifest"], manifest)
        result = run_step(soft_cmd, paths["logs_dir"] / "09_soft_qa.log")
        soft_report = require_soft_qa_result(result, paths["soft_report"])
        hard_gate = (soft_report.get("hard_gate") or {}) if isinstance(soft_report, dict) else {}
        upsert_stage(
            manifest,
            "soft_qa",
            "completed",
            report=str(paths["soft_report"]),
            returncode=result.returncode,
            hard_gate_status=str(hard_gate.get("status") or "pass"),
            hard_gate_violation_count=len(hard_gate.get("violations") or []),
        )
        write_json(paths["manifest"], manifest)
    else:
        soft_report = read_json(paths["soft_report"])
        hard_gate = (soft_report.get("hard_gate") or {}) if isinstance(soft_report, dict) else {}
        upsert_stage(
            manifest,
            "soft_qa",
            "completed",
            report=str(paths["soft_report"]),
            reused_existing_report=True,
            hard_gate_status=str(hard_gate.get("status") or "pass"),
            hard_gate_violation_count=len(hard_gate.get("violations") or []),
        )
        write_json(paths["manifest"], manifest)

    if not paths["review_report"].exists():
        upsert_stage(manifest, "length_review", "running")
        write_json(paths["manifest"], manifest)
        result = run_step(
            [
                str(python_exe),
                "scripts/ui_art_length_review.py",
                "--input",
                str(translation_for_review),
                "--output",
                str(paths["review_queue"]),
                "--report",
                str(paths["review_report"]),
            ],
            paths["logs_dir"] / "10_length_review.log",
        )
        require_success(result, "length_review")
        upsert_stage(manifest, "length_review", "completed", report=str(paths["review_report"]))
        write_json(paths["manifest"], manifest)

    if not paths["final_export"].exists():
        upsert_stage(manifest, "rehydrate_export", "running")
        write_json(paths["manifest"], manifest)
        result = run_step(
            [
                str(python_exe),
                "scripts/rehydrate_export.py",
                str(translation_for_review),
                str(paths["placeholder_map"]),
                str(paths["final_export"]),
                "--overwrite",
                "--target-lang",
                "ru-RU",
            ],
            paths["logs_dir"] / "11_rehydrate_export.log",
        )
        require_success(result, "rehydrate_export")
        upsert_stage(manifest, "rehydrate_export", "completed", output=str(paths["final_export"]))
        write_json(paths["manifest"], manifest)

    if not paths["delivery_csv"].exists():
        upsert_stage(manifest, "restore_delivery", "running")
        write_json(paths["manifest"], manifest)
        result = run_step(
            [
                str(python_exe),
                "scripts/restore_ui_art_delivery.py",
                "--prepared",
                str(paths["prepare_csv"]),
                "--translated",
                str(paths["final_export"]),
                "--output",
                str(paths["delivery_csv"]),
                "--report",
                str(paths["delivery_report"]),
            ],
            paths["logs_dir"] / "12_restore_delivery.log",
        )
        require_success(result, "restore_delivery")
        upsert_stage(manifest, "restore_delivery", "completed", output=str(paths["delivery_csv"]), report=str(paths["delivery_report"]))
        write_json(paths["manifest"], manifest)

    manifest["status"] = "completed"
    manifest["completed_at"] = utc_now()
    write_json(paths["manifest"], manifest)
    print(f"[OK] UI art live batch complete -> {paths['delivery_csv']}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Run a UI-art ru-RU live batch in a single serial process.")
    ap.add_argument("--batch-root", default=str(DEFAULT_BATCH_ROOT))
    ap.add_argument("--input", default="")
    ap.add_argument("--run-id", default="")
    ap.add_argument("--model", default="")
    ap.add_argument("--probe-size", type=int, default=3)
    ap.add_argument("--batch-type", default="ui_art_live")
    ap.add_argument("--prepared-batch-type", default="ui_art")
    ap.add_argument("--franchise", default="ui_art")
    ap.add_argument("--approved-glossary", action="append", default=[])
    ap.add_argument("--style", default=str(REPO_ROOT / "workflow" / "style_guide.md"))
    ap.add_argument("--style-profile", default=str(REPO_ROOT / "workflow" / "style_profile.generated.yaml"))
    ap.add_argument("--schema", default=str(REPO_ROOT / "workflow" / "placeholder_schema.yaml"))
    ap.add_argument("--forbidden-patterns", default=str(REPO_ROOT / "workflow" / "forbidden_patterns.txt"))
    args = ap.parse_args()

    try:
        return run_pipeline(args)
    except Exception as exc:
        print(f"[FAIL] UI art live batch failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
