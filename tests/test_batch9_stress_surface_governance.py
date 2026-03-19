#!/usr/bin/env python3
"""Governance contracts for Batch 9 stress surface canonicalization."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parent.parent


def _inventory_statuses():
    inventory = json.loads((ROOT / "workflow" / "batch4_frozen_zone_inventory.json").read_text(encoding="utf-8"))
    return {item["path"]: item["status"] for item in inventory["surfaces"]}


def test_batch9_inventory_retains_single_canonical_stress_shell():
    statuses = _inventory_statuses()

    assert statuses["scripts/stress_test_3k_run.sh"] == "must-keep"
    assert statuses["scripts/acceptance_stress_final.sh"] == "archive-candidate"
    assert statuses["scripts/acceptance_stress_resume.sh"] == "archive-candidate"
    assert statuses["scripts/acceptance_stress_resume_fix.sh"] == "archive-candidate"
    assert statuses["scripts/acceptance_stress_run.sh"] == "archive-candidate"
    assert statuses["scripts/acceptance_stress_phase3.sh"] == "archive-candidate"


def test_batch9_inventory_classifies_adjacent_stress_helpers():
    statuses = _inventory_statuses()

    assert statuses["scripts/finalize_stress_report.py"] == "archive-candidate"
    assert statuses["scripts/verify_3k_test.py"] == "compat-keep"
    assert statuses["scripts/run_long_text_gate_v1.py"] == "archive-candidate"


def test_batch9_retained_stress_shell_uses_current_soft_repair_contracts():
    script = (ROOT / "scripts" / "stress_test_3k_run.sh").read_text(encoding="utf-8")

    assert "--out_report" in script
    assert "--out_tasks" in script
    assert "--qa-type hard" in script
    assert "--qa-type soft" in script
    assert "$BATCH_DIR/3k_repair_tasks_soft.jsonl" in script


def test_batch9_drifted_acceptance_scripts_do_not_qualify_as_must_keep():
    final_script = (ROOT / "scripts" / "acceptance_stress_final.sh").read_text(encoding="utf-8")
    resume_script = (ROOT / "scripts" / "acceptance_stress_resume.sh").read_text(encoding="utf-8")

    assert "--input" in final_script and "--placeholder-map" in final_script
    assert "--input" in resume_script and "--placeholder-map" in resume_script


def test_batch9_report_records_closeout_readiness_and_canonical_path():
    report = (ROOT / "reports" / "cleanup_batch9_stress_surface_20260319.md").read_text(encoding="utf-8")

    assert "stress_test_3k_run.sh" in report
    assert "acceptance_stress_final.sh" in report
    assert "archive-candidate" in report
    assert "Batch 10" in report
    assert "closeout" in report.lower()
