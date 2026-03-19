#!/usr/bin/env python3
"""Contracts for Batch 8 repair archive closeout."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parent.parent
ARCHIVE_ROOT = ROOT / "_obsolete" / "repair_archive"


def test_batch8_moves_historical_repair_scripts_into_archive():
    assert not (ROOT / "scripts" / "repair_loop_v2.py").exists()
    assert not (ROOT / "scripts" / "repair_checkpoint_gaps.py").exists()
    assert (ARCHIVE_ROOT / "repair_loop_v2.py").exists()
    assert (ARCHIVE_ROOT / "repair_checkpoint_gaps.py").exists()


def test_batch8_archive_readme_explains_retained_paths():
    readme = (ARCHIVE_ROOT / "README.md").read_text(encoding="utf-8")

    assert "repair_loop_v2.py" in readme
    assert "repair_checkpoint_gaps.py" in readme
    assert "repair_loop.py" in readme
    assert "rebuild_checkpoint.py" in readme
    assert "retained repair authority" in readme
    assert "retained checkpoint recovery path" in readme


def test_batch8_inventory_marks_archive_complete():
    inventory = json.loads((ROOT / "workflow" / "batch4_frozen_zone_inventory.json").read_text(encoding="utf-8"))
    statuses = {item["path"]: item["status"] for item in inventory["surfaces"]}

    assert statuses["scripts/repair_loop_v2.py"] == "archive-complete"
    assert statuses["scripts/repair_checkpoint_gaps.py"] == "archive-complete"


def test_batch8_report_records_archive_closeout_paths():
    report = (ROOT / "reports" / "cleanup_batch8_repair_archive_closeout_20260319.md").read_text(encoding="utf-8")

    assert "scripts/repair_loop_v2.py" in report
    assert "_obsolete/repair_archive/repair_loop_v2.py" in report
    assert "scripts/repair_checkpoint_gaps.py" in report
    assert "_obsolete/repair_archive/repair_checkpoint_gaps.py" in report
    assert "no wrapper" in report
    assert "Batch 9" in report
