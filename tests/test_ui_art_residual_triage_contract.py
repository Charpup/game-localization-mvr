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


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, items: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n", encoding="utf-8")


def _prepared_row(string_id: str, source_zh: str, category: str, *, strategy: str = "", compact: str = "", status: str = "ready") -> dict:
    return {
        "string_id": string_id,
        "source_zh": source_zh,
        "source_string_id": string_id.replace("UIART_", ""),
        "batch_row_id": string_id.replace("UIART_", ""),
        "working_string_id": string_id,
        "tokenized_zh": source_zh,
        "source_len_clean": "4",
        "placeholder_budget": "0",
        "max_len_target": "9",
        "max_len_review_limit": "10",
        "ui_art_category": category,
        "ui_art_strategy_hint": strategy,
        "ui_art_compact_term": compact,
        "compact_rule": "compact_preferred",
        "compact_mapping_status": "approved_available" if compact else "optional",
        "translation_mode": "llm",
        "status": status,
    }


def _translated_row(string_id: str, target_text: str) -> dict:
    return {
        "string_id": string_id,
        "target_text": target_text,
        "target": target_text,
        "target_ru": target_text,
        "translate_status": "ok",
        "translate_validation": "ok",
    }


def test_build_slice_classifies_lanes_and_prefill(tmp_path):
    base_run_dir = tmp_path / "base_run"
    out_dir = tmp_path / "slice"
    override_path = tmp_path / "override.json"
    base_run_dir.mkdir(parents=True)
    _write_json(
        override_path,
        {
            "manual_sources": ["熙晨归客"],
            "promo_exact": {"奖励预览": "Нагр."},
            "item_skill_exact": {"反伤试炼": "Контр-тест"},
            "headline_exact": {"守卫木叶": "Щит Конохи"},
        },
    )

    _write_csv(
        base_run_dir / "source_ui_art_prepared.csv",
        [
            _prepared_row("UIART_1", "新", "badge_micro_1c"),
            _prepared_row("UIART_2", "奖励预览", "promo_short", strategy="promo_exact_head"),
            _prepared_row("UIART_3", "守卫木叶", "title_name_short"),
            _prepared_row("UIART_4", "反伤试炼", "title_name_short"),
            _prepared_row("UIART_5", "熙晨归客", "title_name_short"),
        ],
    )
    _write_csv(
        base_run_dir / "ui_art_translated.csv",
        [
            _translated_row("UIART_1", "Новый"),
            _translated_row("UIART_2", "Нагр. превью"),
            _translated_row("UIART_3", "Страж Деревни"),
            _translated_row("UIART_4", "Испытание отражения"),
            _translated_row("UIART_5", "Возвращённый гость рассвета"),
        ],
    )
    _write_json(
        base_run_dir / "ui_art_qa_hard_report.json",
        {
            "error_counts": {"length_overflow": 3, "compact_mapping_missing": 1},
            "errors": [
                {"string_id": "UIART_1", "type": "compact_mapping_missing"},
                {"string_id": "UIART_2", "type": "length_overflow"},
                {"string_id": "UIART_4", "type": "length_overflow"},
            ],
        },
    )
    _write_json(
        base_run_dir / "ui_art_soft_qa_report.json",
        {
            "hard_gate": {
                "violations": [
                    {"string_id": "UIART_3", "type": "length"},
                    {"string_id": "UIART_5", "type": "ambiguity_high_risk"},
                ]
            }
        },
    )
    _write_jsonl(
        base_run_dir / "ui_art_soft_tasks.jsonl",
        [
            {"string_id": "UIART_2", "type": "length"},
            {"string_id": "UIART_3", "type": "mistranslation"},
            {"string_id": "UIART_5", "type": "ambiguity_high_risk"},
        ],
    )
    _write_json(
        base_run_dir / "ui_art_full_rerun_assessment.json",
        {
            "soft_qa": {
                "noise_split": {
                    "true_residual": {
                        "top_sources": [["守卫木叶", 5], ["反伤试炼", 4], ["熙晨归客", 3]]
                    }
                }
            }
        },
    )

    manifest = build_ui_art_residual_slice.build_slice(base_run_dir, out_dir, override_path)

    candidates = build_ui_art_residual_slice.read_csv(out_dir / "ui_art_residual_candidates.csv")[0]
    repair_rows = build_ui_art_residual_slice.read_csv(out_dir / "ui_art_residual_repair_input.csv")[0]
    manual_rows = build_ui_art_residual_slice.read_csv(out_dir / "ui_art_residual_manual_queue_seed.csv")[0]
    candidate_map = {row["string_id"]: row for row in candidates}

    assert manifest["candidate_total"] == 5
    assert candidate_map["UIART_1"]["residual_lane"] == "badge_micro_gap_cleanup"
    assert candidate_map["UIART_1"]["translation_mode"] == "manual_hold"
    assert candidate_map["UIART_2"]["translation_mode"] == "prefill_exact"
    assert candidate_map["UIART_2"]["prefill_target_ru"] == "Нагр."
    assert candidate_map["UIART_3"]["residual_lane"] == "headline_slogan_repair"
    assert candidate_map["UIART_3"]["translation_mode"] == "prefill_exact"
    assert candidate_map["UIART_4"]["residual_lane"] == "item_skill_family_compact"
    assert candidate_map["UIART_4"]["prefill_target_ru"] == "Контр-тест"
    assert candidate_map["UIART_5"]["residual_lane"] == "creative_title_manual"
    assert len(repair_rows) == 3
    assert len(manual_rows) == 2


