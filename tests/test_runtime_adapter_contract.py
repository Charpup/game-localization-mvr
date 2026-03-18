#!/usr/bin/env python3
"""Contract tests for Batch 2 runtime_adapter stabilization."""

import json
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import runtime_adapter
from runtime_adapter import LLMClient, LLMError, LLMResult, LLMRouter


def _make_router(config):
    router = object.__new__(LLMRouter)
    router.config_path = "inline"
    router.config = config
    router.config_hash = "sha256:test"
    router.enabled = config is not None
    return router


def test_router_contracts_cover_chain_params_and_fallback_rules():
    router = _make_router({
        "routing": {
            "translate": {
                "default": "claude-haiku",
                "fallback": ["gpt-4.1-mini"],
                "temperature": 0.1,
                "response_format": {"type": "json_schema"},
                "json_schema": {"name": "payload"},
            },
            "_default": {"default": "fallback-default", "fallback": ["fallback-2"]},
        },
        "capabilities": {
            "gpt-4.1": {"batch": "unfit"},
            "_default": {"batch": "ok"},
        },
        "fallback_triggers": {
            "on_timeout": True,
            "on_network_error": True,
            "on_parse_error": True,
            "http_codes": [429, 503],
        },
    })

    assert router.get_model_chain("translate") == ["claude-haiku", "gpt-4.1-mini"]
    assert router.get_model_chain("unknown_step") == ["fallback-default", "fallback-2"]
    assert router.get_generation_params("translate") == {
        "temperature": 0.1,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": "payload"},
        },
    }
    assert router.check_batch_capability("gpt-4.1") is False
    assert router.check_batch_capability("unknown-model") is True
    assert router.should_fallback(LLMError("timeout", "boom", retryable=True)) is True
    assert router.should_fallback(LLMError("network", "boom", retryable=True)) is True
    assert router.should_fallback(LLMError("parse", "boom", retryable=True)) is True
    assert router.should_fallback(LLMError("http", "fail", retryable=False, http_status=429)) is True

    no_config_router = _make_router(None)
    assert no_config_router.get_model_chain("translate") == []
    assert no_config_router.get_generation_params("translate") == {}
    assert no_config_router.check_batch_capability("anything") is True
    assert no_config_router.should_fallback(LLMError("http", "x", retryable=False)) is False


def test_llm_client_chat_honors_override_router_default_and_batch_enforcement(monkeypatch):
    router = _make_router({
        "routing": {
            "translate": {"default": "gpt-4.1", "fallback": ["claude-haiku", "gpt-4.1-mini"]},
            "_default": {"default": "router-default", "fallback": []},
        },
        "capabilities": {
            "gpt-4.1": {"batch": "unfit"},
            "claude-haiku": {"batch": "ok"},
            "gpt-4.1-mini": {"batch": "ok"},
            "_default": {"batch": "ok"},
        },
        "fallback_triggers": {"http_codes": [503]},
    })

    calls = []

    def fake_call(self, **kwargs):
        calls.append(kwargs["model"])
        if kwargs["model"] == "gpt-4.1":
            raise LLMError("upstream", "retry me", retryable=True, http_status=503)
        return LLMResult(text="ok", latency_ms=1, model=kwargs["model"])

    monkeypatch.setattr(LLMClient, "_call_single_model", fake_call)

    client = LLMClient(
        base_url="https://example.invalid/v1",
        api_key="test-key",
        model="env-default",
        router=router,
    )

    result = client.chat("sys", "user", metadata={"step": "translate", "model_override": "manual-model"})
    assert result.model == "manual-model"
    assert calls == ["manual-model"]

    calls.clear()
    result = client.chat("sys", "user", metadata={"step": "translate"})
    assert result.model == "claude-haiku"
    assert calls == ["gpt-4.1", "claude-haiku"]

    calls.clear()
    result = client.chat("sys", "user", metadata={"step": "translate", "is_batch": True})
    assert result.model == "claude-haiku"
    assert calls == ["claude-haiku"]

    no_chain_router = _make_router({"routing": {}, "capabilities": {}, "fallback_triggers": {}})
    calls.clear()
    client = LLMClient(
        base_url="https://example.invalid/v1",
        api_key="test-key",
        model="env-default",
        router=no_chain_router,
    )
    result = client.chat("sys", "user", metadata={"step": "missing"})
    assert result.model == "env-default"
    assert calls == ["env-default"]

    blocked_router = _make_router({
        "routing": {"translate": {"default": "gpt-4.1", "fallback": []}},
        "capabilities": {"gpt-4.1": {"batch": "unfit"}},
        "fallback_triggers": {},
    })
    client = LLMClient(
        base_url="https://example.invalid/v1",
        api_key="test-key",
        model="",
        router=blocked_router,
    )
    with pytest.raises(LLMError) as exc:
        client.chat("sys", "user", metadata={"step": "translate", "is_batch": True})
    assert exc.value.kind == "config"
    assert exc.value.retryable is False


