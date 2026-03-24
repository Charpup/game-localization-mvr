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


def test_glossary_delta_add_change_remove_writes_typed_row_impacts(monkeypatch, tmp_path):
    old_glossary = tmp_path / "old.yaml"
    new_glossary = tmp_path / "new.yaml"
    csv_path = tmp_path / "translated.csv"
    report_path = tmp_path / "delta_report.json"
    rows_path = tmp_path / "delta_rows.jsonl"

    _write_yaml(
        old_glossary,
        {
            "entries": [
                {"term_zh": "火影", "term_ru": "Наруто"},
                {"term_zh": "木叶", "term_ru": "Старая Коноха"},
                {"term_zh": "苦无", "term_ru": "Кунай"},
            ]
        },
    )
    _write_yaml(
        new_glossary,
        {
            "entries": [
                {"term_zh": "火影", "term_ru": "Хокаге"},
                {"term_zh": "木叶", "term_ru": "Коноха"},
                {"term_zh": "护额", "term_ru": "Повязка"},
            ]
        },
    )
    _write_csv(
        csv_path,
        [
            {"string_id": "1", "source_zh": "火影回来了", "target_text": "Наруто вернулся", "module_tag": "story_dialogue"},
            {"string_id": "2", "source_zh": "木叶按钮", "target_text": "Старая Коноха", "module_tag": "ui_button"},
            {"string_id": "3", "source_zh": "苦无已移除", "target_text": "Кунай", "module_tag": "system_notice"},
            {"string_id": "4", "source_zh": "护额已解锁", "target_text": "Повязка", "module_tag": "system_notice"},
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
            "ru-RU",
        ],
    )

    assert glossary_delta.main() == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert report["change_counts"]["term_added"] == 1
    assert report["change_counts"]["term_changed"] == 2
    assert report["change_counts"]["term_removed"] == 1
    assert report["impact_set"] == ["1", "2", "3", "4"]

    row_by_id = {row["string_id"]: row for row in rows}
    assert row_by_id["1"]["target_locale"] == "ru-RU"
    assert "term_changed" in row_by_id["1"]["delta_types"]
    assert "term_removed" in row_by_id["3"]["delta_types"]
    assert row_by_id["3"]["recommended_action"] == "manual_review"
    assert row_by_id["2"]["placeholder_locked"] is False


def test_glossary_delta_noop_still_writes_safe_report(monkeypatch, tmp_path):
    glossary_path = tmp_path / "glossary.yaml"
    csv_path = tmp_path / "translated.csv"
    report_path = tmp_path / "delta_report.json"
    rows_path = tmp_path / "delta_rows.jsonl"

    _write_yaml(glossary_path, {"entries": [{"term_zh": "火影", "term_ru": "Хокаге"}]})
    _write_csv(
        csv_path,
        [{"string_id": "1", "source_zh": "普通文本", "target_text": "Обычный текст", "module_tag": "general"}],
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
    assert report["impacted_rows_total"] == 0
    assert report["recommended_rerun_scope"] == "no_op"
    assert rows_path.read_text(encoding="utf-8") == ""


def test_load_compiled_does_not_fallback_to_ru_for_non_ru_locale(tmp_path):
    glossary_path = tmp_path / "glossary.yaml"
    _write_yaml(
        glossary_path,
        {
            "entries": [
                {"term_zh": "火影", "term_ru": "Хокаге"},
                {"term_zh": "木叶", "targets": {"ru-RU": "Коноха", "en-US": "Konoha"}},
            ]
        },
    )

    compiled, _, _ = glossary_delta.load_compiled(str(glossary_path), "en-US")

    assert compiled == {"木叶": "Konoha"}
