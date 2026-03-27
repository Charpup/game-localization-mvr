import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import glossary_delta


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(glossary_delta.yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    import csv

    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_style_profile_changes_propagate_without_glossary_diff(monkeypatch, tmp_path):
    glossary_path = tmp_path / "glossary.yaml"
    old_style = tmp_path / "old_style.yaml"
    new_style = tmp_path / "new_style.yaml"
    csv_path = tmp_path / "translated.csv"
    report_path = tmp_path / "delta_report.json"
    rows_path = tmp_path / "delta_rows.jsonl"

    _write_yaml(glossary_path, {"entries": [{"term_zh": "木叶", "term_ru": "Коноха"}]})
    _write_yaml(
        old_style,
        {
            "project": {"target_language": "ru-RU"},
            "terminology": {
                "preferred_terms": [{"term_zh": "木叶", "term_ru": "Старая Коноха"}],
                "banned_terms": [],
                "prohibited_aliases": [],
            },
            "style_contract": {"tone": {"register": "neutral"}},
            "ui": {"length_constraints": {"button_max_chars": 18}},
        },
    )
    _write_yaml(
        new_style,
        {
            "project": {"target_language": "ru-RU"},
            "terminology": {
                "preferred_terms": [{"term_zh": "木叶", "term_ru": "Коноха"}],
                "banned_terms": ["Запретный термин"],
                "prohibited_aliases": ["木叶 -> Старая Коноха"],
            },
            "style_contract": {"tone": {"register": "formal"}},
            "ui": {"length_constraints": {"button_max_chars": 12}},
        },
    )
    _write_csv(
        csv_path,
        [
            {
                "string_id": "1",
                "source_zh": "木叶入口",
                "target_text": "Старая Коноха",
                "module_tag": "ui_button",
            }
        ],
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "glossary_delta.py",
            "--old",
            str(glossary_path),
            "--new",
            str(glossary_path),
            "--old-style-profile",
            str(old_style),
            "--new-style-profile",
            str(new_style),
            "--source_csv",
            str(csv_path),
            "--out_impact",
            str(report_path),
            "--out_rows",
            str(rows_path),
        ],
    )

    assert glossary_delta.main() == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    row = json.loads(rows_path.read_text(encoding="utf-8").strip())

    assert report["change_counts"]["preferred_term_changed"] == 1
    assert report["change_counts"]["banned_term_changed"] == 1
    assert report["change_counts"]["prohibited_alias_changed"] == 1
    assert report["change_counts"]["style_contract_changed"] == 1
    assert report["change_counts"]["risk_class_changed"] == 1
    assert "STYLE_PREFERRED_TERM_CHANGED" in row["reason_codes"]
    assert "STYLE_PROHIBITED_ALIAS_CHANGED" in row["reason_codes"]
    assert row["manual_review_required"] is True
    assert row["recommended_action"] == "manual_review"


def test_typed_delta_ignores_ru_legacy_targets_for_en_us(monkeypatch, tmp_path):
    old_glossary = tmp_path / "old.yaml"
    new_glossary = tmp_path / "new.yaml"
    csv_path = tmp_path / "translated.csv"
    report_path = tmp_path / "delta_report.json"
    rows_path = tmp_path / "delta_rows.jsonl"

    _write_yaml(old_glossary, {"entries": [{"term_zh": "火影", "term_ru": "Хокаге"}]})
    _write_yaml(new_glossary, {"entries": [{"term_zh": "火影", "term_ru": "Наруто"}]})
    _write_csv(
        csv_path,
        [
            {
                "string_id": "1",
                "source_zh": "普通文本",
                "target_text": "Хокаге",
                "target_locale": "en-US",
                "module_tag": "general",
            }
        ],
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "glossary_delta.py",
            "--old",
            str(old_glossary),
            "--new",
            str(new_glossary),
            "--source_csv",
            str(csv_path),
            "--out_impact",
            str(report_path),
            "--out_rows",
            str(rows_path),
            "--target-locale",
            "en-US",
        ],
    )

    assert glossary_delta.main() == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert report["target_locale"] == "en-US"
    assert report["change_counts"]["term_changed"] == 0
    assert report["impacted_rows_total"] == 0
    assert rows_path.read_text(encoding="utf-8") == ""


def test_diff_style_profile_does_not_treat_term_ru_as_en_us_target():
    old_profile = {
        "terminology": {
            "preferred_terms": [{"term_zh": "火影", "term_ru": "Хокаге"}],
        }
    }
    new_profile = {
        "terminology": {
            "preferred_terms": [{"term_zh": "火影", "term_ru": "Наруто"}],
        }
    }

    style_delta = glossary_delta.diff_style_profile(old_profile, new_profile, "en-US")

    assert style_delta["preferred_term_changed"] == []
