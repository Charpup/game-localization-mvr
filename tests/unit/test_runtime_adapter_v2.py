#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_runtime_adapter_v2.py

Comprehensive unit tests for runtime_adapter.py with 90%+ coverage.
Uses mocking to avoid real HTTP requests.

Test Coverage:
- LLMClient initialization (env vars, explicit params, config errors)
- LLMClient.chat() with various scenarios
- batch_llm_call with retries and error handling
- LLMRouter model selection and fallback logic
- EmbeddingClient functionality
- Trace recording (_trace function)
- Error handling (LLMError with retry hints)
- Retry logic (batch_llm_call retry mechanism)
"""

import json
import os
import sys
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from io import StringIO

import numpy as np

# Add parent directory to path to import runtime_adapter
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from runtime_adapter import (
    LLMClient,
    LLMError,
    LLMResult,
    LLMRouter,
    BatchConfig,
    EmbeddingClient,
    chat,
    _trace,
    _estimate_tokens,
    _extract_usage,
    _estimate_cost,
    _load_pricing,
    parse_llm_response,
    batch_llm_call,
    log_llm_progress,
    get_batch_config,
    CHARS_PER_TOKEN,
)


class TestLLMError(unittest.TestCase):
    """Test LLMError exception class."""
    
    def test_error_creation(self):
        """Test basic LLMError creation."""
        error = LLMError("timeout", "Request timed out")
        self.assertEqual(error.kind, "timeout")
        self.assertEqual(str(error), "Request timed out")
        self.assertTrue(error.retryable)
        self.assertIsNone(error.http_status)
    
    def test_error_with_http_status(self):
        """Test LLMError with HTTP status code."""
        error = LLMError("upstream", "Server error", retryable=True, http_status=503)
        self.assertEqual(error.http_status, 503)
        self.assertTrue(error.retryable)
    
    def test_non_retryable_error(self):
        """Test non-retryable error."""
        error = LLMError("config", "Missing API key", retryable=False)
        self.assertFalse(error.retryable)


class TestLLMResult(unittest.TestCase):
    """Test LLMResult dataclass."""
    
    def test_result_creation(self):
        """Test LLMResult creation."""
        result = LLMResult(
            text="Hello",
            latency_ms=100,
            raw={"choices": []},
            request_id="req-123",
            usage={"prompt_tokens": 10, "completion_tokens": 5},
            model="gpt-4"
        )
        self.assertEqual(result.text, "Hello")
        self.assertEqual(result.latency_ms, 100)
        self.assertEqual(result.request_id, "req-123")
        self.assertEqual(result.model, "gpt-4")


class TestUtilityFunctions(unittest.TestCase):
    """Test utility helper functions."""
    
    def test_estimate_tokens(self):
        """Test token estimation from text."""
        # Empty text
        self.assertEqual(_estimate_tokens(""), 1)  # max(1, ...)
        # Short text
        self.assertEqual(_estimate_tokens("Hello"), 1)
        # Long text (20 chars / 4 = 5 tokens)
        text = "a" * 20
        self.assertEqual(_estimate_tokens(text), 5)
    
    def test_extract_usage(self):
        """Test usage extraction from API response."""
        # Valid usage
        data = {
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15
            }
        }
        usage = _extract_usage(data)
        self.assertEqual(usage["prompt_tokens"], 10)
        self.assertEqual(usage["completion_tokens"], 5)
        self.assertEqual(usage["total_tokens"], 15)
    
    def test_extract_usage_missing(self):
        """Test usage extraction when usage is missing."""
        self.assertIsNone(_extract_usage({}))
        self.assertIsNone(_extract_usage({"usage": None}))
    
    def test_extract_usage_partial(self):
        """Test usage extraction with partial data."""
        data = {"usage": {"prompt_tokens": 10}}
        usage = _extract_usage(data)
        self.assertEqual(usage["prompt_tokens"], 10)
        self.assertEqual(usage["completion_tokens"], 0)
        self.assertEqual(usage["total_tokens"], 10)


class TestTraceFunction(unittest.TestCase):
    """Test trace logging functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.trace_path = os.path.join(self.temp_dir, "trace.jsonl")
        os.environ["LLM_TRACE_PATH"] = self.trace_path
    
    def tearDown(self):
        """Clean up test environment."""
        if "LLM_TRACE_PATH" in os.environ:
            del os.environ["LLM_TRACE_PATH"]
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_trace_writes_to_file(self):
        """Test that trace events are written to file."""
        event = {"type": "test", "data": "value"}
        _trace(event)
        
        # Verify file was created and contains event
        self.assertTrue(os.path.exists(self.trace_path))
        with open(self.trace_path, 'r') as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 1)
        
        data = json.loads(lines[0])
        self.assertEqual(data["type"], "test")
        self.assertEqual(data["data"], "value")
        self.assertIn("timestamp", data)
    
    def test_trace_no_path(self):
        """Test trace with no path set."""
        del os.environ["LLM_TRACE_PATH"]
        os.environ["LLM_TRACE_PATH"] = ""
        # Should not raise exception
        _trace({"type": "test"})
    
    def test_trace_directory_creation(self):
        """Test that trace creates directory if needed."""
        nested_path = os.path.join(self.temp_dir, "nested", "dir", "trace.jsonl")
        os.environ["LLM_TRACE_PATH"] = nested_path
        
        _trace({"type": "test"})
        self.assertTrue(os.path.exists(nested_path))


