#!/usr/bin/env python3
"""Deterministic contract tests for the retained validation baseline."""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest


ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = ROOT / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import build_validation_set
import run_validation


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _sample_source_rows() -> list[dict[str, str]]:
    return [
        {"string_id": "ui-1", "source_zh": "确定"},
        {"string_id": "ui-2", "source_zh": "返回"},
        {"string_id": "dialogue-1", "source_zh": "这是一段很长很长的剧情文本，用来确保被分类到对白层级之一。"},
        {"string_id": "dialogue-2", "source_zh": "另一段很长很长的剧情文本，同样应该稳定地进入对白分层集合。"},
        {"string_id": "system-1", "source_zh": "系统提示：操作失败，请稍后重试"},
        {"string_id": "placeholder-1", "source_zh": "造成{0}%伤害并附加⟦PH_1⟧效果"},
    ]


def test_stratified_sample_fills_requested_rows_when_capacity_exists():
    rows = _sample_source_rows()

    selected, counts = build_validation_set.stratified_sample(rows, total_count=5, seed=42)

    assert len(selected) == 5
    assert sum(counts.values()) == 5
    assert len({row["string_id"] for row in selected}) == 5


def test_build_validation_set_main_writes_contract_metadata(monkeypatch, tmp_path):
    source_path = tmp_path / "draft.csv"
    output_dir = tmp_path / "out"
    _write_csv(source_path, _sample_source_rows())

    monkeypatch.setattr(build_validation_set, "VALID_ROW_COUNTS", [5])
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_validation_set.py",
            "--source",
            str(source_path),
            "--rows",
            "5",
            "--output-dir",
            str(output_dir),
            "--seed",
            "7",
        ],
    )

    build_validation_set.main()

    meta_path = output_dir / "validation_5_v1.meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))

    assert meta["target_rows"] == 5
    assert meta["actual_rows"] == 5
    assert meta["source_sha256"] == build_validation_set.calculate_sha256(str(source_path))
    assert meta["input_columns"] == ["string_id", "source_zh"]
    assert meta["output_columns"] == ["string_id", "source_zh"]
    assert meta["required_columns"] == ["string_id"]
    assert meta["source_text_columns"] == ["source_zh", "tokenized_zh"]


def test_run_validation_main_writes_report_and_csv_contract(monkeypatch, tmp_path):
    validation_rows = [
        {"string_id": "row-1", "source_zh": "你好"},
        {"string_id": "row-2", "source_zh": "世界"},
    ]
    _write_csv(tmp_path / "data" / "validation_2_v1.csv", validation_rows)

    frozen_now = datetime(2026, 1, 20, 19, 7, 53)

    class FrozenDateTime:
        @staticmethod
        def now() -> datetime:
            return frozen_now

    class FakeClient:
        def chat(self, **kwargs):
            payload = json.loads(kwargs["user"])
            return type(
                "Resp",
                (),
                {
                    "text": json.dumps(
                        [
                            {"string_id": item["string_id"], "target_ru": f"ru::{item['tokenized_zh']}"}
                            for item in payload
                        ],
                        ensure_ascii=False,
                    ),
                    "latency_ms": 12,
                },
            )()

    captured = {}
    api_key_path = tmp_path / "attachment" / "api_key.txt"
    api_key_path.parent.mkdir(parents=True, exist_ok=True)
    api_key_path.write_text("test-key", encoding="utf-8")
    output_dir = tmp_path / "validation_outputs"
    report_dir = tmp_path / "validation_reports"

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_validation, "VALID_ROW_COUNTS", [2])
    monkeypatch.setattr(run_validation, "datetime", FrozenDateTime)
    monkeypatch.setattr(run_validation, "resolve_api_credentials", lambda args: captured.setdefault("api_key_path", args.api_key_path))
    monkeypatch.setattr(run_validation, "load_pricing", lambda: {})
    monkeypatch.setattr(run_validation, "LLMClient", FakeClient)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_validation.py",
            "--model",
            "demo/model",
            "--rows",
            "2",
            "--input",
            str(tmp_path / "data" / "validation_2_v1.csv"),
            "--output-dir",
            str(output_dir),
            "--report-dir",
            str(report_dir),
            "--api-key-path",
            str(api_key_path),
        ],
    )

    run_validation.main()

    output_csv = output_dir / "validation_2_output_demo_model.csv"
    report_json = report_dir / "validation_2_demo_model_20260120_190753.json"

    assert output_csv.exists()
    assert report_json.exists()
    assert captured["api_key_path"] == str(api_key_path)

    with output_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        output_rows = list(reader)

    assert reader.fieldnames == ["string_id", "source_zh", "target_ru", "status"]
    assert output_rows == [
        {"string_id": "row-1", "source_zh": "你好", "target_ru": "ru::你好", "status": "translated"},
        {"string_id": "row-2", "source_zh": "世界", "target_ru": "ru::世界", "status": "translated"},
    ]

    report = json.loads(report_json.read_text(encoding="utf-8"))

    assert report["report_version"] == "validation.v1"
    assert report["output_csv"] == str(output_csv)
    assert report["output_csv_sha256"] == run_validation.calculate_sha256(str(output_csv))
    assert report["input_columns"] == ["string_id", "source_zh"]
    assert report["output_columns"] == ["string_id", "source_zh", "target_ru", "status"]
    assert report["metrics"]["total_rows"] == 2
    assert report["metrics"]["missing_count"] == 0
    assert report["metrics"]["parse_error_count"] == 0
    assert report["report_path"] == str(report_json)


