#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm_mock_framework.py

Comprehensive LLM Mocking Framework for Testing Without Real API Calls

This module provides a complete mocking infrastructure for testing translation
and LLM-dependent components without making actual API calls.

Features:
- LLMMockClient: Drop-in replacement for LLMClient
- Response pattern matching for predefined responses
- Response sequencing for multi-call test scenarios
- Latency simulation for realistic timing testing
- Error injection for resilience testing
- Rich fixtures for Russian/English translations

Usage:
    from llm_mock_framework import LLMMockClient, MockResponses
    
    # Simple mock
    mock = LLMMockClient()
    mock.add_response_pattern("战士", target_ru="Воин")
    
    # With pytest fixture
    @pytest.fixture
    def mock_llm():
        return LLMMockClient()
"""

import json
import time
import re
import random
from typing import Dict, List, Any, Optional, Callable, Tuple, Union, Pattern
from dataclasses import dataclass, field
from enum import Enum
from unittest.mock import Mock

# Import the real interfaces for type compatibility
try:
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
    from runtime_adapter import LLMResult, LLMError
except ImportError:
    # Fallback definitions for standalone usage
    @dataclass
    class LLMResult:
        text: str
        latency_ms: int
        raw: Optional[dict] = None
        request_id: Optional[str] = None
        usage: Optional[dict] = None
        model: Optional[str] = None

    class LLMError(Exception):
        def __init__(self, kind: str, message: str, 
                     retryable: bool = True,
                     http_status: Optional[int] = None):
            super().__init__(message)
            self.kind = kind
            self.retryable = retryable
            self.http_status = http_status


class ErrorKind(Enum):
    """Types of errors that can be simulated."""
    CONFIG = "config"
    TIMEOUT = "timeout"
    NETWORK = "network"
    UPSTREAM = "upstream"
    HTTP = "http"
    PARSE = "parse"
    RATE_LIMIT = "rate_limit"
    INVALID_JSON = "invalid_json"


@dataclass
class MockResponse:
    """A single mock response configuration."""
    text: Optional[str] = None
    items: Optional[List[Dict]] = None  # For batch responses
    latency_ms: int = 100
    error: Optional[ErrorKind] = None
    error_message: str = ""
    http_status: Optional[int] = None
    usage: Optional[Dict] = None
    model: str = "mock-model"
    
    def to_llm_result(self, request_id: str = "mock-req-001") -> LLMResult:
        """Convert to LLMResult."""
        response_text = self.text or json.dumps({"items": self.items or []}, ensure_ascii=False)
        return LLMResult(
            text=response_text,
            latency_ms=self.latency_ms,
            raw={"choices": [{"message": {"content": response_text}}]},
            request_id=request_id,
            usage=self.usage or {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            model=self.model
        )
    
    def to_error(self) -> LLMError:
        """Convert to LLMError."""
        kind = self.error.value if isinstance(self.error, ErrorKind) else str(self.error)
        retryable = kind not in ("config", "http")
        return LLMError(
            kind=kind,
            message=self.error_message or f"Mock {kind} error",
            retryable=retryable,
            http_status=self.http_status
        )


@dataclass
class ResponsePattern:
    """Pattern matching rule for responses."""
    # Match criteria
    contains: Optional[str] = None
    regex: Optional[Pattern] = None
    predicate: Optional[Callable[[str, str], bool]] = None  # (system, user) -> bool
    
    # Response to return
    response: MockResponse = field(default_factory=lambda: MockResponse())
    priority: int = 0  # Higher priority patterns match first
    
    def matches(self, system: str, user: str) -> bool:
        """Check if this pattern matches the request."""
        combined = f"{system}\n{user}"
        
        if self.contains and self.contains in combined:
            return True
        if self.regex and self.regex.search(combined):
            return True
        if self.predicate and self.predicate(system, user):
            return True
        return False


class ResponseSequence:
    """A sequence of responses for multi-call scenarios."""
    
    def __init__(self, responses: List[MockResponse], cycle: bool = False):
        self.responses = responses
        self.cycle = cycle
        self.index = 0
    
    def next(self) -> MockResponse:
        """Get the next response in sequence."""
        if not self.responses:
            return MockResponse(text='{"items": []}')
        
        # If exhausted and not cycling, return default empty response
        if self.index >= len(self.responses):
            if self.cycle:
                self.index = 0
            else:
                return MockResponse(text='{"items": []}')
        
        response = self.responses[self.index]
        self.index += 1
        
        return response


class LLMMockClient:
    """
    Mock LLM Client that mimics the real LLMClient interface.
    
    Supports:
    - Pattern-based response matching
    - Response sequencing
    - Latency simulation
    - Error injection
    - Call recording for assertions
    
    Usage:
        mock = LLMMockClient()
        
        # Add simple pattern match
        mock.add_response_pattern("战士", response_text='{"items": [{"id": "1", "target_ru": "Воин"}]}')
        
        # Add response sequence
        mock.add_sequence([
            MockResponse(text='{"items": [{"id": "1", "target_ru": "Воин"}]}'),
            MockResponse(text='{"items": [{"id": "2", "target_ru": "Маг"}]}'),
        ])
        
        # Force error
        mock.add_error_response(ErrorKind.TIMEOUT, "Connection timeout")
        
        # Use like real client
        result = mock.chat(system="...", user="...")
    """
    
    def __init__(self, simulate_latency: bool = False, latency_jitter: float = 0.1):
        """
        Initialize mock client.
        
        Args:
            simulate_latency: If True, add artificial delays
            latency_jitter: Random variation in latency (0.1 = 10%)
        """
        self.patterns: List[ResponsePattern] = []
        self.sequence: Optional[ResponseSequence] = None
        self.default_response = MockResponse(text='{"items": []}')
        self.simulate_latency = simulate_latency
        self.latency_jitter = latency_jitter
        
        # Call recording for assertions
        self.calls: List[Dict[str, Any]] = []
        self.request_counter = 0
        
        # Enable pattern matching mode by default
        self.mode = "pattern"  # "pattern", "sequence", "error"
    
    def add_response_pattern(
        self, 
        contains: Optional[str] = None,
        regex: Optional[Union[str, Pattern]] = None,
        predicate: Optional[Callable[[str, str], bool]] = None,
        response_text: Optional[str] = None,
        items: Optional[List[Dict]] = None,
        latency_ms: int = 100,
        priority: int = 0,
        model: str = "mock-model"
    ) -> "LLMMockClient":
        """
        Add a pattern-based response rule.
        
        Args:
            contains: Match if this string is found in request
            regex: Match if this regex pattern matches
            predicate: Custom match function (system, user) -> bool
            response_text: Raw response text
            items: Batch response items (auto-wrapped in JSON)
            latency_ms: Simulated response time
            priority: Higher priority patterns match first
            model: Model name to return
        
        Returns:
            Self for chaining
        """
        if regex and isinstance(regex, str):
            regex = re.compile(regex)
        
        response = MockResponse(
            text=response_text,
            items=items,
            latency_ms=latency_ms,
            model=model
        )
        
        pattern = ResponsePattern(
            contains=contains,
            regex=regex,
            predicate=predicate,
            response=response,
            priority=priority
        )
        
        self.patterns.append(pattern)
        # Sort by priority (higher first)
        self.patterns.sort(key=lambda p: -p.priority)
        self.mode = "pattern"
        
        return self
    
    def add_simple_translation(self, chinese: str, russian: str, id_val: str = "1") -> "LLMMockClient":
        """
        Quick helper to add a Chinese -> Russian translation pattern.
        
        Args:
            chinese: Chinese text to match
            russian: Russian translation to return
            id_val: ID for the response item
        
        Returns:
            Self for chaining
        """
        return self.add_response_pattern(
            contains=chinese,
            items=[{"id": id_val, "target_ru": russian}],
            latency_ms=50
        )
    
    def add_sequence(self, responses: List[MockResponse], cycle: bool = False) -> "LLMMockClient":
        """
        Set up a sequence of responses for sequential calls.
        
        Args:
            responses: List of MockResponse objects
            cycle: If True, restart from beginning when sequence ends
        
        Returns:
            Self for chaining
        """
        self.sequence = ResponseSequence(responses, cycle=cycle)
        self.mode = "sequence"
        return self
    
    def add_error_response(
        self, 
        error_kind: ErrorKind,
        message: str,
        http_status: Optional[int] = None,
        after_calls: int = 0
    ) -> "LLMMockClient":
        """
        Add an error response.
        
        Args:
            error_kind: Type of error to simulate
            message: Error message
            http_status: Optional HTTP status code
            after_calls: Inject error after N successful calls
        
        Returns:
            Self for chaining
        """
        if after_calls > 0:
            # Create a sequence with N successes then error
            successes = [self.default_response] * after_calls
            error_response = MockResponse(
                error=error_kind,
                error_message=message,
                http_status=http_status,
                latency_ms=0
            )
            self.add_sequence(successes + [error_response])
        else:
            self.add_response_pattern(
                predicate=lambda s, u: True,  # Match everything
                response_text=None,
                priority=999
            )
            self.mode = "error"
            self._forced_error = MockResponse(
                error=error_kind,
                error_message=message,
                http_status=http_status
            )
        
        return self
    
    def set_default_response(self, response: MockResponse) -> "LLMMockClient":
        """Set the fallback response when no patterns match."""
        self.default_response = response
        return self
    
    def chat(
        self,
        system: str,
        user: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        response_format: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[int] = None
    ) -> LLMResult:
        """
        Mock chat completion - mimics LLMClient.chat().
        
        Returns predefined response based on patterns or sequence.
        """
        self.request_counter += 1
        request_id = f"mock-req-{self.request_counter:04d}"
        
        # Record the call
        call_record = {
            "request_id": request_id,
            "system": system[:500] if system else "",  # Truncate for memory
            "user": user[:2000] if user else "",  # Truncate for memory
            "temperature": temperature,
            "max_tokens": max_tokens,
            "metadata": metadata,
            "timestamp": time.time()
        }
        self.calls.append(call_record)
        
        # Get response based on mode
        mock_response = self._get_response(system, user)
        
        # Simulate latency if enabled
        if self.simulate_latency:
            jitter = random.uniform(-self.latency_jitter, self.latency_jitter)
            sleep_time = (mock_response.latency_ms / 1000.0) * (1 + jitter)
            time.sleep(max(0, sleep_time))
        
        # Return result or raise error
        if mock_response.error:
            raise mock_response.to_error()
        
        return mock_response.to_llm_result(request_id)
    
    def _get_response(self, system: str, user: str) -> MockResponse:
        """Get appropriate response for the request."""
        # Sequence mode
        if self.mode == "sequence" and self.sequence:
            return self.sequence.next()
        
        # Error mode
        if self.mode == "error" and hasattr(self, '_forced_error'):
            return self._forced_error
        
        # Pattern matching mode
        for pattern in self.patterns:
            if pattern.matches(system, user):
                return pattern.response
        
        # Default fallback
        return self.default_response
    
    def batch_chat(
        self,
        rows: List[Dict[str, Any]],
        system_prompt: Union[str, Callable],
        user_prompt_template: Callable,
        **kwargs
    ) -> List[Dict[str, Any]]:
        """
        Mock batch chat - mimics batch_llm_call behavior.
        
        Returns parsed items from the mock response.
        """
        # Build prompts like real batch_llm_call does
        items = [{"id": r["id"], "source_text": r.get("source_text", "")} for r in rows]
        user_prompt = user_prompt_template(items)
        
        # Handle dynamic system prompt
        if callable(system_prompt):
            final_system = system_prompt(rows)
        else:
            final_system = system_prompt
        
        # Get mock response
        result = self.chat(system=final_system, user=user_prompt)
        
        # Parse the response like real implementation
        try:
            data = json.loads(result.text)
            return data.get("items", [])
        except json.JSONDecodeError:
            return [{"id": r["id"], "target_ru": "MOCK_ERROR"} for r in rows]
    
    def get_call_history(self) -> List[Dict[str, Any]]:
        """Get recorded call history for assertions."""
        return self.calls
    
    def assert_call_count(self, expected: int) -> bool:
        """Assert that N calls were made."""
        actual = len(self.calls)
        if actual != expected:
            raise AssertionError(f"Expected {expected} calls, got {actual}")
        return True
    
    def assert_call_contains(self, substring: str, call_index: int = -1) -> bool:
        """Assert that a call contains a substring."""
        if not self.calls:
            raise AssertionError("No calls recorded")
        
        call = self.calls[call_index]
        combined = f"{call.get('system', '')}\n{call.get('user', '')}"
        
        if substring not in combined:
            raise AssertionError(f"Call does not contain '{substring}'")
        return True
    
    def reset(self) -> "LLMMockClient":
        """Reset all patterns and call history."""
        self.patterns = []
        self.sequence = None
        self.calls = []
        self.request_counter = 0
        self.mode = "pattern"
        if hasattr(self, '_forced_error'):
            delattr(self, '_forced_error')
        return self


# =============================================================================
# Response Fixtures
# =============================================================================

class MockResponses:
    """
    Pre-built response fixtures for common testing scenarios.
    
    Provides ready-to-use MockResponse objects for:
    - Russian translations (with proper placeholders)
    - English translations
    - Error conditions
    - Various text lengths and complexities
    """
    
    # -----------------------------------------------------------------------------
    # Russian Translations
    # -----------------------------------------------------------------------------
    
    @staticmethod
    def russian_warrior(id_val: str = "1", with_ph: bool = True) -> MockResponse:
        """Russian translation for '战士' (warrior)."""
        if with_ph:
            return MockResponse(items=[{"id": id_val, "target_ru": "⟦PH_1⟧Воин⟦PH_2⟧"}])
        return MockResponse(items=[{"id": id_val, "target_ru": "Воин"}])
    
    @staticmethod
    def russian_mage(id_val: str = "1", with_ph: bool = True) -> MockResponse:
        """Russian translation for '法师' (mage)."""
        if with_ph:
            return MockResponse(items=[{"id": id_val, "target_ru": "⟦PH_1⟧Маг⟦PH_2⟧"}])
        return MockResponse(items=[{"id": id_val, "target_ru": "Маг"}])
    
    @staticmethod
    def russian_attack(id_val: str = "1") -> MockResponse:
        """Russian translation for '攻击' (attack)."""
        return MockResponse(items=[{"id": id_val, "target_ru": "Атака"}])
    
    @staticmethod
    def russian_spell(id_val: str = "1") -> MockResponse:
        """Russian translation for '法术' (spell)."""
        return MockResponse(items=[{"id": id_val, "target_ru": "Заклинание"}])
    
    @staticmethod
    def russian_game_text(id_val: str = "1") -> MockResponse:
        """Typical game UI text in Russian."""
        return MockResponse(items=[{
            "id": id_val, 
            "target_ru": "Нажмите, чтобы начать битву"
        }])
    
    @staticmethod
    def russian_long_text(id_val: str = "1") -> MockResponse:
        """Long Russian text for testing long_text content type."""
        return MockResponse(items=[{
            "id": id_val,
            "target_ru": "В далеком королевстве, где горы касались небес, жил-был отважный воин. "
                        "Он защищал свою землю от темных сил, которые угрожали миру. "
                        "Каждый день он тренировался, совершенствуя свои навыки меча и магии."
        }])
    
    @staticmethod
    def russian_with_placeholders(id_val: str = "1", ph_count: int = 3) -> MockResponse:
        """Russian text with multiple placeholders."""
        placeholders = "".join([f"⟦PH_{i}⟧" for i in range(1, ph_count + 1)])
        return MockResponse(items=[{
            "id": id_val,
            "target_ru": f"{placeholders}Воин использует меч{placeholders}"
        }])
    
    @staticmethod
    def russian_with_tags(id_val: str = "1", tag_count: int = 2) -> MockResponse:
        """Russian text with TAG placeholders."""
        tags = "".join([f"⟦TAG_{i}⟧" for i in range(1, tag_count + 1)])
        return MockResponse(items=[{
            "id": id_val,
            "target_ru": f"{tags}Маг читает заклинание{tags}"
        }])
    
    # -----------------------------------------------------------------------------
    # English Translations
    # -----------------------------------------------------------------------------
    
    @staticmethod
    def english_warrior(id_val: str = "1") -> MockResponse:
        """English translation for '战士'."""
        return MockResponse(items=[{"id": id_val, "target_ru": "Warrior"}])
    
    @staticmethod
    def english_mage(id_val: str = "1") -> MockResponse:
        """English translation for '法师'."""
        return MockResponse(items=[{"id": id_val, "target_ru": "Mage"}])
    
    @staticmethod
    def english_game_text(id_val: str = "1") -> MockResponse:
        """Typical game UI text in English."""
        return MockResponse(items=[{
            "id": id_val,
            "target_ru": "Click to start the battle"
        }])
    
    # -----------------------------------------------------------------------------
    # Error Responses
    # -----------------------------------------------------------------------------
    
    @staticmethod
    def error_rate_limit(message: str = "Rate limit exceeded") -> MockResponse:
        """Rate limit error (429)."""
        return MockResponse(
            error=ErrorKind.RATE_LIMIT,
            error_message=message,
            http_status=429,
            latency_ms=0
        )
    
    @staticmethod
    def error_timeout(message: str = "Request timeout after 60s") -> MockResponse:
        """Timeout error."""
        return MockResponse(
            error=ErrorKind.TIMEOUT,
            error_message=message,
            latency_ms=60000
        )
    
    @staticmethod
    def error_network(message: str = "Connection refused") -> MockResponse:
        """Network error."""
        return MockResponse(
            error=ErrorKind.NETWORK,
            error_message=message,
            latency_ms=0
        )
    
    @staticmethod
    def error_invalid_json(bad_json: str = "{invalid") -> MockResponse:
        """Invalid JSON response."""
        return MockResponse(
            text=bad_json,
            latency_ms=100
        )
    
    @staticmethod
    def error_upstream(message: str = "Internal server error", status: int = 500) -> MockResponse:
        """Upstream server error."""
        return MockResponse(
            error=ErrorKind.UPSTREAM,
            error_message=message,
            http_status=status,
            latency_ms=100
        )
    
    @staticmethod
    def error_config(message: str = "Missing API key") -> MockResponse:
        """Configuration error (not retryable)."""
        return MockResponse(
            error=ErrorKind.CONFIG,
            error_message=message,
            http_status=None
        )
    
    # -----------------------------------------------------------------------------
    # Special Responses
    # -----------------------------------------------------------------------------
    
    @staticmethod
    def empty_items() -> MockResponse:
        """Empty items array."""
        return MockResponse(items=[])
    
    @staticmethod
    def missing_items_key() -> MockResponse:
        """Response missing 'items' key."""
        return MockResponse(text='{"results": []}')
    
    @staticmethod
    def partial_match(available_ids: List[str]) -> MockResponse:
        """Partial ID match (for QA scenarios)."""
        return MockResponse(items=[
            {"id": id_val, "target_ru": f"Translation_{id_val}"}
            for id_val in available_ids
        ])
    
    @staticmethod
    def slow_response(latency_ms: int = 5000) -> MockResponse:
        """Slow response for timeout testing."""
        return MockResponse(
            items=[{"id": "1", "target_ru": "Slow translation"}],
            latency_ms=latency_ms
        )
    
    @staticmethod
    def high_latency_batch(size: int = 10, base_latency: int = 200) -> MockResponse:
        """Batch response with realistic latency."""
        return MockResponse(
            items=[{"id": str(i), "target_ru": f"Translation_{i}"} for i in range(1, size + 1)],
            latency_ms=base_latency * size
        )


# =============================================================================
# Convenience Fixtures
# =============================================================================

class MockFixtures:
    """
    Complete fixture sets for common test scenarios.
    
    Usage:
        fixtures = MockFixtures.glossary_batch()
        mock = LLMMockClient()
        mock.add_sequence(fixtures)
    """
    
    @staticmethod
    def glossary_batch() -> List[MockResponse]:
        """Batch of translations for glossary terms."""
        return [
            MockResponses.russian_warrior("1"),
            MockResponses.russian_mage("2"),
            MockResponses.russian_attack("3"),
            MockResponses.russian_spell("4"),
        ]
    
    @staticmethod
    def mixed_batch_with_errors() -> List[MockResponse]:
        """Mixed batch with some errors."""
        return [
            MockResponses.russian_warrior("1"),
            MockResponses.error_rate_limit(),
            MockResponses.russian_mage("2"),
            MockResponses.error_timeout(),
        ]
    
    @staticmethod
    def validation_failures() -> List[MockResponse]:
        """Responses that fail validation (missing placeholders, CJK remaining)."""
        return [
            MockResponse(items=[{"id": "1", "target_ru": "Воин"}]),  # Missing PH
            MockResponse(items=[{"id": "2", "target_ru": "⟦PH_1⟧法师⟦PH_2⟧"}]),  # CJK remaining
            MockResponse(items=[{"id": "3", "target_ru": ""}]),  # Empty
        ]
    
    @staticmethod
    def long_text_batch() -> List[MockResponse]:
        """Long text responses for content_type='long_text' testing."""
        return [
            MockResponses.russian_long_text("1"),
            MockResponses.russian_long_text("2"),
            MockResponses.russian_long_text("3"),
        ]
    
    @staticmethod
    def mixed_languages() -> List[MockResponse]:
        """Mix of Russian and English translations."""
        return [
            MockResponses.russian_warrior("1"),
            MockResponses.english_mage("2"),
            MockResponses.russian_game_text("3"),
            MockResponses.english_game_text("4"),
        ]


# =============================================================================
# Pytest Fixtures (for conftest.py)
# =============================================================================

import pytest

@pytest.fixture
def mock_llm_client():
    """Fresh mock LLM client for each test."""
    client = LLMMockClient()
    yield client
    client.reset()


@pytest.fixture
def mock_llm_with_latency():
    """Mock LLM client with simulated latency."""
    client = LLMMockClient(simulate_latency=True, latency_jitter=0.05)
    yield client
    client.reset()


@pytest.fixture
def mock_responses():
    """Access to MockResponses factory methods."""
    return MockResponses


@pytest.fixture
def mock_fixtures():
    """Access to MockFixtures collections."""
    return MockFixtures


# =============================================================================
# Integration Helpers
# =============================================================================

def patch_llm_client(mock_client: LLMMockClient):
    """
    Create a patcher for runtime_adapter.LLMClient.
    
    Usage:
        with patch_llm_client(mock_client):
            # Code that uses LLMClient will use mock instead
            result = batch_llm_call(...)
    """
    from unittest.mock import patch
    return patch('runtime_adapter.LLMClient', return_value=mock_client)


def patch_batch_llm_call(mock_client: LLMMockClient):
    """
    Create a patcher for runtime_adapter.batch_llm_call.
    
    This is more direct for tests that only need to mock batch calls.
    """
    from unittest.mock import patch
    
    def mock_batch_call(step, rows, model, system_prompt, user_prompt_template, **kwargs):
        return mock_client.batch_chat(rows, system_prompt, user_prompt_template)
    
    return patch('runtime_adapter.batch_llm_call', side_effect=mock_batch_call)


# =============================================================================
# Example Usage (for documentation)
# =============================================================================

EXAMPLE_USAGE = '''
# Basic Usage
mock = LLMMockClient()
mock.add_simple_translation("战士", "Воин")
result = mock.chat(system="Translate", user="战士")
assert "Воин" in result.text

# With Patterns
mock.add_response_pattern(
    contains="战士",
    items=[{"id": "1", "target_ru": "Воин"}],
    latency_ms=50
)

# Error Injection
mock.add_error_response(ErrorKind.TIMEOUT, "Connection failed", after_calls=2)

# Batch Testing
mock.add_sequence([
    MockResponses.russian_warrior("1"),
    MockResponses.russian_mage("2"),
])
results = mock.batch_chat(
    rows=[{"id": "1"}, {"id": "2"}],
    system_prompt="Translate",
    user_prompt_template=lambda items: json.dumps(items)
)
'''

if __name__ == "__main__":
    # Quick self-test
    print("Testing LLM Mock Framework...")
    
    # Test basic mock
    mock = LLMMockClient()
    mock.add_simple_translation("战士", "Воин")
    result = mock.chat(system="Translate", user="战士")
    print(f"✓ Basic mock: {result.text}")
    
    # Test fixtures
    fixtures = MockFixtures.glossary_batch()
    print(f"✓ Fixtures loaded: {len(fixtures)} responses")
    
    # Test assertions
    mock.assert_call_count(1)
    mock.assert_call_contains("战士")
    print("✓ Assertions passed")
    
    print("\nLLM Mock Framework is ready!")
    print(f"MockResponses available: {len([m for m in dir(MockResponses) if not m.startswith('_')])}")
    print(f"MockFixtures available: {len([m for m in dir(MockFixtures) if not m.startswith('_')])}")
