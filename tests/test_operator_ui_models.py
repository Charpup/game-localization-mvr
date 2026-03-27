from __future__ import annotations

import json
from pathlib import Path

import scripts.operator_ui_models as models


def _write_run_fixture(base_dir: Path, run_id: str, *, verify_status: str = "WARN", with_issue: bool = True) -> Path:
    run_dir = base_dir / "data" / "operator_ui_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    verify_report = run_dir / f"smoke_verify_{run_id}.json"
    issue_file = run_dir / "smoke_issues.json"
    log_file = run_dir / "99_smoke_verify.log"
    final_csv = run_dir / "smoke_final_export.csv"
    final_csv.write_text("string_id,target_text\n1,hello\n", encoding="utf-8")
    log_file.write_text("returncode: 0\n", encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "status": "success",
        "verify_mode": "full",
        "target_lang": "en-US",
        "input_csv": str(run_dir / "input.csv"),
        "started_at": "2026-03-27T01:00:00+00:00",
        "issue_file": str(issue_file),
        "row_checks": {
            "input_rows": 1,
            "translate_rows": 1,
            "final_rows": 1,
            "translate_delta": 0,
            "final_delta": 0,
        },
        "stages": [
            {
                "name": "Connectivity",
                "status": "pass",
                "required": True,
                "files": [{"path": str(log_file), "required": True}],
            },
            {
                "name": "Smoke Verify",
                "status": "pass" if verify_status == "PASS" else "warn",
                "required": True,
                "files": [{"path": str(log_file), "required": True}],
            },
        ],
        "artifacts": {
            "smoke_verify_log": str(log_file),
            "smoke_final_csv": str(final_csv),
        },
        "stage_artifacts": {
            "smoke_verify_log": str(log_file),
            "final_csv": str(final_csv),
        },
    }
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    verify_report.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": verify_status,
                "overall": verify_status,
                "issue_count": 1 if with_issue else 0,
                "qa_rows": ["Hard QA: total_errors=0, total_warnings=1, actionable_warnings=1, approved_warnings=0"],
            }
        ),
        encoding="utf-8",
    )
    if with_issue:
        issue_file.write_text(
            json.dumps(
                {
                    "run_id": run_id,
                    "issues": [
                        {
                            "stage": "smoke_verify",
                            "severity": "P2",
                            "error_code": "VERIFY_QA_WARNING",
                            "suggestion": "Review warnings.",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
    return manifest_path


def test_load_run_detail_merges_manifest_verify_and_issues(tmp_path):
    manifest_path = _write_run_fixture(tmp_path, "ui_run_warn")

    detail = models.load_run_detail(manifest_path)

    assert detail.run_id == "ui_run_warn"
    assert detail.overall_status == "warn"
    assert detail.verify.status == "WARN"
    assert detail.issue_summary.total == 1
    assert detail.issue_summary.by_severity["P2"] == 1
    assert "smoke_verify_report" in detail.allowed_artifact_keys
    assert detail.artifacts["smoke_verify_log"].previewable is True
    assert detail.row_checks["final_rows"] == 1


def test_load_run_detail_handles_missing_optional_reports(tmp_path):
    manifest_path = _write_run_fixture(tmp_path, "ui_run_missing", with_issue=False)
    run_dir = manifest_path.parent
    (run_dir / f"smoke_verify_ui_run_missing.json").unlink()

    detail = models.load_run_detail(manifest_path)

    assert detail.run_id == "ui_run_missing"
    assert detail.verify.status == "UNKNOWN"
    assert detail.issue_summary.total == 0
    assert detail.artifacts["smoke_verify_report"].exists is False


def test_load_run_summaries_respects_limit_and_sort_order(tmp_path):
    older = _write_run_fixture(tmp_path, "ui_run_older")
    newer = _write_run_fixture(tmp_path, "ui_run_newer")
    older_manifest = json.loads(older.read_text(encoding="utf-8"))
    older_manifest["started_at"] = "2026-03-27T00:00:00+00:00"
    older.write_text(json.dumps(older_manifest), encoding="utf-8")

    newer_manifest = json.loads(newer.read_text(encoding="utf-8"))
    newer_manifest["started_at"] = "2026-03-27T01:00:00+00:00"
    newer.write_text(json.dumps(newer_manifest), encoding="utf-8")

    summaries = models.load_run_summaries(tmp_path, limit=1)

    assert len(summaries) == 1
    assert summaries[0].run_id == "ui_run_newer"
    assert summaries[0].warning_count == 1