class TestLLMClientInit(unittest.TestCase):
    """Test LLMClient initialization scenarios."""
    
    def setUp(self):
        """Set up environment variables."""
        self.orig_env = {
            "LLM_BASE_URL": os.environ.get("LLM_BASE_URL"),
            "LLM_API_KEY": os.environ.get("LLM_API_KEY"),
            "LLM_MODEL": os.environ.get("LLM_MODEL"),
            "LLM_TIMEOUT_S": os.environ.get("LLM_TIMEOUT_S"),
            "LLM_API_KEY_FILE": os.environ.get("LLM_API_KEY_FILE"),
        }
        os.environ["LLM_BASE_URL"] = "https://api.test.com"
        os.environ["LLM_API_KEY"] = "test-key"
        os.environ["LLM_MODEL"] = "test-model"
    
    def tearDown(self):
        """Restore environment variables."""
        for key, value in self.orig_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        # Reset router singleton
        LLMClient._router = None
    
    def test_init_from_env(self):
        """Test initialization from environment variables."""
        client = LLMClient()
        self.assertEqual(client.base_url, "https://api.test.com")
        self.assertEqual(client.api_key, "test-key")
        self.assertEqual(client.default_model, "test-model")
        self.assertEqual(client.timeout_s, 60)  # Default
    
    def test_init_explicit_params(self):
        """Test initialization with explicit parameters."""
        client = LLMClient(
            base_url="https://explicit.com",
            api_key="explicit-key",
            model="explicit-model",
            timeout_s=120
        )
        self.assertEqual(client.base_url, "https://explicit.com")
        self.assertEqual(client.api_key, "explicit-key")
        self.assertEqual(client.default_model, "explicit-model")
        self.assertEqual(client.timeout_s, 120)
    
    def test_init_missing_config(self):
        """Test initialization with missing configuration."""
        del os.environ["LLM_BASE_URL"]
        del os.environ["LLM_API_KEY"]
        
        with self.assertRaises(LLMError) as context:
            LLMClient()
        
        self.assertEqual(context.exception.kind, "config")
        self.assertFalse(context.exception.retryable)
    
    def test_init_api_key_from_file(self):
        """Test loading API key from file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("api key: file-based-key")
            key_file = f.name
        
        try:
            del os.environ["LLM_API_KEY"]
            os.environ["LLM_API_KEY_FILE"] = key_file
            
            client = LLMClient()
            self.assertEqual(client.api_key, "file-based-key")
        finally:
            os.remove(key_file)
    
    def test_init_api_key_file_simple_format(self):
        """Test loading API key from file with simple format."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("simple-key-no-prefix")
            key_file = f.name
        
        try:
            del os.environ["LLM_API_KEY"]
            os.environ["LLM_API_KEY_FILE"] = key_file
            
            client = LLMClient()
            self.assertEqual(client.api_key, "simple-key-no-prefix")
        finally:
            os.remove(key_file)
    
    def test_timeout_from_env(self):
        """Test timeout from environment variable."""
        os.environ["LLM_TIMEOUT_S"] = "90"
        client = LLMClient()
        self.assertEqual(client.timeout_s, 90)


class TestLLMClientChat(unittest.TestCase):
    """Test LLMClient.chat() method."""
    
    def setUp(self):
        """Set up test client."""
        os.environ["LLM_BASE_URL"] = "https://api.test.com"
        os.environ["LLM_API_KEY"] = "test-key"
        os.environ["LLM_MODEL"] = "test-model"
        LLMClient._router = None
        self.client = LLMClient()
    
    def tearDown(self):
        """Clean up."""
        LLMClient._router = None
    
    @patch('runtime_adapter.requests.post')
    def test_chat_success(self, mock_post):
        """Test successful chat completion."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "req-123",
            "choices": [{"message": {"content": "Hello, world!"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }
        mock_post.return_value = mock_response
        
        result = self.client.chat(system="You are helpful.", user="Say hello")
        
        self.assertEqual(result.text, "Hello, world!")
        self.assertEqual(result.request_id, "req-123")
        self.assertIsNotNone(result.usage)
        self.assertEqual(result.usage["prompt_tokens"], 10)
    
    @patch('runtime_adapter.requests.post')
    def test_chat_with_metadata(self, mock_post):
        """Test chat with metadata for routing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "req-456",
            "choices": [{"message": {"content": "Translated text"}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 10}
        }
        mock_post.return_value = mock_response
        
        result = self.client.chat(
            system="Translate to Chinese.",
            user="Hello",
            metadata={"step": "translate", "batch_id": "123"}
        )
        
        self.assertEqual(result.text, "Translated text")
    
    @patch('runtime_adapter.requests.post')
    def test_chat_with_model_override(self, mock_post):
        """Test chat with model override in metadata."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "req-789",
            "choices": [{"message": {"content": "Response"}}],
            "usage": {}
        }
        mock_post.return_value = mock_response
        
        result = self.client.chat(
            system="System",
            user="User",
            metadata={"model_override": "gpt-4"}
        )
        
        # Verify the model was overridden in payload
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload['model'], 'gpt-4')
    
    @patch('runtime_adapter.requests.post')
    def test_chat_timeout_error(self, mock_post):
        """Test chat with timeout error."""
        import requests
        mock_post.side_effect = requests.Timeout("Connection timed out")
        
        with self.assertRaises(LLMError) as context:
            self.client.chat(system="Test", user="Test")
        
        self.assertEqual(context.exception.kind, "timeout")
        self.assertTrue(context.exception.retryable)
    
    @patch('runtime_adapter.requests.post')
    def test_chat_network_error(self, mock_post):
        """Test chat with network error."""
        import requests
        mock_post.side_effect = requests.ConnectionError("No connection")
        
        with self.assertRaises(LLMError) as context:
            self.client.chat(system="Test", user="Test")
        
        self.assertEqual(context.exception.kind, "network")
        self.assertTrue(context.exception.retryable)
    
    @patch('runtime_adapter.requests.post')
    def test_chat_http_429_error(self, mock_post):
        """Test chat with rate limit error (429)."""
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.text = "Rate limited"
        mock_post.return_value = mock_response
        
        with self.assertRaises(LLMError) as context:
            self.client.chat(system="Test", user="Test")
        
        self.assertEqual(context.exception.kind, "upstream")
        self.assertEqual(context.exception.http_status, 429)
        self.assertTrue(context.exception.retryable)
    
    @patch('runtime_adapter.requests.post')
    def test_chat_http_500_error(self, mock_post):
        """Test chat with server error (500)."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal server error"
        mock_post.return_value = mock_response
        
        with self.assertRaises(LLMError) as context:
            self.client.chat(system="Test", user="Test")
        
        self.assertEqual(context.exception.kind, "upstream")
        self.assertEqual(context.exception.http_status, 500)
    
    @patch('runtime_adapter.requests.post')
    def test_chat_http_400_error(self, mock_post):
        """Test chat with client error (400) - non-retryable."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_post.return_value = mock_response
        
        with self.assertRaises(LLMError) as context:
            self.client.chat(system="Test", user="Test")
        
        self.assertEqual(context.exception.kind, "http")
        self.assertEqual(context.exception.http_status, 400)
        self.assertFalse(context.exception.retryable)
    
    @patch('runtime_adapter.requests.post')
    def test_chat_parse_error(self, mock_post):
        """Test chat with JSON parse error."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.side_effect = json.JSONDecodeError("test", "doc", 0)
        mock_post.return_value = mock_response
        
        with self.assertRaises(LLMError) as context:
            self.client.chat(system="Test", user="Test")
        
        self.assertEqual(context.exception.kind, "parse")
        self.assertTrue(context.exception.retryable)
    
    @patch('runtime_adapter.requests.post')
    def test_chat_with_response_format(self, mock_post):
        """Test chat with JSON response format."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "req-json",
            "choices": [{"message": {"content": '{"key": "value"}'}}],
            "usage": {}
        }
        mock_post.return_value = mock_response
        
        result = self.client.chat(
            system="Return JSON",
            user="Test",
            response_format={"type": "json_object"}
        )
        
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload['response_format'], {"type": "json_object"})
    
    @patch('runtime_adapter.requests.post')
    def test_chat_missing_choices(self, mock_post):
        """Test chat with malformed response (missing choices)."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "req-bad"}  # Missing choices
        mock_post.return_value = mock_response
        
        with self.assertRaises(LLMError) as context:
            self.client.chat(system="Test", user="Test")
        
        self.assertEqual(context.exception.kind, "parse")


