#!/usr/bin/env python3
"""Tests for Batch 1 script authority checks."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import check_script_authority

ROOT = Path(__file__).parent.parent


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_build_authority_report_fails_on_required_mirror_drift(tmp_path, monkeypatch):
    main_root = tmp_path / "main_worktree"
    src_root = tmp_path / "src" / "scripts"
    authority_root = main_root / "scripts"
    archive_root = main_root / "_obsolete" / "diagnostics"

    _write_text(authority_root / "normalize_guard.py", "print('main')\n")
    _write_text(src_root / "normalize_guard.py", "print('src')\n")
    _write_text(archive_root / "debug_auth.py", "archived copy\n")

    manifest = {
        "authority_root": "scripts",
        "compat_root": "../src/scripts",
        "archive_root": "_obsolete/diagnostics",
        "mirror_required": ["normalize_guard.py"],
        "alert_only_drift": [],
        "archived": ["debug_auth.py"],
        "keep_chain": [],
        "protected_exclusions": [],
        "compat_notes": {},
    }

    monkeypatch.setattr(check_script_authority, "_main_worktree_root", lambda: main_root)

    report = check_script_authority.build_authority_report(manifest)

    assert report["status"] == "fail"
    assert report["mirror_required_drift"] == ["normalize_guard.py"]
    assert report["archived_missing_copy"] == []


def test_build_authority_report_warns_on_alert_only_drift(tmp_path, monkeypatch):
    main_root = tmp_path / "main_worktree"
    src_root = tmp_path / "src" / "scripts"
    authority_root = main_root / "scripts"

    _write_text(authority_root / "runtime_adapter.py", "print('main')\n")
    _write_text(src_root / "runtime_adapter.py", "print('src')\n")

    manifest = {
        "authority_root": "scripts",
        "compat_root": "../src/scripts",
        "archive_root": "_obsolete/diagnostics",
        "mirror_required": [],
        "alert_only_drift": ["runtime_adapter.py"],
        "archived": [],
        "keep_chain": [],
        "protected_exclusions": [],
        "compat_notes": {"src_scripts_role": "compatibility mirror only"},
    }

    monkeypatch.setattr(check_script_authority, "_main_worktree_root", lambda: main_root)

    report = check_script_authority.build_authority_report(manifest)

    assert report["status"] == "warn"
    assert report["alert_only_drift"] == ["runtime_adapter.py"]
    assert report["summary"]["diff"] == 1


def test_batch10_manifest_marks_src_scripts_as_exit_planned_compat_liability():
    import json

    manifest = json.loads((ROOT / "workflow" / "script_authority_manifest.json").read_text(encoding="utf-8"))
    compat_notes = manifest["compat_notes"]

    assert manifest["compat_root"] == "../src/scripts"
    assert compat_notes["src_scripts_role"].startswith("managed compatibility liability")
    assert "not the runtime authority" in compat_notes["src_scripts_role"]
    assert compat_notes["closeout_decision"] == "separate-exit-program"
    assert compat_notes["cleanup_roadmap_status"] == "closed-after-batch10"
    assert "package_v1.3.0.sh still packages src/scripts" in compat_notes["exit_blockers"]
    assert any("authority tests" in blocker for blocker in compat_notes["exit_blockers"])
    assert any("inventory" in blocker and "docs" in blocker for blocker in compat_notes["exit_blockers"])
    assert manifest["mirror_required_policy"]["status"] == "frozen-for-closeout"
    assert manifest["mirror_required_policy"]["change_process"] == "separate-compat-change"
