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
        / "2026-03-21"
        / "run_manifest_plc_run_d_verify.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = plc_validate_records.validate_artifact(contract, "run_manifest", manifest_path)

    assert errors == []
    assert manifest["status"] in {"pass", "warn", "blocked"}
    assert manifest["next_step_owner"]
    assert manifest["next_step_scope"]


def test_plc_decision_refs_resolve_to_existing_adr_files():
    manifest_paths = [
        REPO_ROOT
        / "docs"
        / "project_lifecycle"
        / "run_records"
        / "2026-03"
        / "2026-03-21"
        / name
        for name in (
            "run_manifest_plc_run_a_20260321_1000.json",
            "run_manifest_plc_run_b_202603211300.json",
            "run_manifest_plc_run_c_202603212000.json",
        )
    ]

    for manifest_path in manifest_paths:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for ref in manifest.get("decision_refs", []):
            if ref.startswith("docs/"):
                assert (REPO_ROOT / ref).exists(), ref


def test_plc_templates_validate_against_governance_contract():
    exit_code = plc_validate_records.main(["--preset", "templates"])

    assert exit_code == 0


def test_representative_session_and_milestone_records_validate_against_contract():
    contract = plc_validate_records.load_contract(REPO_ROOT / "workflow" / "plc_governance_contract.yaml")
    paths = [
        ("session_start", REPO_ROOT / "docs" / "project_lifecycle" / "run_records" / "2026-03" / "2026-03-25" / "session_start_20260325_phase2_governance_substrate.md"),
        ("session_end", REPO_ROOT / "docs" / "project_lifecycle" / "run_records" / "2026-03" / "2026-03-25" / "session_end_20260325_phase2_governance_substrate.md"),
        ("milestone_state", REPO_ROOT / "docs" / "project_lifecycle" / "run_records" / "2026-03" / "2026-03-21" / "milestone_state_D.md"),
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
                "",
                "## Slice",
                "- bounded implementation target: `example`",
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
