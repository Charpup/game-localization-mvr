from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import review_feedback_ingest
import review_governance
import style_governance_runtime


def test_runtime_governance_accepts_repo_style_profile():
    report = style_governance_runtime.evaluate_runtime_governance(
        style_profile_path="data/style_profile.yaml",
        glossary_path="glossary/compiled.yaml",
        policy_paths=["workflow/style_governance_contract.yaml"],
    )

    assert report["passed"] is True
    assert report["style_profile_path"] == "data/style_profile.yaml"
    assert report["asset_statuses"]["data/style_profile.yaml"]["status"] == "approved"


def test_runtime_governance_rejects_deprecated_lifecycle_entry(tmp_path):
    source_profile = Path(__file__).resolve().parent.parent / "data" / "style_profile.yaml"
    style_profile = tmp_path / "style_profile.yaml"
    style_profile.write_text(source_profile.read_text(encoding="utf-8"), encoding="utf-8")
    lifecycle_registry = tmp_path / "lifecycle_registry.yaml"
    lifecycle_registry.write_text(
        "\n".join(
            [
                'version: "1.0"',
                "entries:",
                '  - asset_id: "tmp-style"',
                '    asset_kind: "style_profile"',
                f'    asset_path: "{style_profile.as_posix()}"',
                '    status: "deprecated"',
                '    approval_ref: "docs/decisions/ADR-0002-skill-governance-framework.md"',
                '    required_runtime_gate: true',
                '    deprecated_by: "style-profile-next"',
            ]
        ),
        encoding="utf-8",
    )

    report = style_governance_runtime.evaluate_runtime_governance(
        style_profile_path=str(style_profile),
        lifecycle_registry_path=str(lifecycle_registry),
    )

    assert report["passed"] is False
    assert "runtime-gated asset is not approved" in " ".join(report["issues"])


def test_review_ticket_and_kpi_helpers_emit_expected_summary(tmp_path):
    review_queue_rows = [
        {
            "task_id": "manual_review:s1",
            "string_id": "s1",
            "review_owner": "human-linguist",
            "review_status": "pending",
            "review_source": "initial_manual_review",
            "queue_reason": "needs human review",
            "current_target": "Current target",
            "reason_codes": json.dumps(["STYLE_CONTRACT_CHANGED"], ensure_ascii=False),
        }
    ]
    task_lookup = {
        "manual_review:s1": {
            "task_id": "manual_review:s1",
            "target_locale": "ru-RU",
            "target_constraints": {"content_class": "general", "risk_level": "high"},
        }
    }
    tickets = review_governance.build_review_tickets(
        review_queue_rows,
        task_lookup=task_lookup,
        source_artifacts={"review_queue": "data/review.csv"},
    )

    assert tickets[0]["ticket_type"] == "manual_review"
    assert tickets[0]["priority"] == "P1"

    manifest = {
        "overall_status": "review_handoff",
        "execution": {"updated": 0, "review_handoff": 1, "blocked": 0},
        "task_outcomes": {"counts_by_execution_status": {"review_handoff": 1}},
    }
    report = review_governance.build_kpi_report(
        scope="translate_refresh",
        manifest=manifest,
        review_tickets=tickets,
        feedback_logs=[],
        runtime_governance={"asset_statuses": {"data/style_profile.yaml": {"status": "approved"}}},
        metrics_payload={"summary": {"total_tokens": 42}},
        extra_sources={"lifecycle_registry_path": "workflow/lifecycle_registry.yaml"},
    )

    assert report["review_summary"]["total_review_tickets"] == 1
    assert report["review_summary"]["manual_intervention_rate"] == 1.0
    assert report["lifecycle_summary"]["deprecated_asset_usage_count"] == 0


def test_feedback_ingest_appends_feedback_log(tmp_path):
    feedback_csv = tmp_path / "feedback.csv"
    with feedback_csv.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(
            fh,
            fieldnames=["ticket_id", "string_id", "target_locale", "decision", "reviewer", "notes", "updated_target"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "ticket_id": "ticket:manual_review:s1:initial_manual_review",
                "string_id": "s1",
                "target_locale": "ru-RU",
                "decision": "approve",
                "reviewer": "linguist-a",
                "notes": "Looks good",
                "updated_target": "Approved target",
            }
        )

    output_log = tmp_path / "feedback.jsonl"
    exit_code = review_feedback_ingest.main(["--input", str(feedback_csv), "--output", str(output_log)])

    assert exit_code == 0
    rows = review_governance.load_feedback_log(str(output_log))
    assert len(rows) == 1
    assert rows[0]["decision"] == "approve"
    assert rows[0]["reviewer"] == "linguist-a"
