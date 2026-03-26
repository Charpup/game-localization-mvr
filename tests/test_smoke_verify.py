import io
import json
import scripts.smoke_verify as sv


def test_set_print_config_invalid_encoding():
    # Invalid encoding should gracefully fall back to utf-8
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="ascii", errors="strict")

    class DummyStdout:
        def __init__(self, inner):
            self.buffer = inner

        def flush(self):
            pass

    dummy = DummyStdout(stream)

    class SysLike:
        stdout = dummy
        stderr = dummy

    sv.set_print_config(encoding="this-encoding-does-not-exist", errors="replace")
    old_sys = sv.sys
    try:
        sv.sys = SysLike()  # type: ignore[attr-defined]
        sv.print("unicode 测试 ✅")
    finally:
        sv.sys = old_sys

    assert raw.getvalue() != b""


def test_safe_print_no_utf8_crash(monkeypatch):
    raw = io.BytesIO()
    stream = io.TextIOWrapper(raw, encoding="ascii", errors="strict")
    class DummyStdout:
        def __init__(self, inner):
            self.buffer = inner
        def flush(self):
            pass
    dummy = DummyStdout(stream)

    class SysLike:
        stdout = dummy
        stderr = dummy

    monkeypatch.setattr(sv, "sys", SysLike())
    sv.set_print_config(encoding="ascii", errors="replace")

    sv.print("tag ✅")
    assert len(raw.getvalue()) > 0


def test_discover_file_from_stage_artifacts(tmp_path):
    manifest = {
        "run_id": "smoke_run_test",
        "stages": [
            {
                "name": "QA",
                "files": [{"path": str(tmp_path / "qa_report.json"), "required": True}],
                "required": True,
            }
        ],
        "stage_artifacts": {
            "final_csv": str(tmp_path / "final_out.csv"),
        },
    }
    stages = sv._normalize_stages(manifest)
    assert sv._find_final_file(stages, manifest).endswith("final_out.csv")

    (tmp_path / "qa_report.json").write_text("{}", encoding="utf-8")
    issues = sv._collect_stage_issues(stages, manifest, manifest.get("run_id", "run"))
    assert issues == []


def test_verify_qa_reports_skips_issue_for_approved_non_blocking_warnings(tmp_path):
    qa_report = tmp_path / "smoke_qa_hard_report.json"
    qa_report.write_text(json.dumps({
        "has_errors": False,
        "warnings": [{"type": "empty_source_translation_soft"}],
        "warning_counts": {"empty_source_translation": 1},
        "warning_policy": {
            "approved_warning_total": 1,
            "actionable_warning_total": 0,
            "approved_non_blocking_types": ["empty_source_translation_soft"],
        },
        "metadata": {"total_errors": 0, "total_warnings": 1},
    }), encoding="utf-8")

    ok, rows, issues = sv._verify_qa_reports(
        "smoke_run_test",
        [("Hard QA", str(qa_report))],
        "",
    )

    assert ok is True
    assert issues == []
    assert "actionable_warnings=0" in rows[0]


def test_verify_qa_reports_emits_issue_for_actionable_warnings(tmp_path):
    qa_report = tmp_path / "smoke_qa_hard_report.json"
    qa_report.write_text(json.dumps({
        "has_errors": False,
        "warnings": [{"type": "token_mismatch_soft"}],
        "warning_counts": {"token_mismatch_soft": 1},
        "warning_policy": {
            "approved_warning_total": 0,
            "actionable_warning_total": 1,
            "approved_non_blocking_types": ["empty_source_translation_soft"],
        },
        "metadata": {"total_errors": 0, "total_warnings": 1},
    }), encoding="utf-8")

    ok, rows, issues = sv._verify_qa_reports(
        "smoke_run_test",
        [("Hard QA", str(qa_report))],
        "",
    )

    assert ok is True
    assert len(issues) == 1
    assert issues[0]["error_code"] == "VERIFY_QA_WARNING"
    assert issues[0]["context"]["actionable_warning_total"] == 1
    assert "actionable_warnings=1" in rows[0]


def test_preflight_blocks_on_hard_qa_issue(tmp_path):
    qa_report = tmp_path / "smoke_qa_hard_report.json"
    qa_report.write_text(json.dumps({
        "has_errors": True,
        "error_counts": {"token_mismatch": 1},
        "metadata": {"total_errors": 1, "total_warnings": 0},
    }), encoding="utf-8")

    manifest = tmp_path / "run_manifest.json"
    manifest.write_text(json.dumps({
        "run_id": "smoke_run_test",
        "stages": [
            {
                "name": "QA Hard",
                "required": True,
                "files": [{"path": str(qa_report), "required": True}],
            }
        ],
    }), encoding="utf-8")

    issue_file = tmp_path / "smoke_issues.json"
    assert sv.run_verify(str(manifest), "preflight", str(issue_file)) is False


def test_find_qa_reports_prefers_terminal_hard_report_from_manifest(tmp_path):
    hard_initial = tmp_path / "smoke_qa_hard_report.json"
    hard_recheck = tmp_path / "smoke_qa_hard_recheck_report.json"
    soft_report = tmp_path / "smoke_qa_soft_report.json"
    for path in (hard_initial, hard_recheck, soft_report):
        path.write_text("{}", encoding="utf-8")

    manifest = {
        "stage_artifacts": {
            "qa_hard_report": str(hard_initial),
            "qa_hard_recheck_report": str(hard_recheck),
            "qa_soft_report": str(soft_report),
        },
        "stages": [
            {"name": "QA Hard", "files": [{"path": str(hard_initial), "required": True}]},
            {"name": "QA Hard Recheck", "files": [{"path": str(hard_recheck), "required": True}]},
            {"name": "Soft QA", "files": [{"path": str(soft_report), "required": False}]},
        ],
    }

    reports = sv._find_qa_reports(sv._normalize_stages(manifest), manifest)

    assert reports[0] == ("Hard QA", str(hard_recheck))
    assert reports[1] == ("Soft QA", str(soft_report))
    assert str(hard_initial) not in [path for _, path in reports]


def test_print_summary_ignores_missing_optional_stage_files(tmp_path):
    required_file = tmp_path / "required.log"
    required_file.write_text("ok", encoding="utf-8")

    stages = [
        {
            "name": "Repair Hard",
            "required": True,
            "files": [
                {"path": str(required_file), "required": True},
                {"path": str(tmp_path / "optional.csv"), "required": False},
            ],
        }
    ]

    assert sv.print_summary(stages, "", {}, "preflight", issues=[]) is True
