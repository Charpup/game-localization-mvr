#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Local LLM setup persistence and launch gate helpers for the operator UI."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Tuple
from urllib.parse import urlparse

from scripts.runtime_adapter import LLMClient, LLMError


class LLMGateError(ValueError):
    """Raised when the operator UI launch gate is not yet satisfied."""


def _iter_api_key_files() -> list[str]:
    reader = getattr(LLMClient, "_iter_api_key_files", None)
    if not callable(reader):
        return []
    try:
        return [str(path).strip() for path in list(reader()) if str(path).strip()]
    except Exception:
        return []


def _read_api_key_file(path: str) -> str:
    reader = getattr(LLMClient, "_read_api_key_file", None)
    if not callable(reader):
        file_path = Path(path)
        if not file_path.exists():
            return ""
        try:
            for raw_line in file_path.read_text(encoding="utf-8").splitlines():
                text = str(raw_line or "").strip()
                if not text or text.startswith("#"):
                    continue
                if "=" in text and not text.lower().startswith("api key:"):
                    lhs, rhs = text.split("=", 1)
                    if lhs.strip() == "LLM_API_KEY":
                        return rhs.strip().strip("\"'")
                lower = text.lower()
                if lower.startswith("api key:") or lower.startswith("api_key:"):
                    return text.split(":", 1)[1].strip()
                return text.strip().strip("\"'")
        except Exception:
            return ""
        return ""
    try:
        return str(reader(path) or "").strip()
    except Exception:
        return ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _settings_root(repo_root: Path | str) -> Path:
    return Path(repo_root) / "data" / "operator_ui_settings"


def _settings_path(repo_root: Path | str) -> Path:
    return _settings_root(repo_root) / "llm_setup.json"


def _default_credential_path() -> Path:
    return Path.home() / ".game-localization-mvr" / ".llm_credentials"


def _read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize_base_url(value: str) -> str:
    base_url = str(value or "").strip().rstrip("/")
    if not base_url:
        return ""
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("base_url must be a valid http(s) URL")
    return base_url


def _normalize_model(value: str) -> str:
    return str(value or "").strip()


def _mask_api_key(api_key: str) -> str:
    token = str(api_key or "").strip()
    if not token:
        return ""
    if len(token) <= 6:
        return "*" * max(len(token) - 2, 1) + token[-2:]
    return f"{token[:3]}...{token[-4:]}"


def _api_key_digest(api_key: str) -> str:
    token = str(api_key or "").strip()
    if not token:
        return ""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:20]


def _config_fingerprint(base_url: str, model: str, api_key_digest: str) -> str:
    if not base_url or not api_key_digest:
        return ""
    payload = f"{base_url}\n{model.strip()}\n{api_key_digest}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _load_saved_record(repo_root: Path | str) -> Dict[str, Any]:
    record = _read_json(_settings_path(repo_root))
    return {
        "base_url": str(record.get("base_url", "")).strip(),
        "model": str(record.get("model", "")).strip(),
        "credential_path": str(record.get("credential_path", "")).strip(),
        "credential_source": str(record.get("credential_source", "")).strip(),
        "last_test_status": str(record.get("last_test_status", "idle")).strip() or "idle",
        "last_test_at": str(record.get("last_test_at", "")).strip(),
        "last_test_message": str(record.get("last_test_message", "")).strip(),
        "last_test_model": str(record.get("last_test_model", "")).strip(),
        "last_test_latency_ms": int(record.get("last_test_latency_ms", 0) or 0),
        "verified_fingerprint": str(record.get("verified_fingerprint", "")).strip(),
        "updated_at": str(record.get("updated_at", "")).strip(),
    }


def _discover_api_key(record: Dict[str, Any]) -> Tuple[str, str, str]:
    explicit_path = str(record.get("credential_path", "")).strip()
    candidates = [explicit_path] if explicit_path else []
    candidates.extend([path for path in _iter_api_key_files() if path != explicit_path])
    for path in candidates:
        if not path:
            continue
        api_key = _read_api_key_file(path)
        if api_key:
            source = "saved_file" if path == explicit_path else "fallback_file"
            return api_key, source, path
    env_key = os.getenv("LLM_API_KEY", "").strip()
    if env_key:
        return env_key, "environment", ""
    return "", "", ""


