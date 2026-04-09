from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import pytest

import scripts.operator_ui_server as server
import scripts.operator_ui_tasks as task_models


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_task_run_fixture(base_dir: Path, run_id: str) -> None:
    run_dir = base_dir / "data" / "operator_ui_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    verify_log = run_dir / "99_smoke_verify.log"
    verify_log.write_text("returncode: 0\nPASS\n", encoding="utf-8")
    verify_report = run_dir / f"smoke_verify_{run_id}.json"
    issue_report = run_dir / "smoke_issues.json"
    delivery_summary = run_dir / "operator_summary.md"
    delivery_summary.write_text("# Delivery summary\nApproved content.\n", encoding="utf-8")
    _write_json(verify_report, {"run_id": run_id, "status": "PASS", "overall": "PASS", "issue_count": 0, "qa_rows": []})
    _write_json(issue_report, {"run_id": run_id, "issues": []})
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "status": "pass",
            "overall_status": "pass",
            "verify_mode": "full",
            "target_lang": "en-US",
            "started_at": "2026-04-06T08:00:00+00:00",
            "issue_file": str(issue_report),
            "stages": [{"name": "Smoke Verify", "status": "pass", "required": True, "files": [{"path": str(verify_log), "required": True}]}],
            "artifacts": {
                "run_manifest": str(run_dir / "run_manifest.json"),
                "smoke_verify_log": str(verify_log),
                "smoke_verify_report": str(verify_report),
                "smoke_issues_report": str(issue_report),
                "operator_summary_md": str(delivery_summary),
            },
        },
    )


