#!/usr/bin/env python3
"""Contracts for Batch 5 archive-candidate fallback cleanup."""

import json
import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent
ARCHIVE_ROOT = ROOT / "_obsolete" / "repair_archive"


def test_batch4_inventory_marks_batch5_targets_as_blocked():
    inventory = json.loads((ROOT / "workflow" / "batch4_frozen_zone_inventory.json").read_text(encoding="utf-8"))
    statuses = {item["path"]: item["status"] for item in inventory["surfaces"]}

    assert statuses["scripts/repair_loop_v2.py"] == "blocked"
    assert statuses["scripts/repair_checkpoint_gaps.py"] == "blocked"


def test_batch5_report_records_fallback_to_blocked():
    report = (ROOT / "reports" / "cleanup_batch5_archive_20260319.md").read_text(encoding="utf-8")

    assert "repair_loop_v2.py" in report
    assert "repair_checkpoint_gaps.py" in report
    assert "fallback-to-blocked" in report


def test_repair_loop_v2_remains_in_runtime_scripts_after_fallback():
    assert (ROOT / "scripts" / "repair_loop_v2.py").exists()
    assert not (ARCHIVE_ROOT / "repair_loop_v2.py").exists()


def test_repair_checkpoint_gaps_remains_in_runtime_scripts_after_fallback():
    assert (ROOT / "scripts" / "repair_checkpoint_gaps.py").exists()
    assert not (ARCHIVE_ROOT / "repair_checkpoint_gaps.py").exists()


def test_repair_loop_v2_cli_contract_is_still_characterized(monkeypatch, tmp_path):
    input_csv = tmp_path / "input.csv"
    tasks_jsonl = tmp_path / "tasks.jsonl"
    output_csv = tmp_path / "output.csv"
    output_dir = tmp_path / "out"
    input_csv.write_text("string_id,target_text\n1,ok\n", encoding="utf-8")
    tasks_jsonl.write_text(
        '{"string_id":"1","source_text":"src","current_translation":"ok","issues":[{"type":"style"}]}\n',
        encoding="utf-8",
    )

    captured = {}

    class FakeLoop:
        def __init__(self, config, qa_type, output_dir_arg):
            captured["qa_type"] = qa_type
            captured["output_dir"] = output_dir_arg

        def run(self, tasks, df):
            captured["task_count"] = len(tasks)
            return df, []

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = __import__("repair_loop_v2")
    monkeypatch.setattr(module, "BatchRepairLoop", FakeLoop)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "repair_loop_v2.py",
            "--input",
            str(input_csv),
            "--tasks",
            str(tasks_jsonl),
            "--output",
            str(output_csv),
            "--output-dir",
            str(output_dir),
            "--qa-type",
            "soft",
        ],
    )

    module.main()

    assert captured["qa_type"] == "soft"
    assert captured["output_dir"] == str(output_dir)
    assert captured["task_count"] == 1
    assert output_csv.exists()


def test_repair_checkpoint_gaps_characterization(monkeypatch, tmp_path):
    part1 = tmp_path / "checkpoint_part1.lock.json"
    part3 = tmp_path / "translated_r1_part3.csv"
    normalized = tmp_path / "normalized.csv"
    target = tmp_path / "translate_checkpoint.json"

    part1.write_text(json.dumps({"done_ids": {"1": True}, "stats": {"ok": 1, "escalated": 0}}), encoding="utf-8")
    part3.write_text("string_id,target_text\n2,done\n", encoding="utf-8")
    normalized.write_text("string_id,source_zh\n1,a\n2,b\n3,c\n", encoding="utf-8")

    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    module = __import__("repair_checkpoint_gaps")
    monkeypatch.setattr(module, "PART1_LOCK", str(part1))
    monkeypatch.setattr(module, "PART3_CSV", str(part3))
    monkeypatch.setattr(module, "NORMALIZED_CSV", str(normalized))
    monkeypatch.setattr(module, "TARGET_CKPT", str(target))

    module.main()

    repaired = json.loads(target.read_text(encoding="utf-8"))
    assert repaired["done_ids"] == {"1": True, "2": True}
    assert repaired["stats"]["ok"] == 2
    assert repaired["batch_idx"] == 0
