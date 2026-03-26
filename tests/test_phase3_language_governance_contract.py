from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import language_governance
import review_feedback_ingest
import translate_refresh


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames: list[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_glossary(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "meta:",
                "  type: compiled",
                "entries:",
                "  - term_zh: 木叶",
                "    targets:",
                "      ru-RU: Коноха",
            ]
        ),
        encoding="utf-8",
    )


def _write_style(path: Path) -> None:
    path.write_text("# style\n- keep concise\n", encoding="utf-8")


def test_validate_style_governance_runtime_accepts_repo_profile():
    profile, lifecycle_entry = language_governance.validate_style_governance_runtime(
        str(Path(__file__).parent.parent / "data" / "style_profile.yaml"),
        lifecycle_registry_path=str(Path(__file__).parent.parent / "workflow" / "lifecycle_registry.yaml"),
    )

    assert profile["style_governance"]["status"] == "approved"
    assert lifecycle_entry["asset_type"] == "style_profile"


def test_external_style_profile_uses_minimal_runtime_validation(tmp_path):
    profile_path = tmp_path / "style_profile.yaml"
    profile_path.write_text(
        json.dumps(
            {
                "project": {"source_language": "zh-CN", "target_language": "ru-RU"},
                "ui": {"length_constraints": {"button_max_chars": 18, "dialogue_max_chars": 120}},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    profile, lifecycle_entry = language_governance.validate_style_governance_runtime(str(profile_path))

    assert profile["project"]["target_language"] == "ru-RU"
    assert lifecycle_entry == {}


def test_validate_style_governance_runtime_fails_closed_for_explicit_incomplete_registry(tmp_path):
    profile_path = tmp_path / "style_profile.yaml"
    profile_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "project": {"source_language": "zh-CN", "target_language": "ru-RU"},
                "ui": {"length_constraints": {"button_max_chars": 18, "dialogue_max_chars": 120}},
                "style_governance": {
                    "status": "approved",
                    "style_guide_id": "guide-v1",
                    "approval_ref": "docs/decisions/ADR-0002-skill-governance-framework.md",
                    "entry_audit": {"loadable": True, "approved": True, "deprecated": False},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    lifecycle_registry = tmp_path / "registry.yaml"
    lifecycle_registry.write_text('version: "1.0"\nentries: []\n', encoding="utf-8")

    with pytest.raises(language_governance.GovernanceError, match="missing lifecycle entry"):
        language_governance.validate_style_governance_runtime(
            str(profile_path),
            lifecycle_registry_path=str(lifecycle_registry),
        )


def test_translate_refresh_generate_only_emits_review_tickets_and_kpi(tmp_path):
    translated_csv = tmp_path / "translated.csv"
    delta_rows = tmp_path / "delta_rows.jsonl"
    glossary = tmp_path / "compiled.yaml"
    style = tmp_path / "style.md"
    tasks_out = tmp_path / "tasks.jsonl"
    review_queue = tmp_path / "review_queue.csv"
    review_tickets = tmp_path / "review_tickets.jsonl"
    review_tickets_csv = tmp_path / "review_tickets.csv"
    feedback_log = tmp_path / "feedback.jsonl"
    manifest = tmp_path / "manifest.json"
    kpi_report = tmp_path / "kpi.json"

    _write_csv(
        translated_csv,
        [
            {
                "string_id": "s1",
                "source_zh": "人工复核文案",
                "tokenized_zh": "人工复核文案",
                "target_text": "Нужна ручная проверка",
                "target_locale": "ru-RU",
            }
        ],
    )
    _write_jsonl(
        delta_rows,
        [
            {
                "string_id": "s1",
                "source_zh": "人工复核文案",
                "current_target": "Нужна ручная проверка",
                "target_locale": "ru-RU",
                "content_class": "general",
                "risk_level": "high",
                "delta_types": ["style_profile"],
                "reason_codes": ["STYLE_CONTRACT_CHANGED"],
                "reason_text": "style governance changed",
                "rule_refs": ["style_governance"],
                "placeholder_locked": False,
                "manual_review_required": True,
                "manual_review_reason": "style_contract_changed",
                "recommended_action": "manual_review",
            }
        ],
    )
    _write_glossary(glossary)
    _write_style(style)

    exit_code = translate_refresh.main(
        [
            "--delta-rows",
            str(delta_rows),
            "--translated",
            str(translated_csv),
            "--glossary",
            str(glossary),
            "--style",
            str(style),
            "--tasks-out",
            str(tasks_out),
            "--review-queue",
            str(review_queue),
            "--review-tickets",
            str(review_tickets),
            "--review-tickets-csv",
            str(review_tickets_csv),
            "--feedback-log",
            str(feedback_log),
            "--kpi-report",
            str(kpi_report),
            "--manifest",
            str(manifest),
            "--generate-only",
        ]
    )

    assert exit_code == 0
    manifest_payload = json.loads(manifest.read_text(encoding="utf-8"))
    review_ticket_lines = review_tickets.read_text(encoding="utf-8").strip().splitlines()
    kpi_payload = json.loads(kpi_report.read_text(encoding="utf-8"))
    assert manifest_payload["artifacts"]["review_tickets_jsonl"] == str(review_tickets)
    assert len(review_ticket_lines) == 1
    assert kpi_payload["ticket_counts"]["total"] == 1


def test_review_feedback_ingest_writes_canonical_feedback_log(tmp_path, monkeypatch):
    input_csv = tmp_path / "tickets.csv"
    output_jsonl = tmp_path / "feedback.jsonl"
    _write_csv(
        input_csv,
        [
            {
                "ticket_id": "ticket:manual_review:s1",
                "string_id": "s1",
                "target_locale": "ru-RU",
                "decision": "accepted",
                "resolution_status": "closed",
                "review_owner": "human-linguist",
                "notes": "approved by linguist",
            }
        ],
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "review_feedback_ingest.py",
            "--input",
            str(input_csv),
            "--output",
            str(output_jsonl),
            "--feedback-source",
            "human_review",
        ],
    )

    assert review_feedback_ingest.main() == 0
    payload = json.loads(output_jsonl.read_text(encoding="utf-8").strip())
    assert payload["decision"] == "approve"
    assert payload["source_artifact"] == "human_review"
