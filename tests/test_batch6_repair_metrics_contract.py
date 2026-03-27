#!/usr/bin/env python3
"""Contracts for Batch 6 repair contract retirement and metrics rewiring."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import scripts.metrics_aggregator as metrics_aggregator
import scripts.run_smoke_pipeline as smoke_pipeline
import scripts.smoke_verify as smoke_verify


ROOT = Path(__file__).parent.parent


def _inventory_path() -> Path:
    candidates = [
        ROOT / "SCRIPTS_INVENTORY.md",
        ROOT / "game-localization-mvr" / "SCRIPTS_INVENTORY.md",
        ROOT.parent / "SCRIPTS_INVENTORY.md",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("SCRIPTS_INVENTORY.md not found in expected repo roots")


def test_batch4_inventory_tracks_repair_targets_as_archived_or_ready_to_archive():
    inventory = json.loads((ROOT / "workflow" / "batch4_frozen_zone_inventory.json").read_text(encoding="utf-8"))
    statuses = {item["path"]: item["status"] for item in inventory["surfaces"]}

    assert statuses["scripts/repair_loop_v2.py"] in {"archive-candidate", "archive-complete"}
    assert statuses["scripts/repair_checkpoint_gaps.py"] in {"archive-candidate", "archive-complete"}


def test_rules_and_inventory_retire_repair_loop_v2_from_current_tooling():
    rules = (ROOT / ".agent" / "rules" / "localization-mvr-rules.md").read_text(encoding="utf-8")
    inventory = _inventory_path().read_text(encoding="utf-8")

    assert "repair_loop_v2.py" in rules
    assert "历史归档" in rules or "历史候选保留" in rules
    assert "scripts/repair_loop_v2.py" not in rules
    assert "python3 repair_loop_v2.py" not in inventory
    assert "repair_loop.py | 修复循环 v1 | retained repair authority" in inventory
    assert "repair_loop_v2.py" in inventory


def test_loc_translate_promotes_rebuild_checkpoint_as_retained_recovery_path():
    workflow = (ROOT / ".agent" / "workflows" / "loc-translate.md").read_text(encoding="utf-8")

    assert "rebuild_checkpoint.py" in workflow
    assert "repair_checkpoint_gaps.py" in workflow
    assert "历史问题处理脚本" in workflow or "历史归档" in workflow


def test_metrics_aggregator_uses_trace_usage_and_estimates_missing_tokens():
    events = [
        {
            "step": "translate",
            "event": "batch_complete",
            "rows_in_batch": 4,
            "latency_ms": 100,
            "status": "ok",
            "model": "gpt-4.1-mini",
            "request_id": "req-1",
        },
        {
            "step": "translate",
            "event": "batch_complete",
            "rows_in_batch": 2,
            "latency_ms": 50,
            "status": "ok",
            "model": "gpt-4.1-mini",
            "request_id": "req-2",
        },
    ]
    trace_events = [
        {
            "request_id": "req-1",
            "usage": {"prompt_tokens": 100, "completion_tokens": 40},
        },
        {
            "request_id": "req-2",
            "req_chars": 40,
            "resp_chars": 20,
        },
    ]
    pricing = {
        "models": {
            "gpt-4.1-mini": {"input_per_1M": 1.0, "output_per_1M": 2.0},
            "_default": {"input_per_1M": 3.0, "output_per_1M": 4.0},
        }
    }

    metrics = metrics_aggregator.aggregate_metrics(events, trace_events, pricing)

    assert metrics["summary"]["total_rows"] == 6
    assert metrics["summary"]["total_prompt_tokens"] == 110
    assert metrics["summary"]["total_completion_tokens"] == 45
    assert metrics["summary"]["total_tokens"] == 155
    assert metrics["summary"]["estimated_cost_usd"] > 0


def _make_args(tmp_path: Path) -> Namespace:
    style = tmp_path / "style.md"
    style_profile = tmp_path / "style_profile.yaml"
    glossary = tmp_path / "glossary.yaml"
    rubric = tmp_path / "soft_qa_rubric.yaml"
    schema = tmp_path / "schema.yaml"
    forbidden = tmp_path / "forbidden.txt"
    input_csv = tmp_path / "input.csv"
    style.write_text("style", encoding="utf-8")
    style_profile.write_text("{}", encoding="utf-8")
    glossary.write_text("approved: []\n", encoding="utf-8")
    rubric.write_text("{}", encoding="utf-8")
    schema.write_text("placeholders: []\n", encoding="utf-8")
    forbidden.write_text("", encoding="utf-8")
    input_csv.write_text("string_id,source_zh\n1,你好\n", encoding="utf-8")

    return Namespace(
        input=str(input_csv),
        run_dir=str(tmp_path / "run"),
        target_lang="ru-RU",
        fallback_target_lang="ru-RU",
        disable_target_fallback=False,
        enable_target_fallback=True,
        verify_mode="full",
        model="claude-haiku-4-5-20251001",
        style=str(style),
        style_profile=str(style_profile),
        glossary=str(glossary),
        soft_qa_rubric=str(rubric),
        schema=str(schema),
        forbidden=str(forbidden),
        source_lang="zh-CN",
        long_text_threshold=200,
        log_level="INFO",
    )


def test_run_pipeline_writes_optional_metrics_artifacts(monkeypatch, tmp_path):
    args = _make_args(tmp_path)

    monkeypatch.setattr(smoke_pipeline, "_timestamp", lambda: "20260319_120000")
    monkeypatch.setattr(smoke_pipeline, "_count_csv_rows", lambda path: 1)
    monkeypatch.setattr(smoke_pipeline, "_read_rows_as_dict", lambda path, key_field: {"1": {"string_id": "1", "source_zh": "你好", "rehydrated_text": "privet"}})
    monkeypatch.setattr(smoke_pipeline, "_append_symbol_regression_checks", lambda **kwargs: None)

    def fake_run_step(cmd, log_path, env=None):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("ok", encoding="utf-8")
        cmd_text = " ".join(str(part) for part in cmd)

        if "llm_ping.py" in cmd_text:
            return SimpleNamespace(returncode=0, stdout="pong", stderr="")
        if "normalize_guard.py" in cmd_text:
            Path(cmd[3]).write_text("string_id,source_zh\n1,你好\n", encoding="utf-8")
            Path(cmd[4]).write_text("{}", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "translate_llm.py" in cmd_text:
            Path(cmd[cmd.index("--output") + 1]).write_text("string_id,target_ru\n1,привет\n", encoding="utf-8")
            (Path(args.run_dir) / "translate_progress.jsonl").write_text(
                json.dumps({"step": "translate", "event": "step_start", "model": "claude-haiku-4-5-20251001"}) + "\n"
                + json.dumps(
                    {
                        "step": "translate",
                        "event": "batch_complete",
                        "rows_in_batch": 1,
                        "latency_ms": 50,
                        "status": "ok",
                        "model": "claude-haiku-4-5-20251001",
                        "request_id": "req-1",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            (Path(args.run_dir) / "llm_trace.jsonl").write_text(
                json.dumps({"request_id": "req-1", "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}) + "\n",
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "soft_qa_llm.py" in cmd_text:
            Path(cmd[cmd.index("--out_report") + 1]).write_text(
                json.dumps({"has_findings": False, "summary": {"major": 0, "minor": 0, "total_tasks": 0}, "hard_gate": {"status": "pass"}}),
                encoding="utf-8",
            )
            Path(cmd[cmd.index("--out_tasks") + 1]).write_text("", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "qa_hard.py" in cmd_text:
            Path(cmd[6]).write_text(json.dumps({"has_errors": False, "metadata": {"total_errors": 0, "total_warnings": 0}}), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "rehydrate_export.py" in cmd_text:
            Path(cmd[4]).write_text("string_id,rehydrated_text,target_ru\n1,привет,привет\n", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "metrics_aggregator.py" in cmd_text:
            output_base = Path(cmd[cmd.index("--output") + 1])
            output_base.with_suffix(".md").write_text("# metrics\n", encoding="utf-8")
            output_base.with_suffix(".json").write_text(json.dumps({"summary": {"total_tokens": 10}}), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "smoke_verify.py" in cmd_text:
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(smoke_pipeline, "_run_step", fake_run_step)

    rc = smoke_pipeline.run_pipeline(args)
    assert rc == 0

    manifest = json.loads((Path(args.run_dir) / "run_manifest.json").read_text(encoding="utf-8"))
    stage_names = [stage["name"] for stage in manifest["stages"]]

    assert "Metrics" in stage_names
    assert manifest["artifacts"]["metrics_report"] == [
        str(Path(args.run_dir) / "smoke_metrics_report.md"),
        str(Path(args.run_dir) / "smoke_metrics_report.json"),
    ]
    assert manifest["stage_artifacts"]["metrics_report_md"].endswith("smoke_metrics_report.md")
    assert manifest["stage_artifacts"]["metrics_report_json"].endswith("smoke_metrics_report.json")


def test_run_pipeline_does_not_block_on_metrics_failure(monkeypatch, tmp_path):
    args = _make_args(tmp_path)

    monkeypatch.setattr(smoke_pipeline, "_timestamp", lambda: "20260319_120001")
    monkeypatch.setattr(smoke_pipeline, "_count_csv_rows", lambda path: 1)
    monkeypatch.setattr(smoke_pipeline, "_read_rows_as_dict", lambda path, key_field: {"1": {"string_id": "1", "source_zh": "你好", "rehydrated_text": "privet"}})
    monkeypatch.setattr(smoke_pipeline, "_append_symbol_regression_checks", lambda **kwargs: None)

    def fake_run_step(cmd, log_path, env=None):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("ok", encoding="utf-8")
        cmd_text = " ".join(str(part) for part in cmd)

        if "llm_ping.py" in cmd_text:
            return SimpleNamespace(returncode=0, stdout="pong", stderr="")
        if "normalize_guard.py" in cmd_text:
            Path(cmd[3]).write_text("string_id,source_zh\n1,你好\n", encoding="utf-8")
            Path(cmd[4]).write_text("{}", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "translate_llm.py" in cmd_text:
            Path(cmd[cmd.index("--output") + 1]).write_text("string_id,target_ru\n1,привет\n", encoding="utf-8")
            (Path(args.run_dir) / "translate_progress.jsonl").write_text(
                json.dumps({"step": "translate", "event": "step_start", "model": "claude-haiku-4-5-20251001"}) + "\n"
                + json.dumps(
                    {
                        "step": "translate",
                        "event": "batch_complete",
                        "rows_in_batch": 1,
                        "latency_ms": 50,
                        "status": "ok",
                        "model": "claude-haiku-4-5-20251001",
                        "request_id": "req-1",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "soft_qa_llm.py" in cmd_text:
            Path(cmd[cmd.index("--out_report") + 1]).write_text(
                json.dumps({"has_findings": False, "summary": {"major": 0, "minor": 0, "total_tasks": 0}, "hard_gate": {"status": "pass"}}),
                encoding="utf-8",
            )
            Path(cmd[cmd.index("--out_tasks") + 1]).write_text("", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "qa_hard.py" in cmd_text:
            Path(cmd[6]).write_text(json.dumps({"has_errors": False, "metadata": {"total_errors": 0, "total_warnings": 0}}), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "rehydrate_export.py" in cmd_text:
            Path(cmd[4]).write_text("string_id,rehydrated_text,target_ru\n1,привет,привет\n", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "metrics_aggregator.py" in cmd_text:
            return SimpleNamespace(returncode=2, stdout="", stderr="metrics failed")
        if "smoke_verify.py" in cmd_text:
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        raise AssertionError(f"Unexpected command: {cmd}")

    monkeypatch.setattr(smoke_pipeline, "_run_step", fake_run_step)

    rc = smoke_pipeline.run_pipeline(args)
    assert rc == 0

    manifest = json.loads((Path(args.run_dir) / "run_manifest.json").read_text(encoding="utf-8"))
    metrics_stage = next(stage for stage in manifest["stages"] if stage["name"] == "Metrics")
    assert metrics_stage["required"] is False
    assert metrics_stage["status"] == "warn"


def test_smoke_verify_accepts_manifest_metrics_report_list(tmp_path):
    metrics_md = tmp_path / "smoke_metrics_report.md"
    metrics_json = tmp_path / "smoke_metrics_report.json"
    qa_report = tmp_path / "smoke_qa_hard_report.json"
    final_csv = tmp_path / "smoke_final_export.csv"
    metrics_md.write_text("# metrics\n", encoding="utf-8")
    metrics_json.write_text("{}", encoding="utf-8")
    qa_report.write_text(json.dumps({"has_errors": False, "metadata": {"total_errors": 0, "total_warnings": 0}}), encoding="utf-8")
    final_csv.write_text("string_id,rehydrated_text\n1,ok\n", encoding="utf-8")

    manifest = tmp_path / "run_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "run_id": "smoke_run_batch6",
                "artifacts": {"metrics_report": [str(metrics_md), str(metrics_json)]},
                "stage_artifacts": {"final_csv": str(final_csv)},
                "stages": [
                    {"name": "QA Hard", "required": True, "files": [{"path": str(qa_report), "required": True}]},
                    {"name": "Export", "required": True, "files": [{"path": str(final_csv), "required": True}]},
                    {"name": "Metrics", "required": False, "files": [{"path": str(metrics_md), "required": True}, {"path": str(metrics_json), "required": True}]},
                ],
            }
        ),
        encoding="utf-8",
    )

    issue_file = tmp_path / "issues.json"
    assert smoke_verify.run_verify(str(manifest), "full", str(issue_file)) is True
