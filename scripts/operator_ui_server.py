#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local HTTP server for the Phase 5 frontend runtime shell."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.operator_ui_launcher import LauncherError, OperatorUILaunchError, OperatorUILauncher, PendingRunView
from scripts.operator_ui_models import (
    ArtifactRecord,
    WORKSPACE_CARD_PRIORITIES,
    WORKSPACE_CARD_STATUSES,
    WORKSPACE_CARD_TYPES,
    build_pending_run_detail,
    find_run_manifest,
    load_run_detail,
    load_run_summaries,
    load_workspace_cards,
    load_workspace_overview,
    load_workspace_run_detail,
)


class OperatorUIApp:
    def __init__(self, repo_root: Path | str, launcher: OperatorUILauncher | None = None):
        self.repo_root = Path(repo_root)
        self.frontend_root = self.repo_root / "operator_ui"
        if not self.frontend_root.exists():
            self.frontend_root = Path(__file__).resolve().parents[1] / "operator_ui"
        self.launcher = launcher or OperatorUILauncher(self.repo_root)

    def list_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        summaries = [summary.to_dict() for summary in load_run_summaries(self.repo_root, limit=limit)]
        known_run_ids = {summary["run_id"] for summary in summaries}
        for pending_run in self.launcher.list_pending_runs():
            payload = pending_run.to_dict() if hasattr(pending_run, "to_dict") else dict(pending_run)
            if payload["run_id"] not in known_run_ids:
                summaries.append(build_pending_run_detail(payload).to_dict())
        return summaries[:limit]

    def get_run_detail(self, run_id: str) -> Dict[str, Any]:
        return self._get_run_detail_object(run_id).to_dict()

    def _get_run_detail_object(self, run_id: str):
        try:
            return load_run_detail(find_run_manifest(self.repo_root, run_id), repo_root=self.repo_root)
        except FileNotFoundError:
            pending_run = self.launcher.get_pending_run(run_id)
            if pending_run is None:
                raise KeyError(run_id) from None
            payload = pending_run.to_dict() if hasattr(pending_run, "to_dict") else dict(pending_run)
            return build_pending_run_detail(payload)

    def start_run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        input_path = str(payload.get("input", "")).strip()
        target_lang = str(payload.get("target_lang", "")).strip()
        verify_mode = str(payload.get("verify_mode", "")).strip()
        if not input_path or not target_lang or not verify_mode:
            raise ValueError("input, target_lang, and verify_mode are required")
        launched = self.launcher.launch_run(input_path, target_lang, verify_mode)
        return launched.to_dict() if hasattr(launched, "to_dict") else dict(launched)

    def get_artifact_preview(self, run_id: str, artifact_key: str) -> Dict[str, Any]:
        detail = self._get_run_detail_object(run_id)
        artifact = detail.artifacts.get(artifact_key)
        if artifact is None or artifact_key not in detail.allowed_artifact_keys:
            raise KeyError(artifact_key)
        return {"artifact": self._preview_artifact(artifact)}

    def get_workspace_overview(self, limit_runs: int = 10) -> Dict[str, Any]:
        overview = load_workspace_overview(self.repo_root, limit_runs=limit_runs)
        payload = overview.to_dict()
        payload["recent_runs"] = self.list_runs(limit=limit_runs)
        return payload

    def list_workspace_cards(
        self,
        *,
        status: str = "open",
        card_type: str = "",
        priority: str = "",
        target_locale: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return [
            card.to_dict()
            for card in load_workspace_cards(
            self.repo_root,
            status=status,
            card_type=card_type,
            priority=priority,
            target_locale=target_locale,
            limit=limit,
        )
        ]

    def get_workspace_run_detail(self, run_id: str) -> Dict[str, Any]:
        try:
            return load_workspace_run_detail(self.repo_root, run_id).to_dict()
        except FileNotFoundError:
            raise KeyError(run_id) from None

    def _preview_artifact(self, artifact: ArtifactRecord) -> Dict[str, Any]:
        payload = artifact.to_dict()
        artifact_path = Path(artifact.path)
        if not artifact.exists:
            payload["content"] = None
            return payload

        if artifact.kind == "json":
            try:
                payload["json"] = json.loads(artifact_path.read_text(encoding="utf-8"))
            except Exception:
                payload["json"] = None
            return payload

        if artifact.kind == "text":
            payload["content"] = artifact_path.read_text(encoding="utf-8", errors="replace")
            return payload

        payload["content"] = None
        return payload

    def serve_static(self, asset_name: str) -> tuple[bytes, str]:
        safe_name = asset_name.strip("/") or "index.html"
        if safe_name not in {"index.html", "styles.css", "app.js"}:
            raise FileNotFoundError(safe_name)
        asset_path = self.frontend_root / safe_name
        if not asset_path.exists():
            raise FileNotFoundError(safe_name)
        content_type, _ = mimetypes.guess_type(str(asset_path))
        return asset_path.read_bytes(), content_type or "application/octet-stream"

    def create_http_server(self, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
        return build_http_server(host, port, self)


OperatorUIServer = OperatorUIApp


def build_http_server(host: str, port: int, app: OperatorUIApp) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        server_version = "OperatorUI/0.1"

        def log_message(self, format: str, *args: Any) -> None:  # pragma: no cover
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/"):
                self._handle_api_get(parsed)
                return
            try:
                content, content_type = app.serve_static("index.html" if parsed.path == "/" else parsed.path.lstrip("/"))
            except FileNotFoundError:
                self._write_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
                return
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/api/runs":
                self._write_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
                return

            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                self._write_json({"error": "invalid_json"}, status=HTTPStatus.BAD_REQUEST)
                return

            try:
                launched = app.start_run(payload)
            except ValueError as exc:
                self._write_json({"error": "bad_request", "detail": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            except (LauncherError, OperatorUILaunchError) as exc:
                self._write_json({"error": "launch_failed", "detail": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
                return

            self._write_json({"run": launched}, status=HTTPStatus.ACCEPTED)

        def _handle_api_get(self, parsed) -> None:
            segments = [segment for segment in parsed.path.strip("/").split("/") if segment]
            query = parse_qs(parsed.query)
            if segments == ["api", "workspace", "overview"]:
                try:
                    limit_runs = int(query.get("limit_runs", ["10"])[0])
                except (TypeError, ValueError):
                    self._write_json({"error": "bad_request", "detail": "limit_runs must be an integer"}, status=HTTPStatus.BAD_REQUEST)
                    return
                self._write_json({"overview": app.get_workspace_overview(limit_runs=limit_runs)})
                return

            if segments == ["api", "workspace", "cards"]:
                status = str(query.get("status", ["open"])[0] or "open")
                card_type = str(query.get("card_type", [""])[0] or "")
                priority = str(query.get("priority", [""])[0] or "").upper()
                target_locale = str(query.get("target_locale", [""])[0] or "")
                try:
                    limit = int(query.get("limit", ["50"])[0])
                except (TypeError, ValueError):
                    self._write_json({"error": "bad_request", "detail": "limit must be an integer"}, status=HTTPStatus.BAD_REQUEST)
                    return
                if status not in WORKSPACE_CARD_STATUSES:
                    self._write_json({"error": "bad_request", "detail": "status must be one of all/open/closed"}, status=HTTPStatus.BAD_REQUEST)
                    return
                if card_type and card_type not in WORKSPACE_CARD_TYPES:
                    self._write_json({"error": "bad_request", "detail": "unsupported card_type"}, status=HTTPStatus.BAD_REQUEST)
                    return
                if priority and priority not in WORKSPACE_CARD_PRIORITIES:
                    self._write_json({"error": "bad_request", "detail": "unsupported priority"}, status=HTTPStatus.BAD_REQUEST)
                    return
                self._write_json(
                    {
                        "cards": app.list_workspace_cards(
                            status=status,
                            card_type=card_type,
                            priority=priority,
                            target_locale=target_locale,
                            limit=limit,
                        )
                    }
                )
                return

            if len(segments) == 4 and segments[:3] == ["api", "workspace", "runs"]:
                run_id = segments[3]
                try:
                    workspace = app.get_workspace_run_detail(run_id)
                except KeyError:
                    self._write_json({"error": "run_not_found"}, status=HTTPStatus.NOT_FOUND)
                    return
                self._write_json({"workspace": workspace})
                return

            if segments == ["api", "runs"]:
                try:
                    limit = int(query.get("limit", ["10"])[0])
                except (TypeError, ValueError):
                    self._write_json({"error": "bad_request", "detail": "limit must be an integer"}, status=HTTPStatus.BAD_REQUEST)
                    return
                self._write_json({"runs": app.list_runs(limit=limit)})
                return

            if len(segments) == 3 and segments[:2] == ["api", "runs"]:
                run_id = segments[2]
                try:
                    detail = app.get_run_detail(run_id)
                except KeyError:
                    self._write_json({"error": "run_not_found"}, status=HTTPStatus.NOT_FOUND)
                    return
                self._write_json({"run": detail})
                return

            if len(segments) == 5 and segments[:2] == ["api", "runs"] and segments[3] == "artifacts":
                run_id = segments[2]
                artifact_key = segments[4]
                try:
                    preview = app.get_artifact_preview(run_id, artifact_key)
                except KeyError:
                    self._write_json({"error": "artifact_not_found"}, status=HTTPStatus.NOT_FOUND)
                    return
                self._write_json(preview)
                return

            self._write_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)

        def _write_json(self, payload: Dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return ThreadingHTTPServer((host, port), Handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the Phase 5 operator UI server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    app = OperatorUIApp(Path(__file__).resolve().parents[1])
    httpd = app.create_http_server(host=args.host, port=args.port)
    print(f"Operator UI listening on http://{args.host}:{args.port}")
    httpd.serve_forever()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
