#!/usr/bin/env python3
"""Fixture contracts for Batch 2 normalize_* audit."""

import csv
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import normalize_ingest
import normalize_tagger
import normalize_tag_llm


def test_normalize_headers_maps_aliases_to_standard_names():
    df = pd.DataFrame(
        {
            "ID": ["001"],
            "Source": ["你好"],
            "Context": ["menu"],
            "Other": ["keep-out"],
        }
    )

    normalized = normalize_ingest.normalize_headers(df)

    assert "string_id" in normalized.columns
    assert "source_zh" in normalized.columns
    assert "context" in normalized.columns
    assert normalized.loc[0, "string_id"] == "001"


def test_ingest_file_enforces_output_schema_and_fills_empty_values(tmp_path):
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "out" / "source_raw.csv"
    input_path.write_text(
        "ID,Source,Context,Other\n001,你好,,drop-me\n002,再见,shop,drop-too\n",
        encoding="utf-8",
    )

    assert normalize_ingest.ingest_file(str(input_path), str(output_path)) is True

    with output_path.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    assert rows[0]["string_id"] == "001"
    assert rows[0]["source_zh"] == "你好"
    assert rows[0]["context"] == ""
    assert "source_locale" in rows[0]
    assert "Other" not in rows[0]


def test_ingest_file_fails_when_required_columns_are_missing(tmp_path):
    input_path = tmp_path / "input.csv"
    output_path = tmp_path / "out" / "source_raw.csv"
    input_path.write_text("ID,Context\n001,menu\n", encoding="utf-8")

    assert normalize_ingest.ingest_file(str(input_path), str(output_path)) is False
    assert output_path.exists() is False


def test_normalize_tagger_prefix_rule_and_llm_fallback_preserve_rows(monkeypatch, tmp_path):
    input_path = tmp_path / "normalized_source.csv"
    input_path.write_text(
        "string_id,source_zh\nBTN_OK,确定\nMISC_01,普通说明文本\n",
        encoding="utf-8",
    )

    def fake_llm_tag_fallback(low_conf_entries, model):
        assert [entry["string_id"] for entry in low_conf_entries] == ["MISC_01"]
        return {"MISC_01": ("dialogue", 0.91)}

    monkeypatch.setattr(normalize_tagger, "llm_tag_fallback", fake_llm_tag_fallback)

    results = normalize_tagger.process_entries(
        str(input_path),
        source_locale="zh-CN",
        llm_threshold=0.7,
        use_llm=True,
        model="claude-haiku-4-5-20251001",
    )

    assert len(results) == 2
    assert results[0].string_id == "BTN_OK"
    assert results[0].module_tag == "ui_button"
    assert results[0].module_confidence == 0.95
    assert results[1].string_id == "MISC_01"
    assert results[1].status == "llm_tagged"
    assert results[1].module_tag == "dialogue"


def test_normalize_tag_llm_uses_length_rules_contract():
    rules = {
        "default": {"multiplier": 3.0, "min_buffer": 5, "max_absolute": 500},
        "by_content_type": {
            "ui_button": {"multiplier": 3.5, "min_buffer": 5, "max_absolute": 20},
        },
    }

    max_len = normalize_tag_llm.calculate_max_len_target("攻击", "ui_button", rules)

    assert max_len == 12
