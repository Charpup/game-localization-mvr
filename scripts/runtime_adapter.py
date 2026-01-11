#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
runtime_adapter.py
A thin, production-oriented LLM adapter:
- OpenAI-compatible chat completions by default
- Standardized errors and retry hints
- Optional trace logging (jsonl)

Env:
  LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
  LLM_TIMEOUT_S (default 60)
  LLM_TRACE_PATH (optional, default data/llm_trace.jsonl)
"""

from __future__ import annotations
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any

import requests


@dataclass
class LLMResult:
    """Result of a successful LLM call."""
    text: str
    latency_ms: int
    raw: Optional[dict] = None
    usage: Optional[dict] = None  # {prompt_tokens, completion_tokens, total_tokens}


class LLMError(Exception):
    """
    Standardized LLM error with retry hints.
    
    Kinds:
      - config: Missing configuration (not retryable)
      - timeout: Request timeout (retryable)
      - network: Network error (retryable)
      - upstream: Server error 429/5xx (retryable)
      - http: Client error 4xx (not retryable)
      - parse: Response parse error (retryable - model may fix on retry)
    """
    def __init__(self, kind: str, message: str, retryable: bool = True):
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable


def _trace(event: Dict[str, Any]) -> None:
    """Append trace event to JSONL file."""
    path = os.getenv("LLM_TRACE_PATH", "data/llm_trace.jsonl").strip()
    if not path:
        return
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        event["timestamp"] = datetime.now().isoformat()
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception:
        pass  # Tracing should never break the main flow


class LLMClient:
    """
    OpenAI-compatible LLM client.
    
    Usage:
        from runtime_adapter import LLMClient, LLMError
        
        llm = LLMClient()
        try:
            result = llm.chat(system="You are helpful.", user="Hello!")
            print(result.text)
        except LLMError as e:
            if e.retryable:
                # retry logic
                pass
            else:
                raise
    """
    
    def __init__(self, 
                 base_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 model: Optional[str] = None,
                 timeout_s: Optional[int] = None):
        """
        Initialize LLM client. Parameters can be passed directly or via environment.
        
        Priority: explicit parameter > environment variable
        """
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "")).strip().rstrip("/")
        self.api_key = (api_key or os.getenv("LLM_API_KEY", "")).strip()
        self.model = (model or os.getenv("LLM_MODEL", "")).strip()
        self.timeout_s = timeout_s or int(os.getenv("LLM_TIMEOUT_S", "60"))

        if not self.base_url or not self.api_key or not self.model:
            raise LLMError(
                "config",
                "Missing LLM configuration. Set env vars: LLM_BASE_URL, LLM_API_KEY, LLM_MODEL",
                retryable=False
            )

    def chat(self, 
             system: str, 
             user: str, 
             temperature: float = 0.2,
             max_tokens: Optional[int] = None,
             step: Optional[str] = None) -> LLMResult:
        """
        Send a chat completion request.
        
        Args:
            system: System prompt
            user: User message
            temperature: Sampling temperature (default 0.2 for consistency)
            max_tokens: Optional max tokens limit
            step: Optional step name for metrics (e.g., 'translate', 'soft_qa', 'repair')
            
        Returns:
            LLMResult with text, latency_ms, raw response, and usage
            
        Raises:
            LLMError with kind and retryable flag
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens

        t0 = time.time()
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout_s)
        except requests.Timeout as e:
            _trace({"type": "llm_error", "kind": "timeout", "msg": str(e), "model": self.model})
            raise LLMError("timeout", f"Request timeout after {self.timeout_s}s: {e}", retryable=True)
        except requests.RequestException as e:
            _trace({"type": "llm_error", "kind": "network", "msg": str(e), "model": self.model})
            raise LLMError("network", f"Network error: {e}", retryable=True)

        latency_ms = int((time.time() - t0) * 1000)

        # Handle HTTP errors
        if resp.status_code in (429, 500, 502, 503, 504):
            _trace({
                "type": "llm_error", 
                "kind": "upstream", 
                "status": resp.status_code, 
                "body": resp.text[:500],
                "model": self.model
            })
            raise LLMError(
                "upstream", 
                f"Upstream error HTTP {resp.status_code}: {resp.text[:200]}", 
                retryable=True
            )

        if resp.status_code >= 400:
            _trace({
                "type": "llm_error", 
                "kind": "http", 
                "status": resp.status_code, 
                "body": resp.text[:500],
                "model": self.model
            })
            raise LLMError(
                "http", 
                f"HTTP error {resp.status_code}: {resp.text[:200]}", 
                retryable=False
            )

        # Parse response
        try:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
        except Exception as e:
            _trace({
                "type": "llm_error", 
                "kind": "parse", 
                "msg": str(e), 
                "body": resp.text[:800],
                "model": self.model
            })
            raise LLMError("parse", f"Response parse error: {e}", retryable=True)

        # Extract usage info if present
        usage = data.get("usage") or {}
        
        # Log successful call with usage and step
        _trace({
            "type": "llm_call",
            "model": self.model,
            "step": step or "unknown",
            "latency_ms": latency_ms,
            "req_chars": len(system) + len(user),
            "resp_chars": len(text),
            "usage": usage if usage else None,
        })
        
        return LLMResult(text=text, latency_ms=latency_ms, raw=data, usage=usage if usage else None)


# Convenience function for simple calls
def chat(system: str, user: str, **kwargs) -> str:
    """Simple chat function that returns just the text."""
    client = LLMClient()
    return client.chat(system=system, user=user, **kwargs).text
