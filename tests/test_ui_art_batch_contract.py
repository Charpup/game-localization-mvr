import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import prepare_ui_art_batch
import qa_hard
import restore_ui_art_delivery
import run_ui_art_live_batch
import ui_art_length_review


def _write_csv(path: Path, rows: list[dict], encoding: str = "utf-8-sig") -> None:
    with path.open("w", encoding=encoding, newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def test_prepare_ui_art_batch_adds_ratio_based_limits(monkeypatch, tmp_path):
    source_csv = tmp_path / "source.csv"
    output_csv = tmp_path / "prepared.csv"
    report_json = tmp_path / "report.json"
    _write_csv(
        source_csv,
        [
            {"string_id": "BTN_1", "source_zh": "十连", "context_note": "gacha button"},
            {"string_id": "BTN_2", "source_zh": "领取{0}奖励", "context_note": "reward claim"},
        ],
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_ui_art_batch.py",
            "--input",
            str(source_csv),
            "--output",
            str(output_csv),
            "--report",
            str(report_json),
        ],
    )

    assert prepare_ui_art_batch.main() == 0
    rows = list(csv.DictReader(output_csv.open("r", encoding="utf-8-sig", newline="")))
    report = json.loads(report_json.read_text(encoding="utf-8"))

    assert rows[0]["module_tag"] == "ui_art_label"
    assert rows[0]["source_string_id"] == "BTN_1"
    assert rows[0]["string_id"] == "UIART_000001"
    assert rows[1]["working_string_id"] == "UIART_000002"
    assert rows[0]["max_len_target"] == "4"
    assert rows[0]["max_len_review_limit"] == "5"
    assert rows[0]["ui_art_category"] == "label_generic_short"
    assert rows[0]["ui_art_compact_term"] == "x10"
    assert rows[0]["ui_art_strategy_hint"] == ""
    assert rows[0]["translation_mode"] == "llm"
    assert rows[1]["max_len_target"] == "12"
    assert rows[1]["max_len_review_limit"] == "13"
    assert rows[1]["ui_art_category"] == "title_name_short"
    assert report["ready_rows"] == 2
    assert report["duplicate_source_id_count"] == 0
    assert report["ui_art_category_counts"]["label_generic_short"] == 1
    assert report["ui_art_category_counts"]["title_name_short"] == 1


def test_prepare_ui_art_batch_assigns_ui_art_categories(monkeypatch, tmp_path):
    source_csv = tmp_path / "source.csv"
    output_csv = tmp_path / "prepared.csv"
    report_json = tmp_path / "report.json"
    _write_csv(
        source_csv,
        [
            {"string_id": "1", "source_zh": "荐"},
            {"string_id": "2", "source_zh": "极品"},
            {"string_id": "3", "source_zh": "商店"},
            {"string_id": "4", "source_zh": "巅峰列传"},
            {"string_id": "5", "source_zh": "首充礼包"},
            {"string_id": "6", "source_zh": "元素之力"},
            {"string_id": "7", "source_zh": "击破气球获得幸运值，累满幸运必得大奖"},
        ],
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_ui_art_batch.py",
            "--input",
            str(source_csv),
            "--output",
            str(output_csv),
            "--report",
            str(report_json),
        ],
    )

    assert prepare_ui_art_batch.main() == 0
    rows = list(csv.DictReader(output_csv.open("r", encoding="utf-8-sig", newline="")))
    categories = {row["source_zh"]: row["ui_art_category"] for row in rows}
    hints = {row["source_zh"]: row["ui_art_strategy_hint"] for row in rows}
    modes = {row["source_zh"]: row["translation_mode"] for row in rows}
    prefills = {row["source_zh"]: row["prefill_target_ru"] for row in rows}

    assert categories["荐"] == "badge_micro_1c"
    assert categories["极品"] == "badge_micro_2c"
    assert categories["商店"] == "label_generic_short"
    assert categories["巅峰列传"] == "title_name_short"
    assert categories["首充礼包"] == "promo_short"
    assert categories["元素之力"] == "item_skill_name"
    assert categories["击破气球获得幸运值，累满幸运必得大奖"] == "slogan_long"
    assert hints["极品"] == "badge_exact_map"
    assert hints["首充礼包"] == "promo_compound_pack"
    assert hints["元素之力"] == "item_compact_noun"
    assert hints["击破气球获得幸运值，累满幸运必得大奖"] == "headline_singleline"
    assert modes["极品"] == "prefill_exact"
    assert prefills["极品"] == "Эпик"


