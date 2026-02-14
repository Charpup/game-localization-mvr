# LLM Mock Framework Documentation

A comprehensive mocking framework for testing translation and LLM-dependent components without making real API calls.

## Overview

The LLM Mock Framework provides a drop-in replacement for `LLMClient` that allows you to:

- **Return predefined responses** based on input patterns
- **Sequence responses** for multi-call test scenarios
- **Simulate latency** for realistic timing testing
- **Inject errors** for resilience testing
- **Record and assert** on call history

## Quick Start

```python
from llm_mock_framework import LLMMockClient, MockResponses

# Create mock client
mock = LLMMockClient()

# Add a simple translation pattern
mock.add_simple_translation("战士", "Воин")

# Use like the real client
result = mock.chat(system="Translate", user="战士")
assert "Воин" in result.text
```

## Core Components

### LLMMockClient

The main mock client that mimics the `LLMClient` interface.

```python
mock = LLMMockClient(
    simulate_latency=False,  # Enable for timing tests
    latency_jitter=0.1       # 10% random variation
)
```

#### Methods

| Method | Description |
|--------|-------------|
| `chat(system, user, ...)` | Mock chat completion |
| `batch_chat(rows, ...)` | Mock batch processing |
| `add_response_pattern(...)` | Add pattern-based response |
| `add_simple_translation(zh, ru)` | Quick translation pattern |
| `add_sequence(responses)` | Set up response sequence |
| `add_error_response(...)` | Inject errors |
| `reset()` | Clear all patterns and history |

### Response Patterns

Match requests and return predefined responses:

```python
# Match by string containment
mock.add_response_pattern(
    contains="战士",
    items=[{"id": "1", "target_ru": "Воин"}]
)

# Match by regex
mock.add_response_pattern(
    regex=r"id.*:\s*\"(\d+)\"",
    items=[{"id": "1", "target_ru": "Воин"}]
)

# Match by custom predicate
def is_battle_context(system, user):
    return "战斗" in system

mock.add_response_pattern(
    predicate=is_battle_context,
    items=[{"id": "1", "target_ru": "Битва"}]
)
```

### Response Sequences

For tests requiring different responses on sequential calls:

```python
mock.add_sequence([
    MockResponses.russian_warrior("1"),
    MockResponses.russian_mage("2"),
    MockResponses.error_rate_limit(),  # Third call fails
], cycle=False)

# Call 1: Returns warrior
# Call 2: Returns mage
# Call 3: Raises rate limit error
```

### Error Injection

Simulate various error conditions:

```python
from llm_mock_framework import ErrorKind

# Immediate error
mock.add_error_response(
    ErrorKind.TIMEOUT,
    "Connection timeout"
)

# Error after N successful calls
mock.add_error_response(
    ErrorKind.RATE_LIMIT,
    "Rate limit exceeded",
    after_calls=3
)
```

**Error Types:**

| ErrorKind | HTTP Status | Retryable |
|-----------|-------------|-----------|
| `CONFIG` | - | No |
| `TIMEOUT` | - | Yes |
| `NETWORK` | - | Yes |
| `RATE_LIMIT` | 429 | Yes |
| `UPSTREAM` | 5xx | Yes |
| `HTTP` | 4xx | No |

### Pre-built Fixtures

Use `MockResponses` for common translation scenarios:

```python
# Russian translations
MockResponses.russian_warrior("1")           # "Воин"
MockResponses.russian_mage("1")              # "Маг"
MockResponses.russian_attack("1")            # "Атака"
MockResponses.russian_long_text("1")         # Long paragraph

# With placeholders
MockResponses.russian_with_placeholders("1", ph_count=3)
MockResponses.russian_with_tags("1", tag_count=2)

# English translations
MockResponses.english_warrior("1")           # "Warrior"
MockResponses.english_mage("1")              # "Mage"

# Error responses
MockResponses.error_rate_limit()
MockResponses.error_timeout()
MockResponses.error_invalid_json()
```

### Fixture Collections

Use `MockFixtures` for complete test scenarios:

```python
# Standard glossary terms
mock.add_sequence(MockFixtures.glossary_batch())
# Returns: warrior, mage, attack, spell

# Mixed with errors (for resilience testing)
mock.add_sequence(MockFixtures.mixed_batch_with_errors())

# Validation failures (missing placeholders, etc.)
mock.add_sequence(MockFixtures.validation_failures())

# Long text content
mock.add_sequence(MockFixtures.long_text_batch())
```

## Integration with Tests

### Basic Unit Test

```python
def test_translation(mock_llm_client):
    mock = mock_llm_client
    mock.add_simple_translation("战士", "Воин")
    
    result = mock.chat(system="Translate", user="战士")
    assert "Воин" in result.text
```

### Patching batch_llm_call

```python
from llm_mock_framework import patch_batch_llm_call

def test_with_batch_patch():
    mock = LLMMockClient()
    mock.add_response_pattern(
        contains="source_text",
        items=[{"id": "1", "target_ru": "Воин"}]
    )
    
    with patch_batch_llm_call(mock):
        from runtime_adapter import batch_llm_call
        
        results = batch_llm_call(
            step="translate",
            rows=[{"id": "1", "source_text": "战士"}],
            model="test",
            system_prompt="Translate",
            user_prompt_template=lambda items: json.dumps(items)
        )
        
        assert results[0]["target_ru"] == "Воин"
```

### Patching LLMClient

