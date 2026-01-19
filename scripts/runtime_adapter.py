#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
runtime_adapter.py (v1.1)

A thin, production-oriented LLM adapter:
- OpenAI-compatible chat completions by default
- Standardized errors and retry hints
- Trace logging with request_id, step, usage tokens

Key features in v1.1:
- Trace includes: request_id, step, usage tokens (if present), usage_present flag
- chat() supports metadata={"step": "...", ...} for downstream cost attribution
- Keeps req_chars/resp_chars for fallback token estimation

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
    request_id: Optional[str] = None
    usage: Optional[dict] = None  # {"prompt_tokens": int, "completion_tokens": int, "total_tokens": int}


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
    def __init__(self, kind: str, message: str, 
                 retryable: bool = True,
                 http_status: Optional[int] = None):
        super().__init__(message)
        self.kind = kind
        self.retryable = retryable
        self.http_status = http_status  # For fallback decisions


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


def _safe_int(x, default: int = 0) -> int:
    """Safely convert to int."""
    try:
        return int(x)
    except Exception:
        return default


# Token estimation constants
CHARS_PER_TOKEN = 4  # Conservative for CJK/Cyrillic mix


def _estimate_tokens(text: str) -> int:
    """Estimate token count from text using chars/4 heuristic."""
    return max(1, len(text or "") // CHARS_PER_TOKEN)


# Pricing loader (cached)
_pricing_cache: Optional[Dict[str, Any]] = None


def _load_pricing() -> Dict[str, Any]:
    """Load pricing config from pricing.yaml."""
    global _pricing_cache
    if _pricing_cache is not None:
        return _pricing_cache
    
    try:
        import yaml
        pricing_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config", "pricing.yaml"
        )
        if not os.path.exists(pricing_path):
            pricing_path = "config/pricing.yaml"
        if os.path.exists(pricing_path):
            with open(pricing_path, 'r', encoding='utf-8') as f:
                _pricing_cache = yaml.safe_load(f) or {}
                return _pricing_cache
    except Exception:
        pass
    _pricing_cache = {}
    return _pricing_cache


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate cost in USD based on pricing.yaml."""
    pricing = _load_pricing()
    models = pricing.get("models", {})
    model_config = models.get(model, {})
    
    # Use per_1M pricing if available
    input_per_1m = model_config.get("input_per_1M", 0)
    output_per_1m = model_config.get("output_per_1M", 0)
    
    if input_per_1m > 0 or output_per_1m > 0:
        cost = (prompt_tokens * input_per_1m / 1_000_000) + \
               (completion_tokens * output_per_1m / 1_000_000)
        return round(cost, 6)
    
    return 0.0


def _extract_usage(data: dict) -> Optional[dict]:
    """
    Extract OpenAI-style usage info:
      data["usage"] = {"prompt_tokens":..., "completion_tokens":..., "total_tokens":...}
    Some gateways omit this field.
    """
    u = data.get("usage")
    if not isinstance(u, dict):
        return None
    
    pt = u.get("prompt_tokens")
    ct = u.get("completion_tokens")
    tt = u.get("total_tokens")
    
    if pt is None and ct is None and tt is None:
        return None
    
    pt_i = _safe_int(pt, 0)
    ct_i = _safe_int(ct, 0)
    tt_i = _safe_int(tt, pt_i + ct_i)
    
    return {
        "prompt_tokens": pt_i,
        "completion_tokens": ct_i,
        "total_tokens": tt_i
    }


# -----------------------------
# LLM Router (Step-based model selection)
# -----------------------------

try:
    import yaml
except ImportError:
    yaml = None

import hashlib
from typing import List


class LLMRouter:
    """
    Step-based model router with fallback support.
    
    Loads routing config from llm_routing.yaml and selects models based on step.
    Router does NOT retry - only switches to next model in chain on failure.
    
    Model selection priority:
        1. metadata.model_override (highest)
        2. routing.yaml step config
        3. env LLM_MODEL
        4. raise config error
    """
    
    DEFAULT_CONFIG_PATH = "config/llm_routing.yaml"
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = self._load_config()
        self.config_hash = self._compute_hash()
        self.enabled = self.config is not None
        
        if not self.enabled:
            _trace({
                "type": "router_init",
                "router_disabled": True,
                "reason": "config_not_found",
                "config_path": self.config_path
            })
    
    def _load_config(self) -> Optional[Dict[str, Any]]:
        """Load routing config from YAML file."""
        if yaml is None:
            return None
        
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            self.config_path
        ) if not os.path.isabs(self.config_path) else self.config_path
        
        # Also try relative to cwd
        if not os.path.exists(config_path):
            config_path = self.config_path
        
        if not os.path.exists(config_path):
            return None
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception:
            return None
    
    def _compute_hash(self) -> str:
        """Compute sha256 hash of config for versioning."""
        if not self.config:
            return ""
        content = json.dumps(self.config, sort_keys=True, ensure_ascii=False)
        return f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]}"
    
    def get_model_chain(self, step: str) -> List[str]:
        """
        Return [default, ...fallbacks] for a step.
        
        Falls back to _default if step not found.
        """
        if not self.config or "routing" not in self.config:
            return []
        
        routing = self.config["routing"]
        step_config = routing.get(step) or routing.get("_default", {})
        
        chain = []
        default = step_config.get("default")
        if default:
            chain.append(default)
        
        fallbacks = step_config.get("fallback", [])
        if isinstance(fallbacks, list):
            chain.extend(fallbacks)
        
        return chain
    
    def get_default_model(self, step: str) -> Optional[str]:
        """Return default model for step."""
        chain = self.get_model_chain(step)
        return chain[0] if chain else None

    def get_generation_params(self, step: str) -> Dict[str, Any]:
        """Return generation parameters (temperature, max_tokens, etc) for step."""
        if not self.config or "routing" not in self.config:
            return {}
        
        routing = self.config["routing"]
        step_config = routing.get(step) or routing.get("_default", {})
        
        # Extract params
        params = {}
        for key in ["temperature", "max_tokens", "json_schema", "response_format"]:
            if key in step_config:
                params[key] = step_config[key]
                
        # Validate json_schema structure if present
        if "response_format" in params and params["response_format"].get("type") == "json_schema":
            if "json_schema" not in params["response_format"]:
                # Map flattened json_schema to response_format if needed
                if "json_schema" in params:
                    params["response_format"]["json_schema"] = params["json_schema"]
                    del params["json_schema"]
                    
        return params
    
    def should_fallback(self, error: LLMError) -> bool:
        """
        Check if error should trigger fallback to next model.
        
        Uses error.kind and error.http_status to make decision.
        """
        if not self.config or "fallback_triggers" not in self.config:
            return error.retryable
        
        triggers = self.config["fallback_triggers"]
        
        # Check by error kind
        if error.kind == "timeout" and triggers.get("on_timeout", False):
            return True
        if error.kind == "network" and triggers.get("on_network_error", False):
            return True
        if error.kind == "parse" and triggers.get("on_parse_error", False):
            return True
        
        # Check by HTTP status (explicit None check)
        if error.http_status is not None:
            http_codes = triggers.get("http_codes", [])
            if error.http_status in http_codes:
                return True
        
        return False


class LLMClient:
    """
    OpenAI-compatible LLM client with step-based model routing.
    
    Usage:
        from runtime_adapter import LLMClient, LLMError
        
        llm = LLMClient()
        try:
            result = llm.chat(
                system="You are helpful.",
                user="Hello!",
                metadata={"step": "translate", "batch_id": "0"}
            )
            print(result.text)
        except LLMError as e:
            if e.retryable:
                # retry logic
                pass
            else:
                raise
    
    Model selection priority:
        1. metadata.model_override
        2. routing.yaml step config
        3. env LLM_MODEL
        4. raise config error
    """
    
    # Shared router instance
    _router: Optional[LLMRouter] = None
    
    @staticmethod
    def _load_api_key() -> str:
        """
        Load API key with file-based injection support.
        
        Priority:
            1. LLM_API_KEY_FILE: Read key from file (supports "api key: xxx" format)
            2. LLM_API_KEY: Direct environment variable
        
        Returns:
            API key string (may be empty if not configured)
        """
        # Try file-based injection first
        key_file = os.getenv("LLM_API_KEY_FILE", "").strip()
        if key_file and os.path.exists(key_file):
            try:
                with open(key_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                
                # Parse "api key: xxx" format (case-insensitive)
                for line in content.splitlines():
                    line = line.strip()
                    if line.lower().startswith("api key:"):
                        return line.split(":", 1)[1].strip()
                    elif line.lower().startswith("api_key:"):
                        return line.split(":", 1)[1].strip()
                
                # If no key: prefix found, treat entire content as key
                # (single-line file with just the key)
                if content and '\n' not in content and ':' not in content:
                    return content
                    
            except Exception as e:
                _trace({
                    "type": "api_key_file_error",
                    "path": key_file,
                    "error": str(e)
                })
        
        # Fallback to direct env var
        return os.getenv("LLM_API_KEY", "")
    
    def __init__(self, 
                 base_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 model: Optional[str] = None,
                 timeout_s: Optional[int] = None,
                 router: Optional[LLMRouter] = None):
        """
        Initialize LLM client. Parameters can be passed directly or via environment.
        
        Priority: explicit parameter > environment variable
        """
        self.base_url = (base_url or os.getenv("LLM_BASE_URL", "")).strip().rstrip("/")
        self.api_key = (api_key or self._load_api_key()).strip()
        self.default_model = (model or os.getenv("LLM_MODEL", "")).strip()
        self.timeout_s = timeout_s or int(os.getenv("LLM_TIMEOUT_S", "60"))
        
        # Initialize or reuse router
        if router is not None:
            self.router = router
        elif LLMClient._router is None:
            LLMClient._router = LLMRouter()
        self.router = LLMClient._router

        # Validate base config (model can come from router)
        if not self.base_url or not self.api_key:
            raise LLMError(
                "config",
                "Missing LLM configuration. Set env vars: LLM_BASE_URL, LLM_API_KEY",
                retryable=False
            )

    def chat(self, 
             system: str, 
             user: str, 
             temperature: Optional[float] = None,
             max_tokens: Optional[int] = None,
             response_format: Optional[Dict[str, Any]] = None,
             metadata: Optional[Dict[str, Any]] = None) -> LLMResult:
        """
        Send a chat completion request with automatic model routing.
        
        Args:
            system: System prompt
            user: User message
            temperature: Sampling temperature (default 0.2 if not in config)
            max_tokens: Optional max tokens limit
            response_format: Optional response format (e.g. {"type": "json_object"})
            metadata: Optional metadata for tracing:
                - step: route key (translate/soft_qa/repair_hard/etc)
                - model_override: bypass routing, use this model
            
        Returns:
            LLMResult with text, latency_ms, request_id, raw response, and usage
        """
        # Extract routing context
        step = "_default"
        model_override = None
        if isinstance(metadata, dict):
            step = metadata.get("step", "_default")
            model_override = metadata.get("model_override")
        
        # 1. Get Config Params
        config_params = self.router.get_generation_params(step) if self.router.enabled else {}
        
        # 2. Resolve Parameters (Arg > Config > Default)
        final_temp = temperature if temperature is not None else config_params.get("temperature", 0.2)
        final_max_tokens = max_tokens if max_tokens is not None else config_params.get("max_tokens")
        final_resp_format = response_format if response_format is not None else config_params.get("response_format")

        # Build model chain (priority: override > routing > default_model)
        if model_override:
            model_chain = [model_override]
        elif self.router.enabled:
            model_chain = self.router.get_model_chain(step)
        else:
            model_chain = []
        
        # Fallback to default_model if chain is empty
        if not model_chain and self.default_model:
            model_chain = [self.default_model]
        
        if not model_chain:
            raise LLMError(
                "config",
                f"No model configured for step '{step}'. Set LLM_MODEL or configure routing.yaml",
                retryable=False
            )
        
        # Router info for tracing
        router_default = self.router.get_default_model(step) if self.router.enabled else None
        router_chain_len = len(model_chain)
        
        # Try each model in chain
        last_error: Optional[LLMError] = None
        for attempt_no, model in enumerate(model_chain):
            fallback_used = attempt_no > 0
            fallback_reason = str(last_error.kind) if last_error else None
            
            try:
                result = self._call_single_model(
                    model=model,
                    system=system,
                    user=user,
                    temperature=final_temp,
                    max_tokens=final_max_tokens,
                    response_format=final_resp_format,
                    metadata=metadata,
                    step=step,
                    attempt_no=attempt_no,
                    router_default=router_default,
                    router_chain_len=router_chain_len,
                    model_override=model_override,
                    fallback_used=fallback_used,
                    fallback_reason=fallback_reason
                )
                return result
                
            except LLMError as e:
                last_error = e
                # Check if we should try next model
                if attempt_no < len(model_chain) - 1 and self.router.should_fallback(e):
                    continue
                raise
        
        # Should not reach here, but just in case
        if last_error:
            raise last_error
        raise LLMError("config", "No models available", retryable=False)
    
    def _call_single_model(self, model: str, system: str, user: str,
                           temperature: float, max_tokens: Optional[int],
                           response_format: Optional[Dict[str, Any]],
                           metadata: Optional[Dict[str, Any]],
                           step: str, attempt_no: int,
                           router_default: Optional[str],
                           router_chain_len: int,
                           model_override: Optional[str],
                           fallback_used: bool,
                           fallback_reason: Optional[str]) -> LLMResult:
        """Execute a single model call with full tracing."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload: Dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        
        if response_format:
            # Only supported by some providers/models
            payload["response_format"] = response_format

        t0 = time.time()
        http_status = None
        
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout_s)
            http_status = resp.status_code
        except requests.Timeout as e:
            self._trace_error("timeout", str(e), step, model, attempt_no, 
                              router_default, router_chain_len, model_override)
            raise LLMError("timeout", f"Request timeout after {self.timeout_s}s: {e}", 
                          retryable=True, http_status=None)
        except requests.RequestException as e:
            self._trace_error("network", str(e), step, model, attempt_no,
                             router_default, router_chain_len, model_override)
            raise LLMError("network", f"Network error: {e}", 
                          retryable=True, http_status=None)

        latency_ms = int((time.time() - t0) * 1000)

        # Handle HTTP errors
        if resp.status_code in (429, 500, 502, 503, 504):
            self._trace_error("upstream", resp.text[:500], step, model, attempt_no,
                             router_default, router_chain_len, model_override, 
                             http_status=resp.status_code)
            raise LLMError(
                "upstream", 
                f"Upstream error HTTP {resp.status_code}: {resp.text[:200]}", 
                retryable=True,
                http_status=resp.status_code
            )

        if resp.status_code >= 400:
            self._trace_error("http", resp.text[:500], step, model, attempt_no,
                             router_default, router_chain_len, model_override,
                             http_status=resp.status_code)
            raise LLMError(
                "http", 
                f"HTTP error {resp.status_code}: {resp.text[:200]}", 
                retryable=False,
                http_status=resp.status_code
            )

        # Parse response
        try:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
        except Exception as e:
            self._trace_error("parse", str(e), step, model, attempt_no,
                             router_default, router_chain_len, model_override)
            raise LLMError("parse", f"Response parse error: {e}", 
                          retryable=True, http_status=resp.status_code)

        # Extract request_id and usage
        request_id = data.get("id") if isinstance(data, dict) else None
        usage = _extract_usage(data) if isinstance(data, dict) else None
        usage_present = bool(usage)

        # Character counts for fallback estimation
        req_chars = len(system) + len(user)
        resp_chars = len(text or "")
        
        # Token estimation (use usage if present, otherwise local estimate)
        if usage and usage.get("prompt_tokens"):
            prompt_tokens = usage["prompt_tokens"]
            completion_tokens = usage.get("completion_tokens", 0)
            total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
            usage_source = "api_usage"
        else:
            # Local estimation fallback
            prompt_tokens = _estimate_tokens(system) + _estimate_tokens(user)
            completion_tokens = _estimate_tokens(text or "")
            total_tokens = prompt_tokens + completion_tokens
            usage_source = "local_estimate"
        
        # Cost estimation
        cost_usd_est = _estimate_cost(model, prompt_tokens, completion_tokens)
        
        # Get max_tokens from metadata if passed
        max_tokens_used = None
        if isinstance(metadata, dict):
            max_tokens_used = metadata.get("max_tokens")

        # Build trace event with enhanced fields
        trace_event = {
            "type": "llm_call",
            "ts": datetime.now().isoformat(),
            # Core fields
            "step": step,
            "request_id": request_id,
            "latency_ms": latency_ms,
            "req_chars": req_chars,
            "resp_chars": resp_chars,
            # Cost monitoring fields
            "base_url": self.base_url,
            "run_id": os.getenv("LLM_RUN_ID", "default"),
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "usage_source": usage_source,
            "usage_present": usage_present,
            "cost_usd_est": cost_usd_est,
            "max_tokens": max_tokens_used,
            # Enhanced router fields
            "selected_model": model,
            "model": model,  # Legacy field for backward compatibility
            "router_default_model": router_default,
            "model_override": model_override,
            "routing_config_version": self.router.config_hash if self.router.enabled else None,
            "fallback_used": fallback_used,
            "fallback_reason": fallback_reason,
            "attempt_no": attempt_no,
            "router_chain_len": router_chain_len,
        }
        
        # Add batch_id from metadata if present
        if isinstance(metadata, dict):
            batch_idx = metadata.get("batch_idx")
            if batch_idx is not None:
                trace_event["batch_id"] = f"{step}:{batch_idx:06d}"
            # Add all extra metadata except routing keys
            routing_keys = {"step", "model_override", "max_tokens", "batch_idx"}
            extra_meta = {k: v for k, v in metadata.items() if k not in routing_keys}
            if extra_meta:
                trace_event["meta"] = extra_meta
        
        _trace(trace_event)
        
        return LLMResult(
            text=text,
            latency_ms=latency_ms,
            raw=data,
            request_id=request_id,
            usage=usage
        )
    
    def _trace_error(self, kind: str, msg: str, step: str, model: str,
                     attempt_no: int, router_default: Optional[str],
                     router_chain_len: int, model_override: Optional[str],
                     http_status: Optional[int] = None) -> None:
        """Log error with router context."""
        _trace({
            "type": "llm_error",
            "kind": kind,
            "msg": msg[:500],
            "step": step,
            "selected_model": model,
            "router_default_model": router_default,
            "model_override": model_override,
            "routing_config_version": self.router.config_hash if self.router.enabled else None,
            "attempt_no": attempt_no,
            "router_chain_len": router_chain_len,
            "http_status": http_status
        })


# Convenience function for simple calls
def chat(system: str, user: str, **kwargs) -> str:
    """Simple chat function that returns just the text."""
    client = LLMClient()
    return client.chat(system=system, user=user, **kwargs).text

