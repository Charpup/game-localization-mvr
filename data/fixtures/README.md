# Test Fixtures

This directory contains stable, self-contained test data for unit and E2E tests.

## Files

| File | Purpose |
|------|---------|
| `input_valid.csv` | 7 rows with various placeholder types |
| `translated_valid.csv` | Correct translations matching input |
| `translated_invalid.csv` | Translations with various errors |
| `placeholder_map.json` | Token mappings for the fixtures |

## Placeholder Coverage

- `{0}` - C# numbered placeholder
- `{level}`, `{playerName}`, etc. - C# named placeholders
- `%d`, `%s` - Printf-style placeholders
- `<color=#FF00FF>`, `</color>` - Unity rich text tags
- `\n` - Escape sequences

## Error Types in `translated_invalid.csv`

1. **token_mismatch** - Missing `PH_1` token
2. **unknown_token** - Invalid token `PH_99`
3. **forbidden_hit** - Contains `[TODO]`
4. **new_placeholder_found** - Unfrozen `{itemName}`

## Usage

Tests should use these fixtures instead of production data in `data/`:

```python
INPUT = "data/fixtures/input_valid.csv"
MAP = "data/fixtures/placeholder_map.json"
```
