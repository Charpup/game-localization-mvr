# Loc-MVR Usage Guide

## Installation

```bash
pip install -r requirements.txt
```

## Commands

### translate

Batch translate game content.

```bash
loc-mvr translate --target-lang en-US --input data.csv --output translated.csv
```

**Options:**
- `--target-lang`: Target language code (e.g., en-US, ja-JP, ko-KR)
- `--input`: Input CSV file path
- `--output`: Output file path
- `--source-lang`: Source language (auto-detect if not specified)
- `--batch-size`: Number of entries per batch (default: 100)
- `--parallel`: Enable parallel processing

### glossary

Manage localization glossary.

```bash
# Extract terms
loc-mvr glossary --action extract --input data.csv

# Translate glossary
loc-mvr glossary --action translate --proposals terms.yaml --target-lang en-US
```

**Actions:**
- `extract`: Extract key terms from source content
- `translate`: Translate glossary terms
- `validate`: Validate glossary consistency
- `export`: Export glossary to various formats

**Options:**
- `--action`: Glossary operation to perform
- `--input`: Source data file
- `--proposals`: Glossary proposals file
- `--target-lang`: Target language for translation

### qa

Run quality assurance.

```bash
loc-mvr qa --input translated.csv --style-guide style.md --glossary glossary.yaml
```

**Options:**
- `--input`: Translated content file
- `--style-guide`: Style guide markdown file
- `--glossary`: Glossary YAML file
- `--report-format`: Output format (json, markdown, html)
- `--severity`: Minimum issue severity to report (info, warning, error)

## Configuration

Language pairs in `config/language_pairs.yaml`.
Prompts in `config/prompts/{lang}/`.

### Example: language_pairs.yaml

```yaml
pairs:
  - source: zh-CN
    target: en-US
    model: gpt-4
    temperature: 0.3
  - source: zh-CN
    target: ja-JP
    model: gpt-4
    temperature: 0.2
  - source: en-US
    target: de-DE
    model: gpt-4
    temperature: 0.3
```

### Prompt Directory Structure

```
config/prompts/
├── en-US/
│   ├── translate.txt
│   ├── review.txt
│   └── qa.txt
├── ja-JP/
│   ├── translate.txt
│   ├── review.txt
│   └── qa.txt
└── ko-KR/
    ├── translate.txt
    ├── review.txt
    └── qa.txt
```

## Quick Start

1. **Setup Configuration**
   ```bash
   cp config/language_pairs.yaml.example config/language_pairs.yaml
   # Edit to add your language pairs
   ```

2. **Prepare Your Data**
   ```bash
   # Create CSV with columns: id, source_text, context
   cat > data.csv << EOF
   id,source_text,context
   item_001,Health Potion,Consumable item
   item_002,Iron Sword,Weapon equipment
   EOF
   ```

3. **Run Translation**
   ```bash
   loc-mvr translate --target-lang en-US --input data.csv --output output.csv
   ```

4. **Review Results**
   ```bash
   loc-mvr qa --input output.csv --style-guide docs/style-guide.md
   ```
