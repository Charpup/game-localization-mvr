#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Launcher adapter for the Phase 5 frontend runtime shell."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional


class LauncherError(RuntimeError):
    """Raised when the runtime shell cannot start a representative run."""


class OperatorUILaunchError(LauncherError):
    """Backward-compatible alias used by the HTTP server."""


@dataclass
class PendingRunView:
    run_id: str
    run_dir: str
    status: str
    pid: Optional[int]
    started_at: str
    command: List[str]
    input_csv: str
    target_lang: str
    verify_mode: str

    def to_dict(self) -> Dict[str, object]:
        return {
            "run_id": self.run_id,
            "run_dir": self.run_dir,
            "status": self.status,
            "pid": self.pid,
            "started_at": self.started_at,
            "command": list(self.command),
            "input_csv": self.input_csv,
            "target_lang": self.target_lang,
            "verify_mode": self.verify_mode,
        }


class OperatorUILauncher:
    def __init__(
        self,
        repo_root: Path | str,
        python_executable: Optional[str] = None,
        now_fn: Optional[Callable[[], datetime]] = None,
        popen_fn: Optional[Callable[..., object]] = None,
    ):
        self.repo_root = Path(repo_root)
        self.python_executable = python_executable or sys.executable
        self.now_fn = now_fn or (lambda: datetime.now(timezone.utc))
        self.popen_fn = popen_fn or subprocess.Popen
        self.pending_runs: Dict[str, Dict[str, object]] = {}

    def create_run_id(self, now: Optional[datetime] = None) -> str:
        timestamp = now or self.now_fn()
        return f"ui_run_{timestamp.strftime('%Y%m%d_%H%M%S')}"

    def build_run_dir(self, run_id: str) -> Path:
        return self.repo_root / "data" / "operator_ui_runs" / run_id

    def build_run_command(
        self,
        input_path: Path | str,
        target_lang: str,
        verify_mode: str,
        run_id: str,
        run_dir: Path | str,
    ) -> List[str]:
        return [
            self.python_executable,
            "scripts/run_smoke_pipeline.py",
            "--input",
            str(input_path),
            "--run-dir",
            str(run_dir),
            "--run-id",
            run_id,
            "--target-lang",
            target_lang,
            "--verify-mode",
            verify_mode,
        ]

    def _materialize_pending_view(self, pending_run: Dict[str, object]) -> PendingRunView:
        return PendingRunView(
            run_id=str(pending_run["run_id"]),
            run_dir=str(pending_run["run_dir"]),
            status=str(pending_run["status"]),
            pid=int(pending_run["pid"]) if pending_run.get("pid") is not None else None,
            started_at=str(pending_run["started_at"]),
            command=list(pending_run["command"]),
            input_csv=str(pending_run["input_csv"]),
            target_lang=str(pending_run["target_lang"]),
            verify_mode=str(pending_run["verify_mode"]),
        )

    def refresh_pending_runs(self) -> None:
        for pending_run in self.pending_runs.values():
            process = pending_run.get("_process")
            if process is None or not hasattr(process, "poll"):
                continue
            returncode = process.poll()
            if returncode is None:
                continue
            pending_run["status"] = "failed" if returncode else "completed"
            pending_run["returncode"] = returncode
            pending_run.pop("_process", None)

    def list_pending_runs(self) -> List[PendingRunView]:
        self.refresh_pending_runs()
        return [self._materialize_pending_view(pending) for pending in self.pending_runs.values()]

    def get_pending_run(self, run_id: str) -> Optional[PendingRunView]:
        self.refresh_pending_runs()
        pending_run = self.pending_runs.get(run_id)
        if pending_run is None:
            return None
        return self._materialize_pending_view(pending_run)

    def launch_run(self, input_path: str, target_lang: str, verify_mode: str) -> PendingRunView:
        run_id = self.create_run_id()
        run_dir = self.build_run_dir(run_id)
        run_dir.mkdir(parents=True, exist_ok=True)
        command = self.build_run_command(input_path, target_lang, verify_mode, run_id, run_dir)

        try:
            process = self.popen_fn(
                command,
                cwd=str(self.repo_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError as exc:
            raise LauncherError(f"Failed to start smoke pipeline: {exc}") from exc

        pending_run: Dict[str, object] = {
            "run_id": run_id,
            "run_dir": str(run_dir),
            "status": "running",
            "pid": getattr(process, "pid", None),
            "started_at": self.now_fn().isoformat(),
            "target_lang": target_lang,
            "verify_mode": verify_mode,
            "input_csv": input_path,
            "command": command,
            "_process": process,
        }
        self.pending_runs[run_id] = pending_run
        return self._materialize_pending_view(pending_run)

    def start_run(self, input_path: str, target_lang: str, verify_mode: str) -> Dict[str, object]:
        return self.launch_run(input_path, target_lang, verify_mode).to_dict()
