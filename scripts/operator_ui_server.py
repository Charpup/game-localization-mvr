#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local HTTP server for the operator UI."""

from __future__ import annotations

import argparse
import cgi
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

from scripts.operator_ui_launcher import (
    LauncherError,
    OperatorUILaunchError,
    OperatorUILauncher,
    PendingRunView,
)
from scripts.operator_ui_llm import (
    LLMGateError,
    ensure_llm_launch_ready,
    ensure_llm_task_ready,
    get_llm_launch_env,
    load_llm_setup_view,
    save_llm_setup,
    test_llm_setup,
)
from scripts.operator_ui_models import (
    ArtifactRecord,
    WORKSPACE_CASE_LANES,
    WORKSPACE_CASE_STATUSES,
    WORKSPACE_CARD_PRIORITIES,
    WORKSPACE_CARD_STATUSES,
    WORKSPACE_CARD_TYPES,
    build_pending_run_detail,
    find_run_manifest,
    load_run_detail,
    load_run_summaries,
    load_workspace_cases,
    load_workspace_cards,
    load_workspace_overview,
    load_workspace_run_detail,
)
from scripts.operator_ui_tasks import (
    TASK_ACTIONS,
    TASK_BUCKETS,
    TASK_STATUSES,
    append_human_task_run,
    approve_human_task_delivery,
    archive_human_task,
    create_human_task_record,
    load_task_upload,
    load_human_task_deliveries,
    load_human_task_detail,
    load_human_task_overview,
    load_human_task_summaries,
    mark_task_delivery_downloaded,
    request_human_task_changes,
    resolve_human_task_delivery,
    stage_task_upload,
)


