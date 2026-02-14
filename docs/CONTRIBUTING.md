# Contributing to Game Localization MVR

Thank you for your interest in contributing! This guide covers setup, development practices, and how to run tests.

## Quick Start

### Prerequisites

- Python 3.7+
- PyYAML (`pip install pyyaml`)

### Clone and Setup

```bash
git clone https://github.com/Charpup/game-localization-mvr.git
cd game-localization-mvr
pip install pyyaml
```

### Run Tests

```bash
# All core tests
python scripts/test_normalize.py
python scripts/test_rehydrate.py
python scripts/test_e2e_workflow.py
```

## Windows Users

### Encoding Compatibility

The project uses UTF-8 encoding with emoji characters for output. On Windows:

1. **PowerShell/Terminal**: Run with UTF-8 enabled:
   ```powershell
   [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
   ```

2. **VS Code**: Ensure terminal encoding is UTF-8 (Settings → Terminal → Encoding)

3. **Scripts**: All core scripts include automatic UTF-8 configuration for Windows:
   ```python
   if sys.platform == 'win32':
       import io
       sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
   ```

### CSV BOM Handling

When reading CSV files, always use `utf-8-sig` to handle the Byte Order Mark:
```python
with open(path, 'r', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
```

## Test Fixtures

Tests use self-contained fixtures from `data/fixtures/`:

| File | Purpose |
|------|---------|
| `input_valid.csv` | Sample input with various placeholder types |
| `translated_valid.csv` | Valid translations (Russian) |
| `translated_invalid.csv` | Translations with intentional errors |
| `placeholder_map.json` | Token mappings |

**Do not modify fixtures** without updating expected test results.

## Code Style

- Python 3.7+ compatible
- Type hints for function signatures
- Docstrings for public functions
- No external dependencies beyond PyYAML

## Adding New Features

1. **Create a branch**: `git checkout -b feature/my-feature`
2. **Add tests**: Update or create test files in `scripts/test_*.py`
3. **Update fixtures**: If needed, add new test data to `data/fixtures/`
4. **Run all tests**: Ensure existing tests pass
5. **Update docs**: Add usage info to relevant `.md` files
6. **Submit PR**: Include description of changes

## Workflow Rules

See [WORKSPACE_RULES.md](docs/WORKSPACE_RULES.md) for mandatory development rules.

Key rules:
- All LLM calls via `runtime_adapter.py`
- Placeholders must be frozen before translation
- `qa_hard.py` is a blocking gate
- No full-table rewrites in repair

## Directory Structure

```
scripts/           # Python scripts
  test_*.py        # Test files
data/
  fixtures/        # Test fixtures (committed)
  temp_*/          # Temp test dirs (ignored)
workflow/          # Configuration files
docs/              # Documentation
.agent/workflows/  # Agentic workflows
```

## Questions?

Open an issue on GitHub or check existing documentation in `docs/`.
