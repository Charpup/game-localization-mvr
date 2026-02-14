# Quick Start Guide

Get started with Game Localization MVR in 5 minutes.

## Table of Contents

- [Installation](#installation)
- [First Translation](#first-translation)
- [Common Use Cases](#common-use-cases)
- [Troubleshooting](#troubleshooting)

---

## Installation

### Option 1: Download Pre-packaged Skill (Recommended)

```bash
# 1. Download the skill
curl -L -o loc-mvr-v1.2.0-stable.skill \
  https://github.com/Charpup/game-localization-mvr/releases/download/v1.2.0-stable/loc-mvr-v1.2.0-stable.skill

# 2. Verify checksum
sha256sum -c loc-mvr-v1.2.0-stable.skill.sha256

# 3. Extract
unzip loc-mvr-v1.2.0-stable.skill
cd skill/

# 4. Configure API keys
cp .env.example .env
# Edit .env with your API credentials

# 5. Run quick test
python scripts/normalize_guard.py examples/sample_input.csv output.csv
```

### Option 2: Clone Repository

```bash
# 1. Clone repository
git clone https://github.com/Charpup/game-localization-mvr.git
cd game-localization-mvr

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env:
#   LLM_API_KEY=your_api_key_here
#   LLM_BASE_URL=https://api.apiyi.com/v1

# 4. Build Docker image
docker build -f Dockerfile.gate -t gate_v2 .
```

### Required Dependencies

```bash
# Core dependencies
pip install pyyaml requests tqdm

# For async processing (v1.2.0+)
pip install aiohttp aiofiles

# For development
pip install pytest pytest-asyncio
```

---

## First Translation

### 1. Prepare Your Data

Create a CSV file with your source text:

```csv
string_id,source_text
1,欢迎来到游戏世界
2,点击开始按钮
3,攻击敌人
```

### 2. Run Translation

**Option A: Using Docker (Recommended)**

```bash
# Windows PowerShell
.\scripts\docker_run.ps1 python -u -m scripts.translate_llm \
  --input data/input.csv \
  --output data/translated.csv

# Linux/Mac
./scripts/docker_run.sh python -u -m scripts.translate_llm \
  --input data/input.csv \
  --output data/translated.csv
```

**Option B: Direct Python (Requires API key in environment)**

```bash
export LLM_API_KEY="your_key_here"
export LLM_BASE_URL="https://api.apiyi.com/v1"

python -m scripts.translate_llm \
  --input data/input.csv \
  --output data/translated.csv
```

### 3. Check Results

```bash
# View output
cat data/translated.csv

# View metrics
python scripts/metrics_aggregator.py \
  --trace-path data/llm_trace.jsonl \
  --output data/metrics_report.md

cat data/metrics_report.md
```

---

## Common Use Cases

### Use Case 1: Translate with Model Routing (Cost Optimization)

```python
from scripts.model_router import patch_translate_llm_with_router

# Enable intelligent routing
patch_translate_llm_with_router()

# Now run translation - models are selected automatically
python scripts/translate_llm.py --input data.csv --output out.csv
```

**Expected savings**: 20-40% cost reduction

### Use Case 2: High-Speed Async Processing

```python
import asyncio
from scripts.async_adapter import process_csv_async

async def main():
    stats = await process_csv_async(
        input_path="data/large_file.csv",
        output_path="data/output.csv",
        progress_callback=lambda stage, done, total: 
            print(f"[{stage}] {done}/{total}")
    )
    
    print(f"Processed {stats['processed_rows']} rows")
    print(f"Speed: {stats['rows_per_second']:.2f} rows/sec")

asyncio.run(main())
```

**Expected speedup**: 2-3x faster than synchronous

### Use Case 3: Glossary-Based Auto-Approval

```python
from scripts.glossary_matcher import GlossaryMatcher

# Load glossary
matcher = GlossaryMatcher()
matcher.load_glossary_from_yaml("glossary/compiled.yaml")

# Find matches in text
text = "忍者的攻击力很高，暴击伤害也很强。"
matches = matcher.find_matches(text)

for match in matches:
    print(f"{match.source_term} -> {match.target_term}")
    print(f"Confidence: {match.confidence:.2%}")
    print(f"Auto-approved: {match.auto_approved}")
```

**Expected accuracy**: 95%+ auto-approval rate

### Use Case 4: Cache for Repeated Content

```bash
# First run - populates cache
python scripts/translate_llm.py \
  --input data.csv --output out1.csv

# Second run - uses cache (much faster, zero cost)
python scripts/translate_llm.py \
  --input data.csv --output out2.csv

# Check cache stats
python scripts/cache_manager.py --stats
```

**Expected savings**: 50%+ on repeated translations

### Use Case 5: Glossary Violation Detection

```python
from scripts.glossary_corrector import GlossaryCorrector

corrector = GlossaryCorrector()
corrector.load_glossary("glossary/compiled.yaml")

# Check translation for violations
text = "Ханкок использует свои силы."  # Misspelled
corrections = corrector.detect_violations(text)

for c in corrections:
    print(f"Fix: '{c.original}' -> '{c.suggested}'")
    print(f"Rule: {c.rule}, Confidence: {c.confidence:.2%}")
```

### Use Case 6: Full Pipeline with All Features

```bash
#!/bin/bash
# full_pipeline.sh

# Step 1: Normalize input
python scripts/normalize_guard.py \
  data/raw.csv \
  data/normalized.csv

# Step 2: Translate with routing and caching
python scripts/translate_llm.py \
  --input data/normalized.csv \
  --output data/translated.csv \
  --smart-routing \
  --cache-enabled

# Step 3: Run QA
python scripts/qa_hard.py \
  --input data/translated.csv \
  --output data/qa_report.json

# Step 4: Export final results
python scripts/rehydrate_export.py \
  --source data/raw.csv \
  --translated data/translated.csv \
  --output data/final.csv
```

### Use Case 7: Benchmark Async vs Sync

```python
from scripts.async_adapter import benchmark_async_vs_sync
import asyncio

test_prompts = [
    {"system": "Translate to Russian.", "user": f"Text {i}"}
    for i in range(50)
]

async def run():
    results = await benchmark_async_vs_sync(
        test_prompts, 
        max_concurrent=10
    )
    
    print(f"Sync time: {results['sync']['duration_seconds']}s")
    print(f"Async time: {results['async']['duration_seconds']}s")
    print(f"Speedup: {results['speedup_factor']}x")

asyncio.run(run())
```

---

## Troubleshooting

### Problem: "API Key not found"

**Solution**:
```bash
# Check .env file exists
cat .env

# Set environment variables explicitly
export LLM_API_KEY="sk-..."
export LLM_BASE_URL="https://api.apiyi.com/v1"

# Or use Docker scripts which handle injection
.\scripts\docker_run.ps1 python scripts/translate_llm.py ...
```

### Problem: "Module not found"

**Solution**:
```bash
# Install missing dependencies
pip install pyyaml requests aiohttp aiofiles

# Ensure you're in the right directory
pwd  # Should show .../game-localization-mvr

# Run with python -m
python -m scripts.translate_llm ...
```

### Problem: "Docker not found"

**Solution**:
```bash
# Option 1: Install Docker
# Visit: https://docs.docker.com/get-docker/

# Option 2: Run without Docker (set API key directly)
export LLM_API_KEY="your_key"
export LLM_BASE_URL="https://api.apiyi.com/v1"
python scripts/translate_llm.py ...
```

### Problem: "Token limit exceeded"

**Solution**:
- Long text (>500 chars) is automatically isolated in v1.1.0+
- Split very long text into smaller chunks manually
- Use model routing to select models with larger context windows

### Problem: "Costs are too high"

**Solution**:
```bash
# 1. Enable caching
python scripts/cache_manager.py --stats  # Check current stats

# 2. Enable model routing
# Edit config/model_routing.yaml, set enabled: true

# 3. Use cheaper models for simple text
# In model_routing.yaml, add:
# - name: "gpt-4.1-nano"
#   cost_per_1k: 0.001
#   max_complexity: 0.4

# 4. Check metrics to identify expensive steps
python scripts/metrics_aggregator.py \
  --trace-path data/llm_trace.jsonl \
  --output data/cost_breakdown.md
```

### Problem: "Translation quality is poor"

**Solution**:
```bash
# 1. Check glossary coverage
python scripts/glossary_matcher.py \
  --input data/input.csv \
  --glossary glossary/compiled.yaml

# 2. Use higher quality models
# In config/model_routing.yaml, adjust:
complexity_threshold: 0.5  # Lower = more premium model usage

# 3. Run QA checks
python scripts/qa_hard.py \
  --input data/translated.csv \
  --output data/qa_report.json

# 4. Review and apply corrections
python scripts/glossary_corrector.py \
  data/translated.csv \
  --glossary glossary/compiled.yaml \
  --suggest-corrections
```

### Problem: "Async processing is slower"

**Solution**:
```bash
# 1. Check concurrency settings
# In config/pipeline.yaml:
async:
  max_concurrent_llm_calls: 20  # Increase
  semaphore_timeout: 120        # Increase for slow APIs

# 2. Monitor queue depth
# Enable detailed metrics:
monitoring:
  collect_metrics:
    queue_depth: true
    semaphore_wait_time: true

# 3. For small files, sync may be faster
# Async benefits appear with 100+ rows
```

### Problem: "Cache not working"

**Solution**:
```bash
# 1. Check cache is enabled
python scripts/cache_manager.py --stats

# 2. Verify cache directory exists
ls -la .cache/

# 3. Check TTL settings
# In config/pipeline.yaml:
cache:
  enabled: true
  ttl_days: 7  # Increase if needed

# 4. Clear and rebuild cache if corrupted
python scripts/cache_manager.py --clear
```

### Problem: "Glossary matches are wrong"

**Solution**:
```bash
# 1. Adjust matching thresholds
# In config/glossary.yaml:
glossary_matching:
  auto_approve_threshold: 0.98  # Higher = stricter
  fuzzy_threshold: 0.95         # Higher = more exact

# 2. Disable auto-approval for review
auto_approve_threshold: 1.01  # Never auto-approve

# 3. Export matches for manual review
python scripts/glossary_matcher.py \
  --input data.csv \
  --export-html reports/glossary_review.html
```

---

## Performance Tips

### For Small Files (<100 rows)
- Use synchronous processing
- Disable async to reduce overhead

### For Medium Files (100-1000 rows)
- Enable async with default settings
- Use model routing for cost savings

### For Large Files (1000+ rows)
- Maximize async concurrency
- Enable caching
- Use batch processing
- Monitor memory usage

### For Production Workloads
- Always use Docker
- Enable all optimizations (routing, caching, async)
- Monitor costs with metrics_aggregator
- Set up automated QA pipeline

---

## Next Steps

- **[API Documentation](API.md)** - Complete API reference
- **[Configuration Guide](CONFIGURATION.md)** - Full configuration options
- **[CHANGELOG.md](../CHANGELOG.md)** - Version history and migration guides

---

## Support

- **Issues**: https://github.com/Charpup/game-localization-mvr/issues
- **Documentation**: See `docs/` directory
- **API Keys**: Try [APIYi](https://api.apiyi.com/register/?aff_code=8Via)
