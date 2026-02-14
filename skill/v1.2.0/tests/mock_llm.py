#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mock_llm.py - Comprehensive LLM Mocking Framework for Offline Tests

This module provides reusable mocking utilities for testing code that depends on
LLM API calls without requiring actual API access. Supports:

- Mock LLMClient.chat() with predefined responses
- Mock batch_llm_call() with simulated batch processing
- Response fixtures for different scenarios
- Simulated failures (rate limit, timeout, etc.)
- Context managers and decorators for easy test integration

Usage:
    from tests.mock_llm import MockLLM, mock_llm_fixture

    # Method 1: Context manager
    with MockLLM() as mock:
        mock.add_response("Hello", "Bonjour")
        result = client.chat(system="", user="Hello")
        assert result.text == "Bonjour"

    # Method 2: Decorator
    @mock_llm_fixture(responses={"Hello": "Bonjour"})
    def test_translation():
        result = client.chat(system="", user="Hello")
        assert result.text == "Bonjour"

Version: 1.0.0
"""

import json
import time
import random
import re
from typing import Dict, List, Any, Optional, Callable, Union, Tuple
from dataclasses import dataclass, field
from contextlib import contextmanager
from functools import wraps
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from runtime_adapter import LLMClient, LLMError, LLMResult, batch_llm_call


# =============================================================================
# Response Fixtures
# =============================================================================

@dataclass
class MockResponse:
    """A predefined mock response for LLM calls."""
    text: str
    latency_ms: int = 100
    model: str = "gpt-4-mock"
    usage: Optional[Dict[str, int]] = None
    request_id: Optional[str] = None
    raw: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.usage is None:
            # Estimate tokens based on text length
            prompt_tokens = 10  # Default estimate
            completion_tokens = max(1, len(self.text) // 4)
            self.usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
        if self.request_id is None:
            self.request_id = f"mock-req-{random.randint(1000, 9999)}"
        if self.raw is None:
            self.raw = {
                "choices": [{"message": {"content": self.text}}],
                "id": self.request_id,
                "usage": self.usage
            }


@dataclass
class MockFailure:
    """Configuration for simulating LLM failures."""
    kind: str  # timeout, network, upstream, http, parse, config
    message: str = "Mock failure"
    retryable: bool = True
    http_status: Optional[int] = None

    def to_error(self) -> LLMError:
        """Convert to LLMError exception."""
        return LLMError(
            kind=self.kind,
            message=self.message,
            retryable=self.retryable,
            http_status=self.http_status
        )


# Predefined failure scenarios
FAILURE_SCENARIOS = {
    "rate_limit": MockFailure(
        kind="upstream",
        message="Rate limit exceeded. Try again later.",
        retryable=True,
        http_status=429
    ),
    "timeout": MockFailure(
        kind="timeout",
        message="Request timeout after 60s",
        retryable=True
    ),
    "network_error": MockFailure(
        kind="network",
        message="Network error: Connection refused",
        retryable=True
    ),
    "server_error": MockFailure(
        kind="upstream",
        message="Internal server error",
        retryable=True,
        http_status=500
    ),
    "bad_request": MockFailure(
        kind="http",
        message="Bad request: Invalid parameters",
        retryable=False,
        http_status=400
    ),
    "unauthorized": MockFailure(
        kind="http",
        message="Unauthorized: Invalid API key",
        retryable=False,
        http_status=401
    ),
    "parse_error": MockFailure(
        kind="parse",
        message="Failed to parse JSON response",
        retryable=True
    ),
    "config_error": MockFailure(
        kind="config",
        message="Missing LLM configuration",
        retryable=False
    )
}


# =============================================================================
# Mock LLM Class
# =============================================================================

class MockLLM:
    """
    Main mocking class for LLM API calls.

    Provides flexible mocking for:
    - LLMClient.chat() - single calls with response matching
    - batch_llm_call() - batch processing simulation
    - Error injection for failure testing

    Example:
        with MockLLM() as mock:
            # Simple response
            mock.add_response("Hello", "Bonjour")

            # Pattern-based response
            mock.add_pattern(r"translate.*Chinese", "翻译结果")

            # Simulate failure
            mock.add_failure("rate_limit", on_keyword="overload")

            # Batch response
            mock.set_batch_response(lambda items: [
                {"id": item["id"], "translation": f"RU_{item['id']}"}
                for item in items
            ])
    """

    def __init__(self, model: str = "gpt-4-mock"):
        self.model = model
        self.responses: List[Tuple[Union[str, re.Pattern], MockResponse]] = []
        self.default_response: Optional[MockResponse] = None
        self.failures: List[Tuple[Optional[str], MockFailure]] = []
        self.batch_handler: Optional[Callable] = None
        self.call_history: List[Dict[str, Any]] = []
        self._patches: List = []

    def __enter__(self):
        """Context manager entry - activate all patches."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop all patches."""
        self.stop()
        return False

    def start(self):
        """Activate mocking patches."""
        # Capture self reference for closures
        mock_self = self
        
        # Create bound methods
        self._bound_chat = lambda this, system, user, **kwargs: mock_self._mock_chat_impl(system, user, **kwargs)
        self._bound_init = lambda this, *args, **kwargs: mock_self._mock_init_impl(*args, **kwargs)
        
        # Patch LLMClient.chat
        patch_chat = patch.object(LLMClient, 'chat', self._bound_chat)
        patch_chat.start()
        self._patches.append(patch_chat)
        
        # Patch batch_llm_call - use a wrapper to preserve self
        def batch_wrapper(*args, **kwargs):
            return mock_self._mock_batch_call(*args, **kwargs)
        patch_batch = patch('runtime_adapter.batch_llm_call', batch_wrapper)
        patch_batch.start()
        self._patches.append(patch_batch)
        
        # Patch LLMClient initialization to not require env vars
        patch_init = patch.object(LLMClient, '__init__', self._bound_init)
        patch_init.start()
        self._patches.append(patch_init)
    
    def stop(self):
        """Deactivate all patches."""
        for p in self._patches:
            p.stop()
        self._patches.clear()
    
    def _mock_init_impl(self, *args, **kwargs):
        """Mock initialization that doesn't require env vars."""
        # Set minimal required attributes
        instance = args[0] if args else None
        if instance is None:
            return
        instance.base_url = "http://mock-llm.local"
        instance.api_key = "mock-api-key"
        instance.default_model = kwargs.get('model', self.model)
        instance.timeout_s = kwargs.get('timeout_s', 60)
        instance.router = MagicMock()
        instance.router.enabled = False
    
    def _mock_chat_impl(self, system: str, user: str, **kwargs) -> LLMResult:
        """Mock implementation of LLMClient.chat()."""
        # Record the call
        call_record = {
            "system": system,
            "user": user,
            "kwargs": kwargs,
            "timestamp": time.time()
        }
        self.call_history.append(call_record)

        # Check for failures first
        for keyword, failure in self.failures:
            if keyword is None or keyword in system or keyword in user:
                raise failure.to_error()

        # Try pattern matching for responses
        combined_input = f"{system} {user}"
        for pattern, response in self.responses:
            if isinstance(pattern, re.Pattern):
                if pattern.search(combined_input):
                    return self._create_result(response)
            else:
                if pattern in system or pattern in user:
                    return self._create_result(response)

        # Return default response or generate one
        if self.default_response:
            return self._create_result(self.default_response)

        # Auto-generate response based on input
        return self._auto_generate_response(system, user, kwargs)

    def _mock_batch_call(self, step: str, rows: list, **kwargs) -> list:
        """Mock implementation of batch_llm_call()."""
        # Record the call
        call_record = {
            "step": step,
            "rows": rows,
            "kwargs": kwargs,
            "timestamp": time.time()
        }
        self.call_history.append(call_record)

        # Use custom batch handler if set
        if self.batch_handler:
            return self.batch_handler(step, rows, **kwargs)

        # Default batch processing simulation
        return self._default_batch_process(step, rows, **kwargs)

    def _create_result(self, response: MockResponse) -> LLMResult:
        """Create LLMResult from MockResponse."""
        return LLMResult(
            text=response.text,
            latency_ms=response.latency_ms,
            raw=response.raw,
            request_id=response.request_id,
            usage=response.usage,
            model=response.model
        )

    def _auto_generate_response(self, system: str, user: str, kwargs: dict) -> LLMResult:
        """Auto-generate a response based on input patterns."""
        # Detect translation requests
        if "translate" in system.lower() or "translate" in user.lower():
            text = self._extract_translation_text(user)
            return self._create_result(MockResponse(
                text=f"RU_{text[:50]}",  # Simulated Russian translation
                model=self.model
            ))

        # Detect QA requests
        if "qa" in system.lower() or "quality" in system.lower():
            return self._create_result(MockResponse(
                text='{"items": []}',  # No issues found
                model=self.model
            ))

        # Default generic response
        return self._create_result(MockResponse(
            text="Mock response for: " + user[:100],
            model=self.model
        ))

    def _extract_translation_text(self, user: str) -> str:
        """Extract text to translate from user prompt."""
        # Try to find JSON with source_text
        try:
            if '"source_text"' in user:
                match = re.search(r'"source_text"\s*:\s*"([^"]+)"', user)
                if match:
                    return match.group(1)
        except Exception:
            pass
        return user[:50]

    def _default_batch_process(self, step: str, rows: list, **kwargs) -> list:
        """Default batch processing simulation."""
        results = []
        system_prompt = kwargs.get('system_prompt', '')
        user_prompt_template = kwargs.get('user_prompt_template')

        # Simulate processing each row
        for row in rows:
            row_id = row.get('id', 'unknown')
            source_text = row.get('source_text', '')

            if step == 'translate':
                # Simulate translation
                results.append({
                    "id": row_id,
                    "translation": f"RU_{source_text[:30]}",
                    "status": "success"
                })
            elif step == 'soft_qa':
                # Simulate QA - return empty issues (pass)
                results.append({
                    "id": row_id,
                    "issues": [],
                    "status": "passed"
                })
            else:
                # Generic response
                results.append({
                    "id": row_id,
                    "result": f"processed_{row_id}",
                    "status": "success"
                })

        return results

    # ==========================================================================
    # Public API for configuring mocks
    # ==========================================================================

    def add_response(self, keyword: str, response_text: str, **kwargs):
        """
        Add a response triggered by a keyword in the input.

        Args:
            keyword: String to match in system or user prompt
            response_text: The response text to return
            **kwargs: Additional MockResponse parameters (latency_ms, model, etc.)
        """
        self.responses.append((
            keyword,
            MockResponse(text=response_text, model=kwargs.get('model', self.model), **kwargs)
        ))

    def add_pattern(self, pattern: str, response_text: str, **kwargs):
        """
        Add a response triggered by a regex pattern.

        Args:
            pattern: Regex pattern to match
            response_text: The response text to return
            **kwargs: Additional MockResponse parameters
        """
        self.responses.append((
            re.compile(pattern, re.IGNORECASE),
            MockResponse(text=response_text, model=kwargs.get('model', self.model), **kwargs)
        ))

    def set_default_response(self, response_text: str, **kwargs):
        """Set the default response when no pattern matches."""
        self.default_response = MockResponse(
            text=response_text,
            model=kwargs.get('model', self.model),
            **kwargs
        )

    def add_failure(self, scenario: str, on_keyword: Optional[str] = None):
        """
        Add a failure scenario.

        Args:
            scenario: One of FAILURE_SCENARIOS keys or custom MockFailure
            on_keyword: Only fail if this keyword appears in input (None = always)
        """
        if isinstance(scenario, str):
            failure = FAILURE_SCENARIOS.get(scenario, MockFailure(
                kind="upstream", message=f"Unknown scenario: {scenario}"
            ))
        else:
            failure = scenario
        self.failures.append((on_keyword, failure))

    def set_batch_handler(self, handler: Callable):
        """
        Set a custom handler for batch_llm_call.

        Args:
            handler: Function(step, rows, **kwargs) -> list
        """
        self.batch_handler = handler

    def set_batch_response(self, response_fn: Callable[[List[dict]], List[dict]]):
        """
        Set a function to generate batch responses from input items.

        Args:
            response_fn: Function that takes items list and returns results list
        """
        def handler(step, rows, **kwargs):
            items = [{"id": r["id"], "source_text": r.get("source_text", "")}
                     for r in rows]
            return response_fn(items)
        self.batch_handler = handler

    def clear(self):
        """Clear all configured responses and failures."""
        self.responses.clear()
        self.failures.clear()
        self.default_response = None
        self.batch_handler = None
        self.call_history.clear()

    def get_call_count(self) -> int:
        """Get the number of calls made to the mock."""
        return len(self.call_history)

    def assert_called(self):
        """Assert that at least one call was made."""
        assert len(self.call_history) > 0, "Expected at least one LLM call"

    def assert_not_called(self):
        """Assert that no calls were made."""
        assert len(self.call_history) == 0, f"Expected no LLM calls, got {len(self.call_history)}"

    def assert_call_count(self, expected: int):
        """Assert exact call count."""
        actual = len(self.call_history)
        assert actual == expected, f"Expected {expected} calls, got {actual}"


