#!/usr/bin/env python3
"""Phase 1 runtime closeout contracts for smoke orchestration."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import scripts.run_smoke_pipeline as smoke_pipeline


def _make_args(tmp_path: Path) -> Namespace:
    input_csv = tmp_path / "input.csv"
    style = tmp_path / "style.md"
    style_profile = tmp_path / "style_profile.yaml"
    glossary = tmp_path / "glossary.yaml"
    rubric = tmp_path / "soft_qa_rubric.yaml"
    schema = tmp_path / "schema.yaml"
    forbidden = tmp_path / "forbidden.txt"

    input_csv.write_text("string_id,source_zh\n1,你好\n", encoding="utf-8")
    style.write_text("# style\n", encoding="utf-8")
    style_profile.write_text("{}", encoding="utf-8")
    glossary.write_text("approved: []\n", encoding="utf-8")
    rubric.write_text("{}", encoding="utf-8")
    schema.write_text("patterns: []\npaired_tags: []\n", encoding="utf-8")
    forbidden.write_text("", encoding="utf-8")

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


def test_run_pipeline_repairs_hard_qa_then_completes_with_warn_status(monkeypatch, tmp_path):
    args = _make_args(tmp_path)

    monkeypatch.setattr(smoke_pipeline, "_timestamp", lambda: "20260325_110000")
    monkeypatch.setattr(smoke_pipeline, "_append_symbol_regression_checks", lambda **kwargs: None)

    def fake_run_step(cmd, log_path, env=None):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("ok", encoding="utf-8")
        cmd_text = " ".join(str(part) for part in cmd)

        if "llm_ping.py" in cmd_text:
            return SimpleNamespace(returncode=0, stdout="pong", stderr="")
        if "normalize_guard.py" in cmd_text:
            Path(cmd[3]).write_text("string_id,source_zh\n1,你好\n", encoding="utf-8")
            Path(cmd[4]).write_text(json.dumps({"mappings": {}}), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "translate_llm.py" in cmd_text:
            Path(cmd[cmd.index("--output") + 1]).write_text("string_id,target_ru\n1,плохой\n", encoding="utf-8")
            (Path(args.run_dir) / "llm_trace.jsonl").write_text("{}", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "repair_loop.py" in cmd_text and "--qa-type hard" in cmd_text:
            Path(cmd[cmd.index("--output") + 1]).write_text("string_id,target_ru\n1,исправлено\n", encoding="utf-8")
            output_dir = Path(cmd[cmd.index("--output-dir") + 1])
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "repair_hard_stats.json").write_text(
                json.dumps({"total_tasks": 1, "repaired": 1, "escalated": 0}),
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
            input_path = Path(cmd[2]).name
            report_path = Path(cmd[6])
            if input_path == "smoke_translated.csv":
                report_path.write_text(
                    json.dumps(
                        {
                            "has_errors": True,
                            "errors": [{"string_id": "1", "type": "placeholder", "current_translation": "плохой"}],
                            "metadata": {"total_errors": 1, "total_warnings": 0},
                            "error_counts": {"placeholder": 1},
                        }
                    ),
                    encoding="utf-8",
                )
                return SimpleNamespace(returncode=1, stdout="", stderr="")
            report_path.write_text(
                json.dumps({"has_errors": False, "metadata": {"total_errors": 0, "total_warnings": 0}}),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "rehydrate_export.py" in cmd_text:
            Path(cmd[4]).write_text("string_id,rehydrated_text,target_ru\n1,исправлено,исправлено\n", encoding="utf-8")
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

    exit_code = smoke_pipeline.run_pipeline(args)
    assert exit_code == 0

    manifest = json.loads((Path(args.run_dir) / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "warn"
    assert manifest["overall_status"] == "warn"
    assert manifest["repair_cycles"]["hard"]["status"] == "completed"
    assert manifest["repair_cycles"]["soft"]["status"] == "skipped"
    assert manifest["delivery_decision"]["selected_candidate_stage"] == "repair_hard"
    assert manifest["review_handoff"]["pending_count"] == 0
    assert "Repair Hard" in [stage["name"] for stage in manifest["stages"]]
    assert "QA Hard Recheck" in [stage["name"] for stage in manifest["stages"]]


def test_run_pipeline_marks_failed_status_when_input_is_missing(tmp_path):
    args = _make_args(tmp_path)
    missing_input = tmp_path / "missing.csv"
    Path(args.input).unlink()
    args.input = str(missing_input)

    exit_code = smoke_pipeline.run_pipeline(args)
    assert exit_code == 1

    manifest = json.loads((Path(args.run_dir) / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "failed"
    assert manifest["overall_status"] == "failed"
    assert manifest["status_reason"] == "input_missing"
    assert manifest["gate_summary"]["status"] == "failed"


def test_run_pipeline_rolls_back_soft_repair_and_routes_review_handoff(monkeypatch, tmp_path):
    args = _make_args(tmp_path)

    monkeypatch.setattr(smoke_pipeline, "_timestamp", lambda: "20260325_120000")
    monkeypatch.setattr(smoke_pipeline, "_append_symbol_regression_checks", lambda **kwargs: None)

    def fake_run_step(cmd, log_path, env=None):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("ok", encoding="utf-8")
        cmd_text = " ".join(str(part) for part in cmd)

        if "llm_ping.py" in cmd_text:
            return SimpleNamespace(returncode=0, stdout="pong", stderr="")
        if "normalize_guard.py" in cmd_text:
            Path(cmd[3]).write_text("string_id,source_zh\n1,你好\n", encoding="utf-8")
            Path(cmd[4]).write_text(json.dumps({"mappings": {}}), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "translate_llm.py" in cmd_text:
            Path(cmd[cmd.index("--output") + 1]).write_text("string_id,target_ru\n1,原始译文\n", encoding="utf-8")
            (Path(args.run_dir) / "llm_trace.jsonl").write_text("{}", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "soft_qa_llm.py" in cmd_text:
            Path(cmd[cmd.index("--out_report") + 1]).write_text(
                json.dumps({"has_findings": True, "summary": {"major": 1, "minor": 0, "total_tasks": 1}, "hard_gate": {"status": "fail"}}),
                encoding="utf-8",
            )
            Path(cmd[cmd.index("--out_tasks") + 1]).write_text(
                json.dumps({"string_id": "1", "type": "style_contract", "severity": "major"}) + "\n",
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=2, stdout="", stderr="")
        if "repair_loop.py" in cmd_text and "--qa-type soft" in cmd_text:
            Path(cmd[cmd.index("--output") + 1]).write_text("string_id,target_ru\n1,坏掉的修复\n", encoding="utf-8")
            output_dir = Path(cmd[cmd.index("--output-dir") + 1])
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "repair_soft_stats.json").write_text(
                json.dumps({"total_tasks": 1, "repaired": 1, "escalated": 0}),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "qa_hard.py" in cmd_text:
            report_path = Path(cmd[6])
            input_name = Path(cmd[2]).name
            if input_name == "smoke_repaired_soft.csv":
                report_path.write_text(
                    json.dumps(
                        {
                            "has_errors": True,
                            "errors": [{"string_id": "1", "type": "placeholder", "current_translation": "坏掉的修复"}],
                            "metadata": {"total_errors": 1, "total_warnings": 0},
                            "error_counts": {"placeholder": 1},
                        }
                    ),
                    encoding="utf-8",
                )
                return SimpleNamespace(returncode=1, stdout="", stderr="")
            report_path.write_text(
                json.dumps({"has_errors": False, "metadata": {"total_errors": 0, "total_warnings": 0}}),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "rehydrate_export.py" in cmd_text:
            input_name = Path(cmd[2]).name
            if input_name == "smoke_repaired_soft.csv":
                text = "坏掉的修复"
            else:
                text = "原始译文"
            Path(cmd[4]).write_text(f"string_id,rehydrated_text,target_ru\n1,{text},{text}\n", encoding="utf-8")
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

    exit_code = smoke_pipeline.run_pipeline(args)
    assert exit_code == 0

    manifest = json.loads((Path(args.run_dir) / "run_manifest.json").read_text(encoding="utf-8"))
    final_csv = (Path(args.run_dir) / "smoke_final_export.csv").read_text(encoding="utf-8")

    assert manifest["status"] == "warn"
    assert manifest["delivery_decision"]["rollback_used"] is True
    assert manifest["delivery_decision"]["rollback_reason"] == "soft_repair_failed_hard_gate"
    assert manifest["delivery_decision"]["selected_candidate_stage"] == "translate"
    assert manifest["review_handoff"]["pending_count"] == 1
    assert manifest["review_handoff"]["by_source"] == {"soft_repair_rollback": 1}
    assert "原始译文" in final_csv
    assert "坏掉的修复" not in final_csv


def test_run_pipeline_keeps_non_ru_target_text_in_soft_failure_review_queue(monkeypatch, tmp_path):
    args = _make_args(tmp_path)
    args.target_lang = "en-US"
    args.fallback_target_lang = "en-US"

    monkeypatch.setattr(smoke_pipeline, "_timestamp", lambda: "20260325_123000")
    monkeypatch.setattr(smoke_pipeline, "_append_symbol_regression_checks", lambda **kwargs: None)

    def fake_run_step(cmd, log_path, env=None):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("ok", encoding="utf-8")
        cmd_text = " ".join(str(part) for part in cmd)

        if "llm_ping.py" in cmd_text:
            return SimpleNamespace(returncode=0, stdout="pong", stderr="")
        if "normalize_guard.py" in cmd_text:
            Path(cmd[3]).write_text("string_id,source_zh\n1,你好\n", encoding="utf-8")
            Path(cmd[4]).write_text(json.dumps({"mappings": {}}), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "translate_llm.py" in cmd_text:
            Path(cmd[cmd.index("--output") + 1]).write_text("string_id,target_en\n1,Original EN text\n", encoding="utf-8")
            (Path(args.run_dir) / "llm_trace.jsonl").write_text("{}", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "soft_qa_llm.py" in cmd_text:
            Path(cmd[cmd.index("--out_report") + 1]).write_text(
                json.dumps({"has_findings": True, "summary": {"major": 1, "minor": 0, "total_tasks": 1}, "hard_gate": {"status": "fail"}}),
                encoding="utf-8",
            )
            Path(cmd[cmd.index("--out_tasks") + 1]).write_text(
                json.dumps({"string_id": "1", "type": "style_contract", "severity": "major"}) + "\n",
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=2, stdout="", stderr="")
        if "repair_loop.py" in cmd_text and "--qa-type soft" in cmd_text:
            output_dir = Path(cmd[cmd.index("--output-dir") + 1])
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / "repair_soft_stats.json").write_text(
                json.dumps({"total_tasks": 1, "repaired": 0, "escalated": 0}),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=1, stdout="", stderr="")
        if "qa_hard.py" in cmd_text:
            Path(cmd[6]).write_text(
                json.dumps({"has_errors": False, "metadata": {"total_errors": 0, "total_warnings": 0}}),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "rehydrate_export.py" in cmd_text:
            Path(cmd[4]).write_text("string_id,rehydrated_text,target_en\n1,Original EN text,Original EN text\n", encoding="utf-8")
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

    exit_code = smoke_pipeline.run_pipeline(args)
    assert exit_code == 0

    manifest = json.loads((Path(args.run_dir) / "run_manifest.json").read_text(encoding="utf-8"))
    review_item = manifest["review_handoff"]["items"][0]

    assert manifest["review_handoff"]["pending_count"] == 1
    assert review_item["review_source"] == "soft_repair_execution_failure"
    assert review_item["current_target"] == "Original EN text"


def test_run_pipeline_routes_soft_hard_gate_without_tasks_to_review_queue(monkeypatch, tmp_path):
    args = _make_args(tmp_path)

    monkeypatch.setattr(smoke_pipeline, "_timestamp", lambda: "20260325_130000")
    monkeypatch.setattr(smoke_pipeline, "_append_symbol_regression_checks", lambda **kwargs: None)

    def fake_run_step(cmd, log_path, env=None):
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text("ok", encoding="utf-8")
        cmd_text = " ".join(str(part) for part in cmd)

        if "llm_ping.py" in cmd_text:
            return SimpleNamespace(returncode=0, stdout="pong", stderr="")
        if "normalize_guard.py" in cmd_text:
            Path(cmd[3]).write_text("string_id,source_zh\n1,你好\n", encoding="utf-8")
            Path(cmd[4]).write_text(json.dumps({"mappings": {}}), encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "translate_llm.py" in cmd_text:
            Path(cmd[cmd.index("--output") + 1]).write_text("string_id,target_ru\n1,原始译文\n", encoding="utf-8")
            (Path(args.run_dir) / "llm_trace.jsonl").write_text("{}", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "soft_qa_llm.py" in cmd_text:
            Path(cmd[cmd.index("--out_report") + 1]).write_text(
                json.dumps({"has_findings": False, "summary": {"major": 1, "minor": 0, "total_tasks": 0}, "hard_gate": {"status": "fail"}}),
                encoding="utf-8",
            )
            Path(cmd[cmd.index("--out_tasks") + 1]).write_text("", encoding="utf-8")
            return SimpleNamespace(returncode=2, stdout="", stderr="")
        if "qa_hard.py" in cmd_text:
            Path(cmd[6]).write_text(
                json.dumps({"has_errors": False, "metadata": {"total_errors": 0, "total_warnings": 0}}),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        if "rehydrate_export.py" in cmd_text:
            Path(cmd[4]).write_text("string_id,rehydrated_text,target_ru\n1,原始译文,原始译文\n", encoding="utf-8")
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

    exit_code = smoke_pipeline.run_pipeline(args)
    assert exit_code == 0

    manifest = json.loads((Path(args.run_dir) / "run_manifest.json").read_text(encoding="utf-8"))

    assert manifest["status"] == "warn"
    assert manifest["review_handoff"]["pending_count"] == 1
    assert manifest["review_handoff"]["by_source"] == {"soft_qa_hard_gate": 1}
    assert manifest["delivery_decision"]["selected_candidate_stage"] == "translate"
