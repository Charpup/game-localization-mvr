#!/usr/bin/env python3
"""Contract tests for Batch 2 soft QA boundary clarification."""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import soft_qa_llm


def _write_translated_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["string_id", "source_zh", "target_text", "tokenized_zh"])
        writer.writeheader()
        writer.writerow({
            "string_id": "id1",
            "source_zh": "你好",
            "target_text": "Привет",
            "tokenized_zh": "",
        })
        writer.writerow({
            "string_id": "id2",
            "source_zh": "再见",
            "target_text": "Пока",
            "tokenized_zh": "",
        })


def test_soft_qa_dry_run_uses_batch_utils_and_returns_success(monkeypatch, tmp_path):
    translated = tmp_path / "translated.csv"
    style = tmp_path / "style.md"
    glossary = tmp_path / "missing_glossary.yaml"
    rubric = tmp_path / "soft_qa_rubric.yaml"
    _write_translated_csv(translated)
    style.write_text("official tone", encoding="utf-8")
    rubric.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "soft_qa_llm.py",
            str(translated),
            str(style),
            str(glossary),
            str(rubric),
            "--dry-run",
            "--batch_size",
            "1",
        ],
    )

    assert soft_qa_llm.main() == 0


def test_soft_qa_resume_skips_rows_before_batch_call(monkeypatch, tmp_path):
    translated = tmp_path / "translated.csv"
    style = tmp_path / "style.md"
    rubric = tmp_path / "soft_qa_rubric.yaml"
    report = tmp_path / "reports" / "qa_soft_report.json"
    tasks = tmp_path / "reports" / "repair_tasks.jsonl"
    checkpoint = report.parent / "soft_qa_checkpoint.json"

    _write_translated_csv(translated)
    style.write_text("official tone", encoding="utf-8")
    rubric.write_text("{}", encoding="utf-8")
    report.parent.mkdir(parents=True, exist_ok=True)
    checkpoint.write_text(json.dumps({"rows_processed": 1}), encoding="utf-8")

    captured = {}

    def fake_batch_llm_call(**kwargs):
        captured["rows"] = kwargs["rows"]
        return []

    class FakeLLMClient:
        def __init__(self, *args, **kwargs):
            self.default_model = "fake-model"

    class FakeConfig:
        def get_batch_size(self, model, content_type="normal"):
            return 10

    monkeypatch.setattr(soft_qa_llm, "batch_llm_call", fake_batch_llm_call)
    monkeypatch.setattr(soft_qa_llm, "get_batch_config", lambda: FakeConfig())
    monkeypatch.setattr(soft_qa_llm, "LLMClient", FakeLLMClient)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "soft_qa_llm.py",
            str(translated),
            str(style),
            str(tmp_path / "missing_glossary.yaml"),
            str(rubric),
            "--resume",
            "--out_report",
            str(report),
            "--out_tasks",
            str(tasks),
        ],
    )

    assert soft_qa_llm.main() == 0
    assert [row["id"] for row in captured["rows"]] == ["id2"]


def test_soft_qa_optional_feature_flags_degrade_gracefully(monkeypatch, tmp_path):
    translated = tmp_path / "translated.csv"
    style = tmp_path / "style.md"
    rubric = tmp_path / "soft_qa_rubric.yaml"
    _write_translated_csv(translated)
    style.write_text("official tone", encoding="utf-8")
    rubric.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(soft_qa_llm, "HAS_RAG", False)
    monkeypatch.setattr(soft_qa_llm, "HAS_SEMANTIC", False)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "soft_qa_llm.py",
            str(translated),
            str(style),
            str(tmp_path / "missing_glossary.yaml"),
            str(rubric),
            "--dry-run",
            "--enable-rag",
            "--enable-semantic",
        ],
    )

    assert soft_qa_llm.main() == 0