def test_ui_art_length_review_builds_review_queue(monkeypatch, tmp_path):
    translated_csv = tmp_path / "translated.csv"
    queue_csv = tmp_path / "queue.csv"
    report_json = tmp_path / "queue.json"
    _write_csv(
        translated_csv,
        [
            {
                "string_id": "1",
                "source_zh": "推荐",
                "source_len_clean": "2",
                "target_text": "Рекомендуется",
                "max_len_target": "6",
                "max_len_review_limit": "8",
                "ui_art_category": "badge_micro_2c",
                "module_tag": "ui_art_label",
                "compact_rule": "dictionary_only",
                "compact_mapping_status": "manual_review_required",
                "ui_art_compact_term": "",
            },
            {
                "string_id": "2",
                "source_zh": "胜",
                "source_len_clean": "1",
                "target_text": "Поб.",
                "max_len_target": "4",
                "max_len_review_limit": "6",
                "ui_art_category": "badge_micro_1c",
                "module_tag": "ui_art_label",
                "compact_rule": "dictionary_only",
                "compact_mapping_status": "approved_available",
                "ui_art_compact_term": "Поб.",
            },
        ],
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ui_art_length_review.py",
            "--input",
            str(translated_csv),
            "--output",
            str(queue_csv),
            "--report",
            str(report_json),
        ],
    )

    assert ui_art_length_review.main() == 0
    rows = list(csv.DictReader(queue_csv.open("r", encoding="utf-8-sig", newline="")))
    report = json.loads(report_json.read_text(encoding="utf-8"))

    assert [row["string_id"] for row in rows] == ["1"]
    assert rows[0]["severity"] == "critical"
    assert rows[0]["ui_art_category"] == "badge_micro_2c"
    assert rows[0]["category_reason"] == "compact_mapping_missing"
    assert report["severity_counts"]["critical"] == 1


def test_ui_art_length_review_flags_slogan_line_budget(monkeypatch, tmp_path):
    translated_csv = tmp_path / "translated.csv"
    queue_csv = tmp_path / "queue.csv"
    report_json = tmp_path / "queue.json"
    _write_csv(
        translated_csv,
        [
            {
                "string_id": "1",
                "source_zh": "赢得大奖",
                "source_len_clean": "4",
                "target_text": "Крупный\nприз",
                "max_len_target": "9",
                "max_len_review_limit": "10",
                "ui_art_category": "slogan_long",
                "module_tag": "ui_art_label",
            },
        ],
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "ui_art_length_review.py",
            "--input",
            str(translated_csv),
            "--output",
            str(queue_csv),
            "--report",
            str(report_json),
        ],
    )

    assert ui_art_length_review.main() == 0
    rows = list(csv.DictReader(queue_csv.open("r", encoding="utf-8-sig", newline="")))

    assert rows[0]["severity"] == "critical"
    assert rows[0]["reason"] == "line_budget_overflow"
    assert rows[0]["category_reason"] == "line_budget_overflow"


def test_prepare_ui_art_batch_supports_gb18030_and_restore_delivery(monkeypatch, tmp_path):
    source_csv = tmp_path / "source_gbk.csv"
    prepared_csv = tmp_path / "prepared.csv"
    prepare_report = tmp_path / "prepare_report.json"
    translated_csv = tmp_path / "translated.csv"
    delivery_csv = tmp_path / "delivery.csv"
    delivery_report = tmp_path / "delivery_report.json"

    _write_csv(
        source_csv,
        [
            {"string_id": "2500", "source_zh": "比赛商城", "context_note": ""},
            {"string_id": "2500", "source_zh": "巅峰列传", "context_note": ""},
            {"string_id": "2501", "source_zh": "", "context_note": "blank row"},
        ],
        encoding="gb18030",
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_ui_art_batch.py",
            "--input",
            str(source_csv),
            "--output",
            str(prepared_csv),
            "--report",
            str(prepare_report),
        ],
    )
    assert prepare_ui_art_batch.main() == 0

    prepared_rows = list(csv.DictReader(prepared_csv.open("r", encoding="utf-8-sig", newline="")))
    prepare_payload = json.loads(prepare_report.read_text(encoding="utf-8"))

    assert [row["string_id"] for row in prepared_rows] == ["UIART_000001", "UIART_000002", "UIART_000003"]
    assert [row["source_string_id"] for row in prepared_rows] == ["2500", "2500", "2501"]
    assert prepared_rows[2]["status"] == "skipped_empty"
    assert prepare_payload["input_encoding"] == "gb18030"
    assert prepare_payload["duplicate_source_id_count"] == 1
    assert prepare_payload["duplicate_source_rows_total"] == 2

    _write_csv(
        translated_csv,
        [
            {
                "string_id": "UIART_000001",
                "source_string_id": "2500",
                "batch_row_id": "1",
                "target_text": "Магазин боя",
                "target_ru": "Магазин боя",
                "target": "Магазин боя",
            },
            {
                "string_id": "UIART_000002",
                "source_string_id": "2500",
                "batch_row_id": "2",
                "target_text": "Пик. хроника",
                "target_ru": "Пик. хроника",
                "target": "Пик. хроника",
            },
        ],
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "restore_ui_art_delivery.py",
            "--prepared",
            str(prepared_csv),
            "--translated",
            str(translated_csv),
            "--output",
            str(delivery_csv),
            "--report",
            str(delivery_report),
        ],
    )
    assert restore_ui_art_delivery.main() == 0

    delivery_rows = list(csv.DictReader(delivery_csv.open("r", encoding="utf-8-sig", newline="")))
    delivery_payload = json.loads(delivery_report.read_text(encoding="utf-8"))

    assert [row["string_id"] for row in delivery_rows] == ["2500", "2500", "2501"]
    assert [row["working_string_id"] for row in delivery_rows] == ["UIART_000001", "UIART_000002", "UIART_000003"]
    assert delivery_rows[0]["delivery_status"] == "translated"
    assert delivery_rows[2]["delivery_status"] == "skipped_empty"
    assert delivery_rows[2]["target_text"] == ""
    assert delivery_payload["row_count_match"] is True


