from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import scripts.operator_control_plane as operator_control_plane


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _write_workspace_run_fixture(
    repo_root: Path,
    run_id: str,
    *,
    target_lang: str,
    runtime_status: str,
    verify_status: str,
    with_tickets: bool,
    with_kpi_drift: bool,
    started_at: str,
) -> Path:
    run_dir = repo_root / "data" / "operator_ui_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    verify_log = run_dir / "99_smoke_verify.log"
    verify_log.write_text(f"returncode: 0\n---- STDOUT ----\n{verify_status}\n", encoding="utf-8")
    verify_report = run_dir / f"smoke_verify_{run_id}.json"
    _write_json(
        verify_report,
        {
            "run_id": run_id,
            "status": verify_status,
            "overall": verify_status,
            "issue_count": 1 if verify_status == "WARN" else 0,
            "qa_rows": ["Hard QA: total_errors=0"],
        },
    )
    issue_file = run_dir / "smoke_issues.json"
    _write_json(
        issue_file,
        {
            "run_id": run_id,
            "issues": (
                [{"stage": "smoke_verify", "severity": "P2", "error_code": "VERIFY_QA_WARNING"}]
                if verify_status == "WARN"
                else []
            ),
        },
    )

    if with_tickets:
        _write_jsonl(
            run_dir / "smoke_review_tickets.jsonl",
            [
                {
                    "ticket_id": f"ticket:manual_review:{run_id}:manual_review",
                    "task_id": f"manual_review:{run_id}",
                    "string_id": run_id,
                    "target_locale": target_lang,
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
                    "created_at": "2026-03-28T08:00:00+00:00",
                    "source_artifacts": {"review_queue": str(run_dir / "smoke_review_queue.csv")},
                }
            ],
        )
        _write_jsonl(run_dir / "smoke_review_feedback_log.jsonl", [])

    _write_json(
        run_dir / "smoke_language_governance_kpi.json",
        {
            "generated_at": "2026-03-28T08:05:00+00:00",
            "scope": {"run_id": run_id},
            "runtime_summary": {
                "overall_status": "running" if with_kpi_drift else runtime_status,
                "total_tasks": 1,
                "updated_count": 1,
                "review_handoff_count": 1 if with_tickets else 0,
            },
            "review_summary": {
                "total_review_tickets": 1 if with_tickets else 0,
                "pending_review_tickets": 1 if with_tickets else 0,
                "manual_intervention_rate": 1.0 if with_tickets else 0.0,
                "feedback_entries": 0,
                "feedback_closure_rate": 0.0,
            },
            "lifecycle_summary": {
                "registry_path": "workflow/lifecycle_registry.yaml",
                "checked_assets": {"data/style_profile.yaml": {"status": "approved"}},
                "deprecated_asset_usage_count": 0,
            },
            "metrics_sources": {"run_manifest": str(run_dir / "run_manifest.json")},
        },
    )

    manifest = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "status": runtime_status,
        "overall_status": runtime_status,
        "verify_mode": "full",
        "target_lang": target_lang,
        "issue_file": str(issue_file),
        "started_at": started_at,
        "runtime_governance": {"passed": True},
        "row_checks": {"input_rows": 1, "translate_rows": 1, "final_rows": 1, "translate_delta": 0, "final_delta": 0},
        "stages": [
            {"name": "Connectivity", "status": "pass", "required": True, "files": [{"path": str(verify_log), "required": True}]},
            {"name": "Smoke Verify", "status": runtime_status, "required": True, "files": [{"path": str(verify_log), "required": True}]},
        ],
        "artifacts": {
            "smoke_verify_log": str(verify_log),
            "smoke_governance_kpi_json": str(run_dir / "smoke_language_governance_kpi.json"),
        },
    }
    if with_tickets:
        manifest["artifacts"]["smoke_review_tickets_jsonl"] = str(run_dir / "smoke_review_tickets.jsonl")
        manifest["artifacts"]["smoke_feedback_log_jsonl"] = str(run_dir / "smoke_review_feedback_log.jsonl")
    _write_json(run_dir / "run_manifest.json", manifest)
    return run_dir


