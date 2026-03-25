from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import plc_validate_records


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_plc_governance_contract_has_required_artifact_types():
    contract = plc_validate_records.load_contract(REPO_ROOT / "workflow" / "plc_governance_contract.yaml")

    artifact_types = set((contract.get("artifacts", {}) or {}).keys())
    assert artifact_types == {"run_manifest", "session_start", "session_end", "milestone_state"}


def test_representative_run_manifest_matches_contract():
    contract = plc_validate_records.load_contract(REPO_ROOT / "workflow" / "plc_governance_contract.yaml")
    manifest_path = (
        REPO_ROOT
        / "docs"
        / "project_lifecycle"
        / "run_records"
        / "2026-03"
        / "2026-03-25"
        / "run_manifest_phase2_governance_closeout.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = plc_validate_records.validate_artifact(contract, "run_manifest", manifest_path)

    assert errors == []
    assert manifest["status"] in {"pass", "warn", "blocked"}
    assert manifest["next_step_owner"]
    assert manifest["next_step_scope"]
    assert manifest["changed_files"]
    assert manifest["evidence_refs"]
    assert manifest["adr_refs"]


def test_plc_decision_refs_resolve_to_existing_adr_files():
    manifest_path = (
        REPO_ROOT
        / "docs"
        / "project_lifecycle"
        / "run_records"
        / "2026-03"
        / "2026-03-25"
        / "run_manifest_phase2_governance_closeout.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for ref in manifest.get("adr_refs", []):
        if ref.startswith("docs/"):
            assert (REPO_ROOT / ref).exists(), ref


def test_plc_templates_validate_against_governance_contract():
    exit_code = plc_validate_records.main(["--preset", "templates"])

    assert exit_code == 0


def test_representative_session_and_milestone_records_validate_against_contract():
    contract = plc_validate_records.load_contract(REPO_ROOT / "workflow" / "plc_governance_contract.yaml")
    paths = [
        (
            "session_start",
            REPO_ROOT / "docs" / "project_lifecycle" / "run_records" / "2026-03" / "2026-03-25" / "session_start_20260325_phase2_governance_closeout.md",
        ),
        (
            "session_end",
            REPO_ROOT / "docs" / "project_lifecycle" / "run_records" / "2026-03" / "2026-03-25" / "session_end_20260325_phase2_governance_closeout.md",
        ),
        (
            "milestone_state",
            REPO_ROOT / "docs" / "project_lifecycle" / "run_records" / "2026-03" / "2026-03-25" / "milestone_state_M.md",
        ),
    ]

    for artifact_type, path in paths:
        assert plc_validate_records.validate_artifact(contract, artifact_type, path) == []


def test_validator_cli_passes_representative_and_template_presets():
    exit_code = plc_validate_records.main(["--preset", "representative", "--preset", "templates"])

    assert exit_code == 0


def test_markdown_parser_preserves_multiline_folded_scalar_content(tmp_path):
    record = tmp_path / "session_start_multiline.md"
    record.write_text(
        "\n".join(
            [
                "# Session Start",
                "",
                "- date: `2026-03-25`",
                "- branch: `codex/example`",
                "- current_scope: `milestone_M_prepare`",
                "- route: `plc + triadev`",
                "- base_branch: `main`",
                "",
                "## Context",
                "- read_versions:",
                "  - `task_plan.md @ 20260325T020346+0800`",
                "- blockers:",
                "  - `none`",
                "",
                "## Slice",
                "- bounded implementation target: `example`",
                "- mini plan:",
                "  - `freeze contract`",
                "",
                "## Validation Decision",
                "- validation mode: `focused-governance-tests`",
                "- smoke run: `not required for this slice`",
                "- rationale: >",
                "  first line of rationale",
                "  second line of rationale",
                "",
                "## Handoff",
                "- next_owner: `Codex`",
                "- next_scope: `next_scope`",
                "- next_action: `do the next thing`",
            ]
        ),
        encoding="utf-8",
    )

    parsed = plc_validate_records.parse_markdown_sections(record)

    assert parsed["Validation Decision"]["rationale"] == "first line of rationale second line of rationale"


def test_validator_rejects_missing_three_point_governance_fields(tmp_path):
    contract = {
        "artifacts": {
            "session_end": {
                "required_top_level": ["date", "branch", "current_scope", "slice_status"],
                "required_sections": {
                    "Delivered Surface": [],
                    "Acceptance": ["command", "result", "smoke run", "rationale"],
                    "Outcome": [],
                    "Governance": ["changed_files", "evidence_refs", "adr_refs", "blocker list"],
                    "Handoff": ["next_owner", "next_scope", "open_issues", "next_action", "next_hour_task"],
                },
            }
        }
    }
    record = tmp_path / "session_end_missing_fields.md"
    record.write_text(
        "\n".join(
            [
                "# Session End",
                "",
                "- date: `2026-03-25`",
                "- branch: `codex/example`",
                "- current_scope: `milestone_M_prepare`",
                "- slice_status: `completed`",
                "",
                "## Delivered Surface",
                "- `docs/project_lifecycle/roadmap_index.md`",
                "",
                "## Acceptance",
                "- command: `pytest -q`",
                "- result: `pass`",
                "- smoke run: `skipped by design`",
                "- rationale: `focused governance only`",
                "",
                "## Outcome",
                "- `done`",
                "",
                "## Governance",
                "- blocker list:",
                "  - `none`",
                "",
                "## Handoff",
                "- next_owner: `Codex`",
                "- next_scope: `phase3_planning_ready`",
                "- open_issues:",
                "  - `none`",
                "- next_hour_task: `close package`",
                "- next_action: `close package`",
            ]
        ),
        encoding="utf-8",
    )

    errors = plc_validate_records.validate_markdown_artifact(record, contract["artifacts"]["session_end"], "session_end")

    assert any("changed_files" in error for error in errors)
    assert any("evidence_refs" in error for error in errors)
    assert any("adr_refs" in error for error in errors)


def test_validator_rejects_invalid_adr_and_missing_evidence_paths(tmp_path):
    contract = {
        "artifacts": {
            "run_manifest": {
                "required_fields": [
                    "manifest_version",
                    "run_id",
                    "run_scope",
                    "status",
                    "started_at",
                    "finished_at",
                    "owner",
                    "input_manifest",
                    "issue_report_path",
                    "verify_report_path",
                    "artifacts",
                    "blockers",
                    "changed_files",
                    "evidence_refs",
                    "adr_refs",
                    "decision_refs",
                    "evidence_ready",
                    "next_step_owner",
                    "next_step_scope",
                ],
                "enum_fields": {"status": ["pass", "warn", "blocked"]},
                "boolean_fields": ["evidence_ready"],
            }
        }
    }
    manifest = tmp_path / "run_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "manifest_version": "demo-v1",
                "run_id": "demo",
                "run_scope": "phase2_closeout",
                "status": "pass",
                "started_at": "2026-03-25T10:00:00+08:00",
                "finished_at": "2026-03-25T10:10:00+08:00",
                "owner": "Codex",
                "input_manifest": "docs/project_lifecycle/roadmap_index.md",
                "issue_report_path": "docs/project_lifecycle/roadmap_index.md",
                "verify_report_path": "docs/project_lifecycle/roadmap_index.md",
                "artifacts": [],
                "blockers": [],
                "changed_files": ["docs/project_lifecycle/roadmap_index.md"],
                "evidence_refs": ["docs/project_lifecycle/missing_verify.md"],
                "adr_refs": ["docs/project_lifecycle/roadmap_index.md"],
                "decision_refs": ["phase:demo"],
                "evidence_ready": True,
                "next_step_owner": "Codex",
                "next_step_scope": "phase3_planning_ready",
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )

    errors = plc_validate_records.validate_run_manifest(manifest, contract["artifacts"]["run_manifest"])

    assert any("evidence_refs" in error and "does not exist" in error for error in errors)
    assert any("adr_refs" in error and "docs/decisions" in error for error in errors)


def test_validator_checks_path_when_evidence_mapping_contains_command_and_path(tmp_path):
    contract = {
        "artifacts": {
            "run_manifest": {
                "required_fields": [
                    "manifest_version",
                    "run_id",
                    "run_scope",
                    "status",
                    "started_at",
                    "finished_at",
                    "owner",
                    "input_manifest",
                    "issue_report_path",
                    "verify_report_path",
                    "artifacts",
                    "blockers",
                    "changed_files",
                    "evidence_refs",
                    "adr_refs",
                    "decision_refs",
                    "evidence_ready",
                    "next_step_owner",
                    "next_step_scope",
                ],
                "enum_fields": {"status": ["pass", "warn", "blocked"]},
                "boolean_fields": ["evidence_ready"],
            }
        }
    }
    manifest = tmp_path / "run_manifest_with_evidence_mapping.json"
    manifest.write_text(
        json.dumps(
            {
                "manifest_version": "demo-v1",
                "run_id": "demo",
                "run_scope": "phase2_closeout",
                "status": "pass",
                "started_at": "2026-03-25T10:00:00+08:00",
                "finished_at": "2026-03-25T10:10:00+08:00",
                "owner": "Codex",
                "input_manifest": "docs/project_lifecycle/roadmap_index.md",
                "issue_report_path": "docs/project_lifecycle/roadmap_index.md",
                "verify_report_path": "docs/project_lifecycle/roadmap_index.md",
                "artifacts": [],
                "blockers": [],
                "changed_files": ["docs/project_lifecycle/roadmap_index.md"],
                "evidence_refs": [{"command": "python -m pytest tests/test_plc_docs_contract.py -q", "path": "docs/project_lifecycle/missing_verify.md"}],
                "adr_refs": ["docs/decisions/ADR-0001-project-continuity-framework.md"],
                "decision_refs": ["phase:demo"],
                "evidence_ready": True,
                "next_step_owner": "Codex",
                "next_step_scope": "phase3_planning_ready",
            },
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )

    errors = plc_validate_records.validate_run_manifest(manifest, contract["artifacts"]["run_manifest"])

    assert any("evidence_refs" in error and "missing_verify.md" in error for error in errors)
