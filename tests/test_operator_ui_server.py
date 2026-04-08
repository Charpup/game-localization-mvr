from __future__ import annotations

import json
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from scripts.operator_ui_launcher import PendingRunView
import scripts.operator_ui_server as server
import scripts.operator_ui_llm as llm_setup


def _write_run_fixture(base_dir: Path, run_id: str) -> Path:
    run_dir = base_dir / "data" / "operator_ui_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    log_file = run_dir / "99_smoke_verify.log"
    verify_report = run_dir / f"smoke_verify_{run_id}.json"
    issue_file = run_dir / "smoke_issues.json"
    final_csv = run_dir / "smoke_final_export.csv"
    log_file.write_text("returncode: 0\n", encoding="utf-8")
    final_csv.write_text("string_id,target_text\n1,hello\n", encoding="utf-8")
    verify_report.write_text(json.dumps({"run_id": run_id, "status": "PASS", "overall": "PASS", "issue_count": 0, "qa_rows": []}), encoding="utf-8")
    issue_file.write_text(json.dumps({"run_id": run_id, "issues": []}), encoding="utf-8")
    manifest = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "status": "success",
        "verify_mode": "full",
        "target_lang": "en-US",
        "issue_file": str(issue_file),
        "started_at": "2026-03-27T01:00:00+00:00",
        "stages": [
            {"name": "Connectivity", "status": "pass", "required": True, "files": [{"path": str(log_file), "required": True}]}
        ],
        "artifacts": {"smoke_verify_log": str(log_file), "smoke_final_csv": str(final_csv)},
        "stage_artifacts": {"smoke_verify_log": str(log_file), "final_csv": str(final_csv)},
    }
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return manifest_path


