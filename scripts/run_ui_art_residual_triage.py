#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run a bounded residual triage slice against the current UI-art full rerun.

The runner:
- builds the residual candidate slice if needed
- compiles a slice-local glossary (main compact glossary + residual overrides)
- repairs only unresolved residual rows via deterministic prefill + serial LLM pass
- merges repaired rows back onto the base translated full run
- reruns hard QA / soft QA / review queue / export / delivery on the repaired full file
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
from typing import Any, Dict, Iterable, List

try:
    from scripts.run_ui_art_live_batch import find_active_batch_processes, resolve_approved_glossaries
except ImportError:  # pragma: no cover
    from run_ui_art_live_batch import find_active_batch_processes, resolve_approved_glossaries


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BATCH_ROOT = REPO_ROOT / "data" / "incoming" / "ui_art_batch"
DEFAULT_BASE_RUN_DIR = DEFAULT_BATCH_ROOT / "runs" / "ui_art_full_rerun_run01"
DEFAULT_SLICE_DIR = DEFAULT_BASE_RUN_DIR / "residual_triage_slice01"
DEFAULT_OVERRIDE_PATH = DEFAULT_BATCH_ROOT / "residual_patch_overrides.json"
PYTHON_EXE = REPO_ROOT / ".venv" / "Scripts" / "python.exe"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_python() -> Path:
    return PYTHON_EXE if PYTHON_EXE.exists() else Path(sys.executable)


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: Iterable[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def select_fieldnames(rows: List[Dict[str, str]]) -> List[str]:
    names: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in names:
                names.append(key)
    return names


def run_step(cmd: List[str], log_path: Path, env: Dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
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
    with log_path.open("w", encoding="utf-8") as fh:
        fh.write(f"command: {cmd}\n")
        fh.write(f"returncode: {result.returncode}\n\n")
        fh.write("---- STDOUT ----\n")
        fh.write(result.stdout or "")
        fh.write("\n---- STDERR ----\n")
        fh.write(result.stderr or "")
    return result


def require_success(result: subprocess.CompletedProcess[str], stage: str) -> None:
    if result.returncode != 0:
        raise RuntimeError(f"{stage} failed with exit code {result.returncode}")


def require_soft_qa(result: subprocess.CompletedProcess[str], report_path: Path) -> Dict[str, Any]:
    if not report_path.exists():
        raise RuntimeError(f"soft_qa report missing: {report_path}")
    if result.returncode not in (0, 2):
        raise RuntimeError(f"soft_qa failed with exit code {result.returncode}")
    return read_json(report_path)


def manifest_for(base_run_dir: Path, slice_dir: Path, chosen_model: str, batch_type: str = "ui_art_residual_triage") -> Dict[str, Any]:
    return {
        "run_id": slice_dir.name,
        "route": "plc + triadev",
        "batch_type": batch_type,
        "base_run_dir": str(base_run_dir),
        "slice_dir": str(slice_dir),
        "status": "initialized",
        "chosen_model": chosen_model,
        "started_at": utc_now(),
        "updated_at": utc_now(),
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


def merge_repaired_rows(base_rows: List[Dict[str, str]], patched_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    patched_map = {str(row.get("string_id") or ""): row for row in patched_rows}
    merged: List[Dict[str, str]] = []
    for row in base_rows:
        sid = str(row.get("string_id") or "")
        patch = patched_map.get(sid)
        if not patch:
            merged.append(dict(row))
            continue
        combined = dict(row)
        for key, value in patch.items():
            if value == "" and key not in {"target_text", "target", "target_ru"}:
                continue
            combined[key] = value
        combined["current_target_text"] = str(patch.get("target_text") or patch.get("target_ru") or "")
        combined["residual_merge_status"] = str(patch.get("translate_status") or "patched")
        merged.append(combined)
    return merged


def merge_patch_rows(base_rows: List[Dict[str, str]], patched_rows: List[Dict[str, str]]) -> tuple[List[Dict[str, str]], int]:
    merged = merge_repaired_rows(base_rows, patched_rows)
    changed = 0
    for original, updated in zip(base_rows, merged):
        if str(original.get("target_text") or "") != str(updated.get("target_text") or ""):
            changed += 1
    return merged, changed


def main() -> int:
    ap = argparse.ArgumentParser(description="Run a UI-art residual triage slice.")
    ap.add_argument("--base-run-dir", default=str(DEFAULT_BASE_RUN_DIR))
    ap.add_argument("--slice-dir", default=str(DEFAULT_SLICE_DIR))
    ap.add_argument("--override-path", default=str(DEFAULT_OVERRIDE_PATH))
    ap.add_argument("--model", default="", help="Override model. Defaults to base run chosen model.")
    ap.add_argument("--batch-type", default="ui_art_residual_triage")
    ap.add_argument("--franchise", default="ui_art")
    ap.add_argument("--approved-glossary", action="append", default=[])
    args = ap.parse_args()

    python_exe = ensure_python()
    base_run_dir = Path(args.base_run_dir)
    slice_dir = Path(args.slice_dir)
    slice_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = slice_dir / "logs"
    manifest_path = slice_dir / "run_manifest.json"

    base_manifest = read_json(base_run_dir / "run_manifest.json")
    chosen_model = str(args.model or base_manifest.get("chosen_model") or "claude-haiku-4-5-20251001")
    manifest = read_json(manifest_path) or manifest_for(base_run_dir, slice_dir, chosen_model, batch_type=args.batch_type)
    manifest["chosen_model"] = chosen_model
    manifest["batch_type"] = args.batch_type
    write_json(manifest_path, manifest)

    batch_root = base_run_dir.parent.parent
    active = find_active_batch_processes(batch_root, slice_dir)
    if active:
        raise RuntimeError(f"Refusing to start residual triage while active batch processes exist: {active}")

    paths = {
        "candidate_csv": slice_dir / "ui_art_residual_candidates.csv",
        "repair_input": slice_dir / "ui_art_residual_repair_input.csv",
        "manual_seed": slice_dir / "ui_art_residual_manual_queue_seed.csv",
        "manifest": slice_dir / "ui_art_residual_manifest.json",
        "patch_glossary": slice_dir / "ui_art_residual_patch_glossary.yaml",
        "compiled_glossary": slice_dir / "glossary_ui_art_residual_compiled.yaml",
        "repaired_subset": slice_dir / "ui_art_residual_patched_rows.csv",
        "translate_checkpoint": slice_dir / "translate_checkpoint.json",
        "merged_translated": slice_dir / "ui_art_translated_repaired.csv",
        "qa_report": slice_dir / "ui_art_qa_hard_report.json",
        "soft_report": slice_dir / "ui_art_soft_qa_report.json",
        "soft_tasks": slice_dir / "ui_art_soft_tasks.jsonl",
        "soft_checkpoint": slice_dir / "soft_qa_checkpoint.json",
        "review_queue": slice_dir / "ui_art_residual_review_queue.csv",
        "review_report": slice_dir / "ui_art_residual_review_queue.json",
        "final_export": slice_dir / "ui_art_final_export.csv",
        "delivery": slice_dir / "ui_art_delivery_repaired.csv",
        "delivery_report": slice_dir / "ui_art_delivery_repaired_report.json",
        "assessment_json": slice_dir / "ui_art_residual_assessment.json",
        "assessment_md": slice_dir / "ui_art_residual_assessment.md",
    }
    approved_glossaries = resolve_approved_glossaries(args.approved_glossary or [])

    if not paths["manifest"].exists():
        upsert_stage(manifest, "build_slice", "running")
        write_json(manifest_path, manifest)
        result = run_step(
            [
                str(python_exe),
                "scripts/build_ui_art_residual_slice.py",
                "--base-run-dir",
                str(base_run_dir),
                "--out-dir",
                str(slice_dir),
                "--override-path",
                str(Path(args.override_path)),
            ],
            logs_dir / "01_build_slice.log",
        )
        require_success(result, "build_slice")
        upsert_stage(manifest, "build_slice", "completed", manifest=str(paths["manifest"]))
        write_json(manifest_path, manifest)

    if not paths["compiled_glossary"].exists():
        upsert_stage(manifest, "glossary_compile", "running")
        write_json(manifest_path, manifest)
        glossary_cmd = [str(python_exe), "scripts/glossary_compile.py"]
        for approved in approved_glossaries:
            glossary_cmd.extend(["--approved", approved])
        glossary_cmd.extend(
            [
                "--approved",
                str(paths["patch_glossary"]),
                "--out_compiled",
                str(paths["compiled_glossary"]),
                "--language_pair",
                "zh-CN->ru-RU",
                "--franchise",
                args.franchise,
                "--resolve_by_scope",
            ]
        )
        result = run_step(
            glossary_cmd,
            logs_dir / "02_glossary_compile.log",
        )
        require_success(result, "glossary_compile")
        upsert_stage(manifest, "glossary_compile", "completed", output=str(paths["compiled_glossary"]))
        write_json(manifest_path, manifest)

    upsert_stage(manifest, "llm_ping", "running")
    write_json(manifest_path, manifest)
    result = run_step([str(python_exe), "scripts/llm_ping.py"], logs_dir / "03_llm_ping.log")
    require_success(result, "llm_ping")
    upsert_stage(manifest, "llm_ping", "completed")
    write_json(manifest_path, manifest)

    if not paths["repaired_subset"].exists():
        repair_input_exists = paths["repair_input"].exists()
        if repair_input_exists:
            upsert_stage(manifest, "translate_residual_subset", "running", model=chosen_model)
            write_json(manifest_path, manifest)
            result = run_step(
                [
                    str(python_exe),
                    "scripts/translate_llm.py",
                    "--input",
                    str(paths["repair_input"]),
                    "--output",
                    str(paths["repaired_subset"]),
                    "--checkpoint",
                    str(paths["translate_checkpoint"]),
                    "--style",
                    "workflow/style_guide.md",
                    "--glossary",
                    str(paths["compiled_glossary"]),
                    "--style-profile",
                    "data/style_profile.yaml",
                    "--model",
                    chosen_model,
                ],
                logs_dir / "04_translate_subset.log",
            )
            require_success(result, "translate_residual_subset")
            upsert_stage(manifest, "translate_residual_subset", "completed", output=str(paths["repaired_subset"]))
            write_json(manifest_path, manifest)
        else:
            write_csv(paths["repaired_subset"], [], [])
            upsert_stage(manifest, "translate_residual_subset", "skipped", reason="no_auto_repair_rows")
            write_json(manifest_path, manifest)

    if not paths["merged_translated"].exists():
        base_translated = read_csv(base_run_dir / "ui_art_translated.csv")
        patched_rows = read_csv(paths["repaired_subset"]) if paths["repaired_subset"].exists() and paths["repaired_subset"].stat().st_size > 0 else []
        merged_rows = merge_repaired_rows(base_translated, patched_rows)
        write_csv(paths["merged_translated"], merged_rows, select_fieldnames(merged_rows))
        upsert_stage(manifest, "merge_repaired_rows", "completed", output=str(paths["merged_translated"]))
        write_json(manifest_path, manifest)

    if not paths["qa_report"].exists():
        upsert_stage(manifest, "qa_hard", "running")
        write_json(manifest_path, manifest)
        result = run_step(
            [
                str(python_exe),
                "scripts/qa_hard.py",
                str(paths["merged_translated"]),
                str(base_run_dir / "placeholder_map.json"),
                "workflow/placeholder_schema.yaml",
                "workflow/forbidden_patterns.txt",
                str(paths["qa_report"]),
            ],
            logs_dir / "05_qa_hard.log",
        )
        if result.returncode not in (0, 1):
            raise RuntimeError(f"qa_hard failed with unexpected exit code {result.returncode}")
        upsert_stage(manifest, "qa_hard", "completed", report=str(paths["qa_report"]), returncode=result.returncode)
        write_json(manifest_path, manifest)

    if not paths["soft_report"].exists():
        upsert_stage(manifest, "soft_qa", "running")
        write_json(manifest_path, manifest)
        soft_cmd = [
            str(python_exe),
            "scripts/soft_qa_llm.py",
            str(paths["merged_translated"]),
            "workflow/style_guide.md",
            str(paths["compiled_glossary"]),
            "workflow/soft_qa_rubric.yaml",
            "--style-profile",
            "data/style_profile.yaml",
            "--model",
            chosen_model,
            "--out_report",
            str(paths["soft_report"]),
            "--out_tasks",
            str(paths["soft_tasks"]),
        ]
        if paths["soft_checkpoint"].exists():
            soft_cmd.append("--resume")
        result = run_step(soft_cmd, logs_dir / "06_soft_qa.log")
        soft_report = require_soft_qa(result, paths["soft_report"])
        upsert_stage(
            manifest,
            "soft_qa",
            "completed",
            report=str(paths["soft_report"]),
            returncode=result.returncode,
            hard_gate_status=str((soft_report.get("hard_gate") or {}).get("status") or "pass"),
            hard_gate_violation_count=len((soft_report.get("hard_gate") or {}).get("violations") or []),
        )
        write_json(manifest_path, manifest)

    if not paths["review_report"].exists():
        upsert_stage(manifest, "length_review", "running")
        write_json(manifest_path, manifest)
        result = run_step(
            [
                str(python_exe),
                "scripts/ui_art_length_review.py",
                "--input",
                str(paths["merged_translated"]),
                "--output",
                str(paths["review_queue"]),
                "--report",
                str(paths["review_report"]),
            ],
            logs_dir / "07_length_review.log",
        )
        require_success(result, "length_review")
        upsert_stage(manifest, "length_review", "completed", report=str(paths["review_report"]))
        write_json(manifest_path, manifest)

    if not paths["final_export"].exists():
        upsert_stage(manifest, "rehydrate_export", "running")
        write_json(manifest_path, manifest)
        result = run_step(
            [
                str(python_exe),
                "scripts/rehydrate_export.py",
                str(paths["merged_translated"]),
                str(base_run_dir / "placeholder_map.json"),
                str(paths["final_export"]),
                "--overwrite",
                "--target-lang",
                "ru-RU",
            ],
            logs_dir / "08_rehydrate_export.log",
        )
        require_success(result, "rehydrate_export")
        upsert_stage(manifest, "rehydrate_export", "completed", output=str(paths["final_export"]))
        write_json(manifest_path, manifest)

    if not paths["delivery"].exists():
        upsert_stage(manifest, "restore_delivery", "running")
        write_json(manifest_path, manifest)
        result = run_step(
            [
                str(python_exe),
                "scripts/restore_ui_art_delivery.py",
                "--prepared",
                str(base_run_dir / "source_ui_art_prepared.csv"),
                "--translated",
                str(paths["final_export"]),
                "--output",
                str(paths["delivery"]),
                "--report",
                str(paths["delivery_report"]),
            ],
            logs_dir / "09_restore_delivery.log",
        )
        require_success(result, "restore_delivery")
        upsert_stage(manifest, "restore_delivery", "completed", output=str(paths["delivery"]), report=str(paths["delivery_report"]))
        write_json(manifest_path, manifest)

    if not paths["assessment_json"].exists():
        upsert_stage(manifest, "residual_assessment", "running")
        write_json(manifest_path, manifest)
        result = run_step(
            [
                str(python_exe),
                "scripts/ui_art_residual_assess.py",
                "--base-run-dir",
                str(base_run_dir),
                "--slice-dir",
                str(slice_dir),
                "--out-json",
                str(paths["assessment_json"]),
                "--out-md",
                str(paths["assessment_md"]),
            ],
            logs_dir / "10_residual_assessment.log",
        )
        require_success(result, "residual_assessment")
        upsert_stage(manifest, "residual_assessment", "completed", report=str(paths["assessment_json"]))
        write_json(manifest_path, manifest)

    manifest["status"] = "completed"
    manifest["completed_at"] = utc_now()
    write_json(manifest_path, manifest)
    print(f"[OK] Residual triage complete -> {paths['delivery']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