# =============================================================================
# Decorator and Context Manager Helpers
# =============================================================================

def mock_llm_fixture(responses: Optional[Dict[str, str]] = None,
                     failures: Optional[List[Tuple[str, str]]] = None,
                     batch_response: Optional[Callable] = None,
                     model: str = "gpt-4-mock"):
    """
    Decorator for mocking LLM calls in tests.

    Args:
        responses: Dict mapping keywords to response texts
        failures: List of (scenario_name, on_keyword) tuples
        batch_response: Function to handle batch calls
        model: Default model name for responses
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with MockLLM(model=model) as mock:
                # Configure responses
                if responses:
                    for keyword, text in responses.items():
                        mock.add_response(keyword, text)

                # Configure failures
                if failures:
                    for scenario, keyword in failures:
                        mock.add_failure(scenario, keyword if keyword else None)

                # Configure batch handler
                if batch_response:
                    mock.set_batch_handler(batch_response)

                return func(*args, **kwargs)
        return wrapper
    return decorator


@contextmanager
def mock_llm_context(responses: Optional[Dict[str, str]] = None,
                     default_response: Optional[str] = None,
                     model: str = "gpt-4-mock"):
    """
    Context manager for simple LLM mocking.

    Example:
        with mock_llm_context({"Hello": "Bonjour"}) as mock:
            result = client.chat(system="", user="Hello")
    """
    mock = MockLLM(model=model)
    mock.start()
    try:
        if responses:
            for keyword, text in responses.items():
                mock.add_response(keyword, text)
        if default_response:
            mock.set_default_response(default_response)
        yield mock
    finally:
        mock.stop()


# =============================================================================
# Specialized Fixtures for Translation Testing
# =============================================================================

class TranslationMock(MockLLM):
    """Specialized mock for translation testing with token preservation."""

    def __init__(self, model: str = "gpt-4-mock"):
        super().__init__(model)
        self.token_pattern = re.compile(r"⟦(PH_\d+|TAG_\d+)⟧")

    def _extract_tokens(self, text: str) -> List[str]:
        """Extract placeholder tokens from text."""
        return self.token_pattern.findall(text)

    def add_translation_response(self, source_pattern: str, translation: str):
        """
        Add a translation response that preserves tokens.

        Args:
            source_pattern: Pattern to match in source text
            translation: Translation result (should include tokens)
        """
        def handler(system, user, **kwargs):
            # Extract tokens from user prompt
            tokens = self._extract_tokens(user)
            # Ensure tokens are in response
            result = translation
            for token in tokens:
                if f"⟦{token}⟧" not in result:
                    result += f" ⟦{token}⟧"
            return MockResponse(text=result, model=self.model)

        self.add_response(source_pattern, translation)

    def set_batch_translation_handler(self, translate_fn: Callable[[str], str]):
        """
        Set a function to handle batch translations.

        Args:
            translate_fn: Function(source_text) -> translation
        """
        def handler(step, rows, **kwargs):
            results = []
            for row in rows:
                source = row.get('source_text', '')
                tokens = self._extract_tokens(source)

                translation = translate_fn(source)

                # Ensure tokens are preserved
                for token in tokens:
                    if f"⟦{token}⟧" not in translation:
                        translation += f" ⟦{token}⟧"

                results.append({
                    "id": row["id"],
                    "translation": translation,
                    "status": "success"
                })
            return results

        self.set_batch_handler(handler)


class QAMock(MockLLM):
    """Specialized mock for QA testing."""

    def __init__(self, model: str = "gpt-4-mock", issue_rate: float = 0.0):
        super().__init__(model)
        self.issue_rate = issue_rate
        self.issues: Dict[str, List[dict]] = {}  # row_id -> issues

    def add_issue(self, row_id: str, issue_type: str, message: str, severity: str = "major"):
        """Add a predefined issue for a specific row."""
        if row_id not in self.issues:
            self.issues[row_id] = []
        self.issues[row_id].append({
            "type": issue_type,
            "message": message,
            "severity": severity
        })

    def set_batch_qa_handler(self):
        """Set up batch QA handler that returns predefined issues."""
        def handler(step, rows, **kwargs):
            results = []
            for row in rows:
                row_id = str(row.get('id', 'unknown'))

                # Return predefined issues if any
                if row_id in self.issues:
                    results.append({
                        "id": row_id,
                        "issues": self.issues[row_id],
                        "status": "issues_found"
                    })
                elif random.random() < self.issue_rate:
                    # Random issue generation
                    results.append({
                        "id": row_id,
                        "issues": [{"type": "random", "message": "Random issue"}],
                        "status": "issues_found"
                    })
                else:
                    # No issues
                    results.append({
                        "id": row_id,
                        "issues": [],
                        "status": "passed"
                    })
            return results

        self.set_batch_handler(handler)


# =============================================================================
# Utility Functions
# =============================================================================

def create_mock_result(text: str,
                       model: str = "gpt-4-mock",
                       latency_ms: int = 100,
                       usage: Optional[Dict[str, int]] = None) -> LLMResult:
    """Create a mock LLMResult for direct use in tests."""
    mock_resp = MockResponse(text=text, model=model, latency_ms=latency_ms, usage=usage)
    return LLMResult(
        text=mock_resp.text,
        latency_ms=mock_resp.latency_ms,
        raw=mock_resp.raw,
        request_id=mock_resp.request_id,
        usage=mock_resp.usage,
        model=mock_resp.model
    )


def create_mock_batch_result(rows: List[dict],
                             result_key: str = "translation") -> List[dict]:
    """Create a mock batch result for given rows."""
    return [
        {
            "id": row["id"],
            result_key: f"result_{row['id']}",
            "status": "success"
        }
        for row in rows
    ]


# =============================================================================
# Pre-configured Mock Sets for Common Scenarios
# =============================================================================

def create_success_mock(response_text: str = "Success") -> MockLLM:
    """Create a mock that always returns success."""
    mock = MockLLM()
    mock.set_default_response(response_text)
    return mock


def create_failure_mock(scenario: str = "server_error") -> MockLLM:
    """Create a mock that always fails."""
    mock = MockLLM()
    mock.add_failure(scenario)
    return mock


def create_retry_mock(success_after: int = 2,
                      failure_scenario: str = "rate_limit") -> MockLLM:
    """
    Create a mock that fails N times before succeeding.

    Args:
        success_after: Number of failures before success
        failure_scenario: Type of failure to simulate
    """
    mock = MockLLM()
    mock._failure_count = 0
    mock._success_after = success_after

    def retry_handler(system, user, **kwargs):
        mock._failure_count += 1
        if mock._failure_count <= success_after:
            raise FAILURE_SCENARIOS[failure_scenario].to_error()
        return MockResponse(text="Success after retry", model=mock.model)

    # Replace the chat method
    mock._mock_chat = lambda self, system, user, **kwargs: retry_handler(system, user, **kwargs)

    return mock


def create_translation_mock(translations: Dict[str, str]) -> TranslationMock:
    """
    Create a translation mock with predefined translations.

    Args:
        translations: Dict mapping source text patterns to translations
    """
    mock = TranslationMock()
    for pattern, translation in translations.items():
        mock.add_translation_response(pattern, translation)
    return mock


def create_batch_translation_mock() -> TranslationMock:
    """Create a mock for batch translation testing with token preservation."""
    mock = TranslationMock()

    def translate_fn(source: str) -> str:
        # Simple mock translation: prefix with RU_
        # In real tests, this could use a dictionary or more complex logic
        return f"RU_{source[:50]}"

    mock.set_batch_translation_handler(translate_fn)
    return mock


# =============================================================================
# Export public API
# =============================================================================

__all__ = [
    # Core classes
    'MockLLM',
    'MockResponse',
    'MockFailure',
    'TranslationMock',
    'QAMock',

    # Decorators and context managers
    'mock_llm_fixture',
    'mock_llm_context',

    # Predefined scenarios
    'FAILURE_SCENARIOS',

    # Utility functions
    'create_mock_result',
    'create_mock_batch_result',
    'create_success_mock',
    'create_failure_mock',
    'create_retry_mock',
    'create_translation_mock',
    'create_batch_translation_mock',
]