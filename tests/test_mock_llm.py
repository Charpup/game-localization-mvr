#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_mock_llm.py

Unit tests for the mock_llm.py mocking framework.
Ensures the mocking utilities work correctly.
"""

import pytest
import json
import re
import sys
import os

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from tests.mock_llm import (
    MockLLM,
    MockResponse,
    MockFailure,
    TranslationMock,
    QAMock,
    FAILURE_SCENARIOS,
    mock_llm_fixture,
    mock_llm_context,
    create_mock_result,
    create_mock_batch_result,
    create_success_mock,
    create_failure_mock,
    create_translation_mock,
)

from runtime_adapter import LLMClient, LLMError, LLMResult, batch_llm_call


# =============================================================================
# MockResponse Tests
# =============================================================================

class TestMockResponse:
    """Tests for MockResponse dataclass."""
    
    def test_default_creation(self):
        """Test creating MockResponse with defaults."""
        resp = MockResponse(text="Hello")
        assert resp.text == "Hello"
        assert resp.latency_ms == 100
        assert resp.model == "gpt-4-mock"
        assert resp.usage is not None
        assert "prompt_tokens" in resp.usage
        assert resp.request_id is not None
        assert resp.raw is not None
    
    def test_custom_values(self):
        """Test creating MockResponse with custom values."""
        resp = MockResponse(
            text="Bonjour",
            latency_ms=200,
            model="claude-3",
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            request_id="req-123"
        )
        assert resp.text == "Bonjour"
        assert resp.latency_ms == 200
        assert resp.model == "claude-3"
        assert resp.request_id == "req-123"
    
    def test_token_estimation(self):
        """Test that tokens are estimated from text length."""
        # 40 chars should be ~10 tokens
        resp = MockResponse(text="a" * 40)
        assert resp.usage["completion_tokens"] == 10


# =============================================================================
# MockFailure Tests
# =============================================================================

class TestMockFailure:
    """Tests for MockFailure dataclass."""
    
    def test_to_error(self):
        """Test converting MockFailure to LLMError."""
        failure = MockFailure(
            kind="timeout",
            message="Request timed out",
            retryable=True,
            http_status=None
        )
        error = failure.to_error()
        
        assert isinstance(error, LLMError)
        assert error.kind == "timeout"
        assert str(error) == "Request timed out"
        assert error.retryable is True
    
    def test_predefined_scenarios(self):
        """Test all predefined failure scenarios."""
        required_scenarios = [
            "rate_limit", "timeout", "network_error", "server_error",
            "bad_request", "unauthorized", "parse_error", "config_error"
        ]
        
        for scenario in required_scenarios:
            assert scenario in FAILURE_SCENARIOS, f"Missing scenario: {scenario}"
            failure = FAILURE_SCENARIOS[scenario]
            assert isinstance(failure, MockFailure)
            error = failure.to_error()
            assert isinstance(error, LLMError)


# =============================================================================
# MockLLM Core Tests
# =============================================================================

class TestMockLLMBasic:
    """Basic tests for MockLLM class."""
    
    def test_initialization(self):
        """Test MockLLM initialization."""
        mock = MockLLM()
        assert mock.model == "gpt-4-mock"
        assert len(mock.responses) == 0
        assert len(mock.failures) == 0
        assert mock.default_response is None
    
    def test_initialization_custom_model(self):
        """Test MockLLM with custom model."""
        mock = MockLLM(model="claude-3-mock")
        assert mock.model == "claude-3-mock"


class TestMockLLMContextManager:
    """Tests for MockLLM context manager usage."""
    
    def test_context_manager_basic(self):
        """Test basic context manager functionality."""
        with MockLLM() as mock:
            mock.add_response("Hello", "Bonjour")
            
            # Client should work within context
            client = LLMClient()
            result = client.chat(system="Translate:", user="Hello")
            
            assert result.text == "Bonjour"
        
        # After context, real implementation would be used
        # (but we don't test that here to avoid API calls)
    
    def test_context_manager_call_recording(self):
        """Test that calls are recorded."""
        with MockLLM() as mock:
            mock.add_response("test", "result")
            
            client = LLMClient()
            client.chat(system="", user="test")
            
            assert mock.get_call_count() == 1
            assert len(mock.call_history) == 1
            assert mock.call_history[0]["user"] == "test"
    
    def test_context_manager_multiple_calls(self):
        """Test multiple calls within context."""
        with MockLLM() as mock:
            mock.add_response("A", "Alpha")
            mock.add_response("B", "Beta")
            
            client = LLMClient()
            
            result1 = client.chat(system="", user="A")
            result2 = client.chat(system="", user="B")
            
            assert result1.text == "Alpha"
            assert result2.text == "Beta"
            assert mock.get_call_count() == 2


class TestMockLLMResponses:
    """Tests for response configuration."""
    
    def test_add_response(self):
        """Test adding keyword response."""
        with MockLLM() as mock:
            mock.add_response("Hello", "Bonjour", latency_ms=150)
            
            client = LLMClient()
            result = client.chat(system="Greet:", user="Hello there")
            
            assert result.text == "Bonjour"
            assert result.latency_ms == 150
    
    def test_add_pattern(self):
        """Test adding pattern response."""
        with MockLLM() as mock:
            mock.add_pattern(r"translate.*French", "Traduction")
            
            client = LLMClient()
            result = client.chat(system="Translate to French:", user="Hello")
            
            assert result.text == "Traduction"
    
    def test_pattern_not_matching(self):
        """Test pattern that doesn't match."""
        with MockLLM() as mock:
            mock.add_pattern(r"translate.*Spanish", "Traducción")
            mock.set_default_response("Unknown")
            
            client = LLMClient()
            result = client.chat(system="Translate to German:", user="Hello")
            
            assert result.text == "Unknown"
    
    def test_default_response(self):
        """Test default response fallback."""
        with MockLLM() as mock:
            mock.set_default_response("Default answer")
            
            client = LLMClient()
            result = client.chat(system="", user="Anything")
            
            assert result.text == "Default answer"
    
    def test_response_priority(self):
        """Test that first matching response wins."""
        with MockLLM() as mock:
            mock.add_response("test", "First")
            mock.add_response("test", "Second")  # Should not be used
            
            client = LLMClient()
            result = client.chat(system="", user="test")
            
            assert result.text == "First"


