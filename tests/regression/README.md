# Regression Testing Framework

This directory contains regression tests for the game localization pipeline.

## Purpose

Regression tests catch bugs that were previously fixed and must not reoccur.
These are known-good test cases that verify critical pipeline functionality:

- **Placeholder Protection**: Ensures all placeholder formats are preserved
- **Tag Balance**: Verifies HTML/Unity rich text tags remain balanced
- **Glossary Terms**: Confirms glossary entries are handled correctly
- **Special Characters**: Validates Unicode and special character handling

## Quick Start

```bash
# Run all regression tests
pytest -m regression

# Run with coverage report
pytest -m regression --cov=scripts --cov-report=term-missing

# Run specific category
pytest -m "regression and placeholder"
pytest -m "regression and tag_balance"
pytest -m "regression and glossary"

# Run integration tests only
pytest -m "regression and integration"
```

## Test Categories

| Marker | Description | Count |
|--------|-------------|-------|
| `@pytest.mark.placeholder` | Placeholder freezing and preservation | 7 tests |
| `@pytest.mark.tag_balance` | HTML/Unity tag balance | 6 tests |
| `@pytest.mark.glossary` | Glossary term handling | 5 tests |
| `@pytest.mark.special_chars` | Unicode/special characters | 7 tests |
| `@pytest.mark.edge_case` | Edge cases and combinations | 7 tests |
| `@pytest.mark.integration` | Full pipeline integration | 3 tests |
| `@pytest.mark.coverage` | Coverage verification | 2 tests |

## Test Data

- `../data/regression/baseline_cases.csv` - 40+ test cases across all categories
- `../data/regression/glossary_baseline.yaml` - 18 approved glossary entries
- `../data/regression/expected_baseline.yaml` - Expected results specification

## Known Pipeline Behaviors

### Jieba Segmentation Effects

The pipeline uses jieba for Chinese text segmentation BEFORE placeholder freezing.
This can cause:

1. **Spaces added to placeholders**: `{name}` → `{ name }`
2. **Bracket placeholders may not freeze**: `[ITEM]` → `[ ITEM ]` (doesn't match regex)
3. **Tag markers spaced**: `__TAG_0__` → `__ TAG _ 0 __`

Tests are designed to document and verify these behaviors.

### Recommended Placeholder Usage

| Format | Reliability | Notes |
|--------|-------------|-------|
| `{name}` | ✅ High | Brace placeholders work reliably |
| `{0}` | ✅ High | Numeric braces work well |
| `%s`, `%d` | ✅ High | Printf style works |
| `[NAME]` | ⚠️ Medium | May be split by jieba |
| `% H` | ✅ High | Percent-space-letter pattern works |

## Adding New Regression Tests

1. Add test case to `baseline_cases.csv`:
```csv
NEW_001,Test text with {placeholder},50,new_category
```

2. Add expected behavior to `expected_baseline.yaml`:
```yaml
NEW_001:
  source: "Test text with {placeholder}"
  must_preserve_tokens: true
```

3. Add test method to `test_regression_baseline.py`:
```python
@pytest.mark.regression
@pytest.mark.new_category
class TestNewCategory:
    def test_new_feature(self, freezer):
        text = "Test text with {placeholder}"
        tokenized, _ = freezer.freeze_text(text)
        assert "⟦PH_" in tokenized
```

## Coverage Target

Target: **80%+** coverage on core pipeline modules:
- `scripts/normalize_guard.py` (currently ~70%)
- `scripts/qa_hard.py`
- `scripts/translate_llm.py`

Run coverage check:
```bash
pytest tests/regression/ --cov=scripts --cov-report=html
```

## Maintenance

When fixing a bug:
1. Add a test case that would have caught the bug
2. Mark with `@pytest.mark.regression`
3. Document in expected_baseline.yaml
4. Run full regression suite before merging

## CI Integration

```yaml
# Example CI configuration
regression_tests:
  script:
    - pytest -m regression --cov=scripts --cov-fail-under=80
```