def test_soft_qa_emits_tasks_without_becoming_a_blocking_gate(monkeypatch, tmp_path):
    translated = tmp_path / "translated.csv"
    style = tmp_path / "style.md"
    rubric = tmp_path / "soft_qa_rubric.yaml"
    report = tmp_path / "reports" / "qa_soft_report.json"
    tasks = tmp_path / "reports" / "repair_tasks.jsonl"
    _write_translated_csv(translated)
    style.write_text("official tone", encoding="utf-8")
    rubric.write_text("{}", encoding="utf-8")

    def fake_batch_llm_call(**kwargs):
        return [{
            "id": "id1",
            "issue_type": "format",
            "severity": "major",
            "problem": "Placeholder style issue",
            "suggestion": "Keep placeholder intact",
            "preferred_fix_ru": "Привет {0}",
        }]

    class FakeLLMClient:
        def __init__(self, *args, **kwargs):
            self.default_model = "fake-model"

    class FakeConfig:
        def get_batch_size(self, model, content_type="normal"):
            return 10

    monkeypatch.setattr(soft_qa_llm, "batch_llm_call", fake_batch_llm_call)
    monkeypatch.setattr(soft_qa_llm, "get_batch_config", lambda: FakeConfig())
    monkeypatch.setattr(soft_qa_llm, "LLMClient", FakeLLMClient)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "soft_qa_llm.py",
            str(translated),
            str(style),
            str(tmp_path / "missing_glossary.yaml"),
            str(rubric),
            "--out_report",
            str(report),
            "--out_tasks",
            str(tasks),
        ],
    )

    assert soft_qa_llm.main() == 0
    report_data = json.loads(report.read_text(encoding="utf-8"))
    assert report_data["has_findings"] is True
    assert report_data["summary"]["major"] == 1
    task_lines = tasks.read_text(encoding="utf-8").strip().splitlines()
    assert len(task_lines) == 1
    task = json.loads(task_lines[0])
    assert task["string_id"] == "id1"
    assert task["severity"] == "major"


def test_merge_tasks_prefers_placeholder_over_lower_priority_length():
    merged = soft_qa_llm.merge_tasks(
        pref=[
            {"string_id": "id1", "type": "length", "severity": "minor"},
            {"string_id": "id1", "type": "placeholder", "severity": "major"},
        ],
        llm_tasks=[],
        cap_per_row=1,
    )

    assert len(merged) == 1
    assert merged[0]["type"] == "placeholder"
    assert merged[0]["severity"] == "major"


def test_preflight_tasks_flags_prohibited_aliases_and_banned_terms():
    tasks = soft_qa_llm.preflight_tasks(
        rows=[
            {
                "string_id": "id1",
                "source_zh": "问候",
                "target_text": "Запретный вариант",
                "tokenized_zh": "",
            },
            {
                "string_id": "id2",
                "source_zh": "奖励",
                "target_text": "Нежелательный термин",
                "tokenized_zh": "",
            },
        ],
        style_profile={
            "terminology": {
                "prohibited_aliases": ["问候 -> Запретный вариант"],
                "banned_terms": ["Нежелательный термин"],
            }
        },
        glossary_entries=[],
    )

    notes = {task["string_id"]: task["note"] for task in tasks}
    assert notes["id1"] == "prohibited alias Запретный вариант"
    assert notes["id2"] == "blocked term Нежелательный термин"


def test_style_contract_block_lists_aliases_and_banned_terms():
    block = soft_qa_llm.build_style_contract_block(
        {
            "project": {"source_language": "zh-CN", "target_language": "ru-RU"},
            "style_contract": {
                "language_policy": {},
                "placeholder_protection": {},
                "style_guard": {},
            },
            "ui": {"length_constraints": {}},
            "terminology": {
                "banned_terms": ["Нежелательный термин"],
                "prohibited_aliases": ["问候 -> Запретный вариант"],
            },
        }
    )

    assert "- Banned term: Нежелательный термин" in block
    assert "- Prohibited alias: Запретный вариант" in block
