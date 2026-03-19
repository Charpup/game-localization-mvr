#!/usr/bin/env python3
"""Governance contracts for Batch 3/4 cleanup planning."""

import json
import runpy
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent


def test_batch3_surface_inventory_keeps_expected_canonical_relationships():
    inventory = json.loads((ROOT / "workflow" / "batch3_surface_inventory.json").read_text(encoding="utf-8"))

    statuses = {item["script"]: item["status"] for item in inventory["surface_status"]}

    assert statuses["normalize_tagger.py"] == "must-keep candidate"
    assert statuses["normalize_tag_llm.py"] == "stress-only compat entrypoint"
    assert statuses["normalize_ingest.py"] == "compat-keep documented ingest"
    assert statuses["qa_soft.py"] == "compat-keep wrapper"
    assert statuses["soft_qa_llm.py"] == "compat-keep canonical"

    relationships = {
        (item["canonical"], item["related"]): item["relationship"]
        for item in inventory["canonical_relationships"]
    }

    assert relationships[("normalize_tagger.py", "normalize_tag_llm.py")] == "stress-only compatibility variant"
    assert relationships[("soft_qa_llm.py", "qa_soft.py")] == "wrapper compatibility entrypoint"


def test_batch4_frozen_zone_inventory_blocks_high_risk_surfaces():
    inventory = json.loads((ROOT / "workflow" / "batch4_frozen_zone_inventory.json").read_text(encoding="utf-8"))

    statuses = {item["path"]: item["status"] for item in inventory["surfaces"]}

    assert statuses["scripts/repair_loop.py"] == "blocked"
    assert statuses["scripts/run_validation.py"] == "blocked"
    assert statuses["scripts/build_validation_set.py"] == "blocked"
    assert statuses["../src/scripts/**"] == "compat-keep"


def test_qa_soft_wrapper_forwards_cli_to_soft_qa_llm(monkeypatch):
    script_path = ROOT / "scripts" / "qa_soft.py"
    captured = {}

    def fake_call(cmd):
        captured["cmd"] = cmd
        return 7

    monkeypatch.setattr("subprocess.call", fake_call)
    monkeypatch.setattr(sys, "argv", ["qa_soft.py", "--dry-run", "--resume"])
    monkeypatch.setattr(sys, "executable", "python-test")

    try:
        runpy.run_path(str(script_path), run_name="__main__")
    except SystemExit as exc:
        assert exc.code == 7
    else:
        raise AssertionError("qa_soft.py should propagate the subprocess exit code")

    assert captured["cmd"][0] == "python-test"
    assert captured["cmd"][-2:] == ["--dry-run", "--resume"]
    assert captured["cmd"][1].endswith("soft_qa_llm.py")


def test_normalize_ingest_main_writes_output_for_valid_input(monkeypatch, tmp_path):
    scripts_dir = ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import normalize_ingest  # pylint: disable=import-outside-toplevel

    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "out" / "source_raw.csv"
    input_path.write_text("ID,Source,Context\n001,你好,menu\n", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        ["normalize_ingest.py", "--input", str(input_path), "--output", str(output_path)],
    )

    try:
        normalize_ingest.main()
    except SystemExit as exc:
        assert exc.code == 0
    else:
        raise AssertionError("normalize_ingest.main() should exit after CLI execution")

    assert output_path.exists()


def test_normalize_ingest_main_exits_nonzero_for_missing_input(monkeypatch):
    scripts_dir = ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import normalize_ingest  # pylint: disable=import-outside-toplevel

    missing = ROOT / "data" / "definitely_missing_input.csv"
    monkeypatch.setattr(sys, "argv", ["normalize_ingest.py", "--input", str(missing)])

    try:
        normalize_ingest.main()
    except SystemExit as exc:
        assert exc.code == 1
    else:
        raise AssertionError("normalize_ingest.main() should exit when input is missing")


def test_normalize_tagger_main_honors_no_llm_cli(monkeypatch, tmp_path):
    scripts_dir = ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import normalize_tagger  # pylint: disable=import-outside-toplevel

    input_path = tmp_path / "source_raw.csv"
    output_path = tmp_path / "normalized.csv"
    input_path.write_text("string_id,source_zh\nBTN_OK,确定\n", encoding="utf-8")

    captured = {}

    def fake_process_entries(input_csv, source_locale, llm_threshold, use_llm, model):
        captured["args"] = (input_csv, source_locale, llm_threshold, use_llm, model)
        return [
            normalize_tagger.TagResult(
                string_id="BTN_OK",
                source_zh="确定",
                module_tag="ui_button",
                module_confidence=0.95,
                max_len_target=10,
                len_tier="S",
                source_locale="zh-CN",
                placeholder_flags="count=0",
            )
        ]

    monkeypatch.setattr(normalize_tagger, "process_entries", fake_process_entries)
    monkeypatch.setattr(normalize_tagger, "configure_standard_streams", lambda: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "normalize_tagger.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--no-llm",
        ],
    )

    normalize_tagger.main()

    assert captured["args"][0] == str(input_path)
    assert captured["args"][3] is False
    assert output_path.exists()


def test_normalize_tag_llm_main_passes_length_rules_cli(monkeypatch, tmp_path):
    scripts_dir = ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import normalize_tag_llm  # pylint: disable=import-outside-toplevel

    input_path = tmp_path / "source_raw.csv"
    output_path = tmp_path / "normalized.csv"
    rules_path = tmp_path / "length_rules.yaml"
    input_path.write_text("string_id,source_zh\nBTN_OK,确定\n", encoding="utf-8")
    rules_path.write_text("default:\n  multiplier: 3.0\n  min_buffer: 5\n  max_absolute: 20\n", encoding="utf-8")

    captured = {}

    def fake_process_entries(input_csv, source_locale, llm_threshold, use_llm, length_rules_path, model):
        captured["args"] = (input_csv, source_locale, llm_threshold, use_llm, length_rules_path, model)
        return [
            normalize_tag_llm.TagResult(
                string_id="BTN_OK",
                source_zh="确定",
                module_tag="ui_button",
                module_confidence=0.95,
                max_len_target=10,
                len_tier="S",
                source_locale="zh-CN",
                placeholder_flags="count=0",
            )
        ]

    monkeypatch.setattr(normalize_tag_llm, "process_entries", fake_process_entries)
    monkeypatch.setattr(normalize_tag_llm, "configure_standard_streams", lambda: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "normalize_tag_llm.py",
            "--input",
            str(input_path),
            "--output",
            str(output_path),
            "--length-rules",
            str(rules_path),
            "--no-llm",
        ],
    )

    normalize_tag_llm.main()

    assert captured["args"][0] == str(input_path)
    assert captured["args"][3] is False
    assert captured["args"][4] == str(rules_path)
    assert output_path.exists()
