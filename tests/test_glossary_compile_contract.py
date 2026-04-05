import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import glossary_compile


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(glossary_compile.yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_load_approved_inherits_meta_scope_and_source(tmp_path):
    glossary_path = tmp_path / "ip_terms.yaml"
    _write_yaml(
        glossary_path,
        {
            "meta": {
                "scope": "ip",
                "language_pair": "zh-CN->ru-RU",
                "source": "research_report",
            },
            "entries": [
                {"term_zh": "战令", "term_ru": "БП", "status": "approved"},
            ],
        },
    )

    entries = glossary_compile.load_approved(str(glossary_path))

    assert entries[0]["scope"] == "ip"
    assert entries[0]["language_pair"] == "zh-CN->ru-RU"
    assert entries[0]["source"] == "research_report"
    assert entries[0]["source_file"].endswith("ip_terms.yaml")


def test_compile_entries_can_merge_multi_source_and_resolve_conflicts_by_scope(tmp_path):
    base_path = tmp_path / "base.yaml"
    ip_path = tmp_path / "ip.yaml"
    _write_yaml(
        base_path,
        {
            "meta": {"scope": "base"},
            "entries": [
                {"term_zh": "活动", "term_ru": "Событие", "status": "approved"},
                {"term_zh": "奖励", "term_ru": "Награды", "status": "approved"},
            ],
        },
    )
    _write_yaml(
        ip_path,
        {
            "meta": {"scope": "ip"},
            "entries": [
                {"term_zh": "活动", "term_ru": "Ивент", "status": "approved"},
            ],
        },
    )

    entries = glossary_compile.load_approved_sources([str(base_path), str(ip_path)])
    compiled, report = glossary_compile.compile_entries(entries, resolve_conflicts=True)
    compiled_map = {entry["term_zh"]: entry for entry in compiled}

    assert report["has_conflicts"] is True
    assert compiled_map["活动"]["term_ru"] == "Ивент"
    assert compiled_map["活动"]["scope"] == "ip"
    assert compiled_map["奖励"]["term_ru"] == "Награды"


def test_compile_entries_preserve_compact_metadata():
    compiled, _ = glossary_compile.compile_entries(
        [
            {
                "term_zh": "商店",
                "term_ru": "Маг.",
                "scope": "ip",
                "status": "approved",
                "tags": ["ui", "art", "short"],
                "preferred_compact": True,
                "avoid_long_form": ["Магазин"],
            }
        ],
        resolve_conflicts=True,
    )

    assert compiled[0]["preferred_compact"] is True
    assert compiled[0]["tags"] == ["ui", "art", "short"]
    assert compiled[0]["avoid_long_form"] == ["Магазин"]
