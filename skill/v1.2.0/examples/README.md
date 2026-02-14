# Game Localization MVR - Sample Input Data

This directory contains sample data for testing the localization pipeline.

## Files

- `sample_input.csv` - Sample CSV file with Chinese game text
- `sample_glossary.yaml` - Sample glossary with game terms
- `sample_output.csv` - Expected output format

## Usage

```bash
# Run translation on sample data
python scripts/normalize_guard.py examples/sample_input.csv examples/normalized.csv
python scripts/translate_llm.py --input examples/normalized.csv --output examples/translated.csv
```
