from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest


def _write_repo_run_fixture(repo_root: Path, run_id: str) -> Path:
    run_dir = repo_root / "data" / "operator_ui_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    verify_log = run_dir / "99_smoke_verify.log"
    verify_log.write_text("returncode: 0\n---- STDOUT ----\nPASS\n", encoding="utf-8")
    verify_report = run_dir / f"smoke_verify_{run_id}.json"
    verify_report.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "status": "PASS",
                "overall": "PASS",
                "issue_count": 0,
                "qa_rows": ["Hard QA: total_errors=0"],
            }
        ),
        encoding="utf-8",
    )
    issue_file = run_dir / "smoke_issues.json"
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
            {"name": "Connectivity", "status": "pass", "required": True, "files": [{"path": str(verify_log), "required": True}]},
            {"name": "Smoke Verify", "status": "pass", "required": True, "files": [{"path": str(verify_log), "required": True}]},
        ],
        "artifacts": {"smoke_verify_log": str(verify_log)},
        "stage_artifacts": {"smoke_verify_log": str(verify_log)},
    }
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return run_dir


def _write_launch_input_fixture(repo_root: Path) -> Path:
    input_path = repo_root / "data" / "operator_ui_runs" / "phase5_acceptance_gate_input.csv"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text("string_id,source_zh\nui-1,你好\n", encoding="utf-8")
    return input_path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http_json(base_url: str, path: str, *, method: str = "GET", payload: dict | None = None, raw_body: bytes | None = None):
    if raw_body is not None:
        data = raw_body
    elif payload is None:
        data = None
    else:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(base_url + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _wait_for_http_ready(base_url: str, process: subprocess.Popen[str]) -> str:
    last_error = None
    for _ in range(50):
        if process.poll() is not None:
            break
        try:
            with urllib.request.urlopen(base_url + "/", timeout=5) as response:
                return response.read().decode("utf-8")
        except Exception as exc:  # pragma: no cover - timing-dependent startup path
            last_error = exc
            time.sleep(0.2)

    stdout = process.stdout.read() if process.stdout else ""
    stderr = process.stderr.read() if process.stderr else ""
    raise AssertionError(
        f"operator_ui_server.py failed to serve '/'. returncode={process.poll()} last_error={last_error!r}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    )


def test_phase5_acceptance_gate_real_entrypoint_and_http_contracts():
    repo_root = Path(__file__).resolve().parents[1]
    run_id = "phase5_acceptance_gate_fixture"
    run_dir = _write_repo_run_fixture(repo_root, run_id)
    input_csv = _write_launch_input_fixture(repo_root)
    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    launched_pid = None
    env = os.environ.copy()
    env.update(
        {
            "LLM_BASE_URL": "http://10.255.255.1/v1",
            "LLM_API_KEY": "acceptance-dummy-key",
            "LLM_MODEL": "gpt-4.1-mini",
        }
    )
    process = subprocess.Popen(
        [sys.executable, "scripts/operator_ui_server.py", "--host", "127.0.0.1", "--port", str(port)],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    try:
        html = _wait_for_http_ready(base_url, process)
        assert "代表性 Smoke Run" in html
        assert "最近 Run" in html
        assert "验证摘要" in html
        assert "问题摘要" in html
        assert "日志、报告与清单" in html

        with urllib.request.urlopen(base_url + "/app.js", timeout=10) as response:
            assert response.status == 200
            assert "/api/runs" in response.read().decode("utf-8")

        status, runs = _http_json(base_url, "/api/runs?limit=12")
        assert status == 200
        fixture = next(run for run in runs["runs"] if run["run_id"] == run_id)
        assert fixture["overall_status"] == "pass"

        status, detail = _http_json(base_url, f"/api/runs/{run_id}")
        assert status == 200
        assert detail["run"]["verify"]["status"] == "PASS"
        assert detail["run"]["issue_summary"]["total"] == 0
        assert "smoke_verify_log" in detail["run"]["allowed_artifact_keys"]

        status, artifact = _http_json(base_url, f"/api/runs/{run_id}/artifacts/smoke_verify_log")
        assert status == 200
        assert "PASS" in artifact["artifact"]["content"]

        for path in ["/api/runs/not-a-real-run", f"/api/runs/{run_id}/artifacts/not_allowed"]:
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(urllib.request.Request(base_url + path, method="GET"), timeout=10)
            assert exc_info.value.code == 404

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(
                urllib.request.Request(
                    base_url + "/api/runs",
                    method="POST",
                    data=b"{bad json",
                    headers={"Content-Type": "application/json"},
                ),
                timeout=10,
            )
        assert exc_info.value.code == 400

        with pytest.raises(urllib.error.HTTPError) as exc_info:
            _http_json(base_url, "/api/runs", method="POST", payload={"input": "only-one-field.csv"})
        assert exc_info.value.code == 400

        status, launched = _http_json(
            base_url,
            "/api/runs",
            method="POST",
            payload={
                "input": str(input_csv),
                "target_lang": "en-US",
                "verify_mode": "preflight",
                "extra_flag": "--not-allowed",
            },
        )
        assert status == 202
        launched_pid = launched["run"]["pid"]
        assert launched["run"]["status"] == "running"
        assert "extra_flag" not in launched["run"]
        assert "data\\operator_ui_runs" in launched["run"]["run_dir"]
        assert "--not-allowed" not in " ".join(launched["run"]["command"])

        status, pending_detail = _http_json(base_url, f"/api/runs/{launched['run']['run_id']}")
        assert status == 200
        assert pending_detail["run"]["pending"] is True
        assert pending_detail["run"]["overall_status"] == "running"
    finally:
        if launched_pid:
            try:
                os.kill(int(launched_pid), signal.SIGTERM)
            except OSError:
                pass
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if input_csv.exists():
            input_csv.unlink()
        if run_dir.exists():
            for path in sorted(run_dir.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
            run_dir.rmdir()