class TestMockLLMFailures:
    """Tests for failure simulation."""
    
    def test_add_failure_always(self):
        """Test unconditional failure."""
        with MockLLM() as mock:
            mock.add_failure("timeout")
            
            client = LLMClient()
            
            with pytest.raises(LLMError) as exc_info:
                client.chat(system="", user="Hello")
            
            assert exc_info.value.kind == "timeout"
            assert exc_info.value.retryable is True
    
    def test_add_failure_conditional(self):
        """Test conditional failure with keyword."""
        with MockLLM() as mock:
            mock.add_failure("rate_limit", on_keyword="slow")
            mock.add_response("fast", "Quick response")
            
            client = LLMClient()
            
            # Should fail
            with pytest.raises(LLMError) as exc_info:
                client.chat(system="", user="This is slow")
            assert exc_info.value.kind == "upstream"
            
            # Should succeed
            result = client.chat(system="", user="This is fast")
            assert result.text == "Quick response"
    
    def test_all_failure_scenarios(self):
        """Test that all failure scenarios raise correctly."""
        for scenario_name, failure in FAILURE_SCENARIOS.items():
            with MockLLM() as mock:
                mock.add_failure(scenario_name)
                
                client = LLMClient()
                
                with pytest.raises(LLMError) as exc_info:
                    client.chat(system="", user="test")
                
                assert exc_info.value.kind == failure.kind


