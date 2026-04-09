from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

import scripts.operator_ui_launcher as launcher


class _DummyProcess:
    def __init__(self, pid: int = 4321):
        self.pid = pid


def test_launch_run_builds_expected_command_and_tracks_pending_run(tmp_path):
    calls = {}

    def fake_popen(cmd, cwd=None, stdout=None, stderr=None):
        calls["cmd"] = cmd
        calls["cwd"] = cwd
        return _DummyProcess()

    ui_launcher = launcher.OperatorUILauncher(
        repo_root=tmp_path,
        now_fn=lambda: datetime(2026, 3, 27, 1, 15, 0, tzinfo=timezone.utc),
        popen_fn=fake_popen,
        run_id_suffix_fn=lambda: "abcd",
    )

    started = ui_launcher.launch_run("fixtures/input.csv", "en-US", "preflight")

    assert started.run_id == "ui_run_20260327_011500_000000_abcd"
    assert started.status == "running"
    assert Path(started.run_dir).exists()
    assert "--run-dir" in calls["cmd"]
    assert "--run-id" in calls["cmd"]
    assert "scripts/run_smoke_pipeline.py" in calls["cmd"]
    assert calls["cwd"] == str(tmp_path)
    assert ui_launcher.get_pending_run(started.run_id).run_id == started.run_id


def test_launch_run_raises_launcher_error_without_leaking_registry(tmp_path):
    def fake_popen(*args, **kwargs):
        raise OSError("boom")

    ui_launcher = launcher.OperatorUILauncher(
        repo_root=tmp_path,
        now_fn=lambda: datetime(2026, 3, 27, 1, 15, 0, tzinfo=timezone.utc),
        popen_fn=fake_popen,
        run_id_suffix_fn=lambda: "boom",
    )

    with pytest.raises(launcher.LauncherError):
        ui_launcher.launch_run("fixtures/input.csv", "en-US", "full")

    assert ui_launcher.list_pending_runs() == []


def test_launch_run_generates_unique_ids_and_run_dirs_with_same_timestamp(tmp_path):
    suffixes = iter(["a1b2", "c3d4"])

    def fake_popen(cmd, cwd=None, stdout=None, stderr=None):
        return _DummyProcess()

    ui_launcher = launcher.OperatorUILauncher(
        repo_root=tmp_path,
        now_fn=lambda: datetime(2026, 3, 27, 1, 15, 0, tzinfo=timezone.utc),
        popen_fn=fake_popen,
        run_id_suffix_fn=lambda: next(suffixes),
    )

    first = ui_launcher.launch_run("fixtures/input.csv", "en-US", "preflight")
    second = ui_launcher.launch_run("fixtures/input.csv", "en-US", "preflight")

    assert first.run_id != second.run_id
    assert first.run_dir != second.run_dir
    assert ui_launcher.get_pending_run(first.run_id).run_id == first.run_id
    assert ui_launcher.get_pending_run(second.run_id).run_id == second.run_id


def test_launch_run_passes_env_to_popen_when_callback_supports_it(tmp_path, monkeypatch):
    calls = {}

    def fake_popen(cmd, cwd=None, stdout=None, stderr=None, env=None):
        calls["cmd"] = cmd
        calls["cwd"] = cwd
        calls["env"] = env
        return _DummyProcess()

    monkeypatch.setenv("BASELINE_ONLY", "keep-me")
    ui_launcher = launcher.OperatorUILauncher(
        repo_root=tmp_path,
        now_fn=lambda: datetime(2026, 3, 27, 1, 15, 0, tzinfo=timezone.utc),
        popen_fn=fake_popen,
        run_id_suffix_fn=lambda: "env1",
        env_provider=lambda: {"LLM_BASE_URL": "https://example.invalid/v1", "LLM_MODEL": "gpt-4.1-mini"},
    )

    ui_launcher.launch_run("fixtures/input.csv", "en-US", "preflight")

    assert calls["cwd"] == str(tmp_path)
    assert calls["env"]["BASELINE_ONLY"] == "keep-me"
    assert calls["env"]["LLM_BASE_URL"] == "https://example.invalid/v1"
    assert calls["env"]["LLM_MODEL"] == "gpt-4.1-mini"
