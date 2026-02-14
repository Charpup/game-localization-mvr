#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_translate_llm_with_mock_llm.py

Example test file demonstrating how to use the MockLLM framework
with translate_llm.py tests.

This file shows the recommended patterns for using mock_llm.py in tests.
"""

import pytest
import json
import csv
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from io import StringIO

# Add paths
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'tests'))

from tests.mock_llm import (
    MockLLM,
    TranslationMock,
    mock_llm_fixture,
    create_translation_mock,
    FAILURE_SCENARIOS
)

from runtime_adapter import LLMClient, LLMError, batch_llm_call
import translate_llm as tl


# =============================================================================
# Example: Using MockLLM with translate_llm
# =============================================================================

class TestTranslateWithMockLLM:
    """Example tests using the new MockLLM framework."""
    
    def test_simple_translation_with_mock(self, tmp_path):
        """Example: Simple translation using MockLLM."""
        with TranslationMock() as mock:
            # Configure translation responses
            mock.add_translation_response("血量", "здоровье ⟦PH_001⟧")
            mock.add_translation_response("攻击", "атака ⟦PH_002⟧")
            
            # Create test CSV
            csv_path = tmp_path / "input.csv"
            with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=["string_id", "source_zh", "tokenized_zh"])
                writer.writeheader()
                writer.writerow({"string_id": "1", "source_zh": "血量", "tokenized_zh": "⟦PH_001⟧血量"})
            
            # The batch handler will auto-generate translations
            # In real usage, you'd call translate_llm.main() or its components
            
            # Verify mock was configured
            assert len(mock.responses) == 2
    
    def test_batch_translation_simulation(self, tmp_path):
        """Example: Simulating batch translation with token preservation."""
        with TranslationMock() as mock:
            # Configure batch translation handler
            def translate_fn(source):
                # Simple mock translation
                translations = {
                    "战士": "Воин",
                    "法师": "Маг",
                    "攻击": "атака",
                }
                for zh, ru in translations.items():
                    if zh in source:
                        return ru
                return f"RU_{source[:20]}"
            
            mock.set_batch_translation_handler(translate_fn)
            
            # Simulate batch processing
            rows = [
                {"id": "1", "source_text": "⟦PH_001⟧战士攻击"},
                {"id": "2", "source_text": "⟦PH_002⟧法师施法"},
            ]
            
            results = batch_llm_call(
                step="translate",
                rows=rows,
                model="gpt-4",
                system_prompt="Translate to Russian",
                user_prompt_template=lambda items: json.dumps({"items": items})
            )
            
            # Verify results
            assert len(results) == 2
            # Tokens should be preserved in translations
            assert "⟦PH_001⟧" in results[0]["translation"]
            assert "⟦PH_002⟧" in results[1]["translation"]
    
    def test_translation_with_glossary_mock(self, tmp_path):
        """Example: Testing glossary integration with MockLLM."""
        with MockLLM() as mock:
            # Track if glossary was used
            glossary_used = [False]
            
            def batch_handler(step, rows, **kwargs):
                system_prompt = kwargs.get('system_prompt', '')
                
                # Check if glossary terms appear in system prompt
                if "血量" in system_prompt or "здоровье" in system_prompt:
                    glossary_used[0] = True
                
                return [
                    {
                        "id": row["id"],
                        "translation": f"здоровье (HP)" if "血量" in row.get('source_text', '') else f"RU_{row['id']}"
                    }
                    for row in rows
                ]
            
            mock.set_batch_handler(batch_handler)
            
            # Create glossary file
            glossary_path = tmp_path / "glossary.yaml"
            import yaml
            with open(glossary_path, 'w', encoding='utf-8') as f:
                yaml.dump({
                    "entries": [
                        {"term_zh": "血量", "term_ru": "здоровье", "status": "approved"}
                    ],
                    "meta": {"compiled_hash": "abc123"}
                }, f)
            
            # Test glossary loading
            entries, hash_val = tl.load_glossary(str(glossary_path))
            assert len(entries) == 1
            assert entries[0].term_zh == "血量"
            
            # Simulate batch call with glossary-aware system prompt
            glossary_summary = tl.build_glossary_summary(entries)
            system_prompt = f"Use glossary:\n{glossary_summary}"
            
            rows = [{"id": "1", "source_text": "血量低于50"}]
            results = batch_llm_call(
                step="translate",
                rows=rows,
                model="gpt-4",
                system_prompt=system_prompt,
                user_prompt_template=lambda x: json.dumps(x)
            )
            
            assert glossary_used[0] is True
    
    def test_translation_retry_with_mock(self, tmp_path):
        """Example: Testing retry logic with simulated failures."""
        with MockLLM() as mock:
            call_count = [0]
            
            def batch_handler_with_retry_simulation(step, rows, **kwargs):
                call_count[0] += 1
                
                # Simulate rate limit on first call
                if call_count[0] == 1:
                    raise FAILURE_SCENARIOS["rate_limit"].to_error()
                
                # Succeed on retry
                return [{"id": row["id"], "translation": f"RU_{row['id']}"} for row in rows]
            
            mock.set_batch_handler(batch_handler_with_retry_simulation)
            
            # Test with retry enabled
            rows = [{"id": "1", "source_text": "Hello"}]
            
            # First attempt should fail
            with pytest.raises(LLMError) as exc_info:
                batch_llm_call(
                    step="translate",
                    rows=rows,
                    model="gpt-4",
                    system_prompt="Translate",
                    user_prompt_template=lambda x: json.dumps(x),
                    retry=0  # No retry
                )
            assert exc_info.value.kind == "upstream"
            
            # Reset counter
            call_count[0] = 0
            
            # With retry, should succeed (mock doesn't auto-retry, 
            # but real batch_llm_call would)
            # This demonstrates how to test retry scenarios
    
    def test_validation_with_mock_responses(self):
        """Example: Testing translation validation with mock responses."""
        with MockLLM() as mock:
            # Configure responses that test validation rules
            mock.add_response("valid", "⟦PH_001⟧Воин⟦PH_002⟧")
            mock.add_response("missing_token", "Воин")  # Missing ⟦PH_002⟧
            mock.add_response("cjk_remaining", "⟦PH_001⟧战士")  # Still has Chinese
            
            # Test valid translation
            client = LLMClient()
            valid_result = client.chat(system="Translate:", user="valid")
            
            source = "⟦PH_001⟧战士⟦PH_002⟧"
            ok, err = tl.validate_translation(source, valid_result.text)
            assert ok is True
            assert err == "ok"
            
            # Test missing token
            missing_result = client.chat(system="Translate:", user="missing_token")
            ok, err = tl.validate_translation(source, missing_result.text)
            assert ok is False
            assert err == "token_mismatch"
            
            # Test CJK remaining
            cjk_result = client.chat(system="Translate:", user="cjk_remaining")
            ok, err = tl.validate_translation(source, cjk_result.text)
            assert ok is False
            assert err == "cjk_remaining"


# =============================================================================
# Example: Using Decorator Pattern
# =============================================================================

class TestWithDecoratorPattern:
    """Examples using the mock_llm_fixture decorator."""
    
    @mock_llm_fixture(responses={
        "血量": "здоровье",
        "攻击": "атака"
    })
    def test_decorator_simple(self):
        """Example: Using decorator for simple responses."""
        client = LLMClient()
        
        result1 = client.chat(system="Translate:", user="血量 is low")
        assert "здоровье" in result1.text
        
        result2 = client.chat(system="Translate:", user="attack with 攻击")
        assert "атака" in result2.text
    
    @mock_llm_fixture(
        responses={"success": "Translation complete"},
        failures=[("slow", "timeout")]
    )
    def test_decorator_with_failures(self):
        """Example: Using decorator with failure scenarios."""
        client = LLMClient()
        
        # Success case
        success = client.chat(system="", user="success")
        assert success.text == "Translation complete"
        
        # Failure case
        with pytest.raises(LLMError) as exc_info:
            client.chat(system="", user="This is slow to translate")
        assert exc_info.value.kind == "timeout"


# =============================================================================
# Example: Testing Error Handling
# =============================================================================

class TestErrorHandlingWithMock:
    """Examples of testing error handling with MockLLM."""
    
    def test_all_error_types(self):
        """Example: Test all error scenario types."""
        for scenario_name, failure in FAILURE_SCENARIOS.items():
            with MockLLM() as mock:
                mock.add_failure(scenario_name)
                
                client = LLMClient()
                
                with pytest.raises(LLMError) as exc_info:
                    client.chat(system="", user="Trigger error")
                
                error = exc_info.value
                assert error.kind == failure.kind
                assert error.retryable == failure.retryable
                
                if failure.http_status:
                    assert error.http_status == failure.http_status
    
    def test_conditional_errors(self):
        """Example: Testing conditional error triggering."""
        with MockLLM() as mock:
            # Only fail on specific inputs
            mock.add_failure("rate_limit", on_keyword="batch_100")
            mock.add_failure("timeout", on_keyword="slow_query")
            
            # Normal query should succeed
            mock.set_default_response("Success")
            
            client = LLMClient()
            
            # Should succeed
            normal = client.chat(system="", user="Normal query")
            assert normal.text == "Success"
            
            # Should fail with rate limit
            with pytest.raises(LLMError) as exc_info:
                client.chat(system="", user="Process batch_100 items")
            assert exc_info.value.kind == "upstream"
            
            # Should fail with timeout
            with pytest.raises(LLMError) as exc_info:
                client.chat(system="", user="This is a slow_query")
            assert exc_info.value.kind == "timeout"


# =============================================================================
# Example: Integration with Existing Test Patterns
# =============================================================================

class TestIntegrationWithExistingPatterns:
    """Examples showing how to integrate MockLLM with existing test patterns."""
    
    def test_with_existing_fixtures(self, tmp_path):
        """Example: Combining MockLLM with existing pytest fixtures."""
        # Create temporary files using tmp_path fixture
        csv_path = tmp_path / "input.csv"
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["string_id", "source_zh", "tokenized_zh"])
            writer.writeheader()
            writer.writerows([
                {"string_id": "1", "source_zh": "战士", "tokenized_zh": "⟦PH_001⟧战士"},
                {"string_id": "2", "source_zh": "法师", "tokenized_zh": "⟦PH_002⟧法师"},
            ])
        
        with MockLLM() as mock:
            # Configure mock to track calls
            call_tracker = []
            
            def batch_handler(step, rows, **kwargs):
                call_tracker.append({
                    "step": step,
                    "row_count": len(rows),
                    "model": kwargs.get('model')
                })
                return [{"id": row["id"], "translation": f"RU_{row['id']}"} for row in rows]
            
            mock.set_batch_handler(batch_handler)
            
            # Simulate the translation workflow
            # In real test, you'd call the actual function
            rows = [
                {"id": "1", "source_text": "⟦PH_001⟧战士"},
                {"id": "2", "source_text": "⟦PH_002⟧法师"},
            ]
            
            results = batch_llm_call(
                step="translate",
                rows=rows,
                model="gpt-4",
                system_prompt="Translate",
                user_prompt_template=lambda items: json.dumps({"items": items})
            )
            
            # Verify tracking
            assert len(call_tracker) == 1
            assert call_tracker[0]["step"] == "translate"
            assert call_tracker[0]["row_count"] == 2
    
    def test_migrating_from_manual_patch(self, tmp_path):
        """
        Example: Showing how to migrate from @patch to MockLLM.
        
        Before (manual patching):
            @patch('runtime_adapter.requests.post')
            def test_old(self, mock_post):
                mock_post.return_value.json.return_value = {...}
                # ... test code ...
        
        After (using MockLLM):
        """
        with MockLLM() as mock:
            # Much cleaner - no need to construct response structure
            mock.add_response("Hello", "Привет", latency_ms=150, model="gpt-4")
            
            client = LLMClient()
            result = client.chat(system="Translate:", user="Hello")
            
            # Assertions are the same
            assert result.text == "Привет"
            assert result.latency_ms == 150
            assert result.model == "gpt-4"
            
            # Plus you get call history automatically
            assert mock.get_call_count() == 1
            assert mock.call_history[0]["system"] == "Translate:"


# =============================================================================
# Best Practices Examples
# =============================================================================

class TestBestPractices:
    """Examples demonstrating best practices."""
    
    def test_assert_call_patterns(self):
        """Example: Using assertion helpers."""
        with MockLLM() as mock:
            # Configure and use mock
            mock.add_response("test", "result")
            client = LLMClient()
            
            # Verify no calls yet
            mock.assert_not_called()
            
            # Make calls
            client.chat(system="", user="test")
            client.chat(system="", user="test")
            
            # Verify calls
            mock.assert_called()
            mock.assert_call_count(2)
    
    def test_clear_between_scenarios(self):
        """Example: Clearing mock between test scenarios."""
        with MockLLM() as mock:
            # Scenario 1: Success
            mock.add_response("hello", "hi")
            client = LLMClient()
            result = client.chat(system="", user="hello")
            assert result.text == "hi"
            
            # Clear for Scenario 2
            mock.clear()
            mock.assert_not_called()  # History cleared too
            
            # Scenario 2: Failure
            mock.add_failure("server_error")
            with pytest.raises(LLMError):
                client.chat(system="", user="hello")
    
    def test_pattern_matching_best_practice(self):
        """Example: Using specific patterns over generic keywords."""
        with MockLLM() as mock:
            # ✅ Good: Specific pattern
            mock.add_pattern(r"translate:\s*(.+)", "Translated: \\1")
            
            # ❌ Avoid: Too generic, might match unexpectedly
            # mock.add_response("a", "b")
            
            client = LLMClient()
            result = client.chat(system="", user="translate: Hello World")
            assert "Translated:" in result.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])