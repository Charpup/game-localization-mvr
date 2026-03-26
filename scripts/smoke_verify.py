#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Flexible smoke pipeline verifier.

Usage:
  python scripts/smoke_verify.py
  python scripts/smoke_verify.py --manifest data/run_manifest.json --mode full
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    import pandas as pd
except ImportError:  # pragma: no cover
    pd = None

try:
    from scripts.smoke_issue_logger import append_issue, build_issue
except ImportError:  # pragma: no cover
    from smoke_issue_logger import append_issue, build_issue


_PRINT_CFG = {
    "encoding": "utf-8",
    "errors": "replace",
}
_BLOCKING_VERIFY_ERROR_CODES = {
    "VERIFY_HARD_QA_FAIL",
    "VERIFY_MISSING_FILE",
    "VERIFY_FAIL",
    "VERIFY_MISSING_HARD_QA_REPORT",
}


def set_print_config(encoding: str = "utf-8", errors: str = "replace") -> None:
    _PRINT_CFG["encoding"] = encoding or "utf-8"
    _PRINT_CFG["errors"] = errors or "replace"


def _coerce_encoding(encoding: str) -> str:
    if not encoding:
        return "utf-8"
    try:
        "x".encode(encoding)
        return encoding
    except LookupError:
        return "utf-8"


def safe_print(*args: Any, sep: str = " ", end: str = "\n", file=None, flush: bool = False) -> None:
    if file is None:
        file = sys.stdout

    text = sep.join("" if obj is None else str(obj) for obj in args) + end
    encoded = text.encode(_coerce_encoding(_PRINT_CFG.get("encoding", "utf-8")), errors=_PRINT_CFG.get("errors", "replace"))

    try:
        file.write(text)
    except UnicodeEncodeError:
        if hasattr(file, "buffer"):
            try:
                file.buffer.write(encoded)
            except TypeError:
                raw_buffer = getattr(file.buffer, "buffer", None)
                if raw_buffer is not None and hasattr(raw_buffer, "write"):
                    raw_buffer.write(encoded)
                else:
                    file.buffer.write(text)
        else:
            raise
    except Exception:
        if hasattr(file, "buffer"):
            try:
                file.buffer.write(encoded)
            except TypeError:
                raw_buffer = getattr(file.buffer, "buffer", None)
                if raw_buffer is not None and hasattr(raw_buffer, "write"):
                    raw_buffer.write(encoded)
                else:
                    file.buffer.write(text)
    if hasattr(file, "flush") and flush:
        file.flush()


print = safe_print  # overwrite builtin print for this module to avoid encoding env dependency


def _configure_standard_streams() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding=_coerce_encoding(_PRINT_CFG.get("encoding", "utf-8")), errors="replace")
        except Exception:
            # Best effort only; safe_print still guards direct output writes.
            pass


_configure_standard_streams()


def _coerce_file_entry(file_item: Any) -> Dict[str, Any]:
    if isinstance(file_item, str):
        return {"path": file_item, "required": True}
    if isinstance(file_item, dict):
        return {
            "path": str(file_item.get("path", "")).strip(),
            "required": bool(file_item.get("required", True)),
        }
    return {"path": "", "required": False}