def _persist_closed_operator_artifacts(run_dir: Path) -> None:
    result = operator_control_plane.derive_operator_artifacts(run_dir=str(run_dir))
    closed_cards = []
    for card in result["cards"]:
        updated = dict(card)
        updated["status"] = "closed"
        if updated["card_type"] == "decision_required":
            updated["summary"] = "Persisted operator summary shows this run is already triaged."
        closed_cards.append(updated)
    report = dict(result["report"])
    report["open_operator_cards"] = 0
    report["next_recommended_actions"] = ["archive run evidence"]
    operator_control_plane.persist_operator_artifacts(
        {
            **result,
            "cards": closed_cards,
            "report": report,
        }
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http_json(base_url: str, path: str):
    with urllib.request.urlopen(base_url + path, timeout=20) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def _wait_for_http_ready(base_url: str, process: subprocess.Popen[str]) -> None:
    last_error = None
    for _ in range(50):
        if process.poll() is not None:
            break
        try:
            with urllib.request.urlopen(base_url + "/", timeout=5):
                return
        except Exception as exc:  # pragma: no cover - timing-dependent startup path
            last_error = exc
            time.sleep(0.2)
    stdout = process.stdout.read() if process.stdout else ""
    stderr = process.stderr.read() if process.stderr else ""
    raise AssertionError(
        f"operator_ui_server.py failed to serve '/'. returncode={process.poll()} last_error={last_error!r}\nSTDOUT:\n{stdout}\nSTDERR:\n{stderr}"
    )


def test_phase6_acceptance_gate_real_workspace_http_and_side_effect_free_reads():
    repo_root = Path(__file__).resolve().parents[1]
    derived_run_id = "phase6_acceptance_derived"
    persisted_run_id = "phase6_acceptance_persisted"
    derived_run_dir = _write_workspace_run_fixture(
        repo_root,
        derived_run_id,
        target_lang="en-US",
        runtime_status="warn",
        verify_status="WARN",
        with_tickets=True,
        with_kpi_drift=True,
        started_at="2026-03-28T08:30:00+00:00",
    )
    persisted_run_dir = _write_workspace_run_fixture(
        repo_root,
        persisted_run_id,
        target_lang="ja-JP",
        runtime_status="pass",
        verify_status="PASS",
        with_tickets=True,
        with_kpi_drift=False,
        started_at="2026-03-28T08:35:00+00:00",
    )
    _persist_closed_operator_artifacts(persisted_run_dir)

    derived_cards_dir = repo_root / "data" / "operator_cards" / derived_run_id
    derived_reports_dir = repo_root / "data" / "operator_reports" / derived_run_id
    persisted_cards_dir = repo_root / "data" / "operator_cards" / persisted_run_id
    persisted_reports_dir = repo_root / "data" / "operator_reports" / persisted_run_id

    port = _free_port()
    base_url = f"http://127.0.0.1:{port}"
    process = subprocess.Popen(
        [sys.executable, "scripts/operator_ui_server.py", "--host", "127.0.0.1", "--port", str(port)],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=os.environ.copy(),
    )

    try:
        _wait_for_http_ready(base_url, process)

        html = urllib.request.urlopen(base_url + "/", timeout=10).read().decode("utf-8")
        assert "运行态 Shell" in html
        assert "运营工作台" in html
        assert "运营收件箱" in html
        assert "决策上下文" in html
        assert "复核负载" in html
        assert "KPI 快照" in html
        assert "治理漂移" in html
        assert 'id="lang-zh"' in html
        assert 'id="lang-en"' in html
        assert "中文" in html
        assert "EN" in html

        app_js = urllib.request.urlopen(base_url + "/app.js", timeout=10).read().decode("utf-8")
        assert "/api/workspace/overview" in app_js
        assert "/api/workspace/cards" in app_js
        assert "/api/workspace/runs/" in app_js
        assert "recommended_actions" in app_js
        assert "artifact_refs" in app_js
        assert "evidence_refs" in app_js
        assert "adr_refs" in app_js
        assert "localStorage" in app_js
        assert "LANG_STORAGE_KEY" in app_js

        status, overview = _http_json(base_url, "/api/workspace/overview?limit_runs=10")
        assert status == 200
        assert overview["overview"]["open_card_count"] >= 1
        assert overview["overview"]["open_case_count"] >= 1
        assert overview["overview"]["case_counts_by_lane"]["review"] >= 1
        assert overview["overview"]["case_counts_by_lane"]["done"] >= 1
        recent_run_ids = {run["run_id"] for run in overview["overview"]["recent_runs"]}
        assert derived_run_id in recent_run_ids
        assert persisted_run_id in recent_run_ids

        status, cards = _http_json(base_url, "/api/workspace/cards?status=open&limit=20")
        assert status == 200
        open_run_ids = {card["run_id"] for card in cards["cards"]}
        assert derived_run_id in open_run_ids
        assert persisted_run_id not in open_run_ids

        status, cases = _http_json(base_url, "/api/workspace/cases?status=open&limit=20")
        assert status == 200
        open_case_run_ids = {case["run_id"] for case in cases["cases"]}
        assert derived_run_id in open_case_run_ids
        assert persisted_run_id not in open_case_run_ids

        status, done_cases = _http_json(base_url, "/api/workspace/cases?status=all&lane=done&limit=20")
        assert status == 200
        done_case_run_ids = {case["run_id"] for case in done_cases["cases"]}
        assert persisted_run_id in done_case_run_ids

        status, derived_workspace = _http_json(base_url, f"/api/workspace/runs/{derived_run_id}")
        assert status == 200
        assert derived_workspace["workspace"]["run_id"] == derived_run_id
        assert derived_workspace["workspace"]["review_workload"]["pending_review_tickets"] == 1
        assert derived_workspace["workspace"]["governance_drift"]["drift_count"] == 1
        assert derived_workspace["workspace"]["decision_context"]["card_id"]
        assert not derived_cards_dir.exists()
        assert not derived_reports_dir.exists()

        status, persisted_workspace = _http_json(base_url, f"/api/workspace/runs/{persisted_run_id}")
        assert status == 200
        assert persisted_workspace["workspace"]["run_id"] == persisted_run_id
        assert all(card["status"] == "closed" for card in persisted_workspace["workspace"]["cards"])
        assert persisted_cards_dir.exists()
        assert persisted_reports_dir.exists()

        status, runtime_detail = _http_json(base_url, f"/api/runs/{derived_run_id}")
        assert status == 200
        assert runtime_detail["run"]["overall_status"] == "warn"
        assert "smoke_verify_log" in runtime_detail["run"]["allowed_artifact_keys"]

        status, artifact = _http_json(base_url, f"/api/runs/{derived_run_id}/artifacts/smoke_verify_log")
        assert status == 200
        assert "WARN" in artifact["artifact"]["content"]

        for path, code in [
            ("/api/workspace/overview?limit_runs=bad", 400),
            ("/api/workspace/cards?status=todo", 400),
            ("/api/workspace/cards?priority=P9", 400),
            ("/api/workspace/cases?status=closed", 400),
            ("/api/workspace/cases?lane=triage", 400),
            ("/api/workspace/cases?limit=bad", 400),
            ("/api/workspace/runs/not-a-real-run", 404),
        ]:
            request = urllib.request.Request(base_url + path, method="GET")
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen(request, timeout=10)
            assert exc_info.value.code == code
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for path in [derived_run_dir, persisted_run_dir, derived_cards_dir, derived_reports_dir, persisted_cards_dir, persisted_reports_dir]:
            if path.exists():
                shutil.rmtree(path)