class TestMockLLMBatch:
    """Tests for batch call mocking."""
    
    def test_batch_handler_basic(self):
        """Test basic batch handler."""
        with MockLLM() as mock:
            def handler(step, rows, **kwargs):
                return [{"id": row["id"], "result": f"res_{row['id']}"} for row in rows]
            
            mock.set_batch_handler(handler)
            
            # Import batch_llm_call inside context to use patched version
            from runtime_adapter import batch_llm_call as _batch_call
            
            rows = [{"id": "1"}, {"id": "2"}]
            results = _batch_call(
                step="test",
                rows=rows,
                model="gpt-4",
                system_prompt="Test",
                user_prompt_template=lambda x: json.dumps(x)
            )
            
            assert len(results) == 2
            assert results[0]["result"] == "res_1"
            assert results[1]["result"] == "res_2"
    
    def test_batch_response_function(self):
        """Test batch response function."""
        with MockLLM() as mock:
            mock.set_batch_response(
                lambda items: [{"id": item["id"], "translation": f"RU_{item['id']}"} for item in items]
            )
            
            # Import batch_llm_call inside context to use patched version
            from runtime_adapter import batch_llm_call as _batch_call
            
            rows = [{"id": "1", "source_text": "Hello"}, {"id": "2", "source_text": "World"}]
            results = _batch_call(
                step="translate",
                rows=rows,
                model="gpt-4",
                system_prompt="Translate",
                user_prompt_template=lambda x: json.dumps(x)
            )
            
            assert results[0]["translation"] == "RU_1"
            assert results[1]["translation"] == "RU_2"
    
    def test_default_batch_processing(self):
        """Test default batch processing when no handler set."""
        with MockLLM() as mock:
            # Import batch_llm_call inside context to use patched version
            from runtime_adapter import batch_llm_call as _batch_call
            
            rows = [
                {"id": "1", "source_text": "Text 1"},
                {"id": "2", "source_text": "Text 2"}
            ]
            
            results = _batch_call(
                step="translate",
                rows=rows,
                model="gpt-4",
                system_prompt="Translate",
                user_prompt_template=lambda x: json.dumps(x)
            )
            
            assert len(results) == 2
            assert "id" in results[0]
            assert "translation" in results[0]


class TestMockLLMAssertions:
    """Tests for assertion helpers."""
    
    def test_assert_called_success(self):
        """Test assert_called when calls were made."""
        with MockLLM() as mock:
            mock.add_response("test", "result")
            client = LLMClient()
            client.chat(system="", user="test")
            
            mock.assert_called()  # Should not raise
    
    def test_assert_called_failure(self):
        """Test assert_called when no calls were made."""
        with MockLLM() as mock:
            with pytest.raises(AssertionError):
                mock.assert_called()
    
    def test_assert_not_called_success(self):
        """Test assert_not_called when no calls were made."""
        with MockLLM() as mock:
            mock.assert_not_called()  # Should not raise
    
    def test_assert_not_called_failure(self):
        """Test assert_not_called when calls were made."""
        with MockLLM() as mock:
            mock.add_response("test", "result")
            client = LLMClient()
            client.chat(system="", user="test")
            
            with pytest.raises(AssertionError):
                mock.assert_not_called()
    
    def test_assert_call_count_success(self):
        """Test assert_call_count with correct count."""
        with MockLLM() as mock:
            mock.add_response("test", "result")
            client = LLMClient()
            client.chat(system="", user="test")
            client.chat(system="", user="test")
            
            mock.assert_call_count(2)  # Should not raise
    
    def test_assert_call_count_failure(self):
        """Test assert_call_count with incorrect count."""
        with MockLLM() as mock:
            mock.add_response("test", "result")
            client = LLMClient()
            client.chat(system="", user="test")
            
            with pytest.raises(AssertionError):
                mock.assert_call_count(2)


# =============================================================================
# Decorator and Context Manager Tests
# =============================================================================

