#!/usr/bin/env python3
"""Governance contracts for Batch 10 compat mirror closeout."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parent.parent


def test_batch10_report_declares_cleanup_roadmap_closed():
    report = (ROOT / "reports" / "cleanup_batch10_compat_mirror_closeout_20260319.md").read_text(encoding="utf-8")

    assert "cleanup roadmap is finished" in report
    assert "separate migration effort" in report
    assert "src/scripts" in report


def test_batch10_task_plan_declares_final_closeout_batch():
    plan = (ROOT / "task_plan.md").read_text(encoding="utf-8")

    assert "Deep Cleanup Batch 10" in plan
    assert "final roadmap closeout" in plan
    assert "separate migration program" in plan


def test_batch10_manifest_marks_src_scripts_as_exit_planned_compat_surface():
    manifest = json.loads((ROOT / "workflow" / "script_authority_manifest.json").read_text(encoding="utf-8"))
    compat_notes = manifest["compat_notes"]

    assert compat_notes["src_scripts_role"].startswith("managed compatibility liability")
    assert compat_notes["closeout_decision"] == "separate-exit-program"
    assert "package_v1.3.0.sh still packages src/scripts" in compat_notes["exit_blockers"]


def test_batch10_inventory_keeps_src_scripts_compat_keep_with_closeout_decision():
    inventory = json.loads((ROOT / "workflow" / "batch4_frozen_zone_inventory.json").read_text(encoding="utf-8"))
    blocked = [item["path"] for item in inventory["surfaces"] if item["status"] == "blocked"]
    src_entry = next(item for item in inventory["surfaces"] if item["path"] == "../src/scripts/**")

    assert blocked == []
    assert src_entry["status"] == "compat-keep"
    assert src_entry["closeout_decision"] == "separate-exit-program"
    assert src_entry["closeout_reason"].startswith("Not runtime authority")
