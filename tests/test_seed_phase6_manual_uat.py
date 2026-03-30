from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import scripts.seed_phase6_manual_uat as seed_phase6_manual_uat


def test_seed_manual_uat_fixtures_creates_derived_and_persisted_runs(tmp_path):
    payload = seed_phase6_manual_uat.seed_manual_uat_fixtures(tmp_path)

    derived_run_dir = tmp_path / "data" / "operator_ui_runs" / payload["derived"]["run_id"]
    persisted_run_dir = tmp_path / "data" / "operator_ui_runs" / payload["persisted"]["run_id"]

    assert (derived_run_dir / "run_manifest.json").exists()
    assert (persisted_run_dir / "run_manifest.json").exists()

    derived_manifest = json.loads((derived_run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    persisted_manifest = json.loads((persisted_run_dir / "run_manifest.json").read_text(encoding="utf-8"))

    assert derived_manifest["status"] == "warn"
    assert persisted_manifest["status"] == "pass"

    assert not (tmp_path / "data" / "operator_cards" / payload["derived"]["run_id"]).exists()
    assert (tmp_path / "data" / "operator_cards" / payload["persisted"]["run_id"] / "operator_cards.jsonl").exists()
    assert (tmp_path / "data" / "operator_reports" / payload["persisted"]["run_id"] / "operator_summary.json").exists()