def _normalize_stages(manifest: Dict[str, Any]) -> List[Dict[str, Any]]:
    stages = []

    # 优先使用 manifest.stages
    if "stages" in manifest and isinstance(manifest["stages"], list):
        for st in manifest["stages"]:
            if not isinstance(st, dict):
                continue
            name = str(st.get("name", "Unknown Stage")).strip()
            raw_files = st.get("files", [])
            files = [_coerce_file_entry(f) for f in (raw_files if isinstance(raw_files, list) else [])]
            if files:
                stages.append({
                    "name": name,
                    "files": files,
                    "required": bool(st.get("required", True)),
                })
        if stages:
            return stages

    # 兼容 stage_artifacts（run pipeline 新标准）
    stage_artifacts = manifest.get("stage_artifacts")
    if isinstance(stage_artifacts, dict) and stage_artifacts:
        files = []
        for name, value in stage_artifacts.items():
            if value:
                item = _coerce_file_entry(value)
                if item["path"]:
                    item["required"] = True
                    files.append(item)
        if files:
            stages.append({
                "name": "Pipeline Artifacts",
                "files": files,
                "required": True,
            })

    # 回退策略：按历史路径做最小验证
    if stages:
        return stages

    artifacts = manifest.get("artifacts")
    if isinstance(artifacts, dict) and artifacts:
        for name, data in artifacts.items():
            raw_files = []
            required = True
            if isinstance(data, dict):
                raw_files = data.get("files", [])
                required = bool(data.get("required", True))
            elif isinstance(data, list):
                raw_files = data
            files = [_coerce_file_entry(f) for f in (raw_files if isinstance(raw_files, list) else [])]
            if files:
                stages.append({
                    "name": str(name),
                    "files": files,
                    "required": required
                })
        if stages:
            return stages

    return [
        {
            "name": "Stage 1 - Normalization",
            "files": [
                _coerce_file_entry("data/smoke_source_raw.csv"),
                _coerce_file_entry("data/smoke_normalized.csv"),
                _coerce_file_entry("data/smoke_draft.csv"),
                _coerce_file_entry("data/smoke_placeholder_map.json"),
            ],
            "required": True,
        },
        {
            "name": "Stage 2 - Style Guide",
            "files": [_coerce_file_entry("workflow/style_guide.md")],
            "required": True,
        },
        {
            "name": "Stage 3 - Glossary",
            "files": [
                _coerce_file_entry("workflow/smoke_glossary_approved.yaml"),
                _coerce_file_entry("workflow/smoke_glossary_compiled.yaml"),
            ],
            "required": False,
        },
        {
            "name": "Stage 4 - Translation",
            "files": [_coerce_file_entry("data/smoke_translated_200.csv"), _coerce_file_entry("data/smoke_translated.csv")],
            "required": True,
        },
        {
            "name": "Stage 5 - Hard QA",
            "files": [
                _coerce_file_entry("reports/smoke_qa_hard_report.json"),
                _coerce_file_entry("data/smoke_repaired_hard.csv"),
            ],
            "required": True,
        },
        {
            "name": "Stage 6 - Export",
            "files": [_coerce_file_entry("data/smoke_final_200.csv"), _coerce_file_entry("data/smoke_final_export.csv")],
            "required": True,
        },
        {
            "name": "Stage 7 - Metrics",
            "files": [
                _coerce_file_entry("reports/smoke_metrics_report.md"),
                _coerce_file_entry("reports/smoke_metrics_report.json"),
            ],
            "required": False,
        },
    ]


def _resolve_path(p: str) -> str:
    if not p:
        return p
    return os.path.abspath(p)


def load_manifest(path: str) -> Dict[str, Any]:
    if not path:
        return {}
    if not os.path.exists(path):
        print(f"WARNING: manifest file missing: {path}")
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _collect_stage_issues(stages: List[Dict[str, Any]], manifest: Dict[str, Any], run_id: str) -> List[Dict[str, Any]]:
    stage_issues = []
    for idx, stage in enumerate(stages, start=1):
        stage_name = stage["name"]
        file_entries = stage.get("files", [])
        if not isinstance(file_entries, list):
            continue

        stage_required = bool(stage.get("required", True))
        if not file_entries:
            if stage_required:
                stage_issues.append(
                    build_issue(
                        run_id=run_id,
                        stage=stage_name,
                        severity="P1",
                        error_code="VERIFY_STAGE_NO_FILES",
                        context={
                            "stage_index": idx,
                            "required": stage_required,
                        },
                        suggest="检查当前 run manifest 中是否正确配置 stage 文件列表。"
                    )
                )
            continue

        for entry in file_entries:
            item = _coerce_file_entry(entry)
            path = _resolve_path(item["path"])
            if not path:
                continue
            if os.path.exists(path):
                continue
            if item["required"] and stage_required:
                stage_issues.append(
                    build_issue(
                        run_id=run_id,
                        stage=stage_name,
                        severity="P0",
                        error_code="VERIFY_MISSING_FILE",
                        context={
                            "stage_index": idx,
                            "file": path,
                            "required": True
                        },
                        suggest="重新执行对应阶段生成缺失文件。"
                    )
                )
    return stage_issues


