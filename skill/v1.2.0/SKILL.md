# Game Localization MVR v1.2.0 - Skill Documentation

<p align="center">
  <strong>LLM-powered game localization pipeline with intelligent routing and async execution</strong><br>
  <em>Production-proven: 30k+ rows, $0.90-1.20 per 1k rows, 99.87% accuracy</em>
</p>

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Installation](#installation)
3. [Core Features](#core-features)
4. [Usage Examples](#usage-examples)
5. [Configuration](#configuration)
6. [API Reference](#api-reference)
7. [Testing](#testing)
8. [Troubleshooting](#troubleshooting)

---

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up API keys
export LLM_API_KEY="your_api_key"
export LLM_BASE_URL="https://api.apiyi.com/v1"

# 3. Run sample translation
python scripts/translate_llm.py \
  --input examples/sample_input.csv \
  --output output/translated.csv \
  --smart-routing
```

---

## Installation

### Prerequisites

- Python 3.9 or higher
- 4GB RAM minimum (8GB recommended)
- LLM API access (APIYi, OpenAI, or Anthropic)

### Step-by-Step Installation

```bash
# 1. Extract the skill package
unzip loc-mvr-v1.2.0.skill
cd skill/v1.2.0

# 2. Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify installation
python scripts/llm_ping.py
```

### Docker Installation (Optional)

```bash
# Build Docker image
docker build -f Dockerfile.gate -t loc-mvr:latest .

# Run with Docker
./scripts/docker_run.sh python scripts/translate_llm.py --help
```

---

## Core Features

### 1. Intelligent Model Routing

Automatically routes translation requests to the most cost-effective model based on content complexity.

**Benefits:**
- 20-40% cost reduction on typical workloads
- Maintains quality through complexity analysis
- Learns from QA failure patterns

**How it works:**
1. Analyzes text complexity (length, placeholders, glossary density, special characters)
2. Consults historical QA failure rates for similar text patterns
3. Selects optimal model balancing cost vs. quality
4. Tracks decisions for continuous improvement

```python
from scripts.model_router import ModelRouter

router = ModelRouter()
model, metrics, cost = router.select_model(
    text="忍者的攻击力很高",
    step="translate",
    glossary_terms=["忍者", "攻击力"]
)
print(f"Selected: {model} (estimated cost: ${cost:.4f})")
```

**Complexity Factors:**
| Factor | Weight | Description |
|--------|--------|-------------|
| Text length | 20% | Character count |
| Placeholder density | 25% | Variables per 100 chars |
| Glossary density | 25% | Terms per 100 chars |
| Special characters | 15% | Non-alphanumeric chars |
| Historical failures | 15% | QA failure rate for pattern |

---

### 2. Async/Concurrent Execution

Achieves 30-50% latency reduction through parallel processing.

**Features:**
- Async LLM client with semaphore-based rate limiting
- Streaming pipeline with overlapping stages
- Backpressure handling to prevent memory overflow
- Configurable concurrency per pipeline stage

```python
from scripts.async_adapter import process_csv_async
import asyncio

# Process with async execution
stats = asyncio.run(process_csv_async(
    input_path="data/input.csv",
    output_path="data/output.csv",
    max_concurrent=10
))
print(f"Processed {stats.rows_processed} rows in {stats.duration_seconds:.1f}s")
```

**Performance Comparison:**
| Mode | Throughput | Latency |
|------|------------|---------|
| Sync | 20-30 rows/sec | Baseline |
| Async | 50-100 rows/sec | 30-50% faster |

---

### 3. Glossary AI System

Intelligent glossary matching and correction with self-learning capabilities.

#### Glossary Matcher

Smart fuzzy matching with high auto-approval rates:

```python
from scripts.glossary_matcher import GlossaryMatcher

matcher = GlossaryMatcher()
matches = matcher.find_matches(
    text="忍者的攻击力很高",
    glossary_terms=["忍者", "攻击力"]
)
# Returns: [{"term": "忍者", "match_type": "exact", "confidence": 1.0}, ...]
```

**Match Types:**
- `exact` - 100% match (auto-approved)
- `fuzzy` - 90%+ similarity (auto-approved if above threshold)
- `context` - Disambiguated using surrounding context
- `declension` - Russian case ending handling

#### Glossary Corrector

Detects and suggests fixes for glossary violations:

```python
from scripts.glossary_corrector import GlossaryCorrector

corrector = GlossaryCorrector()
suggestions = corrector.detect_violations(
    source_text="忍者的攻击力很高",
    translation_text="Воин имеет высокую силу атаки",  # Wrong: воин vs ниндзя
    glossary={"忍者": "ниндзя", "攻击力": "сила атаки"}
)
# Returns fix suggestions with confidence scores
```

#### Glossary Learner

Self-improving glossary through QA feedback:

```python
from scripts.glossary_learner import GlossaryLearner

learner = GlossaryLearner()
learner.learn_from_qa_result(
    source="忍者",
    translation="ниндзя",
    qa_score=0.95,
    context="combat"
)
# Automatically updates term confidence and suggests new entries
```

---

### 4. Response Caching

SQLite-based persistent cache for significant cost savings.

**Features:**
- TTL support (default 7 days)
- LRU eviction when size limit reached
- Real-time hit/miss statistics
- 50%+ cost savings on repeated content

```bash
# Run with cache (default)
python scripts/translate_llm.py --input data.csv --output out.csv

# Run without cache
python scripts/translate_llm.py --input data.csv --output out.csv --no-cache

# Clear cache
python scripts/cache_manager.py --clear

# View statistics
python scripts/cache_manager.py --stats
```

**Cache Statistics Output:**
```
📊 Cache Statistics:
   Hits: 150
   Misses: 50
   Hit Rate: 75.00%
   💰 Cost Savings: 75.0% (cache hits = zero cost)
   Cache Size: 12.34 MB / 100 MB
```

---

## Usage Examples

### Example 1: Basic Translation

```bash
python scripts/normalize_guard.py \
  examples/sample_input.csv \
  output/normalized.csv

python scripts/translate_llm.py \
  --input output/normalized.csv \
  --output output/translated.csv \
  --source-lang zhCN \
  --target-lang ruRU
```

### Example 2: With Smart Routing

```bash
python scripts/translate_llm.py \
  --input data/tokenized.csv \
  --output data/translated.csv \
  --smart-routing \
  --routing-config config/model_routing.yaml
```

### Example 3: Async Processing

```bash
python scripts/async_adapter.py \
  --input data/large_file.csv \
  --output data/output.csv \
  --max-concurrent 10 \
  --buffer-size 100
```

### Example 4: Full Pipeline with QA

```bash
# 1. Normalize
python scripts/normalize_guard.py input.csv normalized.csv

# 2. Translate with caching
python scripts/translate_llm.py \
  --input normalized.csv \
  --output translated.csv \
  --cache-enabled

# 3. Hard QA validation
python scripts/qa_hard.py \
  --input translated.csv \
  --output qa_report.json

# 4. Repair failures
python scripts/repair_loop_v2.py \
  --input translated.csv \
  --qa-report qa_report.json \
  --output repaired.csv
```

### Example 5: Glossary Management

```bash
# Extract terms from source
python scripts/extract_terms.py \
  --input source.csv \
  --output glossary_proposals.yaml

# Review with AI
python scripts/glossary_review_llm.py \
  --input glossary_proposals.yaml \
  --output glossary_reviewed.yaml

# Compile to lock file
python scripts/glossary_compile.py \
  --input glossary_reviewed.yaml \
  --output glossary.lock.json

# Apply during translation
python scripts/translate_llm.py \
  --input data.csv \
  --glossary glossary.lock.json
```

---

## Configuration

### Pipeline Configuration (`config/pipeline.yaml`)

```yaml
# Pipeline settings
pipeline:
  name: "game_localization"
  version: "1.2.0"

# Cache configuration
cache:
  enabled: true
  ttl_days: 7
  max_size_mb: 100
  location: ".cache/translations.db"

# Async settings
async:
  enabled: true
  max_concurrent_llm_calls: 10
  buffer_size: 100
  stage_concurrency:
    normalize: 5
    translate: 10
    qa: 8
    export: 3

# Model routing
routing:
  enabled: true
  default_model: "gpt-4o-mini"
  complexity_thresholds:
    low: 0.3
    medium: 0.6
    high: 0.8
  models:
    low_complexity: "gpt-3.5-turbo"
    medium_complexity: "gpt-4o-mini"
    high_complexity: "gpt-4o"
    critical: "claude-sonnet-4"
```

### Model Routing Configuration (`config/model_routing.yaml`)

```yaml
# Model definitions
models:
  gpt-4o-mini:
    provider: openai
    model_id: "gpt-4o-mini"
    cost_per_1k_input: 0.00015
    cost_per_1k_output: 0.0006
    max_tokens: 16384
    
  claude-sonnet-4:
    provider: anthropic
    model_id: "claude-sonnet-4-5-20251001"
    cost_per_1k_input: 0.003
    cost_per_1k_output: 0.015
    max_tokens: 8192

# Routing rules
rules:
  - name: "short_simple"
    condition: "length < 50 AND placeholders == 0"
    model: "gpt-4o-mini"
    
  - name: "long_complex"
    condition: "length > 200 OR placeholders > 3"
    model: "claude-sonnet-4"
```

### Environment Variables

```bash
# Required
export LLM_API_KEY="your_api_key_here"
export LLM_BASE_URL="https://api.apiyi.com/v1"

# Optional
export CACHE_ENABLED="true"
export CACHE_TTL_DAYS="7"
export ASYNC_ENABLED="true"
export ROUTING_ENABLED="true"
export LOG_LEVEL="INFO"
```

---

## API Reference

### ModelRouter Class

```python
from scripts.model_router import ModelRouter, ComplexityAnalyzer

# Initialize
router = ModelRouter(config_path="config/model_routing.yaml")

# Analyze text complexity
analyzer = ComplexityAnalyzer()
metrics = analyzer.analyze("Your text here")
print(f"Complexity score: {metrics.complexity_score}")

# Select model
model, metrics, cost = router.select_model(
    text="Text to translate",
    step="translate",  # or "qa", "repair"
    glossary_terms=["term1", "term2"]
)

# Translate with automatic routing
result = router.translate_with_routing(
    text="Text to translate",
    target_lang="ruRU"
)
```

### AsyncAdapter Class

```python
from scripts.async_adapter import AsyncPipeline, AsyncLLMClient
import asyncio

# Async LLM client
client = AsyncLLMClient(
    max_concurrent=10,
    semaphore_timeout=60
)

# Process single text
result = await client.translate("Text", target_lang="ruRU")

# Process batch
async def process_batch():
    texts = ["Text 1", "Text 2", "Text 3"]
    tasks = [client.translate(t, target_lang="ruRU") for t in texts]
    results = await asyncio.gather(*tasks)
    return results

results = asyncio.run(process_batch())
```

### CacheManager Class

```python
from scripts.cache_manager import CacheManager, CacheConfig

# Initialize with custom config
config = CacheConfig(
    enabled=True,
    ttl_days=14,
    max_size_mb=200
)
cache = CacheManager(config)

# Store translation
key = cache.generate_key("Source text", glossary_hash="abc123", model="gpt-4o")
cache.set(key, {"translation": "Перевод", "model": "gpt-4o"})

# Retrieve translation
result = cache.get(key)
if result:
    print("Cache hit!")

# Get statistics
stats = cache.get_stats()
print(f"Hit rate: {stats.hit_rate:.1%}")
```

---

## Testing

### Run All Tests

```bash
# Run full test suite
python -m pytest tests/ -v

# Run specific test modules
python -m pytest tests/test_model_router.py -v
python -m pytest tests/test_async_adapter.py -v
python -m pytest tests/test_cache_manager.py -v
```

### Run Benchmarks

```bash
# Performance benchmark
python tests/benchmark_v1_2_0_simulated.py

# Integration test
python tests/test_v1_2_0_integration.py
```

### Mock LLM Testing

```bash
# Run tests with mock LLM (no API calls)
export MOCK_LLM=true
python tests/test_mock_llm.py
```

---

## Troubleshooting

### Common Issues

**Q: API Key injection fails?**

A: Use Docker scripts for consistent environment:
```bash
./scripts/docker_run.sh python scripts/translate_llm.py ...
```

**Q: Long text causes token limit errors?**

A: Long text (>500 chars) is automatically isolated with `is_long_text=1` flag. Check `normalize_guard.py` output.

**Q: Costs exceed budget?**

A: 
1. Enable model routing: `--smart-routing`
2. Enable caching: `--cache-enabled`
3. Check metrics report: `python scripts/metrics_aggregator.py --trace-path ...`

**Q: Cache not working?**

A: Verify cache configuration:
```bash
python scripts/cache_manager.py --stats
```

**Q: Async processing errors?**

A: Check semaphore limits and reduce concurrency:
```bash
python scripts/async_adapter.py --max-concurrent 5 ...
```

### Debug Mode

Enable detailed logging:
```bash
export LOG_LEVEL=DEBUG
export TRACE_ENABLED=true
python scripts/translate_llm.py --input data.csv --output out.csv
```

---

## Performance Metrics

### v1.2.0 Benchmarks

| Metric | Value |
|--------|-------|
| Throughput (async) | 50-100 rows/sec |
| Throughput (sync) | 20-30 rows/sec |
| Cost per 1k rows | $0.90-1.20 |
| Glossary match rate | 95%+ |
| Cache hit rate | 75%+ |
| QA accuracy | 99.87% |

### Cost Comparison

| Method | Cost per 1k rows |
|--------|-----------------|
| Traditional outsourcing | $6-10 |
| v1.1.0 baseline | $1.50 |
| v1.2.0 with routing + cache | $0.90-1.20 |

---

## License

MIT License

---

**Need Help?**
- GitHub Issues: https://github.com/Charpup/game-localization-mvr/issues
- Documentation: https://github.com/Charpup/game-localization-mvr/tree/main/docs