class TestMockLLMFixture:
    """Tests for mock_llm_fixture decorator."""
    
    def test_decorator_basic(self):
        """Test basic decorator usage."""
        @mock_llm_fixture(responses={"Hello": "Bonjour"})
        def test_func():
            client = LLMClient()
            result = client.chat(system="", user="Hello")
            return result.text
        
        assert test_func() == "Bonjour"
    
    def test_decorator_with_failures(self):
        """Test decorator with failures."""
        @mock_llm_fixture(
            responses={"success": "OK"},
            failures=[("fail", "error")]
        )
        def test_func():
            client = LLMClient()
            
            # Should succeed
            result = client.chat(system="", user="success")
            assert result.text == "OK"
            
            # Should fail
            with pytest.raises(LLMError):
                client.chat(system="", user="fail with error")
        
        test_func()


class TestMockLLMContext:
    """Tests for mock_llm_context context manager."""
    
    def test_context_basic(self):
        """Test basic context manager usage."""
        with mock_llm_context({"Hello": "Bonjour"}) as mock:
            client = LLMClient()
            result = client.chat(system="", user="Hello")
            assert result.text == "Bonjour"
    
    def test_context_with_default(self):
        """Test context manager with default response."""
        with mock_llm_context(
            responses={"specific": "Specific"},
            default_response="Default"
        ) as mock:
            client = LLMClient()
            
            specific = client.chat(system="", user="specific")
            default = client.chat(system="", user="anything else")
            
            assert specific.text == "Specific"
            assert default.text == "Default"


# =============================================================================
# TranslationMock Tests
# =============================================================================

class TestTranslationMock:
    """Tests for TranslationMock specialized class."""
    
    def test_token_extraction(self):
        """Test token extraction from text."""
        mock = TranslationMock()
        tokens = mock._extract_tokens("Attack with ⟦PH_001⟧ and ⟦TAG_002⟧")
        
        assert "PH_001" in tokens
        assert "TAG_002" in tokens
    
    def test_add_translation_response(self):
        """Test adding translation response."""
        with TranslationMock() as mock:
            mock.add_translation_response("attack", "атака ⟦PH_001⟧")
            
            client = LLMClient()
            result = client.chat(system="Translate:", user="attack with ⟦PH_001⟧")
            
            # Should contain the translation
            assert "атака" in result.text
    
    def test_batch_translation_handler(self):
        """Test batch translation handler."""
        with TranslationMock() as mock:
            mock.set_batch_translation_handler(lambda src: f"RU_{src[:10]}")
            
            mock.set_batch_handler = lambda h: None  # Override to test directly
            # Note: Full test would require actual batch call


# =============================================================================
# QAMock Tests
# =============================================================================

class TestQAMock:
    """Tests for QAMock specialized class."""
    
    def test_add_issue(self):
        """Test adding predefined issues."""
        mock = QAMock()
        mock.add_issue("row-1", "token_mismatch", "Missing token", "critical")
        
        assert "row-1" in mock.issues
        assert len(mock.issues["row-1"]) == 1
        assert mock.issues["row-1"][0]["type"] == "token_mismatch"
    
    def test_qa_mock_with_issue_rate(self):
        """Test QA mock with random issue rate."""
        mock = QAMock(issue_rate=1.0)  # 100% issue rate
        mock.set_batch_qa_handler()
        
        # Handler should be set
        assert mock.batch_handler is not None


# =============================================================================
# Utility Function Tests
# =============================================================================