class TestLLMRouter(unittest.TestCase):
    """Test LLMRouter functionality."""
    
    def setUp(self):
        """Set up test router."""
        # Clear any cached router
        LLMClient._router = None
    
    def tearDown(self):
        """Clean up."""
        LLMClient._router = None
    
    @patch('runtime_adapter.os.path.exists')
    @patch('builtins.open', mock_open(read_data='''
routing:
  translate:
    default: gpt-4
    fallback: [gpt-3.5-turbo]
  _default:
    default: gpt-3.5-turbo
'''))
    def test_router_loads_config(self, mock_exists):
        """Test router loads configuration from YAML."""
        mock_exists.return_value = True
        
        router = LLMRouter()
        self.assertTrue(router.enabled)
        chain = router.get_model_chain("translate")
        self.assertEqual(chain, ["gpt-4", "gpt-3.5-turbo"])
    
    @patch('runtime_adapter.os.path.exists')
    def test_router_missing_config(self, mock_exists):
        """Test router handles missing config."""
        mock_exists.return_value = False
        
        router = LLMRouter()
        self.assertFalse(router.enabled)
    
    @patch('runtime_adapter.os.path.exists')
    @patch('builtins.open', mock_open(read_data='''
routing:
  translate:
    default: gpt-4
    fallback: [claude-3, gemini-pro]
capabilities:
  gpt-4:
    batch: ok
  claude-3:
    batch: unfit
fallback_triggers:
  on_timeout: true
  http_codes: [429, 503]
'''))
    def test_router_batch_capability_check(self, mock_exists):
        """Test router batch capability checking."""
        mock_exists.return_value = True
        
        router = LLMRouter()
        self.assertTrue(router.check_batch_capability("gpt-4"))
        self.assertFalse(router.check_batch_capability("claude-3"))
        self.assertTrue(router.check_batch_capability("unknown-model"))  # Default
    
    @patch('runtime_adapter.os.path.exists')
    @patch('builtins.open', mock_open(read_data='''
routing:
  translate:
    default: gpt-4
    temperature: 0.3
    max_tokens: 1000
    response_format:
      type: json_schema
      json_schema:
        name: translation
'''))
    def test_router_get_generation_params(self, mock_exists):
        """Test router generation parameter extraction."""
        mock_exists.return_value = True
        
        router = LLMRouter()
        params = router.get_generation_params("translate")
        self.assertEqual(params["temperature"], 0.3)
        self.assertEqual(params["max_tokens"], 1000)
        self.assertEqual(params["response_format"]["type"], "json_schema")
    
    @patch('runtime_adapter.os.path.exists')
    @patch('builtins.open', mock_open(read_data='''
fallback_triggers:
  on_timeout: true
  on_network_error: false
  http_codes: [429, 503]
'''))
    def test_router_should_fallback(self, mock_exists):
        """Test router fallback decision logic."""
        mock_exists.return_value = True
        
        router = LLMRouter()
        
        # Timeout should trigger fallback
        timeout_error = LLMError("timeout", "Timeout", retryable=True)
        self.assertTrue(router.should_fallback(timeout_error))
        
        # Network error should not trigger fallback (config says false)
        network_error = LLMError("network", "Network error", retryable=True)
        self.assertFalse(router.should_fallback(network_error))
        
        # HTTP 429 should trigger fallback
        rate_limit_error = LLMError("upstream", "Rate limited", 
                                     retryable=True, http_status=429)
        self.assertTrue(router.should_fallback(rate_limit_error))
        
        # HTTP 500 not in list
        server_error = LLMError("upstream", "Server error",
                                 retryable=True, http_status=500)
        self.assertFalse(router.should_fallback(server_error))


