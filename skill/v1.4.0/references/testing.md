# Testing Guide

## Overview

Loc-MVR uses pytest for testing. Tests are organized by module and include unit tests, integration tests, and end-to-end tests.

## Running Tests

### Run All Tests

```bash
pytest
```

### Run Specific Test File

```bash
pytest tests/test_translator.py
```

### Run Specific Test

```bash
pytest tests/test_translator.py::test_translate_batch
```

### Run with Coverage

```bash
pytest --cov=loc_mvr --cov-report=html
```

### Run with Verbose Output

```bash
pytest -v
```

### Run Tests Matching Pattern

```bash
pytest -k "glossary"
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures
├── unit/
│   ├── test_parser.py
│   ├── test_translator.py
│   ├── test_glossary.py
│   └── test_qa.py
├── integration/
│   ├── test_api.py
│   └── test_workflows.py
└── e2e/
    └── test_cli.py
```

## Test Coverage

### Current Coverage Areas

| Module | Coverage | Status |
|--------|----------|--------|
| Parser | 95% | ✅ |
| Translator | 88% | ✅ |
| Glossary | 92% | ✅ |
| QA Engine | 85% | ✅ |
| CLI | 78% | ⚠️ |
| Config | 90% | ✅ |

### Coverage Goals

- Unit tests: >90% coverage
- Integration tests: Core workflows
- E2E tests: Critical user paths

## Writing Tests

### Test Naming Convention

```python
# Function being tested: translate_batch
def test_translate_batch_success():
    """Test successful batch translation"""
    pass

def test_translate_batch_empty_input():
    """Test batch translation with empty input"""
    pass

def test_translate_batch_invalid_lang():
    """Test batch translation with invalid language"""
    pass
```

### Unit Test Example

```python
import pytest
from loc_mvr.translator import translate_batch

class TestTranslateBatch:
    """Tests for translate_batch function"""
    
    def test_successful_translation(self, sample_items):
        """Test basic translation"""
        result = translate_batch(
            items=sample_items,
            target_lang="en-US"
        )
        
        assert result["success"] is True
        assert len(result["results"]) == len(sample_items)
        assert result["stats"]["success"] == len(sample_items)
    
    def test_empty_items(self):
        """Test with empty items list"""
        result = translate_batch(
            items=[],
            target_lang="en-US"
        )
        
        assert result["success"] is True
        assert result["results"] == []
        assert result["stats"]["total"] == 0
    
    def test_invalid_language(self, sample_items):
        """Test with invalid language code"""
        with pytest.raises(ValueError) as exc_info:
            translate_batch(
                items=sample_items,
                target_lang="invalid"
            )
        
        assert "Invalid language code" in str(exc_info.value)
```

### Using Fixtures

```python
# conftest.py
import pytest

@pytest.fixture
def sample_items():
    """Sample translation items"""
    return [
        {"id": "item_1", "text": "Hello", "context": "Greeting"},
        {"id": "item_2", "text": "World", "context": "Noun"}
    ]

@pytest.fixture
def sample_glossary():
    """Sample glossary data"""
    return {
        "装备": "Equipment",
        "武器": "Weapon"
    }

@pytest.fixture
def mock_llm_client(mocker):
    """Mock LLM client"""
    mock = mocker.patch("loc_mvr.llm_client.LLMClient")
    mock.translate.return_value = {"translated": "Translated text"}
    return mock
```

### Integration Test Example

```python
import pytest
from loc_mvr import translate_batch, extract_terms

class TestTranslationWorkflow:
    """Integration tests for translation workflow"""
    
    def test_full_translation_pipeline(self, tmp_path):
        """Test complete translation pipeline"""
        # Create test CSV
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("id,text,context\nitem_1,Hello,Greeting\n")
        
        # Parse and translate
        items = parse_csv(csv_file)
        result = translate_batch(items, target_lang="zh-CN")
        
        assert result["success"] is True
        assert result["results"][0]["translated"] == "你好"
    
    def test_glossary_integration(self, sample_glossary):
        """Test translation with glossary"""
        items = [{"id": "1", "text": "装备强化", "context": "Game"}]
        
        result = translate_batch(
            items=items,
            target_lang="en-US",
            options={"glossary": sample_glossary}
        )
        
        assert "Equipment" in result["results"][0]["translated"]
```

### Mocking External APIs

```python
import pytest
from unittest.mock import Mock, patch

class TestLLMClient:
    """Tests for LLM client with mocked API"""
    
    @patch("loc_mvr.llm_client.requests.post")
    def test_api_call_success(self, mock_post):
        """Test successful API call"""
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {
                "choices": [{"message": {"content": "Translated"}}]
            }
        )
        
        client = LLMClient()
        result = client.translate("Hello", target_lang="zh-CN")
        
        assert result == "Translated"
        mock_post.assert_called_once()
    
    @patch("loc_mvr.llm_client.requests.post")
    def test_api_call_failure(self, mock_post):
        """Test API call failure with retry"""
        mock_post.side_effect = [
            Exception("Network error"),
            Mock(
                status_code=200,
                json=lambda: {"choices": [{"message": {"content": "Translated"}}]}
            )
        ]
        
        client = LLMClient()
        result = client.translate("Hello", target_lang="zh-CN")
        
        assert result == "Translated"
        assert mock_post.call_count == 2
```

## Adding New Tests

### Step-by-Step Guide

1. **Identify the Function to Test**
   ```bash
   # Find untested functions
   pytest --cov=loc_mvr --cov-report=term-missing
   ```

2. **Create Test File (if needed)**
   ```bash
   touch tests/unit/test_new_module.py
   ```

3. **Write Test Cases**
   - Happy path
   - Edge cases
   - Error cases

4. **Add Fixtures (if reusable)**
   ```python
   # In conftest.py or test file
   @pytest.fixture
   def my_fixture():
       return {"key": "value"}
   ```

5. **Run Tests**
   ```bash
   pytest tests/unit/test_new_module.py -v
   ```

### Test Checklist

- [ ] Test happy path
- [ ] Test empty/null inputs
- [ ] Test invalid inputs
- [ ] Test boundary conditions
- [ ] Test error handling
- [ ] Test with mocks (external APIs)
- [ ] Verify coverage >90%

## Performance Tests

```python
import pytest
import time

class TestPerformance:
    """Performance tests"""
    
    def test_batch_translation_speed(self):
        """Test translation performance"""
        items = [{"id": f"item_{i}", "text": "Hello"} for i in range(100)]
        
        start = time.time()
        result = translate_batch(items, target_lang="zh-CN")
        duration = time.time() - start
        
        assert duration < 30  # Should complete in 30 seconds
        assert result["success"] is True
```

## Continuous Integration

Tests run automatically on:
- Every pull request
- Every push to main
- Daily scheduled run

### CI Configuration

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements-dev.txt
      - run: pytest --cov=loc_mvr --cov-report=xml
      - uses: codecov/codecov-action@v3
```

## Debugging Tests

### Run Single Test with Debug

```bash
pytest tests/test_translator.py::test_translate_batch -v --pdb
```

### Print Debug Output

```python
def test_with_debug():
    result = some_function()
    print(f"Debug: {result}")  # Use -s flag to see output
    assert result["success"]
```

```bash
pytest test_file.py -s  # Show print statements
```

### Test Logs

```bash
pytest --log-cli-level=DEBUG
```
