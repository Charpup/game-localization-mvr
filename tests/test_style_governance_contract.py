from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import style_guide_bootstrap
import style_sync_check


def test_build_style_profile_emits_governance_header_and_lineage():
    profile = style_guide_bootstrap.build_style_profile(
        {
            "project_context.project_id": "demo_project",
            "project_context.target_language": "ru-RU",
        }
    )

    governance = profile["style_governance"]

    assert governance["style_guide_id"] == "demo_project-ru-RU-style-v1.2"
    assert governance["status"] == "approved"
    assert governance["entry_audit"] == {
        "loadable": True,
        "approved": True,
        "deprecated": False,
    }
    assert governance["lineage"]["canonical_profile"] == "data/style_profile.yaml"
    assert governance["lineage"]["generated_guide"] == "workflow/style_guide.generated.md"


def test_render_style_guide_includes_governance_header():
    rendered = style_guide_bootstrap.render_style_guide(
        {
            "version": "1.2",
            "project": {
                "source_language": "zh-CN",
                "target_language": "ru-RU",
                "franchise": "naruto_localization_demo",
                "title_zh": "火影忍者",
                "title_ru": "Наруто",
            },
            "style_contract": {
                "tone": {"official_ratio": 70, "anime_ratio": 30, "register": "neutral_formal"},
                "language_policy": {"no_over_localization": True, "no_over_literal": True},
                "style_guard": {"character_name_policy": "keep", "proper_noun_strategy": "hybrid"},
            },
            "terminology": {"preferred_terms": [], "forbidden_terms": []},
            "ui": {"length_constraints": {"button_max_chars": 18, "dialogue_max_chars": 120}},
            "units": {
                "time": {"source_unit": "秒", "target_unit": "секунд"},
                "currency": {"source_unit": "原石", "target_unit": "алмазы"},
            },
            "style_governance": {
                "style_guide_id": "demo-ru-RU-style-v1.2",
                "status": "approved",
                "owner": "Codex",
                "approval_ref": "docs/decisions/ADR-0002-skill-governance-framework.md",
            },
        }
    )

    assert "- Style guide ID: demo-ru-RU-style-v1.2" in rendered
    assert "- Style contract version: 1.2" in rendered
    assert "- Governance status: approved" in rendered
    assert "- Approval ref: docs/decisions/ADR-0002-skill-governance-framework.md" in rendered


def test_validate_style_profile_accepts_repo_style_profile():
    profile_path = Path(__file__).resolve().parent.parent / "data" / "style_profile.yaml"

    ok, issues, version = style_sync_check.validate_style_profile(profile_path)

    assert ok is True
    assert issues == []
    assert version == "1.2"


def test_validate_style_governance_rejects_inconsistent_entry_audit():
    issues = style_sync_check.validate_style_governance(
        {
            "style_governance": {
                "style_guide_id": "demo",
                "owner": "Codex",
                "status": "approved",
                "approval_ref": "docs/decisions/ADR-0002-skill-governance-framework.md",
                "adr_refs": ["docs/decisions/ADR-0001-project-continuity-framework.md"],
                "generated_from_script": "scripts/style_guide_bootstrap.py",
                "source_questionnaire": "workflow/style_guide_questionnaire.md",
                "supersedes": "none",
                "deprecated_by": "none",
                "entry_audit": {
                    "loadable": True,
                    "approved": False,
                    "deprecated": False,
                },
                "lineage": {
                    "canonical_profile": "data/style_profile.yaml",
                    "generated_guide": "workflow/style_guide.generated.md",
                    "mirror_guides": ["workflow/style_guide.md"],
                },
            }
        },
        style_sync_check.load_style_governance_contract(),
    )

    assert any("STYLE_SYNC_E144" in issue for issue in issues)
