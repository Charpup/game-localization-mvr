from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent


def test_milestone_b_run_manifest_uses_schema_valid_status():
    manifest_path = (
        REPO_ROOT
        / "docs"
        / "project_lifecycle"
        / "run_records"
        / "2026-03"
        / "2026-03-21"
        / "run_manifest_plc_run_b_202603211300.json"
    )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["status"] in {"pass", "warn", "blocked"}


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