```python
from llm_mock_framework import patch_llm_client

def test_with_client_patch():
    mock = LLMMockClient()
    mock.add_simple_translation("战士", "Воин")
    
    with patch_llm_client(mock):
        from runtime_adapter import LLMClient
        
        client = LLMClient()  # Returns mock
        result = client.chat(system="Test", user="战士")
        
        assert "Воин" in result.text
```

## Call Recording and Assertions

The mock client records all calls for verification:

```python
mock = LLMMockClient()
mock.add_simple_translation("战士", "Воин")

# Make calls
mock.chat(system="System A", user="战士")
mock.chat(system="System B", user="法师")

# Assert call count
mock.assert_call_count(2)

# Assert call content
mock.assert_call_contains("System A")
mock.assert_call_contains("法师")

# Access full history
history = mock.get_call_history()
for call in history:
    print(f"Request {call['request_id']}: {call['user']}")
```

## Pytest Fixtures

Add to your `conftest.py`:

```python
from llm_mock_framework import (
    mock_llm_client,
    mock_llm_with_latency,
    mock_responses,
    mock_fixtures
)

# Fixtures are automatically available
```

| Fixture | Description |
|---------|-------------|
| `mock_llm_client` | Fresh mock client per test |
| `mock_llm_with_latency` | Mock with latency simulation |
| `mock_responses` | Access to MockResponses factory |
| `mock_fixtures` | Access to MockFixtures collections |

## Advanced Usage

### Dynamic System Prompts

```python
def dynamic_prompt(rows):
    return f"Translate {len(rows)} items with glossary"

results = mock.batch_chat(
    rows=[{"id": "1", "source_text": "战士"}],
    system_prompt=dynamic_prompt,  # Callable
    user_prompt_template=lambda items: json.dumps(items)
)
```

### Priority Matching

```python
# Lower priority
mock.add_response_pattern(
    contains="战士",
    items=[{"id": "1", "target_ru": "General"}],
    priority=1
)

# Higher priority (matches first)
mock.add_response_pattern(
    contains="勇敢的战士",
    items=[{"id": "1", "target_ru": "Brave"}],
    priority=10
)
```

### Latency Simulation

```python
mock = LLMMockClient(simulate_latency=True, latency_jitter=0.1)

# This call will take ~100ms ± 10%
mock.add_response_pattern(
    contains="slow",
    items=[{"id": "1", "target_ru": "Slow"}],
    latency_ms=100
)
```

## Examples

See `test_llm_mock_example.py` for comprehensive examples:

- Basic mocking patterns
- Response sequences
- Error injection
- Batch call handling
- Integration with patching
- Latency simulation

Run examples:

```bash
pytest tests/test_llm_mock_example.py -v
```

## Best Practices

1. **Reset between tests**: Use the `mock_llm_client` fixture or call `reset()`
2. **Use specific patterns**: More specific patterns prevent accidental matches
3. **Assert on calls**: Verify the right requests were made
4. **Test error paths**: Use error injection to test resilience
5. **Simulate latency**: Enable for timing-sensitive tests

## Migration from Manual Mocking

### Before (Manual)

```python
@patch('translate_llm.batch_llm_call')
def test_main(mock_batch_call):
    mock_batch_call.return_value = [
        {"id": "1", "target_ru": "Воин"}
    ]
    # ...
```

### After (Framework)

```python
from llm_mock_framework import LLMMockClient, patch_batch_llm_call

def test_main():
    mock = LLMMockClient()
    mock.add_simple_translation("战士", "Воин")
    
    with patch_batch_llm_call(mock):
        # More realistic, tracks calls, supports sequences
        # ...
```

## API Reference

### LLMMockClient

```python
class LLMMockClient:
    def __init__(self, simulate_latency=False, latency_jitter=0.1)
    def add_response_pattern(self, contains=None, regex=None, predicate=None, ...)
    def add_simple_translation(self, chinese: str, russian: str, id_val="1")
    def add_sequence(self, responses: List[MockResponse], cycle=False)
    def add_error_response(self, error_kind, message, http_status=None, after_calls=0)
    def set_default_response(self, response: MockResponse)
    def chat(self, system, user, ...) -> LLMResult
    def batch_chat(self, rows, system_prompt, user_prompt_template) -> List[Dict]
    def get_call_history(self) -> List[Dict]
    def assert_call_count(self, expected: int) -> bool
    def assert_call_contains(self, substring: str, call_index=-1) -> bool
    def reset(self)
```

### MockResponse

```python
@dataclass
class MockResponse:
    text: Optional[str] = None
    items: Optional[List[Dict]] = None
    latency_ms: int = 100
    error: Optional[ErrorKind] = None
    error_message: str = ""
    http_status: Optional[int] = None
    model: str = "mock-model"
```

### ErrorKind

```python
class ErrorKind(Enum):
    CONFIG = "config"
    TIMEOUT = "timeout"
    NETWORK = "network"
    UPSTREAM = "upstream"
    HTTP = "http"
    PARSE = "parse"
    RATE_LIMIT = "rate_limit"
    INVALID_JSON = "invalid_json"
```

## Troubleshooting

### Pattern not matching

- Check that the pattern is specific enough
- Verify priority order (higher priority matches first)
- Use `get_call_history()` to see actual requests

### Sequence exhausted

- Sequences don't cycle by default
- Set `cycle=True` or add more responses
- Falls back to default (empty items) when exhausted

### Error not raised

- Ensure you're in the correct mode
- Check if pattern matching is taking precedence
- Use `priority=999` for error patterns

## License

Part of the game-localization-mvr test suite.
