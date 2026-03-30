from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path

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
    manifest = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "status": "success",
        "verify_mode": "full",
        "target_lang": "en-US",
        "issue_file": str(issue_file),
        "started_at": "2026-03-27T01:00:00+00:00",
        "row_checks": {"input_rows": 1, "translate_rows": 1, "final_rows": 1, "translate_delta": 0, "final_delta": 0},
        "stages": [
            {"name": "Connectivity", "status": "pass", "required": True, "files": [{"path": str(verify_log), "required": True}]},
            {"name": "Smoke Verify", "status": "warn", "required": True, "files": [{"path": str(verify_log), "required": True}]},
        ],
        "artifacts": {"smoke_verify_log": str(verify_log)},
        "stage_artifacts": {"smoke_verify_log": str(verify_log)},
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")


class _NoopLauncher:
    def list_pending_runs(self):
        return []

    def get_pending_run(self, run_id: str):
        return None


def test_runtime_shell_serves_page_and_exposes_run_inspection_flow(tmp_path):
    _write_run_fixture(tmp_path, "ui_run_acceptance")
    app = server.OperatorUIApp(repo_root=tmp_path, launcher=_NoopLauncher())
    httpd = server.build_http_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address
    base_url = f"http://{host}:{port}"

    try:
        html = urllib.request.urlopen(base_url + "/").read().decode("utf-8")
        assert "启动 Run" in html
        assert "最近 Run" in html
        assert "Run 时间线" in html
        assert "产物" in html

        app_js = urllib.request.urlopen(base_url + "/app.js").read().decode("utf-8")
        assert "/api/runs" in app_js

        detail = json.loads(urllib.request.urlopen(base_url + "/api/runs/ui_run_acceptance").read().decode("utf-8"))
        assert detail["run"]["overall_status"] == "warn"
        assert detail["run"]["issue_summary"]["total"] == 1
        assert detail["run"]["verify"]["status"] == "WARN"

        artifact = json.loads(
            urllib.request.urlopen(base_url + "/api/runs/ui_run_acceptance/artifacts/smoke_verify_log").read().decode("utf-8")
        )
        assert "PASS" in artifact["artifact"]["content"]
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def test_runtime_shell_frontend_consumes_stages_and_verify_contract():
    app_js = Path(__file__).resolve().parents[1] / "operator_ui" / "app.js"
    source = app_js.read_text(encoding="utf-8")

    assert "const stages = run.stages || [];" in source
    assert "const verify = run.verify || {};" in source
    assert "run.timeline" not in source
    assert "run.verify_summary" not in source