def _find_qa_reports(stages: List[Dict[str, Any]], manifest: Optional[Dict[str, Any]] = None) -> List[Tuple[str, str]]:
    reports = []
    seen_paths = set()
    selected_labels = set()
    stage_artifacts = manifest.get("stage_artifacts", {}) if isinstance(manifest, dict) else {}
    if isinstance(stage_artifacts, dict):
        for key in ("qa_hard_post_soft_report", "qa_hard_recheck_report", "qa_hard_report"):
            path = stage_artifacts.get(key)
            if isinstance(path, str) and path and path not in seen_paths:
                reports.append(("Hard QA", path))
                seen_paths.add(path)
                selected_labels.add("Hard QA")
                break
        for key in ("soft_qa_report", "qa_soft_report"):
            path = stage_artifacts.get(key)
            if isinstance(path, str) and path and path not in seen_paths:
                reports.append(("Soft QA", path))
                seen_paths.add(path)
                selected_labels.add("Soft QA")
                break

    for stage in stages:
        for item in stage.get("files", []):
            path = _coerce_file_entry(item)["path"]
            lower = path.lower()
            if lower.endswith(".json") and "qa" in lower and path not in seen_paths:
                label = "Soft QA" if "soft" in lower else "Hard QA"
                if label in selected_labels:
                    continue
                reports.append((label, path))
                seen_paths.add(path)
    return reports


def _find_final_file(stages: List[Dict[str, Any]], manifest: Dict[str, Any]) -> str:
    final_file = manifest.get("final_csv") or manifest.get("final_file")
    if final_file:
        return final_file

    stage_artifacts = manifest.get("stage_artifacts", {})
    if isinstance(stage_artifacts, dict):
        candidate = stage_artifacts.get("final_csv") or stage_artifacts.get("final_file")
        if candidate:
            return candidate

    for stage in stages:
        if "export" in stage["name"].lower():
            for item in stage.get("files", []):
                candidate = _coerce_file_entry(item)["path"]
                if candidate.lower().endswith(".csv"):
                    return candidate
    return ""


def _resolve_delivery_columns(manifest: Dict[str, Any], headers: List[str]) -> List[str]:
    preferred = [
        "rehydrated_text",
        "target",
        "target_text",
        "target_en",
        "target_ru",
    ]
    manifest_columns = manifest.get("delivery_columns")
    if isinstance(manifest_columns, list):
        preferred = [col for col in manifest_columns if isinstance(col, str) and col] + preferred

    ordered = []
    seen = set()
    for c in preferred:
        if c not in seen and c in headers:
            ordered.append(c)
            seen.add(c)

    return ordered


