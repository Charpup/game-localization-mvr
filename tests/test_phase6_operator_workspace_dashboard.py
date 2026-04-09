from __future__ import annotations

import json
import sys
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import scripts.operator_ui_server as server


def _write_run_fixture(base_dir: Path, run_id: str) -> None:
    run_dir = base_dir / "data" / "operator_ui_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    verify_log = run_dir / "99_smoke_verify.log"
    verify_log.write_text("returncode: 0\n---- STDOUT ----\nPASS\n", encoding="utf-8")
    verify_report = run_dir / f"smoke_verify_{run_id}.json"
    verify_report.write_text(
        json.dumps({"run_id": run_id, "status": "WARN", "overall": "WARN", "issue_count": 1, "qa_rows": ["Hard QA: total_errors=0"]}),
        encoding="utf-8",
    )
    issue_file = run_dir / "smoke_issues.json"
    issue_file.write_text(
        json.dumps({"run_id": run_id, "issues": [{"stage": "smoke_verify", "severity": "P2", "error_code": "VERIFY_QA_WARNING"}]}),
        encoding="utf-8",
    )
    review_tickets = run_dir / "smoke_review_tickets.jsonl"
    operator_summary = run_dir / "operator_summary.md"
    operator_summary.write_text("# Delivery summary\nReview-ready package.\n", encoding="utf-8")
    review_tickets.write_text(
        json.dumps(
            {
                "ticket_id": f"ticket:manual_review:{run_id}:manual_review",
                "task_id": f"manual_review:{run_id}",
                "string_id": run_id,
                "target_locale": "en-US",
                "ticket_type": "manual_review",
                "priority": "P1",
                "review_owner": "human-linguist",
                "review_status": "pending",
                "review_source": "manual_review",
                "queue_reason": "needs manual review",
                "current_target": "Hello",
                "reason_codes": ["STYLE_CONTRACT_CHANGED"],
                "content_class": "general",
                "risk_level": "high",
                "created_at": "2026-03-27T08:00:00+00:00",
                "source_artifacts": {"review_queue": str(run_dir / "smoke_review_queue.csv")},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (run_dir / "smoke_review_feedback_log.jsonl").write_text("", encoding="utf-8")
    (run_dir / "smoke_language_governance_kpi.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-03-27T08:01:00+00:00",
                "scope": run_id,
                "runtime_summary": {"overall_status": "running", "total_tasks": 1, "updated_count": 1, "review_handoff_count": 1},
                "review_summary": {
                    "total_review_tickets": 1,
                    "pending_review_tickets": 1,
                    "manual_intervention_rate": 1.0,
                    "feedback_entries": 0,
                    "feedback_closure_rate": 0.0,
                },
                "lifecycle_summary": {
                    "registry_path": "workflow/lifecycle_registry.yaml",
                    "checked_assets": {"data/style_profile.yaml": {"status": "approved"}},
                    "deprecated_asset_usage_count": 0,
                },
                "metrics_sources": {"run_manifest": str(run_dir / "run_manifest.json")},
            }
        ),
        encoding="utf-8",
    )
    manifest = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "status": "warn",
        "overall_status": "warn",
        "verify_mode": "full",
        "target_lang": "en-US",
        "issue_file": str(issue_file),
        "started_at": "2026-03-27T01:00:00+00:00",
        "runtime_governance": {"passed": True},
        "row_checks": {"input_rows": 1, "translate_rows": 1, "final_rows": 1, "translate_delta": 0, "final_delta": 0},
        "stages": [
            {"name": "Connectivity", "status": "pass", "required": True, "files": [{"path": str(verify_log), "required": True}]},
            {"name": "Smoke Verify", "status": "warn", "required": True, "files": [{"path": str(verify_log), "required": True}]},
        ],
        "artifacts": {
            "run_manifest": str(run_dir / "run_manifest.json"),
            "smoke_verify_report": str(verify_report),
            "smoke_issues_report": str(issue_file),
            "operator_summary_md": str(operator_summary),
            "smoke_verify_log": str(verify_log),
            "smoke_review_tickets_jsonl": str(review_tickets),
            "smoke_feedback_log_jsonl": str(run_dir / "smoke_review_feedback_log.jsonl"),
            "smoke_governance_kpi_json": str(run_dir / "smoke_language_governance_kpi.json"),
        },
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class _NoopLauncher:
    def list_pending_runs(self):
        return []

    def get_pending_run(self, run_id: str):
        return None


def test_workspace_dashboard_serves_sections_and_drilldown_contract(tmp_path):
    _write_run_fixture(tmp_path, "workspace_dashboard_acceptance")
    app = server.OperatorUIApp(repo_root=tmp_path, launcher=_NoopLauncher())
    httpd = server.build_http_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address
    base_url = f"http://{host}:{port}"

    try:
        html = urllib.request.urlopen(base_url + "/").read().decode("utf-8")
        assert "Loc-MVR 人类交付控制台" in html
        assert "Task Wizard" in html
        assert "继续处理待办" in html
        assert "Case Board" in html
        assert "Runtime Peek" in html
        assert 'id="task-view"' in html
        assert 'id="mode-tasks"' in html
        assert 'id="lane-act"' in html
        assert 'id="inspector-runtime"' in html
        assert 'id="lang-zh"' in html
        assert 'id="lang-en"' in html

        styles = urllib.request.urlopen(base_url + "/styles.css").read().decode("utf-8")
        assert ".board-stage" in styles
        assert ".board-grid" in styles
        assert ".inspector" in styles

        app_js = urllib.request.urlopen(base_url + "/app.js").read().decode("utf-8")
        assert "/api/tasks" in app_js
        assert "/api/workspace/overview" in app_js
        assert "/api/workspace/cases" in app_js
        assert "/api/workspace/runs/" in app_js
        assert "loadRuntimePeek" in app_js
        assert "selectedCaseId" in app_js
        assert "localStorage" in app_js
        assert "LANG_STORAGE_KEY" in app_js

        overview = json.loads(urllib.request.urlopen(base_url + "/api/workspace/overview?limit_runs=5").read().decode("utf-8"))
        assert overview["overview"]["open_card_count"] >= 1
        assert overview["overview"]["open_case_count"] >= 1

        tasks = json.loads(
            urllib.request.urlopen(
                base_url + "/api/tasks?bucket=waiting_on_ops&status=needs_operator_review&query=workspace_dashboard_acceptance&limit=5"
            ).read().decode("utf-8")
        )
        assert len(tasks["tasks"]) == 1
        assert tasks["tasks"][0]["task_id"] == "task_workspace_dashboard_acceptance"
        assert tasks["tasks"][0]["bucket"] == "waiting_on_ops"
        assert tasks["overview"]["counts_by_bucket"]["waiting_on_ops"] >= 1

        cases = json.loads(urllib.request.urlopen(base_url + "/api/workspace/cases?status=open").read().decode("utf-8"))
        selected = cases["cases"][0]
        assert selected["run_id"] == "workspace_dashboard_acceptance"

        detail = json.loads(urllib.request.urlopen(base_url + "/api/workspace/runs/workspace_dashboard_acceptance").read().decode("utf-8"))
        assert detail["workspace"]["decision_context"]["card_id"]
        assert detail["workspace"]["review_workload"]["pending_review_tickets"] == 1

        runtime_detail = json.loads(urllib.request.urlopen(base_url + "/api/runs/workspace_dashboard_acceptance").read().decode("utf-8"))
        assert runtime_detail["run"]["overall_status"] == "warn"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
