#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Run the final narrow residual-v2 slice against the repaired residual-v1 baseline.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

try:
    from scripts.run_ui_art_live_batch import find_active_batch_processes, resolve_approved_glossaries
    from scripts import build_ui_art_residual_v2_slice as residual_v2
except ImportError:  # pragma: no cover
    from run_ui_art_live_batch import find_active_batch_processes, resolve_approved_glossaries
    import build_ui_art_residual_v2_slice as residual_v2


REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BATCH_ROOT = REPO_ROOT / "data" / "incoming" / "ui_art_batch"
DEFAULT_BASE_RUN_DIR = DEFAULT_BATCH_ROOT / "runs" / "ui_art_full_rerun_run01"
DEFAULT_BASE_SLICE_DIR = DEFAULT_BASE_RUN_DIR / "residual_triage_slice01"
DEFAULT_V2_SLICE_DIR = DEFAULT_BASE_SLICE_DIR / "residual_v2_slice02"
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


def manifest_for(base_slice_dir: Path, v2_slice_dir: Path, chosen_model: str, batch_type: str = "ui_art_residual_v2") -> Dict[str, Any]:
    return {
        "run_id": v2_slice_dir.name,
        "route": "plc + triadev",
        "batch_type": batch_type,
        "base_slice_dir": str(base_slice_dir),
        "v2_slice_dir": str(v2_slice_dir),
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


def merge_rows(base_rows: List[Dict[str, str]], patched_rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    patch_map = {str(row.get("string_id") or ""): row for row in patched_rows}
    merged: List[Dict[str, str]] = []
    for row in base_rows:
        sid = str(row.get("string_id") or "")
        patch = patch_map.get(sid)
        if not patch:
            merged.append(dict(row))
            continue
        combined = dict(row)
        for key, value in patch.items():
            if value == "" and key not in {"target_text", "target", "target_ru"}:
                continue
            combined[key] = value
        combined["current_target_text"] = str(patch.get("target_text") or patch.get("target_ru") or "")
        combined["residual_v2_merge_status"] = str(patch.get("translate_status") or "patched")
        merged.append(combined)
    return merged


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the UI-art residual v2 slice.")
    ap.add_argument("--base-run-dir", default=str(DEFAULT_BASE_RUN_DIR))
    ap.add_argument("--base-slice-dir", default=str(DEFAULT_BASE_SLICE_DIR))
    ap.add_argument("--v2-slice-dir", default=str(DEFAULT_V2_SLICE_DIR))
    ap.add_argument("--override-path", default=str(DEFAULT_OVERRIDE_PATH))
    ap.add_argument("--model", default="")
    ap.add_argument("--batch-type", default="ui_art_residual_v2")
    ap.add_argument("--franchise", default="ui_art")
    ap.add_argument("--approved-glossary", action="append", default=[])
    args = ap.parse_args()

    python_exe = ensure_python()
    base_run_dir = Path(args.base_run_dir)
    base_slice_dir = Path(args.base_slice_dir)
    v2_slice_dir = Path(args.v2_slice_dir)
    v2_slice_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = v2_slice_dir / "logs"
    manifest_path = v2_slice_dir / "run_manifest.json"

    base_manifest = read_json(base_slice_dir / "run_manifest.json") or read_json(base_run_dir / "run_manifest.json")
    chosen_model = str(args.model or base_manifest.get("chosen_model") or "claude-haiku-4-5-20251001")
    manifest = read_json(manifest_path) or manifest_for(base_slice_dir, v2_slice_dir, chosen_model, batch_type=args.batch_type)
    manifest["chosen_model"] = chosen_model
    manifest["batch_type"] = args.batch_type
    write_json(manifest_path, manifest)

    batch_root = base_run_dir.parent.parent
    active = find_active_batch_processes(batch_root, v2_slice_dir)
    if active:
        raise RuntimeError(f"Refusing to start residual v2 while active batch processes exist: {active}")

    if not (v2_slice_dir / "ui_art_residual_v2_manifest.json").exists():
        upsert_stage(manifest, "build_v2_slice", "running")
        write_json(manifest_path, manifest)
        result = run_step(
            [
                str(python_exe),
                "scripts/build_ui_art_residual_v2_slice.py",
                "--base-run-dir",
                str(base_run_dir),
                "--base-slice-dir",
                str(base_slice_dir),
                "--out-dir",
                str(v2_slice_dir),
                "--override-path",
                str(Path(args.override_path)),
            ],
            logs_dir / "01_build_v2_slice.log",
        )
        require_success(result, "build_v2_slice")
        upsert_stage(manifest, "build_v2_slice", "completed", manifest=str(v2_slice_dir / "ui_art_residual_v2_manifest.json"))
        write_json(manifest_path, manifest)

    v2_manifest = read_json(v2_slice_dir / "ui_art_residual_v2_manifest.json")
    if not bool(v2_manifest.get("justified_for_narrow_auto")):
        manifest["status"] = "completed_skipped"
        manifest["completed_at"] = utc_now()
        upsert_stage(manifest, "narrow_auto", "skipped", reason="auto_fix_blocker_rows_below_threshold")
        write_json(manifest_path, manifest)
        print("[OK] Residual V2 harness built, but narrow auto was not justified.")
        return 0

    paths = {
        "repair_input": v2_slice_dir / "ui_art_residual_v2_repair_input.csv",
        "patch_glossary": v2_slice_dir / "ui_art_residual_v2_patch_glossary.yaml",
        "compiled_glossary": v2_slice_dir / "glossary_ui_art_residual_v2_compiled.yaml",
        "repaired_subset": v2_slice_dir / "ui_art_residual_v2_patched_rows.csv",
        "translate_checkpoint": v2_slice_dir / "translate_checkpoint.json",
        "merged_translated": v2_slice_dir / "ui_art_translated_repaired_v2.csv",
        "qa_report": v2_slice_dir / "ui_art_qa_hard_report.json",
        "soft_report": v2_slice_dir / "ui_art_soft_qa_report.json",
        "soft_tasks": v2_slice_dir / "ui_art_soft_tasks.jsonl",
        "soft_checkpoint": v2_slice_dir / "soft_qa_checkpoint.json",
        "review_queue_raw": v2_slice_dir / "ui_art_residual_v2_review_queue_raw.csv",
        "review_report": v2_slice_dir / "ui_art_residual_v2_review_queue.json",
        "review_queue_enriched": v2_slice_dir / "ui_art_residual_v2_review_queue_enriched.csv",
        "blocker_rows": v2_slice_dir / "ui_art_residual_v2_blocker_rows.csv",
        "near_limit_rows": v2_slice_dir / "ui_art_residual_v2_near_limit_nonblocking.csv",
        "manual_creative": v2_slice_dir / "ui_art_residual_v2_manual_creative_titles.csv",
        "manual_ambiguity": v2_slice_dir / "ui_art_residual_v2_manual_ambiguity_terms.csv",
        "auto_fix_rows": v2_slice_dir / "ui_art_residual_v2_auto_fixable_repeated_titles.csv",
        "final_export": v2_slice_dir / "ui_art_final_export.csv",
        "delivery": v2_slice_dir / "ui_art_delivery_repaired_v2.csv",
        "delivery_report": v2_slice_dir / "ui_art_delivery_repaired_v2_report.json",
        "assessment_json": v2_slice_dir / "ui_art_residual_v2_assessment.json",
        "assessment_md": v2_slice_dir / "ui_art_residual_v2_assessment.md",
    }
    approved_glossaries = resolve_approved_glossaries(args.approved_glossary or [])

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
        upsert_stage(manifest, "translate_narrow_subset", "running", model=chosen_model)
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
            logs_dir / "04_translate_narrow_subset.log",
        )
        require_success(result, "translate_narrow_subset")
        upsert_stage(manifest, "translate_narrow_subset", "completed", output=str(paths["repaired_subset"]))
        write_json(manifest_path, manifest)

    if not paths["merged_translated"].exists():
        base_rows = read_csv(base_slice_dir / "ui_art_translated_repaired.csv")
        patched_rows = read_csv(paths["repaired_subset"]) if paths["repaired_subset"].exists() else []
        merged_rows = merge_rows(base_rows, patched_rows)
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
                str(paths["review_queue_raw"]),
                "--report",
                str(paths["review_report"]),
            ],
            logs_dir / "07_length_review.log",
        )
        require_success(result, "length_review")
        upsert_stage(manifest, "length_review", "completed", report=str(paths["review_report"]))
        write_json(manifest_path, manifest)

        review_rows, _ = residual_v2.read_csv(paths["review_queue_raw"])
        translated_rows, _ = residual_v2.read_csv(paths["merged_translated"])
        qa_report = read_json(paths["qa_report"])
        soft_report = read_json(paths["soft_report"])
        soft_tasks = residual_v2.read_jsonl(paths["soft_tasks"])
        exact_map, compact_terms = residual_v2.load_compact_glossary(
            Path(args.approved_glossary[-1]).resolve() if args.approved_glossary else REPO_ROOT / "glossary" / "approved.yaml",
            Path(args.override_path),
        )
        enriched_rows, _ = residual_v2.enrich_review_rows(
            review_rows=review_rows,
            translated_rows=translated_rows,
            qa_report=qa_report,
            soft_report=soft_report,
            soft_tasks=soft_tasks,
            exact_map=exact_map,
            compact_terms=compact_terms,
        )
        blocker_rows = [row for row in enriched_rows if str(row.get("severity") or "") in {"major", "critical"}]
        warning_rows = [row for row in enriched_rows if str(row.get("severity") or "") == "warning"]
        manual_creative = [row for row in enriched_rows if str(row.get("manual_bucket") or "") == "manual_creative_titles"]
        manual_ambiguity = [row for row in enriched_rows if str(row.get("manual_bucket") or "") == "manual_ambiguity_terms"]
        auto_fix_rows = [row for row in enriched_rows if str(row.get("auto_fix_candidate") or "") == "true"]
        residual_v2.write_csv(paths["review_queue_enriched"], enriched_rows, residual_v2.select_fieldnames(enriched_rows))
        residual_v2.write_csv(paths["blocker_rows"], blocker_rows, residual_v2.select_fieldnames(blocker_rows))
        residual_v2.write_csv(paths["near_limit_rows"], warning_rows, residual_v2.select_fieldnames(warning_rows))
        if manual_creative:
            residual_v2.write_csv(paths["manual_creative"], manual_creative, residual_v2.select_fieldnames(manual_creative))
        if manual_ambiguity:
            residual_v2.write_csv(paths["manual_ambiguity"], manual_ambiguity, residual_v2.select_fieldnames(manual_ambiguity))
        if auto_fix_rows:
            residual_v2.write_csv(paths["auto_fix_rows"], auto_fix_rows, residual_v2.select_fieldnames(auto_fix_rows))

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
        upsert_stage(manifest, "residual_v2_assessment", "running")
        write_json(manifest_path, manifest)
        result = run_step(
            [
                str(python_exe),
                "scripts/ui_art_residual_v2_assess.py",
                "--base-slice-dir",
                str(base_slice_dir),
                "--v2-slice-dir",
                str(v2_slice_dir),
                "--out-json",
                str(paths["assessment_json"]),
                "--out-md",
                str(paths["assessment_md"]),
            ],
            logs_dir / "10_residual_v2_assessment.log",
        )
        require_success(result, "residual_v2_assessment")
        upsert_stage(manifest, "residual_v2_assessment", "completed", report=str(paths["assessment_json"]))
        write_json(manifest_path, manifest)

    manifest["status"] = "completed"
    manifest["completed_at"] = utc_now()
    write_json(manifest_path, manifest)
    print(f"[OK] Residual V2 complete -> {paths['delivery']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