def test_prepare_ui_art_batch_assigns_focused_strategy_hints(monkeypatch, tmp_path):
    source_csv = tmp_path / "source.csv"
    output_csv = tmp_path / "prepared.csv"
    report_json = tmp_path / "report.json"
    _write_csv(
        source_csv,
        [
            {"string_id": "1", "source_zh": "奖励预览"},
            {"string_id": "2", "source_zh": "仙术印记"},
            {"string_id": "3", "source_zh": "五星忍者·日向雏田"},
            {"string_id": "4", "source_zh": "五系五星忍者自选箱"},
        ],
    )

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_ui_art_batch.py",
            "--input",
            str(source_csv),
            "--output",
            str(output_csv),
            "--report",
            str(report_json),
        ],
    )

    assert prepare_ui_art_batch.main() == 0
    rows = {row["source_zh"]: row for row in csv.DictReader(output_csv.open("r", encoding="utf-8-sig", newline=""))}

    assert rows["奖励预览"]["ui_art_strategy_hint"] == "promo_exact_head"
    assert rows["奖励预览"]["translation_mode"] == "prefill_exact"
    assert rows["仙术印记"]["ui_art_strategy_hint"] == "item_compact_noun"
    assert rows["仙术印记"]["prefill_target_ru"] == "Сэн-знак"
    assert rows["五星忍者·日向雏田"]["ui_art_strategy_hint"] == "headline_nameplate"
    assert rows["五系五星忍者自选箱"]["ui_art_category"] == "promo_short"
    assert rows["五系五星忍者自选箱"]["ui_art_strategy_hint"] == "promo_compound_pack"


def test_reconcile_translate_resume_dedupes_existing_output(tmp_path):
    translated_csv = tmp_path / "translated.csv"
    checkpoint_json = tmp_path / "translate_checkpoint.json"

    _write_csv(
        translated_csv,
        [
            {"string_id": "UIART_000001", "target_text": "A"},
            {"string_id": "UIART_000001", "target_text": "A-dup"},
            {"string_id": "UIART_000002", "target_text": "B"},
        ],
    )

    stats = run_ui_art_live_batch.reconcile_translate_resume(translated_csv, checkpoint_json)
    rows = list(csv.DictReader(translated_csv.open("r", encoding="utf-8-sig", newline="")))
    checkpoint = json.loads(checkpoint_json.read_text(encoding="utf-8"))

    assert stats == {"rows": 3, "deduped_rows": 2, "checkpoint_ids": 2}
    assert [row["string_id"] for row in rows] == ["UIART_000001", "UIART_000002"]
    assert set(checkpoint["done_ids"]) == {"UIART_000001", "UIART_000002"}


def test_qa_hard_uses_category_aware_major_critical_and_badge_issue_type():
    validator = qa_hard.QAHardValidator("translated.csv", "ph.json", "schema.yaml", "forbidden.txt", "report.json")

    badge_row = {
        "string_id": "id_badge",
        "source_zh": "极品",
        "source_len_clean": "2",
        "max_len_target": "4",
        "max_len_review_limit": "5",
        "ui_art_category": "badge_micro_2c",
    }
    generic_major_row = {
        "string_id": "id_major",
        "source_zh": "商店",
        "source_len_clean": "2",
        "max_len_target": "4",
        "max_len_review_limit": "5",
        "ui_art_category": "label_generic_short",
    }
    generic_critical_row = {
        "string_id": "id_critical",
        "source_zh": "巅峰列传",
        "source_len_clean": "4",
        "max_len_target": "9",
        "max_len_review_limit": "10",
        "ui_art_category": "title_name_short",
    }

    validator.check_length_overflow("id_badge", "Легендарный", badge_row, 2)
    validator.check_length_overflow("id_major", "Магазин++", generic_major_row, 3)
    validator.check_length_overflow("id_critical", "Сверхдлинное название", generic_critical_row, 4)

    error_map = {item["string_id"]: item for item in validator.errors}
    assert error_map["id_badge"]["type"] == "compact_mapping_missing"
    assert error_map["id_badge"]["severity"] == "critical"
    assert error_map["id_major"]["type"] == "length_overflow"
    assert error_map["id_major"]["severity"] == "major"
    assert error_map["id_critical"]["severity"] == "critical"
