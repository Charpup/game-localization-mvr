import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import build_ui_art_residual_v2_slice
import ui_art_residual_v2_assess


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, items: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n", encoding="utf-8")


def test_build_v2_slice_separates_manual_and_auto_candidates(tmp_path):
    base_run = tmp_path / "base_run"
    base_slice = tmp_path / "base_slice"
    out_dir = tmp_path / "v2"
    base_run.mkdir(parents=True)
    base_slice.mkdir(parents=True)

    _write_csv(
        base_slice / "ui_art_translated_repaired.csv",
        [
            {
                "string_id": "UIART_1",
                "source_zh": "反伤试炼",
                "target_text": "Испытание отражения",
                "ui_art_category": "title_name_short",
                "residual_lane": "headline_slogan_repair",
                "ui_art_strategy_hint": "",
                "translation_mode": "llm",
            },
            {
                "string_id": "UIART_2",
                "source_zh": "熙晨归客",
                "target_text": "Гость рассвета",
                "ui_art_category": "title_name_short",
                "residual_lane": "creative_title_manual",
                "ui_art_strategy_hint": "",
                "translation_mode": "manual_hold",
            },
            {
                "string_id": "UIART_3",
                "source_zh": "元素之门",
                "target_text": "Врата стихий",
                "ui_art_category": "item_skill_name",
                "residual_lane": "item_skill_family_compact",
                "ui_art_strategy_hint": "item_compact_noun",
                "translation_mode": "llm",
            },
            {
                "string_id": "UIART_4",
                "source_zh": "公告",
                "target_text": "Объявл.",
                "ui_art_category": "label_generic_short",
                "residual_lane": "",
                "ui_art_strategy_hint": "",
                "translation_mode": "llm",
            },
            {
                "string_id": "UIART_5",
                "source_zh": "公告",
                "target_text": "Объявл.",
                "ui_art_category": "label_generic_short",
                "residual_lane": "",
                "ui_art_strategy_hint": "",
                "translation_mode": "llm",
            },
        ],
    )
    _write_csv(
        base_slice / "ui_art_residual_review_queue.csv",
        [
            {"string_id": "UIART_1", "source_zh": "反伤试炼", "severity": "major", "reason": "title_name_short_overflow", "ui_art_category": "title_name_short"},
            {"string_id": "UIART_1", "source_zh": "反伤试炼", "severity": "warning", "reason": "title_name_short_near_limit", "ui_art_category": "title_name_short"},
            {"string_id": "UIART_2", "source_zh": "熙晨归客", "severity": "critical", "reason": "title_name_short_overflow", "ui_art_category": "title_name_short"},
            {"string_id": "UIART_3", "source_zh": "元素之门", "severity": "major", "reason": "item_skill_name_overflow", "ui_art_category": "item_skill_name"},
            {"string_id": "UIART_4", "source_zh": "公告", "severity": "warning", "reason": "label_generic_short_near_limit", "ui_art_category": "label_generic_short"},
            {"string_id": "UIART_5", "source_zh": "公告", "severity": "warning", "reason": "label_generic_short_near_limit", "ui_art_category": "label_generic_short"},
        ],
    )
    _write_json(base_slice / "ui_art_qa_hard_report.json", {"error_counts": {"length_overflow": 3}, "errors": []})
    _write_json(base_slice / "ui_art_soft_qa_report.json", {"hard_gate": {"violations": [{"string_id": "UIART_2", "type": "ambiguity_high_risk"}]}})
    _write_jsonl(base_slice / "ui_art_soft_tasks.jsonl", [{"string_id": "UIART_2", "issue_type": "ambiguity_high_risk"}])
    _write_json(
        tmp_path / "override.json",
        {
            "version": 1,
            "manual_sources": ["熙晨归客"],
            "item_skill_exact": {"元素之门": "Эл. врата"},
        },
    )
    (tmp_path / "glossary.yaml").write_text(
        "meta: {}\nentries:\n  - term_zh: 元素之门\n    term_ru: Эл. врата\n    status: approved\n",
        encoding="utf-8",
    )

    manifest = build_ui_art_residual_v2_slice.build_v2_slice(
        base_run_dir=base_run,
        base_slice_dir=base_slice,
        out_dir=out_dir,
        override_path=tmp_path / "override.json",
        glossary_path=tmp_path / "glossary.yaml",
    )

    enriched, _ = build_ui_art_residual_v2_slice.read_csv(out_dir / "ui_art_residual_v2_review_queue_enriched.csv")
    enriched_map = {(row["string_id"], row["severity"]): row for row in enriched}

    assert manifest["review_queue_total"] == 6
    assert manifest["justified_for_narrow_auto"] is False
    assert enriched_map[("UIART_2", "critical")]["manual_bucket"] == "manual_creative_titles"
    assert enriched_map[("UIART_1", "major")]["auto_fix_candidate"] == "true"
    assert enriched_map[("UIART_1", "major")]["narrow_lane"] == "canonical_title_compact"
    assert enriched_map[("UIART_3", "major")]["narrow_lane"] == "lore_skill_compact"
    assert enriched_map[("UIART_4", "warning")]["narrow_lane"] == "warning_family_compact"


