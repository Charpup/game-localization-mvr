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
