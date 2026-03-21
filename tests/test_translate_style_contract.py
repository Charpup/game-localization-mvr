#!/usr/bin/env python3
"""Contract tests for translate_llm style-profile terminology serialization."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import translate_llm


def test_build_style_contract_serializes_all_terminology_constraints():
    profile = {
        "project": {
            "source_language": "zh-CN",
            "target_language": "ru-RU",
        },
        "style_contract": {
            "language_policy": {
                "no_over_localization": True,
                "no_over_literal": True,
            },
            "placeholder_protection": {
                "preserve_ph_tokens": True,
                "preserve_markup": True,
                "variables": ["⟦PH_01⟧", "{0}"],
            },
            "style_guard": {
                "character_name_policy": "keep",
                "proper_noun_strategy": "hybrid",
                "keep_named_entities": True,
                "no_humor_overreach": True,
                "avoid_wordplay_distortion": True,
            },
        },
        "terminology": {
            "forbidden_terms": ["bug", "issue"],
            "preferred_terms": [
                {"term_zh": "木叶", "term_ru": "Коноха"},
                "忍者 -> ниндзя",
            ],
            "prohibited_aliases": ["木叶 -> деревня_树叶"],
            "banned_terms": ["机翻", "直译"],
        },
        "ui": {
            "length_constraints": {
                "button_max_chars": 18,
                "dialogue_max_chars": 120,
            },
        },
        "segmentation": {
            "domain_hint": "game",
        },
        "units": {
            "time": {"source_unit": "秒", "target_unit": "секунд"},
            "currency": {"source_unit": "原石", "target_unit": "алмазы"},
        },
    }

    contract = translate_llm.build_style_contract(profile)

    assert "- Forbidden terms:" in contract
    assert "  - bug" in contract
    assert "  - issue" in contract
    assert "- Preferred term mapping:" in contract
    assert "  - 木叶 -> Коноха" in contract
    assert "  - 忍者 -> ниндзя" in contract
    assert "- Prohibited aliases:" in contract
    assert "  - 木叶 -> деревня_树叶" in contract
    assert "- Banned terms:" in contract
    assert "  - 机翻" in contract
    assert "  - 直译" in contract