def _http_json(base_url: str, path: str, *, method: str = "GET", payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        base_url + path,
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


class _DummyLauncher:
    def __init__(self):
        self.calls = []
        self.env_provider = lambda: {}

    def launch_run(self, input_path: str, target_lang: str, verify_mode: str):
        self.calls.append((input_path, target_lang, verify_mode))
        return PendingRunView(
            run_id="ui_run_started",
            run_dir="D:/tmp/ui_run_started",
            status="running",
            pid=4321,
            started_at="2026-03-27T01:15:00+00:00",
            command=["python", "scripts/run_smoke_pipeline.py"],
            input_csv=input_path,
            target_lang=target_lang,
            verify_mode=verify_mode,
        )

    def list_pending_runs(self):
        return []

    def get_pending_run(self, run_id: str):
        return None


def _seed_llm_ready(repo_root: Path) -> None:
    credential_path = repo_root / "tmp_llm_credentials.env"
    credential_path.write_text("LLM_API_KEY=test-secret-key\n", encoding="utf-8")
    fingerprint = llm_setup._config_fingerprint(
        "https://example.invalid/v1",
        "gpt-4.1-mini",
        llm_setup._api_key_digest("test-secret-key"),
    )
    payload = {
        "base_url": "https://example.invalid/v1",
        "model": "gpt-4.1-mini",
        "credential_path": str(credential_path),
        "credential_source": "saved_file",
        "last_test_status": "pass",
        "last_test_at": "2026-04-09T10:00:00+00:00",
        "last_test_message": "Connection verified. Translation launch is now unlocked.",
        "last_test_model": "gpt-4.1-mini",
        "last_test_latency_ms": 42,
        "verified_fingerprint": fingerprint,
        "updated_at": "2026-04-09T10:00:00+00:00",
    }
    settings_path = repo_root / "data" / "operator_ui_settings" / "llm_setup.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


@pytest.fixture()
def live_server(tmp_path):
    _write_run_fixture(tmp_path, "ui_run_server")
    _seed_llm_ready(tmp_path)
    app = server.OperatorUIApp(repo_root=tmp_path, launcher=_DummyLauncher())
    httpd = server.build_http_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def test_get_runs_and_run_detail_endpoints(live_server):
    status, payload = _http_json(live_server, "/api/runs?limit=5")
    assert status == 200
    assert payload["runs"][0]["run_id"] == "ui_run_server"

    status, detail = _http_json(live_server, "/api/runs/ui_run_server")
    assert status == 200
    assert detail["run"]["run_id"] == "ui_run_server"
    assert detail["run"]["verify"]["status"] == "PASS"


def test_post_run_and_artifact_preview_endpoints(live_server):
    status, launched = _http_json(
        live_server,
        "/api/runs",
        method="POST",
        payload={"input": "fixtures/input.csv", "target_lang": "en-US", "verify_mode": "preflight"},
    )
    assert status == 202
    assert launched["run"]["run_id"] == "ui_run_started"

    status, artifact = _http_json(live_server, "/api/runs/ui_run_server/artifacts/smoke_verify_log")
    assert status == 200
    assert artifact["artifact"]["key"] == "smoke_verify_log"
    assert "returncode" in artifact["artifact"]["content"]


def test_invalid_artifact_key_returns_404(live_server):
    request = urllib.request.Request(live_server + "/api/runs/ui_run_server/artifacts/not_allowed", method="GET")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(request)

    assert exc_info.value.code == 404


def test_invalid_runs_limit_returns_400(live_server):
    request = urllib.request.Request(live_server + "/api/runs?limit=abc", method="GET")
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(request)

    assert exc_info.value.code == 400


def test_llm_setup_endpoints_and_run_gate(tmp_path, monkeypatch):
    _write_run_fixture(tmp_path, "ui_run_server")

    class _GateLauncher(_DummyLauncher):
        pass

    launcher = _GateLauncher()
    app = server.OperatorUIApp(repo_root=tmp_path, launcher=launcher)
    httpd = server.build_http_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address
    base_url = f"http://{host}:{port}"

    class _FakeResult:
        text = "PONG"
        latency_ms = 37
        model = "test-gate-model"

    class _FakeClient:
        def __init__(self, base_url=None, api_key=None, model=None, **_kwargs):
            self.base_url = base_url
            self.api_key = api_key
            self.model = model

        def chat(self, *_args, **_kwargs):
            return _FakeResult()

    monkeypatch.setattr("scripts.operator_ui_llm.LLMClient", _FakeClient)
    monkeypatch.setattr("scripts.operator_ui_llm._default_credential_path", lambda: tmp_path / ".llm_credentials")

    try:
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _http_json(
                base_url,
                "/api/runs",
                method="POST",
                payload={"input": "fixtures/input.csv", "target_lang": "en-US", "verify_mode": "preflight"},
            )
        assert exc_info.value.code == 412

        status, current = _http_json(base_url, "/api/llm/config")
        assert status == 200
        assert current["llm"]["launch_ready"] is False

        status, saved = _http_json(
            base_url,
            "/api/llm/config",
            method="POST",
            payload={"base_url": "https://example.invalid/v1", "api_key": "secret-test-key", "model": "gpt-4.1-mini"},
        )
        assert status == 200
        assert saved["llm"]["has_api_key"] is True
        assert saved["llm"]["launch_ready"] is False
        assert saved["llm"]["api_key_masked"].endswith("t-key"[-4:])

        status, tested = _http_json(base_url, "/api/llm/test", method="POST", payload={})
        assert status == 200
        assert tested["llm"]["launch_ready"] is True
        assert tested["llm"]["last_test_status"] == "pass"

        status, launched = _http_json(
            base_url,
            "/api/runs",
            method="POST",
            payload={"input": "fixtures/input.csv", "target_lang": "en-US", "verify_mode": "preflight"},
        )
        assert status == 202
        assert launched["run"]["run_id"] == "ui_run_started"
        assert launcher.env_provider()["LLM_BASE_URL"] == "https://example.invalid/v1"
        assert launcher.env_provider()["LLM_MODEL"] == "gpt-4.1-mini"
        assert launcher.env_provider()["LLM_API_KEY_FILE"].endswith(".llm_credentials")
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def test_server_script_entrypoint_supports_cli_help():
    repo_root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "scripts/operator_ui_server.py", "--help"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=20,
        check=False,
    )

    assert result.returncode == 0
    assert "Run the operator UI server" in result.stdout
