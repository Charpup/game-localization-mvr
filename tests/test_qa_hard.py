import json

from scripts.qa_hard import QAHardValidator


def test_generate_report_separates_approved_and_actionable_warnings(tmp_path):
    report_path = tmp_path / "qa_report.json"
    validator = QAHardValidator(
        translated_csv=str(tmp_path / "translated.csv"),
        placeholder_map=str(tmp_path / "placeholder_map.json"),
        schema_yaml=str(tmp_path / "schema.yaml"),
        forbidden_txt=str(tmp_path / "forbidden.txt"),
        report_json=str(report_path),
    )
    validator.warnings = [
        {"type": "empty_source_translation_soft", "row": 2, "string_id": "A"},
        {"type": "source_tag_unbalanced", "row": 3, "string_id": "B"},
        {"type": "token_mismatch_soft", "row": 4, "string_id": "C"},
    ]

    validator.generate_report()

    report = json.loads(report_path.read_text(encoding="utf-8"))
    policy = report["warning_policy"]
    assert policy["approved_warning_total"] == 2
    assert policy["actionable_warning_total"] == 1
    assert policy["approved_warning_counts"]["empty_source_translation_soft"] == 1
    assert policy["approved_warning_counts"]["source_tag_unbalanced"] == 1
    assert policy["actionable_warning_counts"]["token_mismatch_soft"] == 1


def test_validate_csv_treats_missing_target_with_tokenized_source_as_error(tmp_path):
    csv_path = tmp_path / "translated.csv"
    csv_path.write_text("string_id,tokenized_zh,target_text\ns1,源文本,\n", encoding="utf-8")

    validator = QAHardValidator(
        translated_csv=str(csv_path),
        placeholder_map=str(tmp_path / "placeholder_map.json"),
        schema_yaml=str(tmp_path / "schema.yaml"),
        forbidden_txt=str(tmp_path / "forbidden.txt"),
        report_json=str(tmp_path / "qa_report.json"),
    )

    assert validator.validate_csv() is True
    assert validator.error_counts["empty_translation"] == 1
    assert validator.warning_counts["empty_source_translation"] == 0


def test_token_mismatch_soft_only_for_single_extra_copy(tmp_path):
    validator = QAHardValidator(
        translated_csv=str(tmp_path / "translated.csv"),
        placeholder_map=str(tmp_path / "placeholder_map.json"),
        schema_yaml=str(tmp_path / "schema.yaml"),
        forbidden_txt=str(tmp_path / "forbidden.txt"),
        report_json=str(tmp_path / "qa_report.json"),
    )

    validator.check_token_mismatch(
        "s1",
        "Alpha ⟦PH_1⟧",
        "Alpha ⟦PH_1⟧ ⟦PH_1⟧ ⟦PH_1⟧",
        2,
    )

    assert validator.warning_counts["token_mismatch_soft"] == 0
    assert validator.error_counts["token_mismatch"] == 1


def test_check_length_overflow_uses_major_vs_critical_review_limits(tmp_path):
    validator = QAHardValidator(
        translated_csv=str(tmp_path / "translated.csv"),
        placeholder_map=str(tmp_path / "placeholder_map.json"),
        schema_yaml=str(tmp_path / "schema.yaml"),
        forbidden_txt=str(tmp_path / "forbidden.txt"),
        report_json=str(tmp_path / "qa_report.json"),
    )

    validator.check_length_overflow(
        "s1",
        "123456789",
        {
            "source_zh": "奖励",
            "source_len_clean": "2",
            "max_len_target": "8",
            "max_len_review_limit": "10",
            "ui_art_category": "label_generic_short",
        },
        2,
    )

    assert validator.errors[0]["type"] == "length_overflow"
    assert validator.errors[0]["severity"] == "major"


def test_check_length_overflow_flags_badge_without_compact_mapping(tmp_path):
    validator = QAHardValidator(
        translated_csv=str(tmp_path / "translated.csv"),
        placeholder_map=str(tmp_path / "placeholder_map.json"),
        schema_yaml=str(tmp_path / "schema.yaml"),
        forbidden_txt=str(tmp_path / "forbidden.txt"),
        report_json=str(tmp_path / "qa_report.json"),
    )

    validator.check_length_overflow(
        "s2",
        "Рекомендуется",
        {
            "source_zh": "推荐",
            "source_len_clean": "2",
            "max_len_target": "6",
            "max_len_review_limit": "8",
            "ui_art_category": "badge_micro_2c",
            "compact_rule": "dictionary_only",
            "compact_mapping_status": "manual_review_required",
        },
        3,
    )

    assert validator.errors[0]["type"] == "compact_mapping_missing"
    assert validator.errors[0]["severity"] == "critical"


def test_check_length_overflow_accepts_item_skill_ratio_but_flags_structure(tmp_path):
    validator = QAHardValidator(
        translated_csv=str(tmp_path / "translated.csv"),
        placeholder_map=str(tmp_path / "placeholder_map.json"),
        schema_yaml=str(tmp_path / "schema.yaml"),
        forbidden_txt=str(tmp_path / "forbidden.txt"),
        report_json=str(tmp_path / "qa_report.json"),
    )

    validator.check_length_overflow(
        "s3",
        "Сила великого мудреца",
        {
            "source_zh": "仙人之力",
            "source_len_clean": "4",
            "max_len_target": "9",
            "max_len_review_limit": "10",
            "ui_art_category": "item_skill_name",
            "ui_art_compact_term": "Сила Сэн.",
        },
        4,
    )

    assert validator.errors[0]["type"] == "length_overflow"
    assert "at most 2" in validator.errors[0]["detail"]


def test_check_length_overflow_flags_promo_expansion_forbidden(tmp_path):
    validator = QAHardValidator(
        translated_csv=str(tmp_path / "translated.csv"),
        placeholder_map=str(tmp_path / "placeholder_map.json"),
        schema_yaml=str(tmp_path / "schema.yaml"),
        forbidden_txt=str(tmp_path / "forbidden.txt"),
        report_json=str(tmp_path / "qa_report.json"),
    )

    validator.check_length_overflow(
        "s4",
        "Нагр. Превью",
        {
            "source_zh": "奖励预览",
            "source_len_clean": "4",
            "max_len_target": "9",
            "max_len_review_limit": "10",
            "ui_art_category": "promo_short",
            "ui_art_strategy_hint": "promo_compound_pack",
        },
        5,
    )

    assert validator.errors[0]["type"] == "promo_expansion_forbidden"


def test_check_length_overflow_uses_headline_budget_for_slogan_nameplate(tmp_path):
    validator = QAHardValidator(
        translated_csv=str(tmp_path / "translated.csv"),
        placeholder_map=str(tmp_path / "placeholder_map.json"),
        schema_yaml=str(tmp_path / "schema.yaml"),
        forbidden_txt=str(tmp_path / "forbidden.txt"),
        report_json=str(tmp_path / "qa_report.json"),
    )

    validator.check_length_overflow(
        "s5",
        "5★ Ниндзя · Хинаты Хьюга",
        {
            "source_zh": "五星忍者·日向雏田",
            "source_len_clean": "9",
            "max_len_target": "20",
            "max_len_review_limit": "24",
            "ui_art_category": "slogan_long",
            "ui_art_strategy_hint": "headline_nameplate",
        },
        6,
    )

    assert validator.errors[0]["type"] == "headline_budget_overflow"