def _verify_qa_reports(run_id: str, reports: List[Tuple[str, str]], issue_file: str, issue_prefix: str = "") -> Tuple[bool, List[str], List[Dict[str, Any]]]:
    ok = True
    rows = []
    issues = []

    for name, path in reports:
        if not os.path.exists(path):
            if "hard" in name.lower():
                ok = False
                issues.append(
                    build_issue(
                        run_id=run_id,
                        stage="smoke_verify",
                        severity="P0",
                        error_code="VERIFY_MISSING_HARD_QA_REPORT",
                        context={
                            "qa_report": path,
                        },
                        suggest="补生成 hard QA 报告后重试。"
                    )
                )
                rows.append(f"{name}: report missing ({path})")
            continue

        with open(path, "r", encoding="utf-8") as f:
            qa = json.load(f)

        total_errors = qa.get("metadata", {}).get("total_errors", qa.get("total_errors", 0))
        summary = qa.get("summary", {})
        warning_total = int((qa.get("metadata", {}) or {}).get("total_warnings", 0))
        warning_policy = qa.get("warning_policy") or {}
        approved_warning_total = int(warning_policy.get("approved_warning_total", 0))
        actionable_warning_total = int(warning_policy.get("actionable_warning_total", warning_total))
        warning_samples = (qa.get("warnings") or [])[:20]
        if name.lower().startswith("hard") and qa.get("has_errors", False):
            ok = False
            issues.append(
                build_issue(
                    run_id=run_id,
                    stage="smoke_verify",
                    severity="P0",
                    error_code="VERIFY_HARD_QA_FAIL",
                    context={
                        "qa_report": path,
                        "total_errors": total_errors,
                        "error_counts": qa.get("error_counts", {}),
                        "total_rows": qa.get("total_rows", summary.get("total_rows", 0)),
                        "warning_counts": qa.get("warning_counts", {}),
                        "warning_samples": warning_samples,
                    },
                    suggest="修复 hard QA 问题后重新执行 verify。"
                )
            )
            rows.append(f"{name}: has_errors={qa.get('has_errors', True)}")
            continue

        rows.append(
            f"{name}: total_errors={summary.get('total_errors', total_errors)}, "
            f"total_warnings={warning_total}, actionable_warnings={actionable_warning_total}, "
            f"approved_warnings={approved_warning_total}"
        )

        if actionable_warning_total:
            issues.append(
                build_issue(
                    run_id=run_id,
                    stage="smoke_verify",
                    severity="P2",
                    error_code="VERIFY_QA_WARNING",
                    context={
                        "qa_report": path,
                        "total_warnings": warning_total,
                        "approved_warning_total": approved_warning_total,
                        "actionable_warning_total": actionable_warning_total,
                        "warning_counts": qa.get("warning_counts", {}),
                        "warning_samples": warning_samples,
                        "warning_policy": warning_policy,
                    },
                    suggest="确认 warning 的业务策略并补充到主干治理清单。"
                )
            )
    return ok, rows, issues


def _is_blocking_issue(issue: Dict[str, Any]) -> bool:
    if not isinstance(issue, dict):
        return False
    severity = str(issue.get("severity", "")).upper()
    error_code = str(issue.get("error_code", ""))
    return severity == "P0" or error_code in _BLOCKING_VERIFY_ERROR_CODES