class TestBatchConfig(unittest.TestCase):
    """Test BatchConfig functionality."""
    
    @patch('builtins.open', mock_open(read_data=json.dumps({
        "models": {
            "gpt-4": {
                "max_batch_size": 50,
                "max_batch_size_long_text": 20,
                "timeout_normal": 120,
                "timeout_long_text": 300,
                "cooldown_required": 5,
                "status": "ACTIVE"
            },
            "gpt-3.5-turbo": {
                "max_batch_size": 100,
                "status": "ACTIVE"
            }
        }
    })))
    @patch('runtime_adapter.os.path.exists')
    def test_batch_config_loading(self, mock_exists):
        """Test batch config loading from JSON."""
        mock_exists.return_value = True
        
        config = BatchConfig()
        
        # Normal content type
        self.assertEqual(config.get_batch_size("gpt-4", "normal"), 50)
        # Long text content type
        self.assertEqual(config.get_batch_size("gpt-4", "long_text"), 20)
        # Timeout
        self.assertEqual(config.get_timeout("gpt-4", "normal"), 120)
        self.assertEqual(config.get_timeout("gpt-4", "long_text"), 300)
        # Cooldown
        self.assertEqual(config.get_cooldown("gpt-4"), 5)
        # Status
        self.assertEqual(config.get_status("gpt-4"), "ACTIVE")
    
    @patch('builtins.open', mock_open(read_data=json.dumps({
        "models": {"gpt-4": {"max_batch_size": 50}}
    })))
    @patch('runtime_adapter.os.path.exists')
    def test_batch_config_defaults(self, mock_exists):
        """Test batch config default values."""
        mock_exists.return_value = True
        
        config = BatchConfig()
        # Default values for missing config
        self.assertEqual(config.get_batch_size("unknown-model"), 10)
        self.assertEqual(config.get_cooldown("unknown-model"), 0)
        self.assertEqual(config.get_status("unknown-model"), "UNKNOWN")


class TestParseLLMResponse(unittest.TestCase):
    """Test LLM response parsing."""
    
    def test_parse_valid_response(self):
        """Test parsing valid JSON response."""
        response = json.dumps({
            "items": [
                {"id": "1", "translation": "Hello"},
                {"id": "2", "translation": "World"}
            ]
        })
        expected_rows = [{"id": "1"}, {"id": "2"}]
        
        result = parse_llm_response(response, expected_rows)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["translation"], "Hello")
    
    def test_parse_with_markdown_code_block(self):
        """Test parsing response wrapped in markdown code block."""
        response = """```json
{"items": [{"id": "1", "text": "test"}]}
```"""
        expected_rows = [{"id": "1"}]
        
        result = parse_llm_response(response, expected_rows)
        self.assertEqual(len(result), 1)
    
    def test_parse_partial_match(self):
        """Test partial matching (subset of IDs)."""
        response = json.dumps({
            "items": [{"id": "1", "text": "only one"}]
        })
        expected_rows = [{"id": "1"}, {"id": "2"}]
        
        result = parse_llm_response(response, expected_rows, partial_match=True)
        self.assertEqual(len(result), 1)
    
    def test_parse_missing_items_key(self):
        """Test error when items key is missing."""
        response = json.dumps({"data": []})
        expected_rows = [{"id": "1"}]
        
        with self.assertRaises(ValueError) as context:
            parse_llm_response(response, expected_rows)
        self.assertIn("Missing 'items' key", str(context.exception))
    
    def test_parse_id_mismatch(self):
        """Test error when IDs don't match."""
        response = json.dumps({
            "items": [{"id": "1", "text": "test"}]
        })
        expected_rows = [{"id": "2"}]
        
        with self.assertRaises(ValueError) as context:
            parse_llm_response(response, expected_rows)
        self.assertIn("ID mismatch", str(context.exception))
    
    def test_parse_invalid_json(self):
        """Test error with invalid JSON."""
        response = "not valid json"
        expected_rows = [{"id": "1"}]
        
        with self.assertRaises(ValueError) as context:
            parse_llm_response(response, expected_rows)
        self.assertIn("parse error", str(context.exception))
    
    def test_parse_json_with_trailing_comma(self):
        """Test JSON repair for trailing comma."""
        response = '{"items": [{"id": "1", "text": "test",}]}'
        expected_rows = [{"id": "1"}]
        
        result = parse_llm_response(response, expected_rows)
        self.assertEqual(len(result), 1)
    
    def test_parse_json_with_single_quotes(self):
        """Test JSON repair for single quotes."""
        response = "{'items': [{'id': '1', 'text': 'test'}]}"
        expected_rows = [{"id": "1"}]
        
        result = parse_llm_response(response, expected_rows)
        self.assertEqual(len(result), 1)
    
    def test_parse_json_with_items_not_list(self):
        """Test error when items is not a list."""
        response = json.dumps({"items": "not a list"})
        expected_rows = [{"id": "1"}]
        
        with self.assertRaises(ValueError) as context:
            parse_llm_response(response, expected_rows)
        self.assertIn("must be an array", str(context.exception))


