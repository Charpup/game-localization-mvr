import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import translate_llm


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _write_style_profile(path: Path) -> None:
    path.write_text(
        """
project:
  source_language: zh-CN
  target_language: ru-RU
style_contract:
  language_policy: {}
  placeholder_protection: {}
  style_guard: {}
ui:
  length_constraints:
    button_max_chars: 18
    dialogue_max_chars: 120
""".strip(),
        encoding="utf-8",
    )


def test_translate_llm_prefill_exact_bypasses_batch_call(monkeypatch, tmp_path):
    input_csv = tmp_path / "prepared.csv"
    output_csv = tmp_path / "translated.csv"
    checkpoint = tmp_path / "checkpoint.json"
    style = tmp_path / "style.md"
    style_profile = tmp_path / "style_profile.yaml"
    glossary = tmp_path / "glossary.yaml"

    _write_csv(
        input_csv,
        [
            {
                "string_id": "UIART_000001",
                "source_zh": "极品",
                "tokenized_zh": "极品",
                "translation_mode": "prefill_exact",
                "prefill_target_ru": "Эпик",
                "ui_art_category": "badge_micro_2c",
                "ui_art_strategy_hint": "badge_exact_map",
                "max_len_target": "6",
                "max_len_review_limit": "8",
            }
        ],
    )
    style.write_text("compact ui art", encoding="utf-8")
    _write_style_profile(style_profile)
    glossary.write_text("entries: []\n", encoding="utf-8")

    def fail_batch_call(**kwargs):
        raise AssertionError("batch_llm_call should not be invoked for prefill_exact rows")

    monkeypatch.setattr(translate_llm, "batch_llm_call", fail_batch_call)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "translate_llm.py",
            "--input",
            str(input_csv),
            "--output",
            str(output_csv),
            "--checkpoint",
            str(checkpoint),
            "--style",
            str(style),
            "--style-profile",
            str(style_profile),
            "--glossary",
            str(glossary),
        ],
    )

    translate_llm.main()

    rows = list(csv.DictReader(output_csv.open("r", encoding="utf-8-sig", newline="")))
    assert rows[0]["target_text"] == "Эпик"
    assert rows[0]["translate_status"] == "ok"


def test_translate_llm_builds_batch_payload_with_strategy_metadata():
    payload = translate_llm.build_batch_row_payload(
        {
            "string_id": "UIART_000002",
            "source_zh": "奖励预览",
            "ui_art_category": "promo_short",
            "ui_art_strategy_hint": "promo_exact_head",
            "ui_art_compact_term": "Нагр.",
            "max_len_target": "9",
            "max_len_review_limit": "10",
            "translation_mode": "llm",
            "current_target_text": "Награды обзор",
            "residual_lane": "promo_exact_or_compound",
            "residual_prompt_hint": "shorten_to_compact_promo_head",
        }
    )

    assert payload["id"] == "UIART_000002"
    assert payload["ui_art_category"] == "promo_short"
    assert payload["ui_art_strategy_hint"] == "promo_exact_head"
    assert payload["ui_art_compact_term"] == "Нагр."
    assert payload["current_target_text"] == "Награды обзор"
    assert payload["residual_lane"] == "promo_exact_or_compound"
    assert payload["residual_prompt_hint"] == "shorten_to_compact_promo_head"


def test_translate_llm_system_prompt_mentions_v2_residual_lanes():
    builder = translate_llm.build_system_prompt_factory(
        style_guide="compact style",
        glossary_summary="- 试炼 → тест",
        target_lang="ru-RU",
        style_profile={},
    )

    prompt = builder(
        [
            {
                "id": "UIART_900001",
                "source_text": "灵渊试炼",
                "ui_art_category": "title_name_short",
                "ui_art_strategy_hint": "",
                "residual_lane": "canonical_title_compact",
                "residual_prompt_hint": "compact repeated title",
                "current_target_text": "Испытание Бездны",
                "max_len_target": "10",
                "max_len_review_limit": "12",
            },
            {
                "id": "UIART_900002",
                "source_text": "元素之门",
                "ui_art_category": "item_skill_name",
                "ui_art_strategy_hint": "item_compact_noun",
                "residual_lane": "lore_skill_compact",
                "residual_prompt_hint": "compact lore title",
                "current_target_text": "Врата Стихий",
                "max_len_target": "10",
                "max_len_review_limit": "12",
            },
        ]
    )

    assert "residual_lane=canonical_title_compact" in prompt
    assert "residual_lane=lore_skill_compact" in prompt