def test_run_validation_main_rejects_row_count_mismatch(monkeypatch, tmp_path):
    _write_csv(tmp_path / "data" / "validation_2_v1.csv", [{"string_id": "row-1", "source_zh": "你好"}])

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(run_validation, "VALID_ROW_COUNTS", [2])
    monkeypatch.setattr(sys, "argv", ["run_validation.py", "--model", "demo", "--rows", "2"])

    with pytest.raises(SystemExit) as exc:
        run_validation.main()

    assert exc.value.code == 1


def test_compute_score_uses_fixed_weight_formula():
    score = run_validation.compute_score(
        {
            "missing_rate": 0.10,
            "escalation_rate": 0.20,
            "parse_error_rate": 0.30,
            "cost_norm": 0.40,
        }
    )

    assert score == pytest.approx(80.0)


def test_run_batch_accepts_wrapped_result_lists(monkeypatch):
    class FakeClient:
        def chat(self, **kwargs):
            return type(
                "Resp",
                (),
                {
                    "text": json.dumps(
                        {
                            "results": [
                                {"string_id": "row-1", "target_ru": "ru::你好"},
                                {"string_id": "row-2", "target_ru": "ru::世界"},
                            ]
                        },
                        ensure_ascii=False,
                    ),
                    "latency_ms": 8,
                },
            )()

    result = run_validation.run_batch(
        FakeClient(),
        [
            {"string_id": "row-1", "source_zh": "你好"},
            {"string_id": "row-2", "source_zh": "世界"},
        ],
        "demo/model",
    )

    assert result["success"] is True
    assert result["parse_error"] is False
    assert result["missing_ids"] == []
    assert result["translations"] == {"row-1": "ru::你好", "row-2": "ru::世界"}


def test_run_batch_extracts_embedded_json_array_from_text(monkeypatch):
    class FakeClient:
        def chat(self, **kwargs):
            return type(
                "Resp",
                (),
                {
                    "text": 'prefix [{"string_id":"row-1","target_ru":"ru::你好"}] suffix',
                    "latency_ms": 9,
                },
            )()

    result = run_validation.run_batch(
        FakeClient(),
        [{"string_id": "row-1", "source_zh": "你好"}],
        "demo/model",
    )

    assert result["success"] is True
    assert result["parse_error"] is False
    assert result["missing_ids"] == []
    assert result["translations"] == {"row-1": "ru::你好"}


def test_repro_baseline_documents_explicit_validation_contract():
    repro = (ROOT / "docs" / "repro_baseline.md").read_text(encoding="utf-8")

    assert "--source data/draft.csv" in repro
    assert "--rows 100" in repro
    assert "--seed 42" in repro
    assert "--input data/validation_100_v1.csv" in repro
    assert "--output-dir reports" in repro
    assert "--report-dir reports" in repro
    assert "--api-key-path data/attachment/api_key.txt" in repro
    assert "config/api_key.txt" not in repro
