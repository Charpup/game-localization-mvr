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
from pathlib import Path
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
    model: Optional[str] = None  # Model used for the call


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
    billing = pricing.get("billing", {})
    models = pricing.get("models", {})
    model_config = models.get(model, {})
    
    billing_mode = billing.get("mode", "per_1m")
    
    if billing_mode == "multiplier":
        # Multiplier formula from pricing.yaml:
        # cost = conversion_rate * group_mult * model_rate * (prompt_tokens + completion_tokens * completion_ratio) / divisor
        
        # 1. Base conversion rates
        recharge_rate = billing.get("recharge_rate", {})
        group_rate = billing.get("group_rate", {})
        
        conv_rate = (
            (recharge_rate.get("new", 1.0) / max(recharge_rate.get("old", 1.0), 0.001)) *
            (group_rate.get("new", 1.0) / max(group_rate.get("old", 1.0), 0.001))
        )
        
        # 2. User group multiplier
        user_group_mult = billing.get("user_group_multiplier", 1.0)
        
        # 3. Model rates
        prompt_mult = model_config.get("prompt_mult", 0.0)
        completion_mult = model_config.get("completion_mult", 1.0)
        
        # 4. Divisor
        divisor = billing.get("token_divisor", 500000)
        
        effective_tokens = prompt_tokens + (completion_tokens * completion_mult)
        cost = conv_rate * user_group_mult * prompt_mult * effective_tokens / divisor
        return round(cost, 6)
    
    else:
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
    
    def check_batch_capability(self, model: str) -> bool:
        """
        Check if model is capable of batch processing.
        Returns True if batch: ok (or default), False if batch: unfit.
        """
        if not self.config or "capabilities" not in self.config:
            return True  # Default to ok if no config
            
        caps = self.config.get("capabilities", {})
        # Check specific model
        if model in caps:
            return caps[model].get("batch", "ok") != "unfit"
            
        # Check _default
        if "_default" in caps:
            return caps["_default"].get("batch", "ok") != "unfit"
            
        return True
    
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
        
        # Batch Capability Enforcement
        is_batch = False
        if isinstance(metadata, dict):
            # Check explicit flag or implicit batch_size
            is_batch = metadata.get("is_batch") is True or \
                       (isinstance(metadata.get("batch_size"), int) and metadata["batch_size"] > 1) or \
                       (isinstance(metadata.get("planned_batch_size"), int) and metadata["planned_batch_size"] > 1)

        if is_batch and model_chain and self.router.enabled:
            # Check primary model
            primary = model_chain[0]
            if not self.router.check_batch_capability(primary):
                _trace({
                    "type": "router_batch_enforcement",
                    "msg": f"Model {primary} is batch_unfit. Searching fallback chain.",
                    "step": step,
                    "original_chain": model_chain
                })
                
                # Find first capable model in chain
                found_capable = False
                new_chain = []
                for m in model_chain:
                    if self.router.check_batch_capability(m):
                        new_chain.append(m)
                        found_capable = True
                
                if found_capable:
                    model_chain = new_chain
                else:
                    # No capable model in chain - hard fail per requirements?
                    # Or fall back to a safe default if known? 
                    # Requirement: "hard fail or auto-switch to first batch_ok fallback"
                    raise LLMError(
                        "config", 
                        f"Step '{step}' requires batch capability, but no configured models satisfy it. Chain: {model_chain}",
                        retryable=False
                    )
        
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
            # Output record for debugging
            "output": text if len(text) < 10000 else text[:10000] + "...[TRUNCATED]"
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
            usage=usage,
            model=model
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


# ===================================================
# Batch Infrastructure (Phase 3 Week 1)
# ===================================================

