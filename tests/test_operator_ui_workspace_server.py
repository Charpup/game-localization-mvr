from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import scripts.operator_ui_server as server


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _write_workspace_run_fixture(base_dir: Path, run_id: str) -> Path:
    run_dir = base_dir / "data" / "operator_ui_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    verify_log = run_dir / "99_smoke_verify.log"
    verify_log.write_text("returncode: 0\n", encoding="utf-8")
    verify_report = run_dir / f"smoke_verify_{run_id}.json"
    verify_report.write_text(json.dumps({"run_id": run_id, "status": "PASS", "overall": "PASS"}), encoding="utf-8")
    issue_file = run_dir / "smoke_issues.json"
    issue_file.write_text(json.dumps({"run_id": run_id, "issues": []}), encoding="utf-8")
    _write_jsonl(
        run_dir / "smoke_review_tickets.jsonl",
        [
            {
                "ticket_id": f"ticket:manual_review:{run_id}:manual_review",
                "task_id": f"manual_review:{run_id}",
                "string_id": run_id,
                "target_locale": "ru-RU",
                "ticket_type": "manual_review",
                "priority": "P1",
                "review_owner": "human-linguist",
                "review_status": "pending",
                "review_source": "manual_review",
                "queue_reason": "needs manual review",
                "current_target": "Привет",
                "reason_codes": ["STYLE_CONTRACT_CHANGED"],
                "content_class": "general",
                "risk_level": "high",
                "created_at": "2026-03-28T00:00:00+00:00",
                "source_artifacts": {"review_queue": str(run_dir / "smoke_review_queue.csv")},
            }
        ],
    )
    _write_jsonl(run_dir / "smoke_review_feedback_log.jsonl", [])
    _write_json(
        run_dir / "smoke_language_governance_kpi.json",
        {
            "generated_at": "2026-03-28T00:30:00+00:00",
            "scope": {"run_id": run_id},
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
            "metrics_sources": {},
        },
    )
    manifest = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "status": "warn",
        "overall_status": "warn",
        "verify_mode": "full",
        "target_lang": "ru-RU",
        "issue_file": str(issue_file),
        "started_at": "2026-03-28T01:00:00+00:00",
        "runtime_governance": {"passed": True},
        "stages": [
            {"name": "Connectivity", "status": "pass", "required": True, "files": [{"path": str(verify_log), "required": True}]}
        ],
        "artifacts": {
            "smoke_verify_log": str(verify_log),
            "smoke_review_tickets_jsonl": str(run_dir / "smoke_review_tickets.jsonl"),
            "smoke_feedback_log_jsonl": str(run_dir / "smoke_review_feedback_log.jsonl"),
            "smoke_governance_kpi_json": str(run_dir / "smoke_language_governance_kpi.json"),
        },
    }
    _write_json(run_dir / "run_manifest.json", manifest)
    return run_dir


def _http_json(base_url: str, path: str, *, method: str = "GET"):
    request = urllib.request.Request(base_url + path, method=method)
    with urllib.request.urlopen(request) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


@pytest.fixture()
def live_workspace_server(tmp_path):
    _write_workspace_run_fixture(tmp_path, "workspace_server_run")
    app = server.OperatorUIApp(repo_root=tmp_path)
    httpd = server.build_http_server("127.0.0.1", 0, app)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    host, port = httpd.server_address
    try:
        yield f"http://{host}:{port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


def test_workspace_endpoints_return_overview_cards_and_run_detail(live_workspace_server):
    status, overview = _http_json(live_workspace_server, "/api/workspace/overview?limit_runs=5")
    assert status == 200
    assert overview["overview"]["open_card_count"] >= 1

    status, cards = _http_json(live_workspace_server, "/api/workspace/cards?status=open&card_type=review_ticket&priority=P1&target_locale=ru-RU&limit=5")
    assert status == 200
    assert len(cards["cards"]) == 1
    assert cards["cards"][0]["run_id"] == "workspace_server_run"

    status, detail = _http_json(live_workspace_server, "/api/workspace/runs/workspace_server_run")
    assert status == 200
    assert detail["workspace"]["run_id"] == "workspace_server_run"
    assert detail["workspace"]["review_workload"]["pending_review_tickets"] == 1


def test_workspace_invalid_filters_and_unknown_run_fail_closed(live_workspace_server):
    for path in [
        "/api/workspace/overview?limit_runs=abc",
        "/api/workspace/cards?status=todo",
        "/api/workspace/cards?priority=P9",
        "/api/workspace/cards?limit=bad",
        "/api/workspace/runs/not_real",
    ]:
        request = urllib.request.Request(live_workspace_server + path, method="GET")
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(request)

