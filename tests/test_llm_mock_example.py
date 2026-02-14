#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_llm_mock_example.py

Example usage of the LLM Mock Framework.
Demonstrates various mocking patterns for testing translation workflows.

Run with: pytest tests/test_llm_mock_example.py -v
"""

import pytest
import json
import sys
import os
from unittest.mock import patch

# Ensure imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.dirname(__file__))

from llm_mock_framework import (
    LLMMockClient,
    MockResponses,
    MockFixtures,
    ErrorKind,
    patch_llm_client,
    patch_batch_llm_call
)


# =============================================================================
# Basic Mocking Examples
# =============================================================================

class TestBasicMocking:
    """Demonstrate basic mock client usage."""
    
    def test_simple_translation_pattern(self):
        """Test adding a simple translation pattern."""
        mock = LLMMockClient()
        mock.add_simple_translation("战士", "Воин", id_val="1")
        
        result = mock.chat(
            system="You are a translator",
            user='Translate: [{"id": "1", "source_text": "战士"}]'
        )
        
        data = json.loads(result.text)
        assert data["items"][0]["target_ru"] == "Воин"
        assert result.latency_ms == 50
    
    def test_response_pattern_with_regex(self):
        """Test using regex patterns for matching."""
        mock = LLMMockClient()
        mock.add_response_pattern(
            regex=r"id.*:\s*\"(\d+)\"",
            items=[{"id": "1", "target_ru": "Воин"}],
            latency_ms=100
        )
        
        result = mock.chat(system="Test", user='{"id": "1"}')
        assert "Воин" in result.text
    
    def test_custom_predicate_matching(self):
        """Test using custom predicate functions."""
        mock = LLMMockClient()
        
        # Match only when both system and user contain specific terms
        def is_battle_context(system: str, user: str) -> bool:
            return "战斗" in system or "битва" in user
        
        mock.add_response_pattern(
            predicate=is_battle_context,
            items=[{"id": "1", "target_ru": "Битва начинается"}]
        )
        
        result = mock.chat(system="战斗场景", user="Translate battle text")
        assert "Битва" in result.text
    
    def test_priority_matching(self):
        """Test that higher priority patterns match first."""
        mock = LLMMockClient()
        
        # Lower priority (matches "战士")
        mock.add_response_pattern(
            contains="战士",
            items=[{"id": "1", "target_ru": "General Warrior"}],
            priority=1
        )
        
        # Higher priority (matches "勇敢的战士")
        mock.add_response_pattern(
            contains="勇敢的战士",
            items=[{"id": "1", "target_ru": "Brave Warrior"}],
            priority=10
        )
        
        result = mock.chat(system="Test", user="勇敢的战士")
        assert "Brave Warrior" in result.text


# =============================================================================
# Response Sequence Examples
# =============================================================================

class TestResponseSequences:
    """Demonstrate response sequencing for multi-call tests."""
    
    def test_basic_sequence(self):
        """Test sequential responses."""
        mock = LLMMockClient()
        mock.add_sequence([
            MockResponses.russian_warrior("1"),
            MockResponses.russian_mage("2"),
            MockResponses.russian_attack("3"),
        ])
        
        # First call
        result1 = mock.chat(system="Test", user="Call 1")
        assert "Воин" in result1.text
        
        # Second call
        result2 = mock.chat(system="Test", user="Call 2")
        assert "Маг" in result2.text
        
        # Third call
        result3 = mock.chat(system="Test", user="Call 3")
        assert "Атака" in result3.text
    
    def test_cycling_sequence(self):
        """Test that cycling sequences restart from beginning."""
        mock = LLMMockClient()
        mock.add_sequence([
            MockResponse(items=[{"id": "1", "target_ru": "First"}]),
            MockResponse(items=[{"id": "1", "target_ru": "Second"}]),
        ], cycle=True)
        
        # First cycle
        r1 = mock.chat(system="Test", user="Call")
        r2 = mock.chat(system="Test", user="Call")
        
        # Second cycle (should restart)
        r3 = mock.chat(system="Test", user="Call")
        r4 = mock.chat(system="Test", user="Call")
        
        assert "First" in r1.text
        assert "Second" in r2.text
        assert "First" in r3.text  # Cycled back
        assert "Second" in r4.text
    
    def test_sequence_exhaustion(self):
        """Test behavior when sequence is exhausted."""
        mock = LLMMockClient()
        mock.add_sequence([
            MockResponse(items=[{"id": "1", "target_ru": "Only"}]),
        ])
        
        # First call uses the sequence
        r1 = mock.chat(system="Test", user="Call 1")
        assert "Only" in r1.text
        
        # Second call falls back to default (empty items)
        r2 = mock.chat(system="Test", user="Call 2")
        data = json.loads(r2.text)
        assert data["items"] == []


# =============================================================================
# Error Injection Examples
# =============================================================================

class TestErrorInjection:
    """Demonstrate error injection for resilience testing."""
    
    def test_timeout_error(self):
        """Test simulating timeout errors."""
        mock = LLMMockClient()
        mock.add_error_response(ErrorKind.TIMEOUT, "Connection timeout after 60s")
        
        with pytest.raises(Exception) as exc_info:
            mock.chat(system="Test", user="Trigger timeout")
        
        assert "timeout" in str(exc_info.value).lower()
    
    def test_rate_limit_error(self):
        """Test simulating rate limit errors (429)."""
        mock = LLMMockClient()
        mock.add_error_response(
            ErrorKind.RATE_LIMIT,
            "Rate limit exceeded",
            http_status=429
        )
        
        with pytest.raises(Exception) as exc_info:
            mock.chat(system="Test", user="Trigger rate limit")
        
        error = exc_info.value
        assert error.http_status == 429
        assert error.retryable  # Rate limits are retryable
    
    def test_config_error_not_retryable(self):
        """Test that config errors are not retryable."""
        mock = LLMMockClient()
        mock.add_error_response(ErrorKind.CONFIG, "Missing API key")
        
        with pytest.raises(Exception) as exc_info:
            mock.chat(system="Test", user="Trigger config error")
        
        error = exc_info.value
        assert not error.retryable  # Config errors should not be retried
    
    def test_error_after_n_calls(self):
        """Test error injection after N successful calls."""
        mock = LLMMockClient()
        mock.add_error_response(
            ErrorKind.NETWORK,
            "Connection refused",
            after_calls=2
        )
        
        # First two calls succeed
        r1 = mock.chat(system="Test", user="Call 1")
        r2 = mock.chat(system="Test", user="Call 2")
        
        # Third call fails
        with pytest.raises(Exception):
            mock.chat(system="Test", user="Call 3")
        
        assert len(mock.get_call_history()) == 3
    
    def test_invalid_json_response(self):
        """Test handling of malformed JSON responses."""
        mock = LLMMockClient()
        mock.add_response_pattern(
            contains="trigger_bad_json",
            response_text='{invalid json here',
            priority=100
        )
        
        result = mock.chat(system="Test", user="trigger_bad_json")
        # Should return the raw text (parsing handled by caller)
        assert "invalid" in result.text


# =============================================================================
# Pre-built Fixture Examples
# =============================================================================

class TestMockFixtures:
    """Demonstrate using pre-built response fixtures."""
    
    def test_russian_translation_fixtures(self):
        """Test Russian translation fixtures."""
        mock = LLMMockClient()
        mock.add_sequence(MockFixtures.glossary_batch())
        
        results = []
        for i in range(4):
            result = mock.chat(system="Test", user=f"Call {i}")
            results.append(json.loads(result.text)["items"][0]["target_ru"])
        
        assert "Воин" in results[0]
        assert "Маг" in results[1]
        assert "Атака" in results[2]
        assert "Заклинание" in results[3]
    
    def test_long_text_fixtures(self):
        """Test long text content type fixtures."""
        mock = LLMMockClient()
        mock.add_sequence(MockFixtures.long_text_batch())
        
        result = mock.chat(system="Test", user="Long text")
        data = json.loads(result.text)
        
        # Should have long Russian text
        assert len(data["items"][0]["target_ru"]) > 100
        assert "королевстве" in data["items"][0]["target_ru"]
    
    def test_validation_failure_fixtures(self):
        """Test fixtures that simulate validation failures."""
        mock = LLMMockClient()
        mock.add_sequence(MockFixtures.validation_failures())
        
        # Missing placeholders
        r1 = mock.chat(system="Test", user="1")
        assert "Воин" in r1.text  # Missing PH_1, PH_2
        
        # CJK remaining (if this were validated)
        r2 = mock.chat(system="Test", user="2")
        assert "法师" in r2.text  # CJK characters present
        
        # Empty translation
        r3 = mock.chat(system="Test", user="3")
        assert json.loads(r3.text)["items"][0]["target_ru"] == ""


# =============================================================================
# Batch Call Examples
# =============================================================================

class TestBatchCalls:
    """Demonstrate batch call mocking."""
    
    def test_batch_chat_basic(self):
        """Test batch_chat method."""
        mock = LLMMockClient()
        mock.add_response_pattern(
            contains="source_text",
            items=[
                {"id": "1", "target_ru": "Воин"},
                {"id": "2", "target_ru": "Маг"},
            ]
        )
        
        rows = [
            {"id": "1", "source_text": "战士"},
            {"id": "2", "source_text": "法师"},
        ]
        
        results = mock.batch_chat(
            rows=rows,
            system_prompt="Translate",
            user_prompt_template=lambda items: json.dumps(items)
        )
        
        assert len(results) == 2
        assert results[0]["target_ru"] == "Воин"
        assert results[1]["target_ru"] == "Маг"
    
    def test_batch_with_dynamic_system_prompt(self):
        """Test batch with callable system prompt."""
        mock = LLMMockClient()
        mock.add_response_pattern(
            contains="dynamic",
            items=[{"id": "1", "target_ru": "Translated"}]
        )
        
        def dynamic_prompt(rows):
            return f"Translate {len(rows)} items dynamically"
        
        results = mock.batch_chat(
            rows=[{"id": "1", "source_text": "test"}],
            system_prompt=dynamic_prompt,
            user_prompt_template=lambda items: json.dumps(items)
        )
        
        assert results[0]["target_ru"] == "Translated"


# =============================================================================
# Call Recording and Assertions
# =============================================================================

class TestCallRecording:
    """Demonstrate call recording for test assertions."""
    
    def test_call_history_recording(self):
        """Test that all calls are recorded."""
        mock = LLMMockClient()
        mock.add_simple_translation("战士", "Воин")
        
        mock.chat(system="System prompt", user="User content")
        mock.chat(system="Another", user="Request")
        
        history = mock.get_call_history()
        assert len(history) == 2
        assert history[0]["system"] == "System prompt"
        assert history[1]["user"] == "Request"
    
    def test_assert_call_count(self):
        """Test call count assertion."""
        mock = LLMMockClient()
        mock.add_simple_translation("战士", "Воин")
        
        mock.chat(system="Test", user="Call 1")
        mock.chat(system="Test", user="Call 2")
        
        mock.assert_call_count(2)  # Should pass
        
        with pytest.raises(AssertionError):
            mock.assert_call_count(3)  # Should fail
    
    def test_assert_call_contains(self):
        """Test call content assertion."""
        mock = LLMMockClient()
        mock.add_simple_translation("战士", "Воин")
        
        mock.chat(system="Translate warrior", user="战士")
        
        mock.assert_call_contains("Translate warrior")
        mock.assert_call_contains("战士")
        
        with pytest.raises(AssertionError):
            mock.assert_call_contains("法师")


# =============================================================================
# Integration Examples (with runtime_adapter patching)
# =============================================================================

class TestIntegrationPatching:
    """Demonstrate integration with translate_llm via patching."""
    
    def test_patch_batch_llm_call(self):
        """Test patching batch_llm_call function."""
        mock = LLMMockClient()
        mock.add_response_pattern(
            contains='"id": "1"',
            items=[{"id": "1", "target_ru": "Воин"}]
        )
        
        with patch_batch_llm_call(mock):
            # Any call to batch_llm_call in this block uses mock
            from runtime_adapter import batch_llm_call
            
            results = batch_llm_call(
                step="translate",
                rows=[{"id": "1", "source_text": "战士"}],
                model="test-model",
                system_prompt="Translate",
                user_prompt_template=lambda items: json.dumps(items)
            )
            
            assert results[0]["target_ru"] == "Воин"
    
    def test_patch_llm_client_class(self):
        """Test patching LLMClient class."""
        mock = LLMMockClient()
        mock.add_simple_translation("战士", "Воин")
        
        with patch_llm_client(mock):
            from runtime_adapter import LLMClient
            
            client = LLMClient()  # Returns our mock
            result = client.chat(system="Test", user="战士")
            
            assert "Воин" in result.text


# =============================================================================
# Latency Simulation Examples
# =============================================================================

class TestLatencySimulation:
    """Demonstrate latency simulation for timing tests."""
    
    def test_latency_simulation_enabled(self):
        """Test that latency is simulated when enabled."""
        import time
        
        mock = LLMMockClient(simulate_latency=True, latency_jitter=0)
        mock.add_response_pattern(
            contains="slow",
            response_text='{"items": []}',
            latency_ms=100  # 100ms simulated
        )
        
        start = time.time()
        mock.chat(system="Test", user="slow request")
        elapsed = (time.time() - start) * 1000
        
        # Should take at least 100ms
        assert elapsed >= 90  # Allow some tolerance
    
    def test_latency_simulation_disabled(self):
        """Test that latency is not simulated when disabled."""
        import time
        
        mock = LLMMockClient(simulate_latency=False)
        mock.add_response_pattern(
            contains="fast",
            response_text='{"items": []}',
            latency_ms=1000  # Would be 1s if enabled
        )
        
        start = time.time()
        mock.chat(system="Test", user="fast request")
        elapsed = (time.time() - start) * 1000
        
        # Should be nearly instant
        assert elapsed < 50


# =============================================================================
# Reset and Cleanup Examples
# =============================================================================

class TestResetAndCleanup:
    """Demonstrate mock client reset functionality."""
    
    def test_reset_clears_patterns(self):
        """Test that reset clears all patterns."""
        mock = LLMMockClient()
        mock.add_simple_translation("战士", "Воин")
        
        mock.reset()
        
        # After reset, no patterns match
        result = mock.chat(system="Test", user="战士")
        data = json.loads(result.text)
        assert data["items"] == []  # Default empty response
    
    def test_reset_clears_history(self):
        """Test that reset clears call history."""
        mock = LLMMockClient()
        mock.add_simple_translation("战士", "Воин")
        
        mock.chat(system="Test", user="Call")
        assert len(mock.get_call_history()) == 1
        
        mock.reset()
        assert len(mock.get_call_history()) == 0
    
    def test_chaining_interface(self):
        """Test that methods return self for chaining."""
        mock = LLMMockClient()
        
        # All these should return the mock for chaining
        result = (
            mock
            .add_simple_translation("战士", "Воин")
            .add_simple_translation("法师", "Маг")
            .set_default_response(MockResponse(items=[{"id": "1", "target_ru": "Default"}]))
        )
        
        assert result is mock


# Need to import MockResponse for the last test
from llm_mock_framework import MockResponse


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
