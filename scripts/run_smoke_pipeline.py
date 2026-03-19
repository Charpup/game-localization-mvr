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

try:
    from scripts.smoke_issue_logger import append_issue, build_issue
except ImportError:  # pragma: no cover
    from smoke_issue_logger import append_issue, build_issue


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


def _append_stage(manifest: dict, name: str, files: list, status: str, required: bool = True) -> None:
    manifest["stages"].append({
        "name": name,
        "status": status,
        "required": required,
        "files": [{"path": str(p), "required": True} for p in files],
    })


def _write_manifest(manifest_path: Path, manifest: dict) -> None:
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)


def _append_artifact(manifest: dict, name: str, path: Path) -> None:
    manifest.setdefault("artifacts", {})
    manifest["artifacts"][name] = str(path)


def _append_stage_artifact(manifest: dict, name: str, path: Path) -> None:
    manifest.setdefault("stage_artifacts", {})
    manifest["stage_artifacts"][name] = str(path)


def _make_manifest(args: argparse.Namespace, run_id: str, input_csv: Path, run_dir: Path, issue_file: Path) -> dict:
    started = datetime.now(timezone.utc)
    return {
        "run_id": run_id,
        "timestamp": started.isoformat(),
        "manifest_version": "smoke-manifest-v1",
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
            "schema": args.schema,
            "forbidden_patterns": args.forbidden,
            "glossary": args.glossary,
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


def run_pipeline(args: argparse.Namespace) -> int:
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
    final_csv = run_dir / "smoke_final_export.csv"
    run_manifest_path = run_dir / "run_manifest.json"

    manifest = _make_manifest(args, run_id, input_csv, run_dir, issue_file)

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
        manifest["status"] = "failed"
        _write_manifest(run_manifest_path, manifest)
        return 1

    input_row_count = _count_csv_rows(input_csv)
    manifest["row_counts"]["input"] = input_row_count

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
        manifest["status"] = "failed"
        _write_manifest(run_manifest_path, manifest)
        return 1

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
        manifest["status"] = "failed"
        _write_manifest(run_manifest_path, manifest)
        return 1

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
        "--target-lang", active_target,
        "--target-key", _derive_target_key(active_target),
        "--model", args.model,
        "--checkpoint", str(run_dir / "smoke_translate_checkpoint.json")
    ]

    translate = _run_step(target_cmd, translation_log)
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
            "--target-lang", active_target,
            "--target-key", _derive_target_key(active_target),
            "--model", args.model,
            "--checkpoint", str(run_dir / "smoke_translate_checkpoint.json")
        ]
        translate = _run_step(target_cmd, translation_log)
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
        manifest["status"] = "failed"
        _write_manifest(run_manifest_path, manifest)
        return 1

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
    _append_stage(manifest, "QA Hard", [qa_hard_report], "pass" if qa.returncode == 0 else "fail")
    _append_artifact(manifest, "smoke_qa_hard_report", qa_hard_report)
    _append_artifact(manifest, "smoke_qa_hard_log", qa_log)
    _append_stage_artifact(manifest, "qa_hard_report", qa_hard_report)
    _append_stage_artifact(manifest, "qa_hard_log", qa_log)
    manifest["qa_hard_report"] = str(qa_hard_report)
    qa_report = _read_json(qa_hard_report)
    qa_has_errors = bool(qa_report.get("has_errors"))
    qa_warning_total = int((qa_report.get("metadata", {}) or {}).get("total_warnings", 0))
    qa_warning_policy = qa_report.get("warning_policy") or {}
    qa_actionable_warning_total = int(qa_warning_policy.get("actionable_warning_total", qa_warning_total))
    qa_warning_samples = (qa_report.get("warnings") or [])[:50]
    qa_warning_counts = qa_report.get("warning_counts", {})
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
    if qa.returncode != 0:
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="qa_hard",
            severity="P0",
            error_code="QA_HARD_FAIL",
            context={"log": str(qa_log), "returncode": qa.returncode},
            suggest="修复硬性规则问题（token/标签/禁用词）后重试。"
        ))

    if qa.returncode != 0 or qa_has_errors:
        # Keep going only for non-blocking? smoke hard gate is blocking by plan
        manifest["status"] = "failed"
        _write_manifest(run_manifest_path, manifest)
        return 1

    # 4) rehydrate export
    rehydrate_log = run_dir / f"04_{_safe_stage_name('rehydrate')}.log"
    rehydrate = _run_step([
        sys.executable, "scripts/rehydrate_export.py",
        str(translated_csv),
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
        manifest["status"] = "failed"
        _write_manifest(run_manifest_path, manifest)
        return 1

    # 5) row count integrity checks
    translated_rows = _count_csv_rows(translated_csv)
    final_rows = _count_csv_rows(final_csv)
    input_rows_map = _read_rows_as_dict(input_csv, "string_id")
    final_rows_map = _read_rows_as_dict(final_csv, "string_id")
    final_headers = []
    if final_csv.exists():
        with open(final_csv, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            final_headers = next(reader, []) or []
    _write_row_checks(manifest, input_row_count, translated_rows, final_rows)
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
        manifest["status"] = "failed"
        _write_manifest(run_manifest_path, manifest)
        return 1
    if final_rows != input_row_count:
        _issue_row_mismatch(run_id, issue_file, "rehydrate", input_row_count, final_rows, "final output row count mismatch")
        manifest["status"] = "failed"
        _write_manifest(run_manifest_path, manifest)
        return 1

    # 6) verify (manifest-driven)
    verify_log = run_dir / f"99_{_safe_stage_name('smoke_verify')}.log"
    manifest["final_file"] = str(final_csv)
    manifest["stage_artifacts"].update({
        "final_target_lang": active_target,
    })
    _append_stage_artifact(manifest, "verify_input", final_csv)
    _append_artifact(manifest, "smoke_manifest", run_manifest_path)
    _append_artifact(manifest, "smoke_verify_log", verify_log)
    _write_manifest(run_manifest_path, manifest)

    verify = _run_step([
        sys.executable, "scripts/smoke_verify.py",
        "--manifest", str(run_manifest_path),
        "--mode", args.verify_mode,
        "--issue-file", str(issue_file),
    ], verify_log)
    _append_stage(manifest, "Smoke Verify", [verify_log], "pass" if verify.returncode == 0 else "fail")
    if verify.returncode != 0:
        append_issue(str(issue_file), build_issue(
            run_id=run_id,
            stage="smoke_verify",
            severity="P1",
            error_code="SMOKE_VERIFY_FAIL",
            context={"log": str(verify_log), "returncode": verify.returncode},
            suggest="修复被阻断项后复跑 verify。"
        ))
        manifest["status"] = "failed"
        _write_manifest(run_manifest_path, manifest)
        return verify.returncode

    manifest["status"] = "success"
    manifest["passed_at"] = datetime.now(timezone.utc).isoformat()
    manifest["stage_artifacts"]["final_file"] = str(final_csv)
    manifest["pipeline_completion"] = {
        "status": "success",
        "completed_at": manifest["passed_at"],
        "notes": "Pipeline finished without blocking errors."
    }
    _write_manifest(run_manifest_path, manifest)
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
    parser.add_argument("--glossary", default="workflow/smoke_glossary_approved.yaml", help="Glossary path")
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
