from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import operator_control_plane


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _sample_run_dir(tmp_path: Path, *, with_tickets: bool = True, with_kpi_drift: bool = True) -> Path:
    run_dir = tmp_path / "smoke_run"
    run_dir.mkdir(parents=True, exist_ok=True)
    run_id = "smoke_run_demo"
    manifest = {
        "run_id": run_id,
        "status": "warn",
        "overall_status": "warn",
        "target_lang": "ru-RU",
        "runtime_governance": {"passed": True, "asset_statuses": {"data/style_profile.yaml": {"status": "approved"}}},
        "artifacts": {
            "smoke_review_tickets_jsonl": str(run_dir / "smoke_review_tickets.jsonl"),
            "smoke_feedback_log_jsonl": str(run_dir / "smoke_review_feedback_log.jsonl"),
            "smoke_governance_kpi_json": str(run_dir / "smoke_language_governance_kpi.json"),
        },
    }
    verify_payload = {"status": "PASS", "overall": "PASS"}
    kpi_payload = {
        "runtime_summary": {"overall_status": "running" if with_kpi_drift else "pass"},
        "review_summary": {
            "total_review_tickets": 1 if with_tickets else 0,
            "pending_review_tickets": 1 if with_tickets else 0,
            "manual_intervention_rate": 1.0 if with_tickets else 0.0,
            "feedback_closure_rate": 0.0,
        },
        "lifecycle_summary": {
            "registry_path": "workflow/lifecycle_registry.yaml",
            "checked_assets": {"data/style_profile.yaml": {"status": "approved"}},
            "deprecated_asset_usage_count": 0,
        },
    }
    tickets = []
    if with_tickets:
        tickets.append(
            {
                "ticket_id": "ticket:manual_review:s1:manual_review",
                "task_id": "manual_review:s1",
                "string_id": "s1",
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
                "created_at": "2026-03-26T00:00:00+00:00",
                "source_artifacts": {"review_queue": str(run_dir / "smoke_review_queue.csv")},
            }
        )
    _write_json(run_dir / "run_manifest.json", manifest)
    _write_json(run_dir / "smoke_verify_demo.json", verify_payload)
    _write_json(run_dir / "smoke_language_governance_kpi.json", kpi_payload)
    _write_jsonl(run_dir / "smoke_review_tickets.jsonl", tickets)
    _write_jsonl(run_dir / "smoke_review_feedback_log.jsonl", [])
    return run_dir


def test_operator_control_plane_builds_cards_and_summary(tmp_path):
    run_dir = _sample_run_dir(tmp_path, with_tickets=True, with_kpi_drift=True)

    result = operator_control_plane.build_operator_artifacts(run_dir=str(run_dir))

    cards = result["cards"]
    report = result["report"]
    assert any(card["card_type"] == "review_ticket" for card in cards)
    assert any(card["card_type"] == "governance_drift" for card in cards)
    assert any(card["card_type"] == "kpi_watch" for card in cards)
    assert any(card["card_type"] == "decision_required" for card in cards)
    assert report["overall_runtime_health"]["status"] == "pass"
    assert report["governance_drift_summary"]["drift_count"] == 1
    assert any(ref.endswith("ADR-0003-operator-control-plane-operating-model.md") for ref in report["adr_refs"])
    assert report["artifact_refs"]["manifest"].endswith("run_manifest.json")
    assert any(ref.endswith("smoke_language_governance_kpi.json") for ref in report["evidence_refs"])
    assert Path(result["cards_path"]).exists()
    assert Path(result["summary_json_path"]).exists()
    assert Path(result["summary_md_path"]).exists()


def test_operator_control_plane_handles_empty_review_queue_and_feedback_log(tmp_path):
    run_dir = _sample_run_dir(tmp_path, with_tickets=False, with_kpi_drift=False)

    result = operator_control_plane.build_operator_artifacts(run_dir=str(run_dir))

    cards = result["cards"]
    report = result["report"]
    assert all(card["card_type"] != "review_ticket" for card in cards)
    assert report["open_review_workload"]["total_review_tickets"] == 0
    assert report["open_review_workload"]["feedback_entries"] == 0


def test_operator_control_plane_inspect_returns_matching_card(tmp_path, capsys):
    run_dir = _sample_run_dir(tmp_path, with_tickets=True, with_kpi_drift=True)
    result = operator_control_plane.build_operator_artifacts(run_dir=str(run_dir))
    decision_card = next(card for card in result["cards"] if card["card_type"] == "decision_required")

    exit_code = operator_control_plane.main(["inspect", "--run-dir", str(run_dir), "--card-id", decision_card["card_id"]])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["card_id"] == decision_card["card_id"]


def test_operator_control_plane_localizes_windows_absolute_artifact_paths(tmp_path):
    run_dir = _sample_run_dir(tmp_path, with_tickets=True, with_kpi_drift=True)
    manifest_path = run_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"]["smoke_review_tickets_jsonl"] = r"D:\archived\smoke_review_tickets.jsonl"
    manifest["artifacts"]["smoke_feedback_log_jsonl"] = r"D:\archived\smoke_review_feedback_log.jsonl"
    manifest["artifacts"]["smoke_governance_kpi_json"] = r"D:\archived\smoke_language_governance_kpi.json"
    _write_json(manifest_path, manifest)

    result = operator_control_plane.build_operator_artifacts(run_dir=str(run_dir))

    report = result["report"]
    assert report["open_review_workload"]["total_review_tickets"] == 1
    assert report["artifact_refs"]["review_tickets"].endswith("smoke_review_tickets.jsonl")
    assert any(card["card_type"] == "review_ticket" for card in result["cards"])


def test_operator_control_plane_can_derive_without_persisting_operator_artifacts(tmp_path):
    run_dir = _sample_run_dir(tmp_path, with_tickets=True, with_kpi_drift=True)
    expected_cards_path = operator_control_plane.REPO_ROOT / "data" / "operator_cards" / "smoke_run_demo" / "operator_cards.jsonl"
    expected_summary_path = operator_control_plane.REPO_ROOT / "data" / "operator_reports" / "smoke_run_demo" / "operator_summary.json"
    cards_exists_before = expected_cards_path.exists()
    summary_exists_before = expected_summary_path.exists()
    cards_mtime_before = expected_cards_path.stat().st_mtime if cards_exists_before else None
    summary_mtime_before = expected_summary_path.stat().st_mtime if summary_exists_before else None

    result = operator_control_plane.derive_operator_artifacts(run_dir=str(run_dir))

    assert any(card["card_type"] == "review_ticket" for card in result["cards"])
    assert result["report"]["open_operator_cards"] >= 1
    assert Path(result["cards_path"]) == expected_cards_path
    assert Path(result["summary_json_path"]) == expected_summary_path
    assert expected_cards_path.exists() is cards_exists_before
    assert expected_summary_path.exists() is summary_exists_before
    if cards_exists_before:
        assert expected_cards_path.stat().st_mtime == cards_mtime_before
    if summary_exists_before:
        assert expected_summary_path.stat().st_mtime == summary_mtime_before
