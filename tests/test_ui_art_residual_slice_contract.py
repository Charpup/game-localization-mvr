import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import build_ui_art_residual_slice
import run_ui_art_residual_triage
import ui_art_residual_assess


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, items: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n", encoding="utf-8")


def test_build_manifest_rows_uses_override_asset_for_prefill_and_manual(tmp_path):
    override = tmp_path / "overrides.json"
    override.write_text(
        json.dumps(
            {
                "badge_micro_1c_exact": {"新": "Нов."},
                "headline_exact": {"守卫木叶": "Щит Конохи"},
                "manual_sources": ["熙晨归客"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    build_ui_art_residual_slice.apply_override_asset(override)
    prepared_rows = [
        {
            "string_id": "UIART_1",
            "source_zh": "新",
            "ui_art_category": "badge_micro_1c",
            "compact_mapping_status": "manual_review_required",
            "ui_art_strategy_hint": "",
            "ui_art_compact_term": "",
        },
        {
            "string_id": "UIART_2",
            "source_zh": "守卫木叶",
            "ui_art_category": "title_name_short",
            "compact_mapping_status": "optional",
            "ui_art_strategy_hint": "",
            "ui_art_compact_term": "",
        },
        {
            "string_id": "UIART_3",
            "source_zh": "熙晨归客",
            "ui_art_category": "title_name_short",
            "compact_mapping_status": "optional",
            "ui_art_strategy_hint": "",
            "ui_art_compact_term": "",
        },
    ]
    translated_rows = [
        {"string_id": "UIART_1", "target_text": "Новый"},
        {"string_id": "UIART_2", "target_text": "Защита Конохи"},
        {"string_id": "UIART_3", "target_text": "Гость Рассвета"},
    ]
    qa_report = {
        "errors": [
            {"string_id": "UIART_1", "type": "compact_mapping_missing"},
            {"string_id": "UIART_2", "type": "length_overflow"},
            {"string_id": "UIART_3", "type": "ambiguity_high_risk"},
        ]
    }
    soft_report = {"hard_gate": {"violations": []}}
    assessment = {"soft_qa": {"noise_split": {"true_residual": {"top_sources": [["守卫木叶", 1]]}}}}

    rows, manifest = build_ui_art_residual_slice.build_manifest_rows(
        prepared_rows=prepared_rows,
        translated_rows=translated_rows,
        qa_report=qa_report,
        soft_report=soft_report,
        soft_tasks=[],
        assessment=assessment,
    )

    by_id = {row["string_id"]: row for row in rows}
    assert by_id["UIART_1"]["translation_mode"] == "prefill_exact"
    assert by_id["UIART_1"]["prefill_target_ru"] == "Нов."
    assert by_id["UIART_2"]["translation_mode"] == "prefill_exact"
    assert by_id["UIART_2"]["prefill_target_ru"] == "Щит Конохи"
    assert by_id["UIART_3"]["translation_mode"] == "manual_hold"
    assert manifest["translation_mode_counts"]["manual_hold"] == 1


def test_build_patch_glossary_entries_capture_current_long_form():
    entries = build_ui_art_residual_slice.build_patch_glossary_entries(
        [
            {
                "source_zh": "守卫木叶",
                "translation_mode": "prefill_exact",
                "prefill_target_ru": "Щит Конохи",
                "current_target_text": "Защита Конохи",
            }
        ]
    )
    assert entries[0]["term_zh"] == "守卫木叶"
    assert "Защита Конохи" in entries[0]["avoid_long_form"]


def test_merge_repaired_rows_preserves_order_and_marks_patch():
    base_rows = [
        {"string_id": "UIART_1", "target_text": "Старый 1"},
        {"string_id": "UIART_2", "target_text": "Старый 2"},
    ]
    patched_rows = [
        {"string_id": "UIART_2", "target_text": "Новый 2", "translate_status": "ok"},
    ]

    merged = run_ui_art_residual_triage.merge_repaired_rows(base_rows, patched_rows)

    assert [row["string_id"] for row in merged] == ["UIART_1", "UIART_2"]
    assert merged[0]["target_text"] == "Старый 1"
    assert merged[1]["target_text"] == "Новый 2"
    assert merged[1]["residual_merge_status"] == "ok"


def test_residual_assess_maps_soft_gate_top_sources_to_source_text(tmp_path):
    base_dir = tmp_path / "base"
    slice_dir = tmp_path / "slice"
    base_dir.mkdir()
    slice_dir.mkdir()

    (base_dir / "ui_art_full_rerun_assessment.json").write_text(
        json.dumps(
            {
                "family_residuals": {
                    "promo_short": {"rerun_review_rows": 10},
                    "item_skill_name": {"rerun_review_rows": 20},
                    "slogan_long": {"rerun_review_rows": 30},
                }
            }
        ),
        encoding="utf-8",
    )
    (base_dir / "ui_art_qa_hard_report.json").write_text(json.dumps({"error_counts": {"compact_mapping_missing": 2}}), encoding="utf-8")
    (slice_dir / "ui_art_qa_hard_report.json").write_text(json.dumps({"error_counts": {"compact_mapping_missing": 0}}), encoding="utf-8")
    (base_dir / "ui_art_soft_qa_report.json").write_text(json.dumps({"hard_gate": {"violations": [{"string_id": "UIART_1"}]}}), encoding="utf-8")
    (slice_dir / "ui_art_soft_qa_report.json").write_text(json.dumps({"hard_gate": {"violations": [{"string_id": "UIART_1"}]}}), encoding="utf-8")
    _write_csv(
        slice_dir / "ui_art_translated_repaired.csv",
        [
            {"string_id": "UIART_1", "source_zh": "守卫木叶"},
        ],
    )
    _write_csv(
        slice_dir / "ui_art_residual_candidates.csv",
        [
            {"string_id": "UIART_1", "residual_lane": "headline_slogan_repair", "translation_mode": "llm"},
        ],
    )
    _write_csv(
        slice_dir / "ui_art_residual_review_queue.csv",
        [
            {"string_id": "UIART_1", "ui_art_category": "slogan_long", "severity": "major", "reason": "headline_budget_overflow"},
        ],
    )
    _write_csv(slice_dir / "ui_art_residual_manual_queue_seed.csv", [{"string_id": "UIART_9"}])

    out_json = tmp_path / "assessment.json"
    out_md = tmp_path / "assessment.md"
    sys.argv = [
        "ui_art_residual_assess.py",
        "--base-run-dir",
        str(base_dir),
        "--slice-dir",
        str(slice_dir),
        "--out-json",
        str(out_json),
        "--out-md",
        str(out_md),
    ]
    assert ui_art_residual_assess.main() == 0
    payload = json.loads(out_json.read_text(encoding="utf-8"))
    assert payload["remaining_soft_hard_gate_top_sources"][0][0] == "守卫木叶"