class _FakeResponse:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def test_single_model_call_classifies_errors_and_emits_trace(monkeypatch):
    trace_events = []
    monkeypatch.setattr(runtime_adapter, "_trace", trace_events.append)

    client = LLMClient(
        base_url="https://example.invalid/v1",
        api_key="test-key",
        model="env-default",
        router=_make_router({"routing": {}, "capabilities": {}, "fallback_triggers": {}}),
    )

    def raise_timeout(*args, **kwargs):
        raise requests.Timeout("slow")

    monkeypatch.setattr(runtime_adapter.requests, "post", raise_timeout)
    with pytest.raises(LLMError) as exc:
        client._call_single_model(
            model="gpt-4.1-mini",
            system="sys",
            user="user",
            temperature=0.0,
            max_tokens=None,
            response_format=None,
            metadata=None,
            step="translate",
            attempt_no=0,
            router_default="gpt-4.1-mini",
            router_chain_len=1,
            model_override=None,
            fallback_used=False,
            fallback_reason=None,
            timeout=3,
        )
    assert exc.value.kind == "timeout"
    assert trace_events[-1]["kind"] == "timeout"

    def raise_network(*args, **kwargs):
        raise requests.RequestException("offline")

    monkeypatch.setattr(runtime_adapter.requests, "post", raise_network)
    with pytest.raises(LLMError) as exc:
        client._call_single_model(
            model="gpt-4.1-mini",
            system="sys",
            user="user",
            temperature=0.0,
            max_tokens=None,
            response_format=None,
            metadata=None,
            step="translate",
            attempt_no=0,
            router_default="gpt-4.1-mini",
            router_chain_len=1,
            model_override=None,
            fallback_used=False,
            fallback_reason=None,
        )
    assert exc.value.kind == "network"

    monkeypatch.setattr(
        runtime_adapter.requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(503, payload={"error": "retry"}, text="server fail"),
    )
    with pytest.raises(LLMError) as exc:
        client._call_single_model(
            model="gpt-4.1-mini",
            system="sys",
            user="user",
            temperature=0.0,
            max_tokens=None,
            response_format=None,
            metadata=None,
            step="translate",
            attempt_no=0,
            router_default="gpt-4.1-mini",
            router_chain_len=1,
            model_override=None,
            fallback_used=False,
            fallback_reason=None,
        )
    assert exc.value.kind == "upstream"
    assert exc.value.http_status == 503

    monkeypatch.setattr(
        runtime_adapter.requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(401, payload={"error": "denied"}, text="unauthorized"),
    )
    with pytest.raises(LLMError) as exc:
        client._call_single_model(
            model="gpt-4.1-mini",
            system="sys",
            user="user",
            temperature=0.0,
            max_tokens=None,
            response_format=None,
            metadata=None,
            step="translate",
            attempt_no=0,
            router_default="gpt-4.1-mini",
            router_chain_len=1,
            model_override=None,
            fallback_used=False,
            fallback_reason=None,
        )
    assert exc.value.kind == "http"
    assert exc.value.retryable is False

    monkeypatch.setattr(
        runtime_adapter.requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(200, payload=ValueError("bad json"), text="oops"),
    )
    with pytest.raises(LLMError) as exc:
        client._call_single_model(
            model="gpt-4.1-mini",
            system="sys",
            user="user",
            temperature=0.0,
            max_tokens=None,
            response_format=None,
            metadata=None,
            step="translate",
            attempt_no=0,
            router_default="gpt-4.1-mini",
            router_chain_len=1,
            model_override=None,
            fallback_used=False,
            fallback_reason=None,
        )
    assert exc.value.kind == "parse"

    monkeypatch.setattr(runtime_adapter, "_estimate_cost", lambda *args, **kwargs: 0.123456)
    monkeypatch.setattr(
        runtime_adapter.requests,
        "post",
        lambda *args, **kwargs: _FakeResponse(
            200,
            payload={
                "id": "req-1",
                "choices": [{"message": {"content": "hello world"}}],
                "usage": {"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
            },
            text="ok",
        ),
    )
    result = client._call_single_model(
        model="gpt-4.1-mini",
        system="sys",
        user="user",
        temperature=0.1,
        max_tokens=128,
        response_format={"type": "json_object"},
        metadata={"batch_idx": 3, "custom": "value"},
        step="translate",
        attempt_no=1,
        router_default="claude-haiku",
        router_chain_len=2,
        model_override=None,
        fallback_used=True,
        fallback_reason="upstream",
    )
    assert result.text == "hello world"
    trace = trace_events[-1]
    assert trace["type"] == "llm_call"
    assert trace["usage_source"] == "api_usage"
    assert trace["fallback_used"] is True
    assert trace["fallback_reason"] == "upstream"
    assert trace["router_default_model"] == "claude-haiku"
    assert trace["attempt_no"] == 1
    assert trace["router_chain_len"] == 2
    assert trace["batch_id"] == "translate:000003"
    assert trace["meta"] == {"custom": "value"}
    assert trace["cost_usd_est"] == 0.123456


def test_batch_llm_call_retries_and_partial_match_forwarding(monkeypatch, tmp_path):
    class FakeConfig:
        def get_batch_size(self, model, content_type="normal"):
            return 2

        def get_timeout(self, model, content_type="normal"):
            return 5

        def get_cooldown(self, model):
            return 0

    class FakeClient:
        def chat(self, **kwargs):
            return type("Resp", (), {"text": "[]", "request_id": "req-1", "usage": None})()

    parse_calls = []
    attempts = {"count": 0}
    progress_events = []

    def fake_parse(text, expected_rows, partial_match=False):
        parse_calls.append(partial_match)
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ValueError("parse failed once")
        return [{"id": row["id"]} for row in expected_rows]

    def fake_log(step, event_type, data, silent=False):
        progress_events.append((event_type, data.get("status")))

    monkeypatch.setattr(runtime_adapter, "get_batch_config", lambda: FakeConfig())
    monkeypatch.setattr(runtime_adapter, "LLMClient", FakeClient)
    monkeypatch.setattr(runtime_adapter, "parse_llm_response", fake_parse)
    monkeypatch.setattr(runtime_adapter, "log_llm_progress", fake_log)
    monkeypatch.setattr(runtime_adapter.time, "sleep", lambda *_args, **_kwargs: None)

    output_dir = tmp_path / "out"
    rows = [{"id": "1", "source_text": "a"}, {"id": "2", "source_text": "b"}]
    result = runtime_adapter.batch_llm_call(
        step="soft_qa",
        rows=rows,
        model="claude-haiku",
        system_prompt="sys",
        user_prompt_template=lambda items: json.dumps(items),
        partial_match=True,
        allow_fallback=True,
        retry=1,
        output_dir=str(output_dir),
    )

    assert result == [{"id": "1"}, {"id": "2"}]
    assert parse_calls == [True, True]
    assert ("batch_complete", "ok") in progress_events
    assert (output_dir / "soft_qa_checkpoint.json").exists()
    assert (output_dir / "soft_qa_heartbeat.txt").exists()
    assert (output_dir / "soft_qa_DONE").exists()


def test_batch_llm_call_writes_failed_batch_report_when_enabled(monkeypatch, tmp_path):
    class FakeConfig:
        def get_batch_size(self, model, content_type="normal"):
            return 1

        def get_timeout(self, model, content_type="normal"):
            return 5

        def get_cooldown(self, model):
            return 0

    class FailingClient:
        def chat(self, **kwargs):
            raise LLMError("upstream", "still failing", retryable=True, http_status=503)

    monkeypatch.setattr(runtime_adapter, "get_batch_config", lambda: FakeConfig())
    monkeypatch.setattr(runtime_adapter, "LLMClient", FailingClient)
    monkeypatch.setattr(runtime_adapter.time, "sleep", lambda *_args, **_kwargs: None)
    monkeypatch.chdir(tmp_path)

    rows = [{"id": "1", "source_text": "a"}]
    result = runtime_adapter.batch_llm_call(
        step="soft_qa",
        rows=rows,
        model="claude-haiku",
        system_prompt="sys",
        user_prompt_template=lambda items: json.dumps(items),
        retry=0,
        save_partial=True,
        output_dir=str(tmp_path / "out"),
    )
    assert result == []
    assert (tmp_path / "reports" / "soft_qa_failed_batches.json").exists()
