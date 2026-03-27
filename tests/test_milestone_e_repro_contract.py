#!/usr/bin/env python3
"""Repro and authority contract tests for milestone E entrypoints."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import translate_llm


def test_resolve_glossary_path_prefers_tracked_compiled_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    glossary_dir = tmp_path / "glossary"
    glossary_dir.mkdir()
    (glossary_dir / "compiled.yaml").write_text("meta: {}\nentries: []\n", encoding="utf-8")

    resolved = translate_llm.resolve_glossary_path("")

    assert Path(resolved) == Path("glossary/compiled.yaml")


def test_resolve_style_profile_path_prefers_generated_workflow_target(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "workflow").mkdir()

    resolved = translate_llm.resolve_style_profile_path("")

    assert Path(resolved) == Path("workflow/style_profile.generated.yaml")


def test_load_glossary_accepts_compiled_entries_without_status(tmp_path):
    glossary_path = tmp_path / "compiled.yaml"
    glossary_path.write_text(
        "\n".join(
            [
                "meta:",
                "  type: compiled",
                "entries:",
                "  - term_zh: 木叶",
                "    term_ru: Коноха",
                "  - term_zh: ninja",
                "    targets:",
                "      ru-RU: ниндзя",
                "      en-US: ninja",
            ]
        ),
        encoding="utf-8",
    )

    glossary, compiled_hash = translate_llm.load_glossary(str(glossary_path), "ru-RU")

    assert compiled_hash is None
    assert [entry.term_zh for entry in glossary] == ["木叶", "ninja"]
    assert [entry.term_ru for entry in glossary] == ["Коноха", "ниндзя"]


def test_load_glossary_does_not_fallback_to_other_locale_targets(tmp_path):
    glossary_path = tmp_path / "compiled.yaml"
    glossary_path.write_text(
        "\n".join(
            [
                "meta:",
                "  type: compiled",
                "entries:",
                "  - term_zh: 木叶",
                "    term_ru: Коноха",
                "  - term_zh: ninja",
                "    targets:",
                "      ru-RU: ниндзя",
                "      en-US: ninja",
            ]
        ),
        encoding="utf-8",
    )

    glossary, _ = translate_llm.load_glossary(str(glossary_path), "en-US")

    assert [entry.term_zh for entry in glossary] == ["ninja"]
    assert [entry.term_ru for entry in glossary] == ["ninja"]


def test_load_glossary_keeps_term_ru_compat_for_ru_ru(tmp_path):
    glossary_path = tmp_path / "compiled.yaml"
    glossary_path.write_text(
        "\n".join(
            [
                "meta:",
                "  type: compiled",
                "entries:",
                "  - term_zh: 火影",
                "    term_ru: Хокаге",
            ]
        ),
        encoding="utf-8",
    )

    glossary, _ = translate_llm.load_glossary(str(glossary_path), "ru-RU")

    assert [entry.term_zh for entry in glossary] == ["火影"]
    assert [entry.term_ru for entry in glossary] == ["Хокаге"]