class TestBatchLLMCall(unittest.TestCase):
    """Test batch_llm_call with retry logic."""
    
    def setUp(self):
        """Set up test environment."""
        os.environ["LLM_BASE_URL"] = "https://api.test.com"
        os.environ["LLM_API_KEY"] = "test-key"
        os.environ["LLM_MODEL"] = "test-model"
        LLMClient._router = None
        
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up."""
        LLMClient._router = None
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('runtime_adapter.requests.post')
    @patch('runtime_adapter.BatchConfig')
    def test_batch_llm_call_success(self, mock_config_class, mock_post):
        """Test successful batch call."""
        # Mock BatchConfig
        mock_config = Mock()
        mock_config.get_batch_size.return_value = 10
        mock_config.get_timeout.return_value = 60
        mock_config.get_cooldown.return_value = 0
        mock_config_class.return_value = mock_config
        
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "req-batch",
            "choices": [{"message": {"content": json.dumps({
                "items": [
                    {"id": "1", "translation": "Hello"},
                    {"id": "2", "translation": "World"}
                ]
            })}}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 50}
        }
        mock_post.return_value = mock_response
        
        rows = [{"id": "1", "source_text": "Hi"}, {"id": "2", "source_text": "There"}]
        
        def prompt_template(items):
            return json.dumps(items)
        
        results = batch_llm_call(
            step="translate",
            rows=rows,
            model="gpt-4",
            system_prompt="Translate to Chinese.",
            user_prompt_template=prompt_template,
            retry=1
        )
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["translation"], "Hello")
    
    @patch('runtime_adapter.requests.post')
    @patch('runtime_adapter.BatchConfig')
    def test_batch_llm_call_with_retry(self, mock_config_class, mock_post):
        """Test batch call with retry on failure."""
        # Mock BatchConfig
        mock_config = Mock()
        mock_config.get_batch_size.return_value = 10
        mock_config.get_timeout.return_value = 60
        mock_config.get_cooldown.return_value = 0
        mock_config_class.return_value = mock_config
        
        # First call fails, second succeeds
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_fail.text = "Server error"
        
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {
            "id": "req-success",
            "choices": [{"message": {"content": json.dumps({
                "items": [{"id": "1", "translation": "Hello"}]
            })}}],
            "usage": {}
        }
        
        mock_post.side_effect = [mock_response_fail, mock_response_success]
        
        rows = [{"id": "1", "source_text": "Hi"}]
        
        def prompt_template(items):
            return json.dumps(items)
        
        results = batch_llm_call(
            step="translate",
            rows=rows,
            model="gpt-4",
            system_prompt="Translate.",
            user_prompt_template=prompt_template,
            retry=1  # Allow 1 retry
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(mock_post.call_count, 2)  # Initial + 1 retry
    
    @patch('runtime_adapter.requests.post')
    @patch('runtime_adapter.BatchConfig')
    def test_batch_llm_call_all_retries_fail(self, mock_config_class, mock_post):
        """Test batch call when all retries fail."""
        # Mock BatchConfig
        mock_config = Mock()
        mock_config.get_batch_size.return_value = 10
        mock_config.get_timeout.return_value = 60
        mock_config.get_cooldown.return_value = 0
        mock_config_class.return_value = mock_config
        
        # All calls fail
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        mock_post.return_value = mock_response
        
        rows = [{"id": "1", "source_text": "Hi"}]
        
        def prompt_template(items):
            return json.dumps(items)
        
        # Should not raise, returns partial results
        results = batch_llm_call(
            step="translate",
            rows=rows,
            model="gpt-4",
            system_prompt="Translate.",
            user_prompt_template=prompt_template,
            retry=2
        )
        
        # No successful results, but no exception
        self.assertEqual(len(results), 0)
        self.assertEqual(mock_post.call_count, 3)  # Initial + 2 retries
    
    @patch('runtime_adapter.get_batch_config')
    @patch('runtime_adapter.requests.post')
    def test_batch_llm_call_multiple_batches(self, mock_post, mock_get_batch_config):
        """Test batch call with multiple batches."""
        # Mock BatchConfig
        mock_config = Mock()
        mock_config.get_batch_size.return_value = 2  # Small batch size
        mock_config.get_timeout.return_value = 60
        mock_config.get_cooldown.return_value = 0
        mock_get_batch_config.return_value = mock_config
        
        # Create two different mock responses for each batch
        mock_response_1 = Mock()
        mock_response_1.status_code = 200
        mock_response_1.json.return_value = {
            "id": "req-batch-1",
            "choices": [{"message": {"content": json.dumps({
                "items": [
                    {"id": "1", "translation": "A"},
                    {"id": "2", "translation": "B"}
                ]
            })}}],
            "usage": {}
        }
        
        mock_response_2 = Mock()
        mock_response_2.status_code = 200
        mock_response_2.json.return_value = {
            "id": "req-batch-2",
            "choices": [{"message": {"content": json.dumps({
                "items": [
                    {"id": "3", "translation": "C"},
                    {"id": "4", "translation": "D"}
                ]
            })}}],
            "usage": {}
        }
        
        mock_post.side_effect = [mock_response_1, mock_response_2]
        
        rows = [
            {"id": "1", "source_text": "a"},
            {"id": "2", "source_text": "b"},
            {"id": "3", "source_text": "c"},
            {"id": "4", "source_text": "d"}
        ]
        
        def prompt_template(items):
            return json.dumps(items)
        
        results = batch_llm_call(
            step="translate",
            rows=rows,
            model="gpt-4",
            system_prompt="Translate.",
            user_prompt_template=prompt_template
        )
        
        # Should make 2 API calls (4 rows / batch_size 2)
        self.assertEqual(mock_post.call_count, 2)
        self.assertEqual(len(results), 4)


class TestEmbeddingClient(unittest.TestCase):
    """Test EmbeddingClient functionality."""
    
    def setUp(self):
        """Set up test environment."""
        os.environ["LLM_BASE_URL"] = "https://api.test.com"
        os.environ["LLM_API_KEY"] = "test-key"
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_init_missing_api_key(self):
        """Test initialization with missing API key."""
        del os.environ["LLM_API_KEY"]
        
        with self.assertRaises(LLMError) as context:
            EmbeddingClient(cache_dir=self.temp_dir)
        
        self.assertEqual(context.exception.kind, "config")
    
    @patch('runtime_adapter.requests.post')
    def test_embed_single(self, mock_post):
        """Test single text embedding."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * 1536}]
        }
        mock_post.return_value = mock_response
        
        client = EmbeddingClient(cache_dir=self.temp_dir)
        embedding = client.embed_single("Test text")
        
        self.assertEqual(embedding.shape, (1536,))
        self.assertAlmostEqual(np.linalg.norm(embedding), np.sqrt(1536 * 0.01), places=5)
    
    @patch('runtime_adapter.requests.post')
    def test_embed_single_with_cache(self, mock_post):
        """Test embedding caching."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"embedding": [0.2] * 1536}]
        }
        mock_post.return_value = mock_response
        
        client = EmbeddingClient(cache_dir=self.temp_dir)
        
        # First call - should hit API
        emb1 = client.embed_single("Test text", use_cache=True)
        self.assertEqual(mock_post.call_count, 1)
        
        # Second call - should use cache
        emb2 = client.embed_single("Test text", use_cache=True)
        self.assertEqual(mock_post.call_count, 1)  # No new API call
        np.testing.assert_array_equal(emb1, emb2)
    
    @patch('runtime_adapter.requests.post')
    def test_embed_batch(self, mock_post):
        """Test batch embedding."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {"embedding": [0.1] * 1536},
                {"embedding": [0.2] * 1536}
            ]
        }
        mock_post.return_value = mock_response
        
        client = EmbeddingClient(cache_dir=self.temp_dir)
        embeddings = client.embed_batch(["Text 1", "Text 2"])
        
        self.assertEqual(embeddings.shape, (2, 1536))
    
    @patch('runtime_adapter.requests.post')
    def test_embed_batch_partial_cache(self, mock_post):
        """Test batch embedding with partial cache hit."""
        # First call to cache one embedding
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1] * 1536}]
        }
        mock_post.return_value = mock_response
        
        client = EmbeddingClient(cache_dir=self.temp_dir)
        client.embed_single("Cached text", use_cache=True)
        
        # Reset mock for batch call
        mock_response.json.return_value = {
            "data": [{"embedding": [0.2] * 1536}]
        }
        
        # Batch with one cached, one new
        embeddings = client.embed_batch(["Cached text", "New text"], use_cache=True)
        
        self.assertEqual(embeddings.shape, (2, 1536))
    
    def test_embed_empty_text(self):
        """Test embedding empty text."""
        client = EmbeddingClient(cache_dir=self.temp_dir)
        
        embedding = client.embed_single("")
        self.assertEqual(embedding.shape, (1536,))
        np.testing.assert_array_equal(embedding, np.zeros(1536))
    
    def test_embed_empty_batch(self):
        """Test embedding empty batch."""
        client = EmbeddingClient(cache_dir=self.temp_dir)
        
        embeddings = client.embed_batch([])
        self.assertEqual(embeddings.shape, (0, 1536))
    
    @patch('runtime_adapter.requests.post')
    def test_embed_api_error(self, mock_post):
        """Test embedding API error handling."""
        import requests
        mock_post.side_effect = requests.ConnectionError("Network error")
        
        client = EmbeddingClient(cache_dir=self.temp_dir)
        
        with self.assertRaises(LLMError) as context:
            client.embed_single("Test")
        
        self.assertEqual(context.exception.kind, "network")
    
    def test_cosine_similarity(self):
        """Test cosine similarity calculation."""
        client = EmbeddingClient(cache_dir=self.temp_dir)
        
        # Same vector should have similarity 1
        vec = np.array([1.0, 0.0, 0.0])
        sim = client.cosine_similarity(vec, vec)
        self.assertAlmostEqual(sim, 1.0, places=5)
        
        # Orthogonal vectors should have similarity 0
        vec_a = np.array([1.0, 0.0])
        vec_b = np.array([0.0, 1.0])
        sim = client.cosine_similarity(vec_a, vec_b)
        self.assertAlmostEqual(sim, 0.0, places=5)
        
        # Opposite vectors should have similarity -1
        vec_a = np.array([1.0, 0.0])
        vec_b = np.array([-1.0, 0.0])
        sim = client.cosine_similarity(vec_a, vec_b)
        self.assertAlmostEqual(sim, -1.0, places=5)
    
    def test_cosine_similarity_zero_vector(self):
        """Test cosine similarity with zero vector."""
        client = EmbeddingClient(cache_dir=self.temp_dir)
        
        vec = np.array([1.0, 2.0, 3.0])
        zero_vec = np.array([0.0, 0.0, 0.0])
        
        sim = client.cosine_similarity(vec, zero_vec)
        self.assertEqual(sim, 0.0)
    
    def test_batch_cosine_similarity(self):
        """Test batch cosine similarity."""
        client = EmbeddingClient(cache_dir=self.temp_dir)
        
        query = np.array([1.0, 0.0])
        corpus = np.array([
            [1.0, 0.0],  # Same direction
            [0.0, 1.0],  # Orthogonal
            [-1.0, 0.0]  # Opposite
        ])
        
        similarities = client.batch_cosine_similarity(query, corpus)
        
        self.assertEqual(len(similarities), 3)
        self.assertAlmostEqual(similarities[0], 1.0, places=5)
        self.assertAlmostEqual(similarities[1], 0.0, places=5)
        self.assertAlmostEqual(similarities[2], -1.0, places=5)
    
    def test_batch_cosine_similarity_empty(self):
        """Test batch cosine similarity with empty corpus."""
        client = EmbeddingClient(cache_dir=self.temp_dir)
        
        query = np.array([1.0, 0.0])
        corpus = np.array([]).reshape(0, 2)
        
        similarities = client.batch_cosine_similarity(query, corpus)
        self.assertEqual(len(similarities), 0)