def test_residual_v2_assessment_compares_against_base_slice(tmp_path):
    base_slice = tmp_path / "base_slice"
    v2_slice = tmp_path / "v2_slice"
    base_slice.mkdir(parents=True)
    v2_slice.mkdir(parents=True)

    _write_json(base_slice / "ui_art_qa_hard_report.json", {"error_counts": {"length_overflow": 10, "compact_mapping_missing": 2}})
    _write_json(v2_slice / "ui_art_qa_hard_report.json", {"error_counts": {"length_overflow": 4}})
    _write_json(base_slice / "ui_art_soft_qa_report.json", {"hard_gate": {"violations": [{"string_id": "UIART_1", "type": "length"} for _ in range(510)]}})
    _write_json(v2_slice / "ui_art_soft_qa_report.json", {"hard_gate": {"violations": [{"string_id": "UIART_2", "type": "length"} for _ in range(420)]}})
    _write_csv(
        base_slice / "ui_art_residual_review_queue.csv",
        [
            {"string_id": "UIART_1", "ui_art_category": "title_name_short", "severity": "critical", "reason": "title_name_short_overflow"},
            {"string_id": "UIART_2", "ui_art_category": "item_skill_name", "severity": "major", "reason": "item_skill_name_overflow"},
        ],
    )
    _write_csv(
        v2_slice / "ui_art_residual_v2_review_queue_enriched.csv",
        [
            {"string_id": "UIART_1", "ui_art_category": "title_name_short", "severity": "major", "reason": "title_name_short_overflow"},
            {"string_id": "UIART_3", "ui_art_category": "item_skill_name", "severity": "warning", "reason": "item_skill_name_near_limit"},
        ],
    )
    _write_csv(v2_slice / "ui_art_residual_v2_manual_creative_titles.csv", [{"string_id": "UIART_10"}])
    _write_csv(v2_slice / "ui_art_residual_v2_manual_ambiguity_terms.csv", [{"string_id": "UIART_11"}])
    _write_json(v2_slice / "ui_art_residual_v2_manifest.json", {"auto_fix_candidate_rows": 42, "repair_input_rows": 30})

    payload = ui_art_residual_v2_assess.build_assessment(base_slice, v2_slice)

    assert payload["deltas"]["hard_total_before"] == 12
    assert payload["deltas"]["hard_total_after"] == 4
    assert payload["deltas"]["soft_gate_before"] == 510
    assert payload["deltas"]["soft_gate_after"] == 420
    assert payload["acceptance"]["soft_hard_gate_below_500"] is True
    assert payload["acceptance"]["manual_only_queue_separated"] is True