class TestUtilityFunctions:
    """Tests for utility functions."""
    
    def test_create_mock_result(self):
        """Test create_mock_result utility."""
        result = create_mock_result("Test text", model="test-model", latency_ms=200)
        
        assert isinstance(result, LLMResult)
        assert result.text == "Test text"
        assert result.model == "test-model"
        assert result.latency_ms == 200
    
    def test_create_mock_batch_result(self):
        """Test create_mock_batch_result utility."""
        rows = [{"id": "1"}, {"id": "2"}]
        results = create_mock_batch_result(rows, result_key="translation")
        
        assert len(results) == 2
        assert results[0]["id"] == "1"
        assert results[0]["translation"] == "result_1"
    
    def test_create_success_mock(self):
        """Test create_success_mock utility."""
        mock = create_success_mock("Always success")
        
        assert isinstance(mock, MockLLM)
        assert mock.default_response.text == "Always success"
    
    def test_create_failure_mock(self):
        """Test create_failure_mock utility."""
        mock = create_failure_mock("timeout")
        
        assert isinstance(mock, MockLLM)
        assert len(mock.failures) == 1
    
    def test_create_translation_mock(self):
        """Test create_translation_mock utility."""
        translations = {"Hello": "Bonjour", "World": "Monde"}
        mock = create_translation_mock(translations)
        
        assert isinstance(mock, TranslationMock)
        assert len(mock.responses) == 2


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error conditions."""
    
    def test_clear_mock(self):
        """Test clearing mock state."""
        mock = MockLLM()
        mock.add_response("test", "result")
        mock.add_failure("timeout")
        mock.set_default_response("default")
        
        mock.clear()
        
        assert len(mock.responses) == 0
        assert len(mock.failures) == 0
        assert mock.default_response is None
    
    def test_empty_batch(self):
        """Test batch call with empty rows."""
        with MockLLM() as mock:
            # Import batch_llm_call inside context to use patched version
            from runtime_adapter import batch_llm_call as _batch_call
            
            results = _batch_call(
                step="test",
                rows=[],
                model="gpt-4",
                system_prompt="Test",
                user_prompt_template=lambda x: x
            )
            
            assert results == []
    
    def test_auto_generated_response_translation(self):
        """Test auto-generated response for translation context."""
        with MockLLM() as mock:
            client = LLMClient()
            result = client.chat(
                system="You are a translator. Translate to Russian.",
                user='{"items": [{"id": "1", "source_text": "Hello"}]}'
            )
            
            # Should auto-generate a translation-like response
            assert "RU_" in result.text or "translation" in result.text.lower()
    
    def test_auto_generated_response_qa(self):
        """Test auto-generated response for QA context."""
        with MockLLM() as mock:
            client = LLMClient()
            result = client.chat(
                system="You are a QA checker. Check quality.",
                user="Check this text"
            )
            
            # Should auto-generate a QA-like response
            assert "items" in result.text or "[]" in result.text


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests combining multiple features."""
    
    def test_complex_scenario(self):
        """Test complex scenario with multiple configurations."""
        with MockLLM(model="gpt-4-test") as mock:
            # Set up multiple responses
            mock.add_response("greeting", "Hello!")
            mock.add_pattern(r"question:.*", "Answer here")
            mock.set_default_response("I don't know")
            
            # Set up conditional failure
            mock.add_failure("rate_limit", on_keyword="overload")
            
            # Set up batch handler
            mock.set_batch_response(
                lambda items: [{"id": i["id"], "result": f"processed_{i['id']}"} for i in items]
            )
            
            client = LLMClient()
            
            # Test responses
            assert client.chat("", "greeting").text == "Hello!"
            assert client.chat("", "question: What?").text == "Answer here"
            assert client.chat("", "unknown").text == "I don't know"
            
            # Test failure
            with pytest.raises(LLMError):
                client.chat("", "server overload")
            
            # Test batch - import inside context
            from runtime_adapter import batch_llm_call as _batch_call
            
            results = _batch_call(
                step="process",
                rows=[{"id": "1"}, {"id": "2"}],
                model="gpt-4",
                system_prompt="Process",
                user_prompt_template=lambda x: str(x)
            )
            
            assert len(results) == 2
            assert results[0]["result"] == "processed_1"
            
            # Verify call count (3 chat calls + batch call recorded)
            assert mock.get_call_count() >= 3
    
    def test_manual_start_stop(self):
        """Test manual start/stop lifecycle."""
        mock = MockLLM()
        mock.add_response("test", "result")
        
        try:
            mock.start()
            
            client = LLMClient()
            result = client.chat(system="", user="test")
            
            assert result.text == "result"
            assert mock.get_call_count() == 1
        finally:
            mock.stop()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])