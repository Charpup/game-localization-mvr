# Mock LLM Guide

Comprehensive guide for using the LLM mocking framework in offline tests.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Core Concepts](#core-concepts)
3. [MockLLM Class](#mockllm-class)
4. [Response Fixtures](#response-fixtures)
5. [Failure Simulation](#failure-simulation)
6. [Batch Call Mocking](#batch-call-mocking)
7. [Specialized Mocks](#specialized-mocks)
8. [Integration Examples](#integration-examples)
9. [Best Practices](#best-practices)
10. [Troubleshooting](#troubleshooting)

---

## Quick Start

### Basic Usage

```python
from tests.mock_llm import MockLLM

def test_simple_translation():
    with MockLLM() as mock:
        # Configure mock response
        mock.add_response("Hello", "Bonjour")
        
        # Use the code under test
        from runtime_adapter import LLMClient
        client = LLMClient()
        result = client.chat(system="Translate:", user="Hello")
        
        # Assert
        assert result.text == "Bonjour"
```

### Using Decorators

```python
from tests.mock_llm import mock_llm_fixture

@mock_llm_fixture(responses={"Hello": "Bonjour"})
def test_with_decorator():
    client = LLMClient()
    result = client.chat(system="", user="Hello")
    assert result.text == "Bonjour"
```

---

## Core Concepts

### Architecture

The mocking framework intercepts calls at two levels:

1. **LLMClient.chat()** - Single API calls
2. **batch_llm_call()** - Batch processing calls

```
Your Test Code
      ↓
[MockLLM Patches]
      ↓
Mock Response (no network)
```

### Call Matching

Responses are matched in order of registration:

1. **Exact keyword match** - First match wins
2. **Pattern match** - Regex patterns
3. **Default response** - Fallback
4. **Auto-generation** - Based on context

---

## MockLLM Class

### Initialization

```python
from tests.mock_llm import MockLLM

# Basic mock
mock = MockLLM()

# With specific model name
mock = MockLLM(model="claude-3-mock")
```

### Context Manager (Recommended)

```python
with MockLLM() as mock:
    # Patches are active here
    mock.add_response("input", "output")
    result = client.chat(system="", user="input")
# Patches are automatically removed
```

### Manual Start/Stop

```python
mock = MockLLM()
mock.start()
try:
    # Your test code
    pass
finally:
    mock.stop()  # Important!
```

---

## Response Fixtures

### Adding Simple Responses

```python
mock.add_response(
    keyword="Hello",           # Trigger keyword
    response_text="Bonjour",   # Response
    latency_ms=150,            # Optional: simulated latency
    model="gpt-4"              # Optional: model name
)
```

### Pattern-Based Responses

```python
import re

# Match any translation request
mock.add_pattern(
    pattern=r"translate.*Chinese",
    response_text="中文翻译结果"
)

# Match with capture groups
mock.add_pattern(
    pattern=r"translate:\s*(.+)",
    response_text=lambda m: f"RU_{m.group(1)}"
)
```

### Default Response

```python
# Used when no pattern matches
mock.set_default_response(
    response_text="I don't understand",
    latency_ms=50
)
```

### Complete Example

```python
def test_complex_responses():
    with MockLLM() as mock:
        # Specific translations
        mock.add_response("Hello", "Привет")
        mock.add_response("Goodbye", "До свидания")
        
        # Pattern for numbers
        mock.add_pattern(r"number:\s*(\d+)", "Число: N")
        
        # Default fallback
        mock.set_default_response("Неизвестно")
        
        client = LLMClient()
        
        assert client.chat("", "Hello").text == "Привет"
        assert client.chat("", "number: 42").text == "Число: N"
        assert client.chat("", "xyz").text == "Неизвестно"
```

---

## Failure Simulation

### Predefined Scenarios

```python
from tests.mock_llm import FAILURE_SCENARIOS

# Available scenarios:
# - rate_limit    (HTTP 429, retryable)
# - timeout       (Request timeout, retryable)
# - network_error (Connection error, retryable)
# - server_error  (HTTP 500, retryable)
# - bad_request   (HTTP 400, not retryable)
# - unauthorized  (HTTP 401, not retryable)
# - parse_error   (JSON parse error, retryable)
# - config_error  (Missing config, not retryable)

mock.add_failure("rate_limit")
```

### Conditional Failures

```python
# Only fail on specific input
mock.add_failure("rate_limit", on_keyword="overload")

# Multiple failures
mock.add_failure("timeout", on_keyword="slow")
mock.add_failure("server_error", on_keyword="error")
```

### Testing Retry Logic

```python
def test_retry_on_rate_limit():
    with MockLLM() as mock:
        mock.add_failure("rate_limit")
        mock.add_response("Hello", "Success")  # Second call succeeds
        
        client = LLMClient()
        
        # First call should raise
        with pytest.raises(LLMError) as exc:
            client.chat("", "Hello")
        assert exc.value.kind == "upstream"
        
        # Second call should succeed
        result = client.chat("", "Hello")
        assert result.text == "Success"
```

### Custom Failures

```python
from tests.mock_llm import MockFailure

custom_failure = MockFailure(
    kind="upstream",
    message="Custom error message",
    retryable=True,
    http_status=503
)

mock.add_failure(custom_failure, on_keyword="custom")
```

---

## Batch Call Mocking

### Basic Batch Mocking

```python
from tests.mock_llm import MockLLM

def test_batch_translation():
    with MockLLM() as mock:
        # Configure batch handler
        def batch_handler(step, rows, **kwargs):
            return [
                {"id": row["id"], "translation": f"RU_{row['id']}"}
                for row in rows
            ]
        
        mock.set_batch_handler(batch_handler)
        
        # Use batch_llm_call
        from runtime_adapter import batch_llm_call
        
        rows = [
            {"id": "1", "source_text": "Hello"},
            {"id": "2", "source_text": "World"}
        ]
        
        results = batch_llm_call(
            step="translate",
            rows=rows,
            model="gpt-4",
            system_prompt="Translate to Russian",
            user_prompt_template=lambda items: json.dumps({"items": items})
        )
        
        assert len(results) == 2
        assert results[0]["translation"] == "RU_1"
```

### Batch Response Function

```python
# Simpler API for batch responses
mock.set_batch_response(
    response_fn=lambda items: [
        {"id": item["id"], "translation": f"RU_{item['id']}"}
        for item in items
    ]
)
```

### Simulating Batch Failures

```python
def test_batch_with_failures():
    with MockLLM() as mock:
        call_count = [0]
        
        def batch_handler(step, rows, **kwargs):
            call_count[0] += 1
            
            # Fail first batch
            if call_count[0] == 1:
                raise LLMError("upstream", "Rate limit", retryable=True)
            
            # Succeed on retry
            return [{"id": row["id"], "translation": "RU"} for row in rows]
        
        mock.set_batch_handler(batch_handler)
        
        # Test with retry
        results = batch_llm_call(
            step="translate",
            rows=rows,
            model="gpt-4",
            system_prompt="...",
            user_prompt_template=lambda x: "...",
            retry=2  # Should retry on failure
        )
```

---

## Specialized Mocks

### TranslationMock

```python
from tests.mock_llm import TranslationMock

def test_translation_with_tokens():
    with TranslationMock() as mock:
        # Add translation that preserves tokens
        mock.add_translation_response(
            source_pattern="attack",
            translation="атака ⟦PH_001⟧"
        )
        
        # Configure batch handler
        mock.set_batch_translation_handler(
            translate_fn=lambda src: f"RU_{src}"
        )
        
        # Test translation
        from scripts.translate_llm import translate_text
        result = translate_text(
            source="attack with ⟦PH_001⟧",
            mock_client=mock
        )
        
        # Tokens should be preserved
        assert "⟦PH_001⟧" in result
```

### QAMock

```python
from tests.mock_llm import QAMock

def test_qa_with_issues():
    with QAMock(issue_rate=0.1) as mock:
        # Add specific issues for specific rows
        mock.add_issue(
            row_id="row-5",
            issue_type="token_mismatch",
            message="Missing placeholder",
            severity="critical"
        )
        
        # Set up QA handler
        mock.set_batch_qa_handler()
        
        # Run QA
        from scripts.qa_hard import run_qa
        results = run_qa(rows, mock_client=mock)
        
        # Check issues found
        assert len(results["issues"]) > 0
```

---

## Integration Examples

### Testing translate_llm.py

```python
import pytest
from tests.mock_llm import MockLLM, create_batch_translation_mock

def test_translate_pipeline():
    """Test the full translation pipeline with mocks."""
    with MockLLM() as mock:
        # Configure glossary-aware translation
        def batch_handler(step, rows, **kwargs):
            system_prompt = kwargs.get('system_prompt', '')
            
            # Check if glossary is in system prompt
            has_glossary = "术语表" in system_prompt or "glossary" in system_prompt.lower()
            
            results = []
            for row in rows:
                source = row.get('source_text', '')
                
                # Simulate glossary application
                if "血量" in source and has_glossary:
                    translation = "здоровье (HP)"
                else:
                    translation = f"RU_{source[:20]}"
                
                results.append({
                    "id": row["id"],
                    "translation": translation,
                    "status": "success"
                })
            
            return results
        
        mock.set_batch_handler(batch_handler)
        
        # Run actual translation
        from scripts.translate_llm import main
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv') as f:
            f.write("id,source_text\n")
            f.write("1,血量低于50\n")
            f.flush()
            
            # Mock sys.argv
            with patch.object(sys, 'argv', [
                'translate_llm.py',
                '--input', f.name,
                '--output', '/tmp/output.csv',
                '--glossary', 'data/glossary.yaml'
            ]):
                main()
        
        # Verify call history
        assert mock.get_call_count() > 0
```

### Testing qa_hard.py

```python
def test_qa_hard_validation():
    """Test QA with various issue types."""
    with MockLLM() as mock:
        def qa_handler(step, rows, **kwargs):
            results = []
            for row in rows:
                issues = []
                translation = row.get('translation', '')
                
                # Simulate token mismatch detection
                if "⟦PH_" in row.get('source_text', '') and "⟦PH_" not in translation:
                    issues.append({
                        "type": "token_mismatch",
                        "message": "Placeholder missing in translation",
                        "severity": "critical"
                    })
                
                # Simulate CJK detection
                if any('\u4e00' <= c <= '\u9fff' for c in translation):
                    issues.append({
                        "type": "cjk_remaining",
                        "message": "Chinese characters remain",
                        "severity": "major"
                    })
                
                results.append({
                    "id": row["id"],
                    "issues": issues,
                    "status": "issues_found" if issues else "passed"
                })
            
            return results
        
        mock.set_batch_handler(qa_handler)
        
        # Run QA
        from scripts.qa_hard import validate_csv
        issues = validate_csv('/tmp/translated.csv', mock=mock)
        
        assert len(issues) > 0
```

### Testing runtime_adapter.py

```python
def test_llm_router_fallback():
    """Test router fallback with mocked failures."""
    with MockLLM() as mock:
        call_count = [0]
        
        def chat_with_fallback(self, system, user, **kwargs):
            call_count[0] += 1
            
            metadata = kwargs.get('metadata', {})
            model = metadata.get('model_override', 'default')
            
            # First model fails
            if model == 'gpt-4' or (model == 'default' and call_count[0] == 1):
                raise LLMError(
                    kind="upstream",
                    message="GPT-4 overloaded",
                    retryable=True,
                    http_status=503
                )
            
            # Fallback model succeeds
            return MockResponse(text="Fallback response", model="gpt-3.5-mock")
        
        # Patch the chat method
        mock._mock_chat = chat_with_fallback
        
        client = LLMClient()
        
        # Should fail with primary model
        with pytest.raises(LLMError):
            client.chat("", "Hello", metadata={"model_override": "gpt-4"})
        
        # Should succeed with fallback
        result = client.chat("", "Hello", metadata={"model_override": "gpt-3.5"})
        assert "Fallback" in result.text
```

---

## Best Practices

### 1. Use Context Managers

```python
# ✅ Good - automatic cleanup
with MockLLM() as mock:
    pass

# ❌ Bad - manual cleanup required
mock = MockLLM()
mock.start()
# ... might forget mock.stop()
```

### 2. Assert Call Counts

```python
def test_api_usage():
    with MockLLM() as mock:
        # ... run code ...
        
        # Verify expected number of calls
        mock.assert_call_count(3)
        
        # Or check minimum
        assert mock.get_call_count() >= 1
```

### 3. Clear State Between Tests

```python
@pytest.fixture
def fresh_mock():
    with MockLLM() as mock:
        yield mock
        # Automatically cleared on exit

def test_one(fresh_mock):
    fresh_mock.add_response("a", "b")
    # ...

def test_two(fresh_mock):
    # Fresh state - no responses from test_one
    pass
```

### 4. Test Error Paths

```python
def test_error_handling():
    with MockLLM() as mock:
        # Test each error type
        for scenario in ["timeout", "rate_limit", "parse_error"]:
            mock.clear()
            mock.add_failure(scenario)
            
            with pytest.raises(LLMError) as exc:
                client.chat("", "test")
            
            assert exc.value.kind in ["timeout", "upstream", "parse"]
```

### 5. Use Descriptive Keywords

```python
# ✅ Good - specific and clear
mock.add_response("translate:Hello", "Bonjour")
mock.add_response("glossary_term:血量", "здоровье")

# ❌ Bad - too generic, might match unexpectedly
mock.add_response("H", "B")
```

### 6. Validate Token Preservation

```python
def test_token_preservation():
    with TranslationMock() as mock:
        source = "Attack with ⟦PH_001⟧ weapon"
        expected = "Атака ⟦PH_001⟧ оружием"
        
        mock.add_translation_response(source, expected)
        
        result = translate(source)
        
        # Verify tokens preserved
        import re
        source_tokens = set(re.findall(r"⟦PH_\d+⟧", source))
        result_tokens = set(re.findall(r"⟦PH_\d+⟧", result.text))
        assert source_tokens == result_tokens
```

---

## Troubleshooting

### Issue: Mock Not Intercepting Calls

```python
# Check import order - runtime_adapter must be imported AFTER mock setup
# ❌ Wrong
from runtime_adapter import LLMClient  # Imported before mock
with MockLLM() as mock:
    client = LLMClient()  # Already imported, not patched

# ✅ Correct
with MockLLM() as mock:
    from runtime_adapter import LLMClient  # Imported within mock context
    client = LLMClient()
```

### Issue: Responses Not Matching

```python
# Add debug output
with MockLLM() as mock:
    mock.add_response("Hello", "Bonjour")
    
    client = LLMClient()
    result = client.chat("Translate:", "Hello world")  # "Hello world" not "Hello"
    
    # Check what was actually called
    print(mock.call_history)
    # [{'system': 'Translate:', 'user': 'Hello world', ...}]
    
    # Fix: use pattern matching
    mock.add_pattern(r"Hello", "Bonjour")
```

### Issue: Batch Handler Not Called

```python
# Ensure batch_llm_call is imported from the patched module
# ❌ Wrong
from scripts.my_module import batch_llm_call  # Different import path

# ✅ Correct
with MockLLM() as mock:
    from runtime_adapter import batch_llm_call  # Same path as patch
```

### Issue: State Leaking Between Tests

```python
# Always clear or use fresh mocks
@pytest.fixture(autouse=True)
def reset_mocks():
    # Clean up any lingering patches
    yield
    # Reset state after test

# Or use function-scoped fixtures
@pytest.fixture
def mock_llm():
    with MockLLM() as mock:
        yield mock
```

---

## API Reference

### MockLLM Methods

| Method | Description |
|--------|-------------|
| `add_response(keyword, text, **kwargs)` | Add keyword-triggered response |
| `add_pattern(regex, text, **kwargs)` | Add pattern-triggered response |
| `set_default_response(text, **kwargs)` | Set fallback response |
| `add_failure(scenario, on_keyword=None)` | Add failure scenario |
| `set_batch_handler(fn)` | Set batch processing handler |
| `set_batch_response(fn)` | Set batch response generator |
| `clear()` | Clear all configuration |
| `get_call_count()` | Get number of calls made |
| `assert_called()` | Assert at least one call |
| `assert_not_called()` | Assert no calls |
| `assert_call_count(n)` | Assert exact call count |

### Failure Scenarios

| Scenario | Kind | Retryable | HTTP Status |
|----------|------|-----------|-------------|
| rate_limit | upstream | ✅ | 429 |
| timeout | timeout | ✅ | None |
| network_error | network | ✅ | None |
| server_error | upstream | ✅ | 500 |
| bad_request | http | ❌ | 400 |
| unauthorized | http | ❌ | 401 |
| parse_error | parse | ✅ | None |
| config_error | config | ❌ | None |

---

## Migration Guide

### From Manual Patching

```python
# Before
@patch('runtime_adapter.requests.post')
def test_old(mock_post):
    mock_post.return_value.json.return_value = {
        "choices": [{"message": {"content": "Hi"}}]
    }
    # ...

# After
with MockLLM() as mock:
    mock.add_response("Hello", "Hi")
    # ...
```

### From VCR.py

```python
# VCR required network recording
@vcr.use_cassette('cassettes/test.yaml')
def test_with_vcr():
    pass

# MockLLM works offline
with MockLLM() as mock:
    mock.add_response("input", "output")
    pass
```

---

## Contributing

To add new failure scenarios or response types:

1. Add to `FAILURE_SCENARIOS` in `mock_llm.py`
2. Add specialized mock class if needed
3. Update this documentation
4. Add tests in `test_mock_llm.py`

---

*Version: 1.0.0*  
*Last Updated: 2026-02-14*