def print_summary(
    stages: List[Dict[str, Any]],
    final_file: str,
    manifest: Dict[str, Any],
    mode: str,
    issues: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    print("=" * 70)
    print(f"Full Pipeline Smoke Test 验证报告 ({mode})")
    print("=" * 70)

    all_pass = True
    issues = issues or []
    qa_warning_count = 0
    for stage in stages:
        print(f"\n--- {stage['name']} ---")
        stage_pass = True
        for item in stage.get("files", []):
            file_entry = _coerce_file_entry(item)
            path = file_entry["path"]
            exists = os.path.exists(_resolve_path(path))
            status = "✅" if exists else "❌"
            print(f"  {status} {path}")
            if stage.get("required", True) and file_entry.get("required", True) and not exists:
                stage_pass = False
                all_pass = False
        if len(stage.get("files", [])) > 0:
            print(f"  → {'PASS' if stage_pass else 'FAIL'}")

    if any(_is_blocking_issue(issue) for issue in issues):
        all_pass = False

    if mode == "full":
        print("\n--- 翻译统计 ---")
        if final_file:
            if os.path.exists(final_file):
                print(f"最终文件: {final_file}")
                if pd:
                    try:
                        df = pd.read_csv(final_file)
                        print(f"总行数: {len(df)}")
                        target_candidates = _resolve_delivery_columns(manifest, list(df.columns))
                        if not target_candidates:
                            target_candidates = [
                                c for c in df.columns
                                if "target" in c.lower() or "rehydrated" in c.lower() or "ru" in c.lower() or "en" in c.lower()
                            ]
                        if target_candidates:
                            tcol = target_candidates[0]
                            translated = df[tcol].notna().sum()
                            pct = translated / max(len(df), 1) * 100
                            print(f"已翻译({tcol}): {translated} ({pct:.1f}%)")
                    except Exception as e:
                        all_pass = False
                        print(f"读取统计失败: {e}")
            else:
                all_pass = False
                print(f"最终文件缺失: {final_file}")
        else:
            print("未提供最终文件路径，跳过翻译统计。")

        print("\n--- QA 统计 ---")
        qa_reports = _find_qa_reports(stages, manifest)
        _, qa_rows, qa_issues = _verify_qa_reports(manifest.get("run_id", ""), qa_reports, "")
        for row in qa_rows:
            print(row)
        qa_warning_count = len([issue for issue in qa_issues if issue.get("error_code") == "VERIFY_QA_WARNING"])
        if qa_warning_count:
            print(f"  QA warning items: {qa_warning_count}")
        if any(_is_blocking_issue(issue) for issue in qa_issues):
            all_pass = False

        print("\n--- LLM 调用统计 ---")
        metrics = manifest.get("artifacts", {}).get("metrics_report") or manifest.get("metrics_report")
        if isinstance(metrics, list):
            for path in metrics:
                if os.path.exists(path):
                    print(f"Metrics Report valid: {path}")
        elif isinstance(metrics, str) and os.path.exists(metrics):
            print(f"Metrics Report valid: {metrics}")

    print("\n" + "=" * 70)
    print(f"Overall Status: {'✅ PASS' if all_pass else '❌ FAIL'}")
    print("=" * 70)
    return all_pass


def run_verify(manifest_path: str, mode: str, issue_file: str = "") -> bool:
    manifest = load_manifest(manifest_path) if manifest_path else {}
    stages = _normalize_stages(manifest)
    run_id = manifest.get("run_id") or os.path.basename(manifest_path or "smoke_run_unknown")
    final_file = _find_final_file(stages, manifest)

    if not issue_file:
        issue_file = manifest.get("issue_file", os.path.join("reports", f"smoke_issues_{run_id}.json"))
    report_dir = os.path.dirname(os.path.abspath(issue_file)) or os.getcwd()
    verify_report = os.path.join(report_dir, f"smoke_verify_{run_id}.json")

    issues = _collect_stage_issues(stages, manifest, run_id)

    # QA issue 归类（硬 QA 失败作为阻断）
    qa_reports = _find_qa_reports(stages, manifest)
    _, qa_rows, qa_issues = _verify_qa_reports(run_id, qa_reports, issue_file)
    issues.extend(qa_issues)

    for issue in issues:
        append_issue(issue_file, issue)

    all_pass = print_summary(stages, final_file, manifest, mode, issues=issues)
    if (not all_pass or not qa_rows) and issues:
        print(f"\n问题已记录到: {issue_file}")

    if (not all_pass) and issues:
        append_issue(
            issue_file,
            build_issue(
                run_id=run_id,
                stage="smoke_verify",
                severity="P1",
                error_code="VERIFY_FAIL",
                context={"mode": mode, "final_file": final_file},
                suggest="修复被阻断项后重新执行 verify。"
            )
        )
        all_pass = False

    # Persist a dedicated smoke-verify summary report for downstream tracking.
    summary = {
        "run_id": run_id,
        "manifest": manifest_path,
        "mode": mode,
        "status": "PASS" if all_pass else "FAIL",
        "overall": "PASS" if all_pass else "FAIL",
        "stages": stages,
        "final_file": final_file,
        "issue_count": len(issues),
        "qa_rows": qa_rows,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with open(verify_report, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    except Exception:
        # verification report is best-effort for compatibility
        pass

    return bool(all_pass)


def main():
    parser = argparse.ArgumentParser(description="Run smoke pipeline verifier")
    parser.add_argument("--manifest", default="", help="Run manifest JSON path")
    parser.add_argument(
        "--mode",
        choices=["preflight", "full"],
        default="full",
        help="preflight 只做关键文件存在性检查, full 额外做统计"
    )
    parser.add_argument("--issue-file", default="", help="Issue output file (JSON)")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Output verbosity (compatibility option)."
    )
    parser.add_argument("--encoding", default="utf-8", help="Output encoding for smoke verify logs")
    args = parser.parse_args()

    set_print_config(args.encoding, "replace")
    ok = run_verify(args.manifest, args.mode, args.issue_file)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