def test_merge_patch_rows_preserves_row_count_and_updates_target():
    base_rows = [
        {"string_id": "UIART_1", "target_text": "A", "target": "A"},
        {"string_id": "UIART_2", "target_text": "B", "target": "B"},
    ]
    patch_rows = [
        {"string_id": "UIART_2", "target_text": "B2", "target": "B2", "target_ru": "B2"}
    ]

    merged_rows, changed = run_ui_art_residual_triage.merge_patch_rows(base_rows, patch_rows)

    assert len(merged_rows) == 2
    assert changed == 1
    assert merged_rows[1]["target_text"] == "B2"


def test_residual_assessment_reports_delta(tmp_path):
    base_run = tmp_path / "base"
    slice_run = tmp_path / "slice"
    base_run.mkdir(parents=True)
    slice_run.mkdir(parents=True)

    _write_json(
        base_run / "ui_art_full_rerun_assessment.json",
        {
            "family_residuals": {
                "promo_short": {"rerun_review_rows": 10},
                "item_skill_name": {"rerun_review_rows": 20},
                "slogan_long": {"rerun_review_rows": 8},
            }
        },
    )
    _write_json(base_run / "ui_art_qa_hard_report.json", {"error_counts": {"length_overflow": 10}})
    _write_json(slice_run / "ui_art_qa_hard_report.json", {"error_counts": {"length_overflow": 4, "headline_budget_overflow": 1}})

    _write_json(base_run / "ui_art_soft_qa_report.json", {"hard_gate": {"violations": [{"string_id": "UIART_1", "type": "length"}]}})
    _write_json(slice_run / "ui_art_soft_qa_report.json", {"hard_gate": {"violations": []}})
    _write_csv(
        slice_run / "ui_art_residual_candidates.csv",
        [{"string_id": "UIART_1", "residual_lane": "headline_slogan_repair", "translation_mode": "prefill_exact"}],
    )
    _write_csv(
        slice_run / "ui_art_residual_review_queue.csv",
        [{"string_id": "UIART_1", "residual_lane": "headline_slogan_repair", "severity": "major", "ui_art_category": "slogan_long", "reason": "headline_budget_overflow"}],
    )
    _write_csv(
        slice_run / "ui_art_residual_manual_queue_seed.csv",
        [{"string_id": "UIART_2", "residual_lane": "creative_title_manual", "translation_mode": "manual_hold"}],
    )
    _write_csv(
        slice_run / "ui_art_translated_repaired.csv",
        [{"string_id": "UIART_1", "source_zh": "守卫木叶", "target_text": "Щит Конохи"}],
    )

    payload = ui_art_residual_assess.build_assessment(base_run, slice_run)

    assert payload["deltas"]["hard_total_before"] == 10
    assert payload["deltas"]["hard_total_after"] == 5
    assert payload["deltas"]["soft_gate_before"] == 1
    assert payload["deltas"]["soft_gate_after"] == 0
    assert payload["lane_metrics"]["headline_slogan_repair"]["mode:prefill_exact"] == 1
