#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Seed deterministic Phase 5 + 6 manual UI acceptance fixtures."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import operator_control_plane


DERIVED_RUN_ID = "phase6_manual_uat_derived"
PERSISTED_RUN_ID = "phase6_manual_uat_persisted"


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _reset_seed_paths(repo_root: Path, run_id: str) -> None:
    for path in [
        repo_root / "data" / "operator_ui_runs" / run_id,
        repo_root / "data" / "operator_cards" / run_id,
        repo_root / "data" / "operator_reports" / run_id,
    ]:
        if path.exists():
            shutil.rmtree(path)


def _write_run_fixture(
    repo_root: Path,
    run_id: str,
    *,
    target_lang: str,
    runtime_status: str,
    verify_status: str,
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
                "review_handoff_count": 1,
            },
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
        },
    )

    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "status": runtime_status,
            "overall_status": runtime_status,
            "verify_mode": "full",
            "target_lang": target_lang,
            "issue_file": str(issue_file),
            "started_at": started_at,
            "runtime_governance": {"passed": True},
            "row_checks": {
                "input_rows": 1,
                "translate_rows": 1,
                "final_rows": 1,
                "translate_delta": 0,
                "final_delta": 0,
            },
            "stages": [
                {
                    "name": "Connectivity",
                    "status": "pass",
                    "required": True,
                    "files": [{"path": str(verify_log), "required": True}],
                },
                {
                    "name": "Smoke Verify",
                    "status": runtime_status,
                    "required": True,
                    "files": [{"path": str(verify_log), "required": True}],
                },
            ],
            "artifacts": {
                "smoke_verify_log": str(verify_log),
                "smoke_review_tickets_jsonl": str(run_dir / "smoke_review_tickets.jsonl"),
                "smoke_feedback_log_jsonl": str(run_dir / "smoke_review_feedback_log.jsonl"),
                "smoke_governance_kpi_json": str(run_dir / "smoke_language_governance_kpi.json"),
            },
        },
    )
    return run_dir


def _persist_closed_operator_artifacts(repo_root: Path, run_dir: Path) -> None:
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
    adjusted_result = {
        **result,
        "cards_path": str(repo_root / "data" / "operator_cards" / run_dir.name / "operator_cards.jsonl"),
        "summary_json_path": str(repo_root / "data" / "operator_reports" / run_dir.name / "operator_summary.json"),
        "summary_md_path": str(repo_root / "data" / "operator_reports" / run_dir.name / "operator_summary.md"),
        "cards": closed_cards,
        "report": report,
    }
    adjusted_result["report"]["artifact_refs"] = {
        **dict(adjusted_result["report"].get("artifact_refs", {}) or {}),
        "operator_cards": adjusted_result["cards_path"],
        "operator_summary_json": adjusted_result["summary_json_path"],
        "operator_summary_md": adjusted_result["summary_md_path"],
    }
    operator_control_plane.persist_operator_artifacts(adjusted_result)


def seed_manual_uat_fixtures(repo_root: Path | str) -> Dict[str, Any]:
    repo_root_path = Path(repo_root)
    _reset_seed_paths(repo_root_path, DERIVED_RUN_ID)
    _reset_seed_paths(repo_root_path, PERSISTED_RUN_ID)

    derived_run_dir = _write_run_fixture(
        repo_root_path,
        DERIVED_RUN_ID,
        target_lang="en-US",
        runtime_status="warn",
        verify_status="WARN",
        with_kpi_drift=True,
        started_at="2026-03-28T08:30:00+00:00",
    )
    persisted_run_dir = _write_run_fixture(
        repo_root_path,
        PERSISTED_RUN_ID,
        target_lang="ja-JP",
        runtime_status="pass",
        verify_status="PASS",
        with_kpi_drift=False,
        started_at="2026-03-28T08:35:00+00:00",
    )
    _persist_closed_operator_artifacts(repo_root_path, persisted_run_dir)

    return {
        "derived": {
            "run_id": DERIVED_RUN_ID,
            "run_dir": str(derived_run_dir),
            "expectations": {
                "workspace_cards": "open",
                "governance_drift": "visible",
                "persisted_operator_artifacts": "absent",
            },
        },
        "persisted": {
            "run_id": PERSISTED_RUN_ID,
            "run_dir": str(persisted_run_dir),
            "expectations": {
                "workspace_cards": "closed",
                "governance_drift": "empty",
                "persisted_operator_artifacts": "present",
            },
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed deterministic fixtures for Phase 5 + 6 human UI acceptance")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    payload = seed_manual_uat_fixtures(args.repo_root)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
