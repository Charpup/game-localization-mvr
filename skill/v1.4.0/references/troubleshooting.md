# Troubleshooting Guide

## Common Errors

### Installation Issues

#### Error: `ModuleNotFoundError: No module named 'loc_mvr'`

**Cause:** Package not installed or installed in wrong environment

**Solution:**
```bash
# Verify Python environment
which python
python --version

# Install in current environment
pip install -e .

# Or install from requirements
pip install -r requirements.txt
```

#### Error: `ImportError: cannot import name 'translate_batch'`

**Cause:** Version mismatch or partial installation

**Solution:**
```bash
# Clean install
pip uninstall loc-mvr
pip install -e .

# Verify installation
python -c "from loc_mvr import translate_batch; print('OK')"
```

---

### Translation Errors

#### Error: `TranslationError: Rate limit exceeded`

**Cause:** Too many requests to LLM API

**Solution:**
```bash
# Reduce batch size
loc-mvr translate --batch-size 50

# Add delay between batches
loc-mvr translate --rate-limit 10  # requests per minute

# Use retry with backoff
export LLM_RETRY_ATTEMPTS=3
export LLM_RETRY_DELAY=5
```

#### Error: `TranslationError: Context length exceeded`

**Cause:** Input too long for model context window

**Solution:**
```bash
# Reduce batch size
loc-mvr translate --batch-size 10

# Split long texts manually
# Or enable automatic splitting
export AUTO_SPLIT_LONG_TEXTS=true
```

#### Error: `InvalidLanguageError: Language 'xx-XX' not supported`

**Cause:** Unsupported language code

**Solution:**
```bash
# Check supported languages
loc-mvr languages

# Use correct format (e.g., 'zh-CN' not 'cn')
loc-mvr translate --target-lang zh-CN
```

---

### Configuration Errors

#### Error: `ConfigError: language_pairs.yaml not found`

**Cause:** Configuration file missing

**Solution:**
```bash
# Create default config
mkdir -p config
cp config/language_pairs.yaml.example config/language_pairs.yaml

# Or specify custom path
loc-mvr translate --config /path/to/config.yaml
```

#### Error: `ConfigError: Invalid YAML syntax`

**Cause:** YAML syntax error in config file

**Solution:**
```bash
# Validate YAML
python -c "import yaml; yaml.safe_load(open('config/language_pairs.yaml'))"

# Use online YAML validator
# https://www.yamllint.com/
```

---

### File Errors

#### Error: `ParseError: CSV format invalid`

**Cause:** Malformed CSV file

**Solution:**
```bash
# Verify CSV structure
head -5 data.csv

# Check for encoding issues
file -i data.csv

# Convert to UTF-8 if needed
iconv -f GBK -t UTF-8 data.csv > data_utf8.csv

# Validate with Python
python -c "import pandas as pd; pd.read_csv('data.csv')"
```

#### Error: `PermissionError: [Errno 13] Permission denied`

**Cause:** Insufficient file permissions

**Solution:**
```bash
# Check permissions
ls -la data.csv

# Fix permissions
chmod 644 data.csv

# Or use different output directory
loc-mvr translate --output /tmp/output.csv
```

---

## Debugging Techniques

### Enable Debug Logging

```bash
# Set log level
export LOG_LEVEL=DEBUG

# Or use CLI flag
loc-mvr translate --debug
```

### Check API Response

```python
# Debug script
from loc_mvr.llm_client import LLMClient
import logging

logging.basicConfig(level=logging.DEBUG)

client = LLMClient()
response = client.translate("Hello", target_lang="zh-CN")
print(response)
```

### Verify Configuration

```bash
# Print loaded config
loc-mvr config --show

# Validate config
loc-mvr config --validate
```

### Test Individual Components

```python
# Test parser
from loc_mvr.parser import parse_csv
items = parse_csv("data.csv")
print(f"Parsed {len(items)} items")

# Test translator
from loc_mvr.translator import translate_single
result = translate_single("Hello", target_lang="zh-CN")
print(result)

# Test glossary
from loc_mvr.glossary import load_glossary
glossary = load_glossary("glossary.yaml")
print(f"Loaded {len(glossary)} terms")
```

---

## Performance Issues

### Slow Translation

**Symptoms:** Translation takes too long

**Diagnosis:**
```bash
# Check batch size
time loc-mvr translate --batch-size 100

# Profile the code
python -m cProfile -o profile.stats -m loc_mvr translate ...
```

**Solutions:**

1. **Increase batch size** (if memory allows)
   ```bash
   loc-mvr translate --batch-size 200
   ```

2. **Enable parallel processing**
   ```bash
   loc-mvr translate --parallel --workers 4
   ```

3. **Use faster model**
   ```yaml
   # config/language_pairs.yaml
   pairs:
     - source: zh-CN
       target: en-US
       model: gpt-3.5-turbo  # Faster than gpt-4
   ```

4. **Cache glossary lookups**
   ```bash
   export GLOSSARY_CACHE=true
   export GLOSSARY_CACHE_SIZE=10000
   ```

### High Memory Usage

**Symptoms:** Out of memory errors

**Solutions:**

1. **Reduce batch size**
   ```bash
   loc-mvr translate --batch-size 25
   ```

2. **Process in chunks**
   ```bash
   # Split large file
   split -l 1000 large.csv chunk_
   
   # Process each chunk
   for f in chunk_*; do
     loc-mvr translate --input $f --output out_$f
   done
   ```

3. **Enable streaming mode**
   ```bash
   loc-mvr translate --stream
   ```

---

## Known Issues

### Issue: Japanese Text Overflow

**Problem:** Japanese translations exceed UI limits

**Workaround:**
```yaml
# config/language_pairs.yaml
pairs:
  - source: en-US
    target: ja-JP
    max_length_ratio: 0.6
    truncate_if_needed: true
```

### Issue: German Compound Words

**Problem:** German translations are too long for buttons

**Workaround:**
```yaml
pairs:
  - source: en-US
    target: de-DE
    compound_handling: abbreviate
    abbreviations:
      "Einstellungen": "Einst."
      "Fortsetzen": "Forts."
```

### Issue: Chinese Traditional/Simplified Mix

**Problem:** Mix of traditional and simplified characters

**Workaround:**
```python
# Normalize text before translation
import opencc

converter = opencc.OpenCC('s2t')  # Simplified to Traditional
normalized = converter.convert(text)
```

---

## Getting Help

### Collect Debug Information

```bash
# System info
python --version
pip show loc-mvr

# Config
loc-mvr config --show

# Run with debug
loc-mvr translate --debug --input test.csv 2>&1 | tee debug.log

# Create issue bundle
tar czf issue_bundle.tar.gz debug.log config/ data.csv
```

### Report Issues

Include:
1. Error message (full traceback)
2. Command used
3. Sample input data
4. Configuration
5. Environment info (OS, Python version)

### Resources

- Documentation: `docs/`
- API Reference: `references/api-reference.md`
- FAQ: `docs/faq.md`
- Issues: GitHub Issues page