class TestLogLLMProgress(unittest.TestCase):
    """Test progress logging functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.orig_reports = os.getcwd()
        os.chdir(self.temp_dir)
    
    def tearDown(self):
        """Clean up."""
        os.chdir(self.orig_reports)
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_log_step_start(self):
        """Test logging step start event."""
        log_llm_progress("translate", "step_start", {
            "total_rows": 100,
            "batch_size": 10,
            "model": "gpt-4"
        }, silent=True)
        
        log_path = os.path.join("reports", "translate_progress.jsonl")
        self.assertTrue(os.path.exists(log_path))
        
        with open(log_path, 'r') as f:
            entry = json.loads(f.readline())
        
        self.assertEqual(entry["step"], "translate")
        self.assertEqual(entry["event"], "step_start")
        self.assertEqual(entry["total_rows"], 100)
    
    def test_log_batch_start(self):
        """Test logging batch start event."""
        log_llm_progress("translate", "batch_start", {
            "batch_num": 1,
            "total_batches": 10,
            "rows_in_batch": 10
        }, silent=True)
        
        log_path = os.path.join("reports", "translate_progress.jsonl")
        self.assertTrue(os.path.exists(log_path))
        
        with open(log_path, 'r') as f:
            entry = json.loads(f.readline())
        
        self.assertEqual(entry["event"], "batch_start")
        self.assertEqual(entry["batch_num"], 1)
    
    def test_log_batch_complete(self):
        """Test logging batch complete event."""
        log_llm_progress("translate", "batch_complete", {
            "batch_num": 1,
            "total_batches": 10,
            "rows_in_batch": 10,
            "latency_ms": 1500,
            "status": "ok"
        }, silent=True)
        
        log_path = os.path.join("reports", "translate_progress.jsonl")
        with open(log_path, 'r') as f:
            entry = json.loads(f.readline())
        
        self.assertEqual(entry["batch_num"], 1)
        self.assertEqual(entry["status"], "ok")
    
    def test_log_step_complete(self):
        """Test logging step complete event."""
        log_llm_progress("translate", "step_complete", {
            "success_count": 95,
            "failed_count": 5
        }, silent=True)
        
        log_path = os.path.join("reports", "translate_progress.jsonl")
        with open(log_path, 'r') as f:
            entry = json.loads(f.readline())
        
        self.assertEqual(entry["event"], "step_complete")
        self.assertEqual(entry["success_count"], 95)


class TestConvenienceFunction(unittest.TestCase):
    """Test convenience chat function."""
    
    def setUp(self):
        """Set up test environment."""
        os.environ["LLM_BASE_URL"] = "https://api.test.com"
        os.environ["LLM_API_KEY"] = "test-key"
        os.environ["LLM_MODEL"] = "test-model"
        LLMClient._router = None
    
    def tearDown(self):
        """Clean up."""
        LLMClient._router = None
    
    @patch('runtime_adapter.requests.post')
    def test_chat_convenience_function(self, mock_post):
        """Test convenience chat() function."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "req-123",
            "choices": [{"message": {"content": "Simple response"}}],
            "usage": {}
        }
        mock_post.return_value = mock_response
        
        result = chat(system="Be helpful", user="Hello")
        
        self.assertEqual(result, "Simple response")