class OperatorUIApp:
    def __init__(self, repo_root: Path | str, launcher: OperatorUILauncher | None = None):
        self.repo_root = Path(repo_root)
        self.frontend_root = self.repo_root / "operator_ui"
        if not self.frontend_root.exists():
            self.frontend_root = Path(__file__).resolve().parents[1] / "operator_ui"
        self.launcher = launcher or OperatorUILauncher(self.repo_root)
        if hasattr(self.launcher, "env_provider"):
            self.launcher.env_provider = lambda: get_llm_launch_env(self.repo_root)

    def _pending_runs_payload(self) -> list[dict[str, Any]]:
        payloads: list[dict[str, Any]] = []
        for pending_run in self.launcher.list_pending_runs():
            payloads.append(pending_run.to_dict() if hasattr(pending_run, "to_dict") else dict(pending_run))
        return payloads

    def list_runs(self, limit: int = 10) -> list[dict[str, Any]]:
        summaries = [summary.to_dict() for summary in load_run_summaries(self.repo_root, limit=limit)]
        known_run_ids = {summary["run_id"] for summary in summaries}
        for pending_run in self._pending_runs_payload():
            if pending_run["run_id"] not in known_run_ids:
                summaries.append(build_pending_run_detail(pending_run).to_dict())
        return summaries[:limit]

    def _get_run_detail_object(self, run_id: str):
        try:
            return load_run_detail(find_run_manifest(self.repo_root, run_id), repo_root=self.repo_root)
        except FileNotFoundError:
            pending_run = self.launcher.get_pending_run(run_id)
            if pending_run is None:
                raise KeyError(run_id) from None
            payload = pending_run.to_dict() if hasattr(pending_run, "to_dict") else dict(pending_run)
            return build_pending_run_detail(payload)

    def get_run_detail(self, run_id: str) -> Dict[str, Any]:
        return self._get_run_detail_object(run_id).to_dict()

    def get_llm_config(self) -> Dict[str, Any]:
        return load_llm_setup_view(self.repo_root)

    def save_llm_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return save_llm_setup(
            self.repo_root,
            base_url=payload.get("base_url"),
            api_key=payload.get("api_key"),
            model=payload.get("model"),
        )

    def test_llm_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        return test_llm_setup(
            self.repo_root,
            base_url=payload.get("base_url"),
            api_key=payload.get("api_key"),
            model=payload.get("model"),
        )

    def start_run(self, payload: Dict[str, Any], *, require_gate: bool = True) -> Dict[str, Any]:
        input_path = str(payload.get("input", "")).strip()
        target_lang = str(payload.get("target_lang", "")).strip()
        verify_mode = str(payload.get("verify_mode", "")).strip()
        if not input_path or not target_lang or not verify_mode:
            raise ValueError("input, target_lang, and verify_mode are required")
        if require_gate:
            ensure_llm_launch_ready(self.repo_root)
        launched = self.launcher.launch_run(input_path, target_lang, verify_mode)
        return launched.to_dict() if hasattr(launched, "to_dict") else dict(launched)

    def upload_task_input(self, filename: str, content: bytes) -> Dict[str, Any]:
        return stage_task_upload(self.repo_root, filename=filename, content=content)

    def list_tasks(self, *, status: str = "", bucket: str = "", query: str = "", limit: int = 25) -> Dict[str, Any]:
        pending_runs = self._pending_runs_payload()
        tasks = load_human_task_summaries(
            self.repo_root,
            pending_runs=pending_runs,
            limit=limit,
            status=status,
            bucket=bucket,
            query=query,
            include_archived=(bucket == "archived"),
        )
        overview = load_human_task_overview(self.repo_root, pending_runs=pending_runs)
        return {
            "overview": overview.to_dict(),
            "tasks": [task.to_dict() for task in tasks[: max(limit, 0)]],
        }

    def get_task_detail(self, task_id: str) -> Dict[str, Any]:
        pending_runs = self._pending_runs_payload()
        return load_human_task_detail(self.repo_root, task_id, pending_runs=pending_runs).to_dict()

    def get_task_deliveries(self, task_id: str) -> Dict[str, Any]:
        pending_runs = self._pending_runs_payload()
        return load_human_task_deliveries(self.repo_root, task_id, pending_runs=pending_runs)

    def get_task_delivery_preview(self, task_id: str, delivery_id: str) -> Dict[str, Any]:
        pending_runs = self._pending_runs_payload()
        task, delivery, artifact = resolve_human_task_delivery(
            self.repo_root,
            task_id,
            delivery_id,
            pending_runs=pending_runs,
        )
        return {
            "task_id": task_id,
            "task": task.to_dict(),
            "delivery": delivery.to_dict(),
            "artifact": self._preview_artifact(artifact),
        }

    def get_task_delivery_download(self, task_id: str, delivery_id: str) -> Dict[str, Any]:
        pending_runs = self._pending_runs_payload()
        _, delivery, artifact = resolve_human_task_delivery(
            self.repo_root,
            task_id,
            delivery_id,
            pending_runs=pending_runs,
        )
        return {
            "delivery": delivery.to_dict(),
            "path": artifact.path,
            "content_type": mimetypes.guess_type(artifact.path)[0] or "application/octet-stream",
            "filename": Path(artifact.path).name,
        }

    def _resolve_task_launch_payload(self, payload: Dict[str, Any]) -> Dict[str, str]:
        input_mode = str(payload.get("input_mode", "")).strip().lower()
        if input_mode not in {"upload", "path"}:
            input_mode = "upload" if str(payload.get("upload_id", "")).strip() else "path"
        target_locale = str(payload.get("target_locale", payload.get("target_lang", ""))).strip()
        verify_mode = str(payload.get("verify_mode", "")).strip()
        title = str(payload.get("title", "")).strip()
        if input_mode == "upload":
            upload_id = str(payload.get("upload_id", "")).strip()
            upload = load_task_upload(self.repo_root, upload_id)
            if upload is None:
                raise ValueError("upload_id is required and must exist")
            return {
                "input_mode": "upload",
                "input_path": str(upload.get("staged_path", "")),
                "input_label": str(upload.get("original_filename", "")),
                "upload_id": upload_id,
                "target_locale": target_locale,
                "verify_mode": verify_mode,
                "title": title,
            }
        input_path = str(payload.get("input_path", payload.get("input", payload.get("source_input", "")))).strip()
        return {
            "input_mode": "path",
            "input_path": input_path,
            "input_label": Path(input_path).name if input_path else "",
            "upload_id": "",
            "target_locale": target_locale,
            "verify_mode": verify_mode,
            "title": title,
        }

    def start_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        ensure_llm_task_ready(self.repo_root)
        launch = self._resolve_task_launch_payload(payload)
        input_path = str(launch.get("input_path", "")).strip()
        target_locale = str(launch.get("target_locale", "")).strip()
        verify_mode = str(launch.get("verify_mode", "")).strip()
        if not input_path or not target_locale or not verify_mode:
            raise ValueError("input_path/upload_id, target_locale, and verify_mode are required")
        launched = self.start_run(
            {"input": input_path, "target_lang": target_locale, "verify_mode": verify_mode},
            require_gate=False,
        )
        title = str(launch.get("title", "")).strip() or str(launch.get("input_label", "")).strip() or Path(input_path).name
        record = create_human_task_record(
            self.repo_root,
            title=title,
            source_input=input_path,
            source_input_label=str(launch.get("input_label", "")).strip(),
            input_mode=str(launch.get("input_mode", "path")),
            upload_id=str(launch.get("upload_id", "")),
            target_locale=target_locale,
            verify_mode=verify_mode,
            linked_run_id=str(launched["run_id"]),
            created_at=str(launched.get("started_at", "")),
        )
        return self.get_task_detail(str(record["task_id"]))

    def perform_task_action(self, task_id: str, action: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if action not in TASK_ACTIONS:
            raise ValueError("unsupported task action")

        request_payload = dict(payload or {})
        task = self.get_task_detail(task_id)
        linked_run_id = str(task.get("latest_run_id", "") or "")

        if action == "refresh_status":
            return {
                "result_status": task["status"],
                "user_message": "Task status refreshed.",
                "next_recommended_step": task["current_step"],
                "linked_run_id": linked_run_id,
                "updated_task_ids": [task_id],
                "task": self.get_task_detail(task_id),
            }
        if action == "open_monitor":
            return {
                "result_status": "ok",
                "user_message": "Open the Ops Monitor to review the linked run.",
                "next_recommended_step": "Switch to Ops Monitor and inspect the linked case.",
                "linked_run_id": linked_run_id,
                "updated_task_ids": [task_id],
                "task": self.get_task_detail(task_id),
            }
        if action == "open_runtime":
            return {
                "result_status": "ok",
                "user_message": "Open Pro Runtime to inspect raw pipeline details.",
                "next_recommended_step": "Switch to Pro Runtime for technical diagnostics.",
                "linked_run_id": linked_run_id,
                "updated_task_ids": [task_id],
                "task": self.get_task_detail(task_id),
            }
        if action == "view_deliveries":
            deliveries = self.get_task_deliveries(task_id)
            return {
                "result_status": "ok",
                "user_message": "Delivery bundle loaded.",
                "next_recommended_step": "Inspect the available delivery artifacts.",
                "linked_run_id": linked_run_id,
                "updated_task_ids": [task_id],
                "task": self.get_task_detail(task_id),
                "deliveries": deliveries["deliveries"],
                "bundle_summary": deliveries["bundle_summary"],
            }
        if action == "approve_delivery":
            deliveries = self.get_task_deliveries(task_id)
            delivery_id = str(request_payload.get("delivery_id", "")).strip() or str(deliveries["bundle_summary"].get("primary_delivery_id", "")).strip()
            if not delivery_id:
                raise ValueError("delivery_id is required when no primary package item is available")
            resolve_human_task_delivery(self.repo_root, task_id, delivery_id, pending_runs=self._pending_runs_payload())
            approve_human_task_delivery(self.repo_root, task_id, delivery_id=delivery_id)
            return {
                "result_status": "ready_for_download",
                "user_message": "The package was approved and is ready to collect.",
                "next_recommended_step": "Open the package and download the files you need.",
                "linked_run_id": linked_run_id,
                "updated_task_ids": [task_id],
                "task": self.get_task_detail(task_id),
                "deliveries": self.get_task_deliveries(task_id)["deliveries"],
            }
        if action == "request_changes":
            note = str(request_payload.get("note", "")).strip()
            if not note:
                raise ValueError("note is required when requesting changes")
            task_detail = self.get_task_detail(task_id)
            input_path = str(task_detail.get("source_input", "")).strip()
            target_locale = str(task_detail.get("target_locale", "")).strip()
            verify_mode = str(task_detail.get("verify_mode", "")).strip()
            if not input_path or not target_locale or not verify_mode:
                request_human_task_changes(self.repo_root, task_id, note=note)
                return {
                    "result_status": "needs_operator_review",
                    "user_message": "Automatic rerun was unavailable, so the task was moved to Waiting on Ops.",
                    "next_recommended_step": "Open the Ops Monitor and inspect the blocked case.",
                    "linked_run_id": linked_run_id,
                    "updated_task_ids": [task_id],
                    "task": self.get_task_detail(task_id),
                }
            try:
                ensure_llm_task_ready(self.repo_root)
                launched = self.launcher.launch_run(input_path, target_locale, verify_mode)
                launched_payload = launched.to_dict() if hasattr(launched, "to_dict") else dict(launched)
                request_human_task_changes(
                    self.repo_root,
                    task_id,
                    note=note,
                    new_run_id=str(launched_payload["run_id"]),
                    at=str(launched_payload.get("started_at", "")),
                )
                return {
                    "result_status": "queued",
                    "user_message": "Your requested changes were recorded and a follow-up run has started.",
                    "next_recommended_step": "Track the follow-up run in the inbox, monitor, or runtime shell.",
                    "linked_run_id": str(launched_payload["run_id"]),
                    "updated_task_ids": [task_id],
                    "task": self.get_task_detail(task_id),
                }
            except (LauncherError, OperatorUILaunchError):
                request_human_task_changes(self.repo_root, task_id, note=note)
                return {
                    "result_status": "needs_operator_review",
                    "user_message": "Automatic rerun failed, so the task was moved to Waiting on Ops.",
                    "next_recommended_step": "Open the Ops Monitor and inspect the blocked case.",
                    "linked_run_id": linked_run_id,
                    "updated_task_ids": [task_id],
                    "task": self.get_task_detail(task_id),
                }
        if action == "rerun":
            task_detail = self.get_task_detail(task_id)
            input_path = str(task_detail.get("source_input", "")).strip()
            target_locale = str(task_detail.get("target_locale", "")).strip()
            verify_mode = str(task_detail.get("verify_mode", "")).strip()
            if not input_path or not target_locale or not verify_mode:
                raise ValueError("task does not contain enough launch metadata to rerun")
            ensure_llm_task_ready(self.repo_root)
            launched = self.launcher.launch_run(input_path, target_locale, verify_mode)
            launched_payload = launched.to_dict() if hasattr(launched, "to_dict") else dict(launched)
            append_human_task_run(
                self.repo_root,
                task_id,
                run_id=str(launched_payload["run_id"]),
                updated_at=str(launched_payload.get("started_at", "")),
                note="A fresh run was launched from the task console.",
            )
            return {
                "result_status": "queued",
                "user_message": "A fresh run has been launched for this task.",
                "next_recommended_step": "Track the rerun in Ops Monitor or Pro Runtime.",
                "linked_run_id": str(launched_payload["run_id"]),
                "updated_task_ids": [task_id],
                "task": self.get_task_detail(task_id),
            }
        if action == "archive_task":
            archive_human_task(self.repo_root, task_id)
            return {
                "result_status": "ok",
                "user_message": "The task was archived from the active inbox.",
                "next_recommended_step": "Use the Archived bucket if you need to reopen the record later.",
                "linked_run_id": linked_run_id,
                "updated_task_ids": [task_id],
                "task": self.get_task_detail(task_id),
            }
        raise ValueError("unsupported task action")

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

    def list_workspace_cases(
        self,
        *,
        status: str = "open",
        lane: str = "all",
        target_locale: str = "",
        query: str = "",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return [
            case.to_dict()
            for case in load_workspace_cases(
                self.repo_root,
                status=status,
                lane=lane,
                target_locale=target_locale,
                query=query,
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
            if parsed.path == "/favicon.ico":
                self.send_response(HTTPStatus.NO_CONTENT)
                self.end_headers()
                return
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
            segments = [segment for segment in parsed.path.strip("/").split("/") if segment]
            if parsed.path == "/api/task_uploads":
                self._handle_task_upload()
                return
            if parsed.path not in {"/api/runs", "/api/tasks", "/api/llm/config", "/api/llm/test"} and not (
                len(segments) == 5 and segments[:2] == ["api", "tasks"] and segments[3] == "actions"
            ):
                self._write_json({"error": "not_found"}, status=HTTPStatus.NOT_FOUND)
                return

            length = int(self.headers.get("Content-Length", "0") or 0)
            raw = self.rfile.read(length) if length else b"{}"
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                self._write_json({"error": "invalid_json"}, status=HTTPStatus.BAD_REQUEST)
                return

            if parsed.path == "/api/llm/config":
                try:
                    llm = app.save_llm_config(payload)
                except ValueError as exc:
                    self._write_json({"error": "bad_request", "detail": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                    return
                self._write_json({"llm": llm})
                return

            if parsed.path == "/api/llm/test":
                try:
                    result = app.test_llm_config(payload)
                except ValueError as exc:
                    self._write_json({"error": "bad_request", "detail": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                    return
                self._write_json({"llm": result})
                return

            if parsed.path == "/api/tasks":
                try:
                    task = app.start_task(payload)
                except LLMGateError as exc:
                    self._write_json({"error": "llm_not_ready", "detail": str(exc)}, status=HTTPStatus.PRECONDITION_FAILED)
                    return
                except ValueError as exc:
                    self._write_json({"error": "bad_request", "detail": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                    return
                except (LauncherError, OperatorUILaunchError) as exc:
                    self._write_json({"error": "launch_failed", "detail": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
                    return
                self._write_json({"task": task}, status=HTTPStatus.ACCEPTED)
                return

            if len(segments) == 5 and segments[:2] == ["api", "tasks"] and segments[3] == "actions":
                task_id = segments[2]
                action = segments[4]
                try:
                    result = app.perform_task_action(task_id, action, payload)
                except LLMGateError as exc:
                    self._write_json({"error": "llm_not_ready", "detail": str(exc)}, status=HTTPStatus.PRECONDITION_FAILED)
                    return
                except FileNotFoundError:
                    self._write_json({"error": "task_not_found"}, status=HTTPStatus.NOT_FOUND)
                    return
                except ValueError as exc:
                    self._write_json({"error": "bad_request", "detail": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                    return
                except (LauncherError, OperatorUILaunchError) as exc:
                    self._write_json({"error": "launch_failed", "detail": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
                    return
                self._write_json(result, status=HTTPStatus.ACCEPTED)
                return

            try:
                launched = app.start_run(payload)
            except LLMGateError as exc:
                self._write_json({"error": "llm_not_ready", "detail": str(exc)}, status=HTTPStatus.PRECONDITION_FAILED)
                return
            except ValueError as exc:
                self._write_json({"error": "bad_request", "detail": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            except (LauncherError, OperatorUILaunchError) as exc:
                self._write_json({"error": "launch_failed", "detail": str(exc)}, status=HTTPStatus.BAD_GATEWAY)
                return

            self._write_json({"run": launched}, status=HTTPStatus.ACCEPTED)

        def _handle_task_upload(self) -> None:
            content_type = self.headers.get("Content-Type", "")
            if "multipart/form-data" not in content_type:
                self._write_json({"error": "bad_request", "detail": "multipart/form-data is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                form = cgi.FieldStorage(
                    fp=self.rfile,
                    headers=self.headers,
                    environ={
                        "REQUEST_METHOD": "POST",
                        "CONTENT_TYPE": content_type,
                    },
                )
            except Exception:
                self._write_json({"error": "bad_request", "detail": "invalid multipart payload"}, status=HTTPStatus.BAD_REQUEST)
                return
            upload_field = form["file"] if "file" in form else None
            if upload_field is None or not getattr(upload_field, "file", None):
                self._write_json({"error": "bad_request", "detail": "file is required"}, status=HTTPStatus.BAD_REQUEST)
                return
            filename = str(getattr(upload_field, "filename", "") or "")
            content = upload_field.file.read()
            if not isinstance(content, (bytes, bytearray)):
                content = bytes(content or b"")
            try:
                upload = app.upload_task_input(filename, bytes(content))
            except ValueError as exc:
                self._write_json({"error": "bad_request", "detail": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._write_json(upload, status=HTTPStatus.ACCEPTED)

        def _handle_api_get(self, parsed) -> None:
            segments = [segment for segment in parsed.path.strip("/").split("/") if segment]
            query = parse_qs(parsed.query)
            if segments == ["api", "llm", "config"] or segments == ["api", "llm", "status"]:
                self._write_json({"llm": app.get_llm_config()})
                return

            if segments == ["api", "tasks"]:
                status = str(query.get("status", [""])[0] or "")
                bucket = str(query.get("bucket", [""])[0] or "")
                text_query = str(query.get("query", [""])[0] or "")
                try:
                    limit = int(query.get("limit", ["25"])[0])
                except (TypeError, ValueError):
                    self._write_json({"error": "bad_request", "detail": "limit must be an integer"}, status=HTTPStatus.BAD_REQUEST)
                    return
                if status and status not in TASK_STATUSES:
                    self._write_json(
                        {
                            "error": "bad_request",
                            "detail": "status must be one of draft/queued/running/needs_user_action/needs_operator_review/ready_for_download/failed",
                        },
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                if bucket and bucket not in TASK_BUCKETS:
                    self._write_json(
                        {
                            "error": "bad_request",
                            "detail": "bucket must be one of all/needs_your_action/running/waiting_on_ops/ready_to_collect/failed/archived",
                        },
                        status=HTTPStatus.BAD_REQUEST,
                    )
                    return
                self._write_json(app.list_tasks(status=status, bucket=bucket, query=text_query, limit=limit))
                return

            if len(segments) == 3 and segments[:2] == ["api", "tasks"]:
                task_id = segments[2]
                try:
                    task = app.get_task_detail(task_id)
                except FileNotFoundError:
                    self._write_json({"error": "task_not_found"}, status=HTTPStatus.NOT_FOUND)
                    return
                self._write_json({"task": task})
                return

            if len(segments) == 4 and segments[:2] == ["api", "tasks"] and segments[3] == "deliveries":
                task_id = segments[2]
                try:
                    payload = app.get_task_deliveries(task_id)
                except FileNotFoundError:
                    self._write_json({"error": "task_not_found"}, status=HTTPStatus.NOT_FOUND)
                    return
                self._write_json(payload)
                return

            if len(segments) == 5 and segments[:2] == ["api", "tasks"] and segments[3] == "deliveries":
                task_id = segments[2]
                delivery_id = segments[4]
                try:
                    payload = app.get_task_delivery_preview(task_id, delivery_id)
                except FileNotFoundError:
                    self._write_json({"error": "delivery_not_found"}, status=HTTPStatus.NOT_FOUND)
                    return
                self._write_json(payload)
                return

            if len(segments) == 6 and segments[:2] == ["api", "tasks"] and segments[3] == "deliveries" and segments[5] == "download":
                task_id = segments[2]
                delivery_id = segments[4]
                try:
                    payload = app.get_task_delivery_download(task_id, delivery_id)
                except FileNotFoundError:
                    self._write_json({"error": "delivery_not_found"}, status=HTTPStatus.NOT_FOUND)
                    return
                delivered = self._write_file(Path(payload["path"]), filename=str(payload["filename"]), content_type=str(payload["content_type"]))
                if delivered:
                    mark_task_delivery_downloaded(app.repo_root, task_id, delivery_id=delivery_id)
                return

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

            if segments == ["api", "workspace", "cases"]:
                status = str(query.get("status", ["open"])[0] or "open")
                lane = str(query.get("lane", ["all"])[0] or "all")
                target_locale = str(query.get("target_locale", [""])[0] or "")
                text_query = str(query.get("query", [""])[0] or "")
                try:
                    limit = int(query.get("limit", ["50"])[0])
                except (TypeError, ValueError):
                    self._write_json({"error": "bad_request", "detail": "limit must be an integer"}, status=HTTPStatus.BAD_REQUEST)
                    return
                if status not in WORKSPACE_CASE_STATUSES:
                    self._write_json({"error": "bad_request", "detail": "status must be one of all/open"}, status=HTTPStatus.BAD_REQUEST)
                    return
                if lane not in WORKSPACE_CASE_LANES:
                    self._write_json({"error": "bad_request", "detail": "lane must be one of all/act/review/watch/done"}, status=HTTPStatus.BAD_REQUEST)
                    return
                self._write_json(
                    {
                        "cases": app.list_workspace_cases(
                            status=status,
                            lane=lane,
                            target_locale=target_locale,
                            query=text_query,
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

        def _write_file(self, path: Path, *, filename: str, content_type: str) -> bool:
            try:
                body = path.read_bytes()
            except FileNotFoundError:
                self._write_json(
                    {
                        "error": "delivery_file_missing",
                        "detail": "The selected delivery file is no longer available on disk.",
                    },
                    status=HTTPStatus.NOT_FOUND,
                )
                return False
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(body)
            return True

    return ThreadingHTTPServer((host, port), Handler)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the operator UI server")
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