class BatchConfig:
    """批次配置管理器,从 batch_runtime_v2.json 加载模型批次配置"""

    def __init__(self, config_path: str = "config/batch_runtime_v2.json"):
        """从 JSON 文件加载批次配置"""
        # Try relative to script directory first
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(script_dir, config_path)
        if not os.path.exists(full_path):
            full_path = config_path  # Try as-is
        
        with open(full_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        self.models = self.config.get("models", {})

    def get_batch_size(self, model: str, content_type: str = "normal") -> int:
        """
        动态获取批次大小

        Args:
            model: 模型名称
            content_type: "normal" | "long_text"

        Returns:
            int: 批次大小
        """
        model_config = self.models.get(model, {})

        if content_type == "long_text":
            return model_config.get("max_batch_size_long_text", 10)
        else:
            return model_config.get("max_batch_size", 10)

    def get_cooldown(self, model: str) -> int:
        """获取模型冷却期 (秒)"""
        return self.models.get(model, {}).get("cooldown_required", 0)

    def get_timeout(self, model: str, content_type: str = "normal") -> int:
        """获取超时配置 (秒)"""
        model_config = self.models.get(model, {})

        if content_type == "long_text":
            return model_config.get("timeout_long_text", 300)
        else:
            return model_config.get("timeout_normal", 180)

    def get_status(self, model: str) -> str:
        """获取模型状态"""
        return self.models.get(model, {}).get("status", "UNKNOWN")


# 全局单例
_batch_config: Optional[BatchConfig] = None


def get_batch_config() -> BatchConfig:
    """获取全局批次配置单例"""
    global _batch_config
    if _batch_config is None:
        _batch_config = BatchConfig()
    return _batch_config


def log_llm_progress(step: str, event_type: str, data: Dict[str, Any], 
                     log_file: Optional[str] = None) -> None:
    """
    统一 LLM 调用进度汇报

    Args:
        step: 步骤名称 (如 "glossary_translate", "qa_soft")
        event_type: 事件类型
            - "step_start": 步骤开始
            - "batch_start": 批次开始
            - "batch_complete": 批次完成
            - "step_complete": 步骤完成
        data: 事件数据 (dict)
        log_file: 日志文件路径 (默认 reports/{step}_progress.jsonl)
    """
    if log_file is None:
        log_file = f"reports/{step}_progress.jsonl"

    # 确保目录存在
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    # 构造事件
    event = {
        "timestamp": datetime.now().isoformat(),
        "step": step,
        "event": event_type,
        "data": data
    }

    # 写入 JSONL
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    # 终端输出 (简化版)
    if event_type == "step_start":
        d = data
        print(f"\n{'='*60}")
        print(f"[{step}] Starting | Total: {d.get('total_rows', '?')} rows | "
              f"Batch size: {d.get('batch_size', '?')} | Model: {d.get('model', '?')}")
        print(f"{'='*60}")

    elif event_type == "batch_complete":
        d = data
        status_symbol = "✅" if d.get("status") == "SUCCESS" else "❌"
        print(f"{status_symbol} [{step}] Batch {d.get('batch_index', '?')}/{d.get('total_batches', '?')} | "
              f"{d.get('batch_size', '?')} rows | {d.get('latency_ms', '?')}ms")

    elif event_type == "step_complete":
        d = data
        print(f"\n[{step}] ✅ Complete")
        print(f"  Total rows: {d.get('total_rows', '?')}")
        print(f"  Success: {d.get('success_count', '?')}")
        print(f"  Failed: {d.get('failed_count', '?')}")
        print(f"{'='*60}\n")


def parse_llm_response(response_text: str, expected_rows: list, partial_match: bool = False) -> list:
    """
    解析 LLM JSON 响应

    Args:
        response_text: LLM 原始响应文本
        expected_rows: 期望的数据行 (用于验证 ID 覆盖率)
        partial_match: 是否允许返回 ID 为输入的子集 (用于 QA 等仅报问题的场景)

    Returns:
        list: 解析后的结果 (items 数组)

    Raises:
        ValueError: 如果解析失败或 ID 不匹配
    """
    # 去除可能的 Markdown 代码块
    text = response_text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 3:
            inner = parts[1].strip()
            if inner.startswith("json"):
                text = inner[4:].strip()
            else:
                text = inner
    
    # 解析 JSON
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON parse error: {str(e)[:100]}")

    # 验证结构
    if "items" not in data:
        raise ValueError("Missing 'items' key in response")

    items = data["items"]

    if not isinstance(items, list):
        raise ValueError("'items' must be an array")

    # 验证 ID 覆盖率
    expected_ids = {str(r["id"]) for r in expected_rows}
    returned_ids = {str(item.get("id", "")) for item in items if item.get("id")}

    if partial_match:
        # 子集校验
        extra = returned_ids - expected_ids
        if extra:
            raise ValueError(f"ID mismatch: extra={extra}")
    else:
        # 完全匹配校验
        if expected_ids != returned_ids:
            missing = expected_ids - returned_ids
            extra = returned_ids - expected_ids
            raise ValueError(f"ID mismatch: missing={missing}, extra={extra}")

    return items


def batch_llm_call(
    step: str,
    rows: list,
    model: str,
    system_prompt: str,
    user_prompt_template,
    content_type: str = "normal",
    retry: int = 0,
    allow_fallback: bool = False,
    partial_match: bool = False
) -> list:
    """
    批次化 LLM 调用 (统一接口)

    Args:
        step: 步骤名称 (用于日志,如 "glossary_translate")
        rows: 数据行列表,每行需包含:
            - id: 唯一标识
            - source_text: 源文本 (或其他必要字段)
        model: 模型名称 (需在 batch_runtime_v2.json 中定义)
        system_prompt: 系统提示 (字符串)
        user_prompt_template: 函数,接收 items 列表,返回 user prompt 字符串
            示例: lambda items: json.dumps({"items": items}, ensure_ascii=False)
        content_type: "normal" | "long_text" (影响批次大小和超时)
        retry: 重试次数
        allow_fallback: 是否允许模型降级
        partial_match: 是否允许返回 ID 为输入的子集 (用于 QA 等仅报问题的场景)

    Returns:
        list: 处理结果 (与 rows 顺序一致, partial_match 模式下可能更少)

    Raises:
        Exception: 如果任何批次失败
    """
    config = get_batch_config()

    # 动态获取批次配置
    batch_size = config.get_batch_size(model, content_type)
    timeout = config.get_timeout(model, content_type)
    cooldown = config.get_cooldown(model)

    total_batches = (len(rows) + batch_size - 1) // batch_size
    results = []

    # 步骤开始
    log_llm_progress(step, "step_start", {
        "total_rows": len(rows),
        "batch_size": batch_size,
        "total_batches": total_batches,
        "model": model,
        "content_type": content_type,
        "timeout": timeout,
        "cooldown": cooldown,
        "partial_match": partial_match
    })

    for i in range(total_batches):
        start_idx = i * batch_size
        end_idx = min(start_idx + batch_size, len(rows))
        batch_rows = rows[start_idx:end_idx]

        # 构造 user prompt
        items = [{"id": r["id"], "source_text": r.get("source_text", "")} for r in batch_rows]
        user_prompt = user_prompt_template(items)

        # 批次开始
        log_llm_progress(step, "batch_start", {
            "batch_index": i + 1,
            "total_batches": total_batches,
            "batch_size": len(batch_rows)
        })

        # 调用 LLM
        t0 = time.time()
        try:
            client = LLMClient()
            response = client.chat(
                system=system_prompt,
                user=user_prompt,
                temperature=0,
                metadata={
                    "step": step,
                    "model_override": model,
                    "force_llm": True,
                    "allow_fallback": allow_fallback,
                    "retry": retry
                }
            )

            latency_ms = int((time.time() - t0) * 1000)

            # 解析响应
            batch_results = parse_llm_response(response.text, batch_rows, partial_match=partial_match)
            results.extend(batch_results)

            # 批次完成
            log_llm_progress(step, "batch_complete", {
                "batch_index": i + 1,
                "total_batches": total_batches,
                "batch_size": len(batch_rows),
                "status": "SUCCESS",
                "latency_ms": latency_ms
            })

        except Exception as e:
            log_llm_progress(step, "batch_complete", {
                "batch_index": i + 1,
                "total_batches": total_batches,
                "batch_size": len(batch_rows),
                "status": "FAIL",
                "error": str(e)[:200]
            })
            raise  # 中断整个步骤

        # 冷却期 (除了最后一个批次)
        if i < total_batches - 1 and cooldown > 0:
            time.sleep(cooldown)

    # 步骤完成
    log_llm_progress(step, "step_complete", {
        "total_rows": len(rows),
        "success_count": len(results),
        "failed_count": len(rows) - len(results)
    })

    return results


# -----------------------------
# Embedding Client (v1.0)
# Text vectorization with caching
# -----------------------------

import numpy as np
import hashlib

# Embedding configuration
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
EMBEDDING_CACHE_DIR = "cache/embeddings"


class EmbeddingClient:
    """
    文本向量化客户端
    
    Features:
    - 单条/批量文本向量化
    - 本地文件缓存 (避免重复调用)
    - 余弦相似度计算
    
    Usage:
        from runtime_adapter import EmbeddingClient
        
        client = EmbeddingClient()
        emb = client.embed_single("测试文本")
        print(f"Embedding shape: {emb.shape}")  # (1536,)
    """
    
    def __init__(self, cache_dir: str = EMBEDDING_CACHE_DIR):
        """
        Initialize embedding client.
        
        Uses same env vars as LLMClient:
        - LLM_BASE_URL (default: https://api.apiyi.com/v1)
        - LLM_API_KEY or LLM_API_KEY_FILE
        """
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.apiyi.com/v1").strip().rstrip("/")
        self.api_key = LLMClient._load_api_key()
        self.model = EMBEDDING_MODEL
        self.cache_dir = cache_dir
        
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        
        if not self.api_key:
            raise LLMError("config", "Missing API key for EmbeddingClient", retryable=False)
    
    def _cache_key(self, text: str) -> str:
        """生成缓存键 (MD5 hash of text + model)"""
        content = f"{text}_{self.model}"
        return hashlib.md5(content.encode('utf-8')).hexdigest()
    
    def _get_cache_path(self, cache_key: str) -> str:
        """获取缓存文件路径"""
        return os.path.join(self.cache_dir, f"{cache_key}.npy")
    
    def embed_single(self, text: str, use_cache: bool = True) -> np.ndarray:
        """
        单条文本向量化
        
        Args:
            text: 输入文本
            use_cache: 是否使用缓存 (默认 True)
            
        Returns:
            np.ndarray: 向量 (shape: EMBEDDING_DIMENSIONS,)
        """
        if not text or not text.strip():
            return np.zeros(EMBEDDING_DIMENSIONS)
        
        # Check cache
        if use_cache and self.cache_dir:
            cache_key = self._cache_key(text)
            cache_path = self._get_cache_path(cache_key)
            if os.path.exists(cache_path):
                return np.load(cache_path)
        
        # API call
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "input": text,
            "model": self.model
        }
        
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            embedding = np.array(data["data"][0]["embedding"])
        except requests.RequestException as e:
            raise LLMError("network", f"Embedding API error: {e}", retryable=True)
        except (KeyError, IndexError) as e:
            raise LLMError("parse", f"Embedding response parse error: {e}", retryable=False)
        
        # Save to cache
        if use_cache and self.cache_dir:
            np.save(cache_path, embedding)
        
        return embedding
    
    def embed_batch(self, texts: list, use_cache: bool = True) -> np.ndarray:
        """
        批量文本向量化
        
        Args:
            texts: 输入文本列表
            use_cache: 是否使用缓存 (默认 True)
            
        Returns:
            np.ndarray: 向量矩阵 (shape: len(texts), EMBEDDING_DIMENSIONS)
        """
        if not texts:
            return np.array([]).reshape(0, EMBEDDING_DIMENSIONS)
        
        embeddings = []
        texts_to_fetch = []
        fetch_indices = []
        
        # Check cache for each text
        for i, text in enumerate(texts):
            if not text or not text.strip():
                embeddings.append((i, np.zeros(EMBEDDING_DIMENSIONS)))
                continue
                
            if use_cache and self.cache_dir:
                cache_key = self._cache_key(text)
                cache_path = self._get_cache_path(cache_key)
                if os.path.exists(cache_path):
                    embeddings.append((i, np.load(cache_path)))
                    continue
            
            texts_to_fetch.append(text)
            fetch_indices.append(i)
        
        # Batch API call for uncached texts
        if texts_to_fetch:
            url = f"{self.base_url}/embeddings"
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "input": texts_to_fetch,
                "model": self.model
            }
            
            try:
                resp = requests.post(url, headers=headers, json=payload, timeout=60)
                resp.raise_for_status()
                data = resp.json()
                
                for j, item in enumerate(data["data"]):
                    idx = fetch_indices[j]
                    emb = np.array(item["embedding"])
                    embeddings.append((idx, emb))
                    
                    # Save to cache
                    if use_cache and self.cache_dir:
                        cache_key = self._cache_key(texts_to_fetch[j])
                        cache_path = self._get_cache_path(cache_key)
                        np.save(cache_path, emb)
                        
            except requests.RequestException as e:
                raise LLMError("network", f"Embedding batch API error: {e}", retryable=True)
            except (KeyError, IndexError) as e:
                raise LLMError("parse", f"Embedding batch response parse error: {e}", retryable=False)
        
        # Sort by original index and return
        embeddings.sort(key=lambda x: x[0])
        return np.array([e[1] for e in embeddings])
    
    def cosine_similarity(self, vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        """
        计算两个向量的余弦相似度
        
        Args:
            vec_a: 向量 A
            vec_b: 向量 B
            
        Returns:
            float: 相似度 [-1, 1]
        """
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
    
    def batch_cosine_similarity(self, query_vec: np.ndarray, corpus_vecs: np.ndarray) -> np.ndarray:
        """
        批量计算余弦相似度 (query vs corpus)
        
        Args:
            query_vec: 查询向量 (shape: D,)
            corpus_vecs: 语料向量矩阵 (shape: N, D)
            
        Returns:
            np.ndarray: 相似度数组 (shape: N,)
        """
        if corpus_vecs.size == 0:
            return np.array([])
        
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return np.zeros(len(corpus_vecs))
        
        query_normalized = query_vec / query_norm
        corpus_norms = np.linalg.norm(corpus_vecs, axis=1, keepdims=True)
        corpus_norms = np.where(corpus_norms == 0, 1, corpus_norms)  # Avoid div by zero
        corpus_normalized = corpus_vecs / corpus_norms
        
        return np.dot(corpus_normalized, query_normalized)