def _serialize_view(record: Dict[str, Any]) -> Dict[str, Any]:
    api_key, source, discovered_path = _discover_api_key(record)
    env_base_url = os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    env_model = os.getenv("LLM_MODEL", "").strip()
    base_url = record["base_url"] or env_base_url
    model = record["model"] or env_model
    digest = _api_key_digest(api_key)
    fingerprint = _config_fingerprint(base_url, model, digest)
    last_test_status = record["last_test_status"] if record["last_test_status"] in {"idle", "pass", "fail"} else "idle"
    saved_ready = bool(
        base_url
        and api_key
        and last_test_status == "pass"
        and record.get("verified_fingerprint", "") == fingerprint
    )
    environment_configured = bool(
        not str(record.get("base_url", "")).strip()
        and not str(record.get("credential_path", "")).strip()
        and base_url
        and api_key
    )
    launch_ready = saved_ready
    configured = bool(base_url and api_key)
    credential_path = str(record.get("credential_path", "")).strip() or discovered_path
    display_test_status = last_test_status
    display_test_message = str(record.get("last_test_message", "")).strip()
    if environment_configured and not saved_ready and not display_test_message:
        display_test_message = "Existing local runtime credentials were detected. Run Test connection to unlock launch."
    return {
        "source": "environment" if environment_configured else ("saved" if record["base_url"] or record["credential_path"] else "none"),
        "base_url": base_url,
        "model": model,
        "api_key_masked": _mask_api_key(api_key),
        "has_api_key": bool(api_key),
        "credential_source": source or record.get("credential_source", ""),
        "credential_path": credential_path,
        "configured": configured,
        "verified": saved_ready,
        "can_launch_tasks": saved_ready,
        "can_launch_runtime": launch_ready,
        "launch_ready": launch_ready,
        "status": "ready" if saved_ready else ("configured" if configured else "not_configured"),
        "last_test_status": display_test_status,
        "last_test_at": record.get("last_test_at", ""),
        "last_test_message": display_test_message,
        "last_test_model": record.get("last_test_model", ""),
        "last_test_latency_ms": int(record.get("last_test_latency_ms", 0) or 0),
        "updated_at": record.get("updated_at", ""),
    }


def load_llm_setup_view(repo_root: Path | str) -> Dict[str, Any]:
    return _serialize_view(_load_saved_record(repo_root))


def load_llm_setup(repo_root: Path | str) -> Dict[str, Any]:
    return load_llm_setup_view(repo_root)


