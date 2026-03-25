#!/usr/bin/env python3
"""Contracts for the retained repair_loop authority."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd


ROOT = Path(__file__).parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.repair_loop as repair_loop
import scripts.runtime_adapter as runtime_adapter


def test_repair_loop_soft_repairs_route_to_repair_soft_major_and_create_output_dir(monkeypatch, tmp_path):
    calls = []

    class FakeClient:
        def chat(self, **kwargs):
            calls.append(kwargs["metadata"])
            return SimpleNamespace(text="fixed text")

    monkeypatch.setattr(runtime_adapter, "LLMClient", FakeClient)

    data = pd.DataFrame([{"string_id": "1", "target_ru": "old text"}])
    tasks = [
        repair_loop.RepairTask(
            {
                "string_id": "1",
                "source_text": "source text",
                "current_translation": "old text",
                "issues": [{"type": "style", "detail": "too literal"}],
            }
        )
    ]

    output_dir = tmp_path / "repair_artifacts"
    loop = repair_loop.RepairLoop(
        {
            "repair_loop": {
                "max_rounds": 1,
                "rounds": {1: {"model": "test-model", "prompt_variant": "standard"}},
            }
        },
        qa_type="soft",
    )

    repaired_df, escalations = loop.run(tasks, data, str(output_dir))

    assert output_dir.is_dir()
    assert calls[0]["step"] == "repair_soft_major"
    assert repaired_df.loc[0, "target_ru"] == "fixed text"
    assert escalations == []


def test_repair_loop_docs_publish_flags_only_cli_authority():
    repair_workflow = (ROOT / ".agent" / "workflows" / "loc-repair-loop.md").read_text(encoding="utf-8")
    pipeline_workflow = (ROOT / ".agent" / "workflows" / "loc-pipeline-full.md").read_text(encoding="utf-8")
    user_workflow = (ROOT / "docs" / "localization_pipeline_workflow.md").read_text(encoding="utf-8")

    assert "--mode" not in repair_workflow

    for text in (repair_workflow, pipeline_workflow, user_workflow):
        assert "--report" not in text
        assert "--only_soft_major" not in text

    assert "--input data/translated.csv" in repair_workflow
    assert "--tasks data/qa_hard_report.json" in repair_workflow
    assert "--tasks data/repair_tasks.jsonl" in repair_workflow
    assert "--output data/repaired.csv" in repair_workflow
    assert "--output-dir data/repair_reports" in repair_workflow
    assert "--qa-type hard" in repair_workflow
    assert "--qa-type soft" in repair_workflow
    assert "repair_soft_major" in repair_workflow

    assert "--qa-type hard" in pipeline_workflow
    assert "--qa-type soft" in pipeline_workflow

    assert "--qa-type hard" in user_workflow
    assert "--qa-type soft" in user_workflow
    assert "repair_soft_major" in user_workflow


def test_repair_loop_docs_and_rules_stop_claiming_resume_support():
    repair_workflow = (ROOT / ".agent" / "workflows" / "loc-repair-loop.md").read_text(encoding="utf-8")
    rules = (ROOT / ".agent" / "rules" / "localization-mvr-rules.md").read_text(encoding="utf-8")
    workspace_rules = (ROOT / "docs" / "WORKSPACE_RULES.md").read_text(encoding="utf-8")
    inventory = json.loads((ROOT / "workflow" / "batch4_frozen_zone_inventory.json").read_text(encoding="utf-8"))
    statuses = {item["path"]: item["status"] for item in inventory["surfaces"]}

    assert "断点续传" not in repair_workflow
    assert "--checkpoint" not in repair_workflow
    assert "checkpoint snapshot" in repair_workflow
    assert "不承诺恢复中断前的 repair 状态" in repair_workflow

    assert "不承诺恢复中断前的 repair 状态" in rules
    assert "checkpoint snapshot / 运行证据" in workspace_rules
    assert "repair_hard" in workspace_rules
    assert "repair_soft_major" in workspace_rules
    assert statuses["scripts/repair_loop.py"] == "must-keep"


def test_repair_loop_main_accepts_hard_report_json_as_tasks(monkeypatch, tmp_path):
    input_path = tmp_path / "translated.csv"
    tasks_path = tmp_path / "qa_hard_report.json"
    output_path = tmp_path / "repaired.csv"
    output_dir = tmp_path / "repair_reports" / "hard"

    pd.DataFrame([{"string_id": "1", "target_ru": "old text"}]).to_csv(input_path, index=False, encoding="utf-8")
    tasks_path.write_text(
        json.dumps(
            {
                "has_errors": True,
                "errors": [
                    {
                        "string_id": "1",
                        "source_text": "source text",
                        "current_translation": "old text",
                        "issues": [{"type": "placeholder", "detail": "missing token"}],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    captured = {}

    class DummyRepairLoop:
        def __init__(self, config, qa_type):
            captured["config"] = config
            captured["qa_type"] = qa_type
            self.stats = {"total_tasks": 1, "repaired": 1, "escalated": 0}

        def run(self, tasks, df, artifact_dir):
            captured["task_count"] = len(tasks)
            captured["artifact_dir"] = artifact_dir
            return df, []

    monkeypatch.setattr(repair_loop, "load_repair_config", lambda path: {"repair_loop": {"max_rounds": 1}})
    monkeypatch.setattr(repair_loop, "RepairLoop", DummyRepairLoop)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "repair_loop.py",
            "--input",
            str(input_path),
            "--tasks",
            str(tasks_path),
            "--output",
            str(output_path),
            "--output-dir",
            str(output_dir),
            "--qa-type",
            "hard",
        ],
    )

    repair_loop.main()

    assert captured["qa_type"] == "hard"
    assert captured["task_count"] == 1
    assert captured["artifact_dir"] == str(output_dir)
    assert output_path.exists()


def test_repair_loop_main_accepts_soft_jsonl_as_tasks(monkeypatch, tmp_path):
    input_path = tmp_path / "translated.csv"
    tasks_path = tmp_path / "repair_tasks.jsonl"
    output_path = tmp_path / "repaired.csv"
    output_dir = tmp_path / "repair_reports" / "soft"

    pd.DataFrame([{"string_id": "1", "target_ru": "old text"}]).to_csv(input_path, index=False, encoding="utf-8")
    tasks_path.write_text(
        json.dumps(
            {
                "string_id": "1",
                "source_text": "source text",
                "current_translation": "old text",
                "issues": [{"type": "style", "detail": "too literal"}],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    captured = {}

    class DummyRepairLoop:
        def __init__(self, config, qa_type):
            captured["qa_type"] = qa_type
            self.stats = {"total_tasks": 1, "repaired": 1, "escalated": 0}

        def run(self, tasks, df, artifact_dir):
            captured["task_count"] = len(tasks)
            captured["artifact_dir"] = artifact_dir
            return df, []

    monkeypatch.setattr(repair_loop, "load_repair_config", lambda path: {"repair_loop": {"max_rounds": 1}})
    monkeypatch.setattr(repair_loop, "RepairLoop", DummyRepairLoop)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "repair_loop.py",
            "--input",
            str(input_path),
            "--tasks",
            str(tasks_path),
            "--output",
            str(output_path),
            "--output-dir",
            str(output_dir),
            "--qa-type",
            "soft",
        ],
    )

    repair_loop.main()

    assert captured["qa_type"] == "soft"
    assert captured["task_count"] == 1
    assert captured["artifact_dir"] == str(output_dir)
    assert output_path.exists()


def test_repair_loop_main_passthrough_copies_input_when_no_tasks(tmp_path, monkeypatch):
    input_path = tmp_path / "translated.csv"
    tasks_path = tmp_path / "repair_tasks.jsonl"
    output_path = tmp_path / "repaired.csv"
    output_dir = tmp_path / "repair_reports" / "soft"

    expected = pd.DataFrame([{"string_id": "1", "target_ru": "kept text"}])
    expected.to_csv(input_path, index=False, encoding="utf-8")
    tasks_path.write_text("", encoding="utf-8")

    monkeypatch.setattr(repair_loop, "load_repair_config", lambda path: {"repair_loop": {"max_rounds": 1}})
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "repair_loop.py",
            "--input",
            str(input_path),
            "--tasks",
            str(tasks_path),
            "--output",
            str(output_path),
            "--output-dir",
            str(output_dir),
            "--qa-type",
            "soft",
        ],
    )

    repair_loop.main()

    actual = pd.read_csv(output_path, dtype=str)
    pd.testing.assert_frame_equal(actual, expected.astype(str))