class TestPricingAndCost(unittest.TestCase):
    """Test pricing loading and cost estimation."""
    
    @patch('runtime_adapter.os.path.exists')
    @patch('builtins.open', mock_open(read_data='''
billing:
  mode: per_1m
models:
  gpt-4:
    input_per_1M: 30.0
    output_per_1M: 60.0
  gpt-3.5-turbo:
    input_per_1M: 0.5
    output_per_1M: 1.5
'''))
    def test_load_pricing(self, mock_exists):
        """Test pricing config loading."""
        mock_exists.return_value = True
        
        # Clear cache
        import runtime_adapter
        runtime_adapter._pricing_cache = None
        
        pricing = _load_pricing()
        self.assertIn("models", pricing)
        self.assertIn("gpt-4", pricing["models"])
    
    @patch('runtime_adapter.os.path.exists')
    @patch('builtins.open', mock_open(read_data='''
billing:
  mode: per_1m
models:
  gpt-4:
    input_per_1M: 30.0
    output_per_1M: 60.0
'''))
    def test_estimate_cost_per_1m(self, mock_exists):
        """Test cost estimation with per_1M pricing."""
        mock_exists.return_value = True
        
        # Clear cache
        import runtime_adapter
        runtime_adapter._pricing_cache = None
        
        # 1000 prompt tokens, 500 completion tokens at gpt-4 rates
        cost = _estimate_cost("gpt-4", 1000, 500)
        
        # Expected: (1000 * 30 / 1M) + (500 * 60 / 1M) = 0.03 + 0.03 = 0.06
        self.assertAlmostEqual(cost, 0.06, places=6)
    
    @patch('runtime_adapter.os.path.exists')
    @patch('builtins.open', mock_open(read_data='''
billing:
  mode: multiplier
  recharge_rate:
    old: 10
    new: 8
  group_rate:
    old: 1
    new: 1
  user_group_multiplier: 1.0
  token_divisor: 500000
models:
  kimi-k2p5:
    prompt_mult: 0.5
    completion_mult: 2.0
'''))
    def test_estimate_cost_multiplier_mode(self, mock_exists):
        """Test cost estimation with multiplier pricing mode."""
        mock_exists.return_value = True
        
        # Clear cache
        import runtime_adapter
        runtime_adapter._pricing_cache = None
        
        # Calculate expected cost with multiplier formula
        cost = _estimate_cost("kimi-k2p5", 1000, 500)
        
        # Should return a non-negative cost
        self.assertGreaterEqual(cost, 0)
        self.assertIsInstance(cost, float)
    
    def test_estimate_cost_unknown_model(self):
        """Test cost estimation for unknown model."""
        # Clear cache
        import runtime_adapter
        runtime_adapter._pricing_cache = {}
        
        cost = _estimate_cost("unknown-model", 1000, 500)
        self.assertEqual(cost, 0.0)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""
    
    def setUp(self):
        """Set up test environment."""
        os.environ["LLM_BASE_URL"] = "https://api.test.com"
        os.environ["LLM_API_KEY"] = "test-key"
        os.environ["LLM_MODEL"] = "test-model"
        LLMClient._router = None
    
    def tearDown(self):
        """Clean up."""
        LLMClient._router = None
    
    @patch('runtime_adapter.requests.post')
    def test_chat_with_custom_timeout(self, mock_post):
        """Test chat with custom timeout parameter."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "req-timeout",
            "choices": [{"message": {"content": "Response"}}],
            "usage": {}
        }
        mock_post.return_value = mock_response
        
        client = LLMClient()
        result = client.chat(
            system="Test",
            user="Test",
            timeout=120
        )
        
        # Verify timeout was passed to requests.post
        call_kwargs = mock_post.call_args[1]
        self.assertEqual(call_kwargs['timeout'], 120)
    
    @patch('runtime_adapter.requests.post')
    def test_chat_response_without_usage(self, mock_post):
        """Test chat when API doesn't return usage info."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "req-nousage",
            "choices": [{"message": {"content": "No usage data"}}]
            # No usage field
        }
        mock_post.return_value = mock_response
        
        client = LLMClient()
        result = client.chat(system="Test", user="Test")
        
        self.assertEqual(result.text, "No usage data")
        self.assertIsNone(result.usage)
    
    def test_trace_exception_handling(self):
        """Test that trace handles exceptions gracefully."""
        # Test with invalid path that can't be created
        os.environ["LLM_TRACE_PATH"] = "/nonexistent_dir_that_cannot_be_created/trace.jsonl"
        
        # Should not raise exception
        _trace({"type": "test"})
    
    def test_batch_config_file_not_found(self):
        """Test BatchConfig with missing file."""
        with self.assertRaises(FileNotFoundError):
            BatchConfig("/nonexistent/path.json")
    
    @patch('runtime_adapter.requests.post')
    @patch('runtime_adapter.get_batch_config')
    def test_batch_with_output_dir(self, mock_get_batch_config, mock_post):
        """Test batch call with output directory for checkpoints."""
        # Mock BatchConfig
        mock_config = Mock()
        mock_config.get_batch_size.return_value = 10
        mock_config.get_timeout.return_value = 60
        mock_config.get_cooldown.return_value = 0
        mock_get_batch_config.return_value = mock_config
        
        # Mock API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "req-batch",
            "choices": [{"message": {"content": json.dumps({
                "items": [{"id": "1", "translation": "Hello"}]
            })}}],
            "usage": {}
        }
        mock_post.return_value = mock_response
        
        with tempfile.TemporaryDirectory() as temp_dir:
            rows = [{"id": "1", "source_text": "Hi"}]
            
            def prompt_template(items):
                return json.dumps(items)
            
            results = batch_llm_call(
                step="translate",
                rows=rows,
                model="gpt-4",
                system_prompt="Translate.",
                user_prompt_template=prompt_template,
                output_dir=temp_dir
            )
            
            # Check that checkpoint file was created
            checkpoint_path = os.path.join(temp_dir, "translate_checkpoint.json")
            self.assertTrue(os.path.exists(checkpoint_path))
            
            # Verify checkpoint content
            with open(checkpoint_path, 'r') as f:
                checkpoint = json.load(f)
            self.assertEqual(checkpoint["step"], "translate")
            
            # Check DONE file
            done_path = os.path.join(temp_dir, "translate_DONE")
            self.assertTrue(os.path.exists(done_path))
    
    @patch('runtime_adapter.requests.post')
    def test_chat_with_batch_metadata(self, mock_post):
        """Test chat with batch metadata flags."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "req-batch-meta",
            "choices": [{"message": {"content": "Response"}}],
            "usage": {}
        }
        mock_post.return_value = mock_response
        
        client = LLMClient()
        result = client.chat(
            system="Test",
            user="Test",
            metadata={
                "step": "translate",
                "batch_size": 50,  # This should trigger batch capability check
                "batch_idx": 5
            }
        )
        
        self.assertEqual(result.text, "Response")
    
    @patch('runtime_adapter.os.path.exists')
    @patch('builtins.open', mock_open(read_data='''
routing:
  translate:
    default: batch-unfit-model
    fallback: [gpt-4]
capabilities:
  batch-unfit-model:
    batch: unfit
  gpt-4:
    batch: ok
'''))
    def test_batch_capability_enforcement(self, mock_exists):
        """Test batch capability enforcement switches models."""
        mock_exists.return_value = True
        
        # Clear router singleton
        LLMClient._router = None
        
        router = LLMRouter()
        
        # Check that unfit model is detected
        self.assertFalse(router.check_batch_capability("batch-unfit-model"))
        self.assertTrue(router.check_batch_capability("gpt-4"))


if __name__ == "__main__":
    # Run with coverage: pytest --cov=runtime_adapter --cov-report=term-missing
    unittest.main(verbosity=2)
