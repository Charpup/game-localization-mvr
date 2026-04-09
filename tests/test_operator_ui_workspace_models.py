from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import operator_control_plane
import scripts.operator_ui_models as models


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _write_workspace_run_fixture(
    base_dir: Path,
    run_id: str,
    *,
    with_tickets: bool = True,
    with_kpi: bool = True,
    with_kpi_drift: bool = True,
    started_at: str = "2026-03-28T01:00:00+00:00",
    manifest_status: str = "warn",
    verify_status: str = "PASS",
    target_lang: str = "ru-RU",
) -> Path:
    run_dir = base_dir / "data" / "operator_ui_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    verify_log = run_dir / "99_smoke_verify.log"
    verify_log.write_text("returncode: 0\n", encoding="utf-8")
    verify_report = run_dir / f"smoke_verify_{run_id}.json"
    verify_report.write_text(
        json.dumps({"run_id": run_id, "status": verify_status, "overall": verify_status}),
        encoding="utf-8",
    )
    issue_file = run_dir / "smoke_issues.json"
    issue_file.write_text(json.dumps({"run_id": run_id, "issues": []}), encoding="utf-8")

    manifest = {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "status": manifest_status,
        "overall_status": manifest_status,
        "verify_mode": "full",
        "target_lang": target_lang,
        "started_at": started_at,
        "issue_file": str(issue_file),
        "runtime_governance": {"passed": True, "asset_statuses": {"data/style_profile.yaml": {"status": "approved"}}},
        "stages": [
            {"name": "Connectivity", "status": "pass", "required": True, "files": [{"path": str(verify_log), "required": True}]},
            {"name": "Smoke Verify", "status": "warn", "required": True, "files": [{"path": str(verify_log), "required": True}]},
        ],
        "artifacts": {
            "smoke_verify_log": str(verify_log),
        },
    }

    if with_tickets:
        manifest["artifacts"]["smoke_review_tickets_jsonl"] = str(run_dir / "smoke_review_tickets.jsonl")
        manifest["artifacts"]["smoke_feedback_log_jsonl"] = str(run_dir / "smoke_review_feedback_log.jsonl")
    if with_kpi:
        manifest["artifacts"]["smoke_governance_kpi_json"] = str(run_dir / "smoke_language_governance_kpi.json")

    tickets = []
    if with_tickets:
        tickets.append(
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
                "current_target": "Привет",
                "reason_codes": ["STYLE_CONTRACT_CHANGED"],
                "content_class": "general",
                "risk_level": "high",
                "created_at": "2026-03-28T00:00:00+00:00",
                "source_artifacts": {"review_queue": str(run_dir / "smoke_review_queue.csv")},
            }
        )

    if with_tickets:
        _write_jsonl(run_dir / "smoke_review_tickets.jsonl", tickets)
        _write_jsonl(run_dir / "smoke_review_feedback_log.jsonl", [])

    if with_kpi:
        _write_json(
            run_dir / "smoke_language_governance_kpi.json",
            {
                "generated_at": "2026-03-28T00:30:00+00:00",
                "scope": {"run_id": run_id},
                "runtime_summary": {"overall_status": "running" if with_kpi_drift else "pass", "total_tasks": 1, "updated_count": 1, "review_handoff_count": len(tickets)},
                "review_summary": {
                    "total_review_tickets": len(tickets),
                    "pending_review_tickets": len(tickets),
                    "manual_intervention_rate": 1.0 if tickets else 0.0,
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

    _write_json(run_dir / "run_manifest.json", manifest)
    return run_dir


def test_load_workspace_run_detail_derives_without_persisting_operator_artifacts(tmp_path):
    run_dir = _write_workspace_run_fixture(tmp_path, "workspace_run_a", with_tickets=True, with_kpi=True, with_kpi_drift=True)

    detail = models.load_workspace_run_detail(tmp_path, "workspace_run_a")

    assert detail.run_id == "workspace_run_a"
    assert detail.review_workload["pending_review_tickets"] == 1
    assert detail.governance_drift["drift_count"] == 1
    assert any(card.card_type == "decision_required" for card in detail.cards)
    assert detail.decision_context["card_id"].startswith("card:")
    assert not (tmp_path / "data" / "operator_cards" / "workspace_run_a").exists()
    assert not (tmp_path / "data" / "operator_reports" / "workspace_run_a").exists()


def test_load_workspace_run_detail_prefers_persisted_operator_artifacts(tmp_path):
    run_dir = _write_workspace_run_fixture(tmp_path, "workspace_run_persisted", with_tickets=True, with_kpi=True, with_kpi_drift=False)
    result = operator_control_plane.derive_operator_artifacts(run_dir=str(run_dir))
    cards_path = tmp_path / "data" / "operator_cards" / "workspace_run_persisted" / "operator_cards.jsonl"
    summary_path = tmp_path / "data" / "operator_reports" / "workspace_run_persisted" / "operator_summary.json"
    rows = list(result["cards"])
    for row in rows:
        row["status"] = "closed"
    _write_jsonl(cards_path, rows)
    _write_json(summary_path, result["report"])

    detail = models.load_workspace_run_detail(tmp_path, "workspace_run_persisted")

    assert detail.operator_summary["open_operator_cards"] == result["open_card_count"]
    assert all(card.status == "closed" for card in detail.cards)


def test_load_workspace_cards_filters_and_overview_counts(tmp_path):
    _write_workspace_run_fixture(tmp_path, "workspace_run_old", with_tickets=False, with_kpi=False, started_at="2026-03-28T00:00:00+00:00")
    _write_workspace_run_fixture(tmp_path, "workspace_run_new", with_tickets=True, with_kpi=True, with_kpi_drift=True, started_at="2026-03-28T02:00:00+00:00")

    cards = models.load_workspace_cards(tmp_path, status="open", card_type="review_ticket", priority="P1", target_locale="ru-RU", limit=10)
    overview = models.load_workspace_overview(tmp_path, limit_runs=5)

    assert len(cards) == 1
    assert cards[0].run_id == "workspace_run_new"
    assert overview.open_card_count >= 1
    assert overview.runs_with_open_cards == 1
    assert overview.runs_with_drift == 1
    assert overview.open_review_tickets == 1
    assert overview.recent_runs[0].run_id == "workspace_run_new"


def test_workspace_derivation_respects_repo_root_and_counts_open_review_cards_without_kpi(tmp_path):
    _write_workspace_run_fixture(
        tmp_path,
        "workspace_run_repo_root",
        with_tickets=True,
        with_kpi=False,
        with_kpi_drift=False,
        started_at="2026-03-28T03:00:00+00:00",
    )

    detail = models.load_workspace_run_detail(tmp_path, "workspace_run_repo_root")
    overview = models.load_workspace_overview(tmp_path, limit_runs=5)

    expected_cards_path = tmp_path / "data" / "operator_cards" / "workspace_run_repo_root" / "operator_cards.jsonl"
    expected_summary_path = tmp_path / "data" / "operator_reports" / "workspace_run_repo_root" / "operator_summary.json"

    assert Path(detail.operator_summary["artifact_refs"]["operator_cards"]) == expected_cards_path
    assert Path(detail.operator_summary["artifact_refs"]["operator_summary_json"]) == expected_summary_path
    assert overview.open_review_tickets == 1


def test_load_workspace_cases_aggregates_runs_into_lanes_and_done_views(tmp_path):
    _write_workspace_run_fixture(
        tmp_path,
        "workspace_run_act",
        with_tickets=False,
        with_kpi=True,
        with_kpi_drift=False,
        started_at="2026-03-28T04:00:00+00:00",
        manifest_status="fail",
        verify_status="FAIL",
        target_lang="fr-FR",
    )
    _write_workspace_run_fixture(
        tmp_path,
        "workspace_run_review",
        with_tickets=True,
        with_kpi=True,
        with_kpi_drift=False,
        started_at="2026-03-28T03:00:00+00:00",
        target_lang="ru-RU",
    )
    _write_workspace_run_fixture(
        tmp_path,
        "workspace_run_watch",
        with_tickets=False,
        with_kpi=True,
        with_kpi_drift=True,
        started_at="2026-03-28T02:00:00+00:00",
        manifest_status="pass",
        verify_status="PASS",
        target_lang="ja-JP",
    )
    done_dir = _write_workspace_run_fixture(
        tmp_path,
        "workspace_run_done",
        with_tickets=True,
        with_kpi=True,
        with_kpi_drift=False,
        started_at="2026-03-28T01:00:00+00:00",
        manifest_status="pass",
        verify_status="PASS",
        target_lang="en-US",
    )

    result = operator_control_plane.derive_operator_artifacts(run_dir=str(done_dir))
    closed_rows = []
    for row in list(result["cards"]):
        row["status"] = "closed"
        closed_rows.append(row)

    persisted_report = dict(result["report"])
    persisted_report["open_operator_cards"] = 0
    _write_jsonl(tmp_path / "data" / "operator_cards" / "workspace_run_done" / "operator_cards.jsonl", closed_rows)
    _write_json(tmp_path / "data" / "operator_reports" / "workspace_run_done" / "operator_summary.json", persisted_report)

    open_cases = models.load_workspace_cases(tmp_path, status="open", limit=10)
    all_cases = models.load_workspace_cases(tmp_path, status="all", limit=10)
    review_cases = models.load_workspace_cases(tmp_path, status="all", lane="review", limit=10)
    locale_query_cases = models.load_workspace_cases(
        tmp_path,
        status="all",
        target_locale="fr-FR",
        query="workspace_run_act",
        limit=10,
    )
    overview = models.load_workspace_overview(tmp_path, limit_runs=10)

    assert {case.run_id for case in open_cases} == {
        "workspace_run_act",
        "workspace_run_review",
        "workspace_run_watch",
    }
    assert {case.run_id for case in all_cases} == {
        "workspace_run_act",
        "workspace_run_review",
        "workspace_run_watch",
        "workspace_run_done",
    }

    case_lanes = {case.run_id: case.lane for case in all_cases}
    persisted_flags = {case.run_id: case.has_persisted_operator_artifacts for case in all_cases}

    assert case_lanes["workspace_run_act"] == "act"
    assert case_lanes["workspace_run_review"] == "review"
    assert case_lanes["workspace_run_watch"] == "watch"
    assert case_lanes["workspace_run_done"] == "done"
    assert persisted_flags["workspace_run_done"] is True
    assert persisted_flags["workspace_run_review"] is False

    assert len(review_cases) == 1
    assert review_cases[0].run_id == "workspace_run_review"
    assert len(locale_query_cases) == 1
    assert locale_query_cases[0].run_id == "workspace_run_act"

    assert overview.open_case_count == 3
    assert overview.case_counts_by_lane["act"] == 1
    assert overview.case_counts_by_lane["review"] == 1
    assert overview.case_counts_by_lane["watch"] == 1
    assert overview.case_counts_by_lane["done"] == 1