def _http_json(base_url: str, path: str, *, method: str = "GET", payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(base_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _http_upload(base_url: str, filename: str, content: bytes):
    boundary = "----CodexBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: text/csv\r\n\r\n"
    ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = urllib.request.Request(base_url + "/api/task_uploads", data=body, method="POST")
    request.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(request) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _http_download(base_url: str, path: str):
    request = urllib.request.Request(base_url + path, method="GET")
    with urllib.request.urlopen(request) as response:
        return response.status, response.read(), dict(response.headers)


def _http_error_json(base_url: str, path: str, *, method: str = "GET", payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(base_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(request)
    body = exc_info.value.read().decode("utf-8")
    return exc_info.value.code, json.loads(body)


@dataclass
class _PendingRun:
    run_id: str
    run_dir: str
    target_lang: str
    verify_mode: str
    input: str
    started_at: str
    status: str = "running"

    def to_dict(self):
        return {
            "run_id": self.run_id,
            "run_dir": self.run_dir,
            "target_lang": self.target_lang,
            "verify_mode": self.verify_mode,
            "input": self.input,
            "started_at": self.started_at,
            "status": self.status,
            "command": ["loc-mvr", "--input", self.input],
            "pid": 4321,
        }


class _StubLauncher:
    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.pending: dict[str, _PendingRun] = {}
        self.counter = 0
        self.env_provider = lambda: {}

    def list_pending_runs(self):
        return list(self.pending.values())

    def get_pending_run(self, run_id: str):
        return self.pending.get(run_id)

    def launch_run(self, input_path: str, target_lang: str, verify_mode: str):
        self.counter += 1
        run_id = f"pending_task_run_{self.counter:02d}"
        run_dir = self.repo_root / "data" / "operator_ui_runs" / run_id
        pending = _PendingRun(
            run_id=run_id,
            run_dir=str(run_dir),
            target_lang=target_lang,
            verify_mode=verify_mode,
            input=input_path,
            started_at="2026-04-06T09:00:00+00:00",
        )
        self.pending[run_id] = pending
        return pending


def test_task_endpoints_surface_buckets_preview_download_and_archive(tmp_path):
    _write_task_run_fixture(tmp_path, "task_server_ready")
    task_id = task_models.task_id_for_run("task_server_ready")
    task_models.create_human_task_record(
        tmp_path,
        task_id=task_id,
        title="Server task ready",
        source_input="fixtures/input.csv",
        source_input_label="launch_copy.csv",
        target_locale="en-US",
        verify_mode="full",
        linked_run_id="task_server_ready",
        created_at="2026-04-06T08:00:00+00:00",
    )

    app = server.OperatorUIApp(repo_root=tmp_path)
    httpd = server.build_http_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address
    base_url = f"http://{host}:{port}"

    try:
        status, tasks = _http_json(base_url, "/api/tasks?limit=10")
        assert status == 200
        assert tasks["overview"]["counts_by_status"]["needs_user_action"] == 1
        assert tasks["overview"]["counts_by_bucket"]["needs_your_action"] == 1
        assert tasks["tasks"][0]["task_id"] == task_id

        status, detail = _http_json(base_url, f"/api/tasks/{task_id}")
        assert status == 200
        assert detail["task"]["title"] == "Server task ready"
        assert detail["task"]["status"] == "needs_user_action"
        assert detail["task"]["bundle_summary"]["groups"]
        delivery_id = detail["task"]["bundle_summary"]["primary_delivery_id"]

        status, preview = _http_json(base_url, f"/api/tasks/{task_id}/deliveries/{delivery_id}")
        assert status == 200
        assert preview["delivery"]["label"] == "Delivery summary"
        assert "Delivery summary" in preview["artifact"]["content"]

        status, action = _http_json(base_url, f"/api/tasks/{task_id}/actions/approve_delivery", method="POST", payload={"delivery_id": delivery_id})
        assert status == 202
        assert action["task"]["status"] == "ready_for_download"

        status, body, headers = _http_download(base_url, f"/api/tasks/{task_id}/deliveries/{delivery_id}/download")
        assert status == 200
        assert b"Delivery summary" in body
        assert "attachment" in headers["Content-Disposition"]

        status, downloaded = _http_json(base_url, f"/api/tasks/{task_id}")
        assert status == 200
        assert downloaded["task"]["metrics"]["downloaded_at"]
        assert any(event["type"] == "delivery_downloaded" for event in downloaded["task"]["history"])

        status, archived = _http_json(base_url, f"/api/tasks/{task_id}/actions/archive_task", method="POST", payload={})
        assert status == 202
        assert archived["task"]["bucket"] == "archived"

        status, active_tasks = _http_json(base_url, "/api/tasks?limit=10")
        assert status == 200
        assert not active_tasks["tasks"]

        status, archived_tasks = _http_json(base_url, "/api/tasks?bucket=archived&limit=10")
        assert status == 200
        assert archived_tasks["tasks"][0]["task_id"] == task_id
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def test_task_delivery_download_returns_structured_404_without_auditing_missing_file(tmp_path):
    _write_task_run_fixture(tmp_path, "task_server_missing")
    task_id = task_models.task_id_for_run("task_server_missing")
    task_models.create_human_task_record(
        tmp_path,
        task_id=task_id,
        title="Missing file task",
        source_input="fixtures/input.csv",
        source_input_label="launch_copy.csv",
        target_locale="en-US",
        verify_mode="full",
        linked_run_id="task_server_missing",
        created_at="2026-04-06T08:00:00+00:00",
    )

    app = server.OperatorUIApp(repo_root=tmp_path)
    httpd = server.build_http_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address
    base_url = f"http://{host}:{port}"

    try:
        status, detail = _http_json(base_url, f"/api/tasks/{task_id}")
        assert status == 200
        delivery_id = detail["task"]["bundle_summary"]["primary_delivery_id"]
        (tmp_path / "data" / "operator_ui_runs" / "task_server_missing" / "operator_summary.md").unlink()

        status, error = _http_error_json(base_url, f"/api/tasks/{task_id}/deliveries/{delivery_id}/download")
        assert status == 404
        assert error["error"] == "delivery_file_missing"

        status, unchanged = _http_json(base_url, f"/api/tasks/{task_id}")
        assert status == 200
        assert unchanged["task"]["metrics"]["downloaded_at"] == ""
        assert not any(event["type"] == "delivery_downloaded" for event in unchanged["task"]["history"])
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def test_task_creation_supports_upload_and_request_changes_requires_note(tmp_path):
    launcher = _StubLauncher(tmp_path)
    app = server.OperatorUIApp(repo_root=tmp_path, launcher=launcher)
    httpd = server.build_http_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address
    base_url = f"http://{host}:{port}"

    try:
        status, upload = _http_upload(base_url, "new_input.csv", b"id,source\n1,hello\n")
        assert status == 202
        assert upload["upload_id"]

        status, created = _http_json(
            base_url,
            "/api/tasks",
            method="POST",
            payload={
                "title": "Fresh task",
                "input_mode": "upload",
                "upload_id": upload["upload_id"],
                "target_locale": "ja-JP",
                "verify_mode": "preflight",
            },
        )
        assert status == 202
        task = created["task"]
        assert task["title"] == "Fresh task"
        assert task["input_mode"] == "upload"
        assert task["upload_id"] == upload["upload_id"]
        assert task["source_input_label"] == "new_input.csv"
        assert task["status"] == "running"
        assert task["latest_run_id"].startswith("pending_task_run_")

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _http_json(base_url, f"/api/tasks/{task['task_id']}/actions/request_changes", method="POST", payload={})
        assert exc_info.value.code == 400

        status, changed = _http_json(
            base_url,
            f"/api/tasks/{task['task_id']}/actions/request_changes",
            method="POST",
            payload={"note": "Please rerun after tightening the glossary choices."},
        )
        assert status == 202
        assert changed["task"]["status"] == "running"
        assert changed["task"]["latest_feedback_note"] == "Please rerun after tightening the glossary choices."
        assert len(changed["task"]["linked_run_ids"]) == 2
        assert changed["linked_run_id"].startswith("pending_task_run_")
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def test_task_filters_validate_bucket_and_status_and_404_missing_task(tmp_path):
    app = server.OperatorUIApp(repo_root=tmp_path, launcher=_StubLauncher(tmp_path))
    httpd = server.build_http_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address
    base_url = f"http://{host}:{port}"

    try:
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(urllib.request.Request(base_url + "/api/tasks?bucket=not-real", method="GET"))
        assert exc_info.value.code == 400

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(urllib.request.Request(base_url + "/api/tasks?status=not-real", method="GET"))
        assert exc_info.value.code == 400

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(urllib.request.Request(base_url + "/api/tasks/not-real", method="GET"))
        assert exc_info.value.code == 404
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
