from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import soft_qa_llm
import translate_llm


def _write_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_translate_llm_fails_closed_on_runtime_governance(monkeypatch, tmp_path):
    input_csv = tmp_path / "input.csv"
    output_csv = tmp_path / "output.csv"
    style_md = tmp_path / "style.md"

    _write_csv(input_csv, [{"string_id": "1", "source_zh": "你好", "tokenized_zh": "你好"}])
    style_md.write_text("# style\n", encoding="utf-8")

    monkeypatch.setattr(
        translate_llm,
        "evaluate_runtime_governance",
        lambda **_kwargs: {"passed": False, "issues": ["STYLE_RUNTIME_E999 blocked"]},
    )
    monkeypatch.setattr(translate_llm, "configure_standard_streams", lambda: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "translate_llm.py",
            "--input",
            str(input_csv),
            "--output",
            str(output_csv),
            "--style",
            str(style_md),
            "--glossary",
            "glossary/compiled.yaml",
            "--style-profile",
            "data/style_profile.yaml",
        ],
    )

    assert translate_llm.main() == 1
    assert not output_csv.exists()


def test_soft_qa_governance_failure_writes_report_and_tasks(monkeypatch, tmp_path):
    translated_csv = tmp_path / "translated.csv"
    style_md = tmp_path / "style.md"
    rubric_yaml = tmp_path / "rubric.yaml"
    report_json = tmp_path / "qa_soft_report.json"
    tasks_jsonl = tmp_path / "repair_tasks.jsonl"

    _write_csv(
        translated_csv,
        [
            {
                "string_id": "1",
                "source_zh": "你好",
                "target_text": "Привет",
            }
        ],
    )
    style_md.write_text("# style\n", encoding="utf-8")
    rubric_yaml.write_text("gate:\n  enabled: true\n  severity_threshold: major\n  fail_on_types:\n    - style_contract\n", encoding="utf-8")

    monkeypatch.setattr(
        soft_qa_llm,
        "evaluate_runtime_governance",
        lambda **_kwargs: {"passed": False, "issues": ["STYLE_RUNTIME_E999 blocked"]},
    )
    monkeypatch.setattr(soft_qa_llm, "configure_standard_streams", lambda: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "soft_qa_llm.py",
            str(translated_csv),
            str(style_md),
            "data/glossary.yaml",
            str(rubric_yaml),
            "--style-profile",
            "data/style_profile.yaml",
            "--out_report",
            str(report_json),
            "--out_tasks",
            str(tasks_jsonl),
        ],
    )

    assert soft_qa_llm.main() == 2

    report = json.loads(report_json.read_text(encoding="utf-8"))
    tasks = [json.loads(line) for line in tasks_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert report["hard_gate"]["status"] == "fail"
    assert report["hard_gate"]["rule_id"] == "PHASE3_STYLE_GOVERNANCE"
    assert report["metadata"]["runtime_governance"]["passed"] is False
    assert tasks[0]["rule_id"] == "D-SQA-009"
    assert tasks[0]["severity"] == "major"
    assert tasks[0]["governance_issues"] == ["STYLE_RUNTIME_E999 blocked"]