def save_llm_setup(
    repo_root: Path | str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> Dict[str, Any]:
    repo_root_path = Path(repo_root)
    current = _load_saved_record(repo_root_path)
    current_key, current_source, current_path = _discover_api_key(current)

    resolved_base_url = current["base_url"] or os.getenv("LLM_BASE_URL", "").strip().rstrip("/")
    if base_url is not None:
        resolved_base_url = _normalize_base_url(base_url)

    resolved_model = current["model"] or os.getenv("LLM_MODEL", "").strip()
    if model is not None:
        resolved_model = _normalize_model(model)

    resolved_key = current_key
    credential_path = current.get("credential_path", "").strip() or current_path
    credential_source = current_source or current.get("credential_source", "").strip()
    submitted_key = str(api_key or "").strip() if api_key is not None else ""
    if submitted_key:
        credential_file = _default_credential_path()
        credential_file.parent.mkdir(parents=True, exist_ok=True)
        credential_file.write_text(f"LLM_API_KEY={submitted_key}\n", encoding="utf-8")
        resolved_key = submitted_key
        credential_path = str(credential_file)
        credential_source = "saved_file"

    digest = _api_key_digest(resolved_key)
    fingerprint = _config_fingerprint(resolved_base_url, resolved_model, digest)
    previous_fingerprint = current.get("verified_fingerprint", "").strip()
    if fingerprint != previous_fingerprint:
        current["last_test_status"] = "idle"
        current["last_test_message"] = "Run Test connection to unlock launch."
        current["last_test_at"] = ""
        current["last_test_model"] = ""
        current["last_test_latency_ms"] = 0
        current["verified_fingerprint"] = ""

    current.update(
        {
            "base_url": resolved_base_url,
            "model": resolved_model,
            "credential_path": credential_path,
            "credential_source": credential_source,
            "updated_at": _now_iso(),
        }
    )
    _write_json(_settings_path(repo_root_path), current)
    return _serialize_view(current)


def test_llm_setup(
    repo_root: Path | str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
    model: str | None = None,
) -> Dict[str, Any]:
    repo_root_path = Path(repo_root)
    save_llm_setup(repo_root_path, base_url=base_url, api_key=api_key, model=model)
    record = _load_saved_record(repo_root_path)
    api_key_value, _source, _path = _discover_api_key(record)
    view = _serialize_view(record)
    if not view["base_url"] or not api_key_value:
        record.update(
            {
                "last_test_status": "fail",
                "last_test_at": _now_iso(),
                "last_test_message": "Enter both base URL and API key before testing.",
                "last_test_model": "",
                "last_test_latency_ms": 0,
                "verified_fingerprint": "",
            }
        )
        _write_json(_settings_path(repo_root_path), record)
        return _serialize_view(record)

    try:
        client = LLMClient(base_url=view["base_url"], api_key=api_key_value, model=view["model"] or None)
        result = client.chat(
            system="You are a connectivity test.",
            user="Reply with exactly: PONG",
            metadata={"step": "llm_ping", "purpose": "human_console_setup_gate"},
        )
        response_text = str(result.text or "").strip().upper()
        if "PONG" not in response_text:
            raise LLMError("parse", f"Unexpected response: {result.text[:100]}", retryable=True)
        fingerprint = _config_fingerprint(view["base_url"], view["model"], _api_key_digest(api_key_value))
        record.update(
            {
                "last_test_status": "pass",
                "last_test_at": _now_iso(),
                "last_test_message": "Connection verified. Translation launch is now unlocked.",
                "last_test_model": str(getattr(result, "model", "") or view["model"] or ""),
                "last_test_latency_ms": int(getattr(result, "latency_ms", 0) or 0),
                "verified_fingerprint": fingerprint,
            }
        )
    except Exception as exc:
        record.update(
            {
                "last_test_status": "fail",
                "last_test_at": _now_iso(),
                "last_test_message": str(exc),
                "last_test_model": "",
                "last_test_latency_ms": 0,
                "verified_fingerprint": "",
            }
        )
    _write_json(_settings_path(repo_root_path), record)
    return _serialize_view(record)


def ensure_llm_launch_ready(repo_root: Path | str) -> Dict[str, Any]:
    view = load_llm_setup_view(repo_root)
    if not view["can_launch_runtime"]:
        raise LLMGateError("LLM setup has not passed Test connection yet. Open LLM Setup and verify the connection first.")
    return view


def ensure_llm_task_ready(repo_root: Path | str) -> Dict[str, Any]:
    view = load_llm_setup_view(repo_root)
    if not view["can_launch_tasks"]:
        raise LLMGateError("Configure and test the LLM connection before starting a localization task.")
    return view


def get_llm_launch_env(repo_root: Path | str) -> Dict[str, str]:
    view = ensure_llm_launch_ready(repo_root)
    env = {"LLM_BASE_URL": str(view["base_url"])}
    if view["credential_path"]:
        env["LLM_API_KEY_FILE"] = str(view["credential_path"])
    if view["model"]:
        env["LLM_MODEL"] = str(view["model"])
    return env


def require_llm_runtime_gate(repo_root: Path | str) -> Dict[str, Any]:
    return ensure_llm_launch_ready(repo_root)


def require_llm_task_gate(repo_root: Path | str) -> Dict[str, Any]:
    return ensure_llm_task_ready(repo_root)


def llm_launch_env(repo_root: Path | str) -> Dict[str, str]:
    return get_llm_launch_env(repo_root)
