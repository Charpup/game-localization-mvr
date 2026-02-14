# Loc-mvr: Game Localization Automation Workflow

<p align="center">
  <strong>LLM-powered translation pipeline replacing traditional outsourcing</strong><br>
  <a href="README_zh.md">中文文档</a>
</p>

## 🎯 Quick Start with Skill

**Download the pre-packaged Skill** (Recommended for first-time users):

[![Download Skill](https://img.shields.io/badge/Download-Skill_v1.2.0-blue?style=for-the-badge)](https://github.com/Charpup/game-localization-mvr/releases/download/v1.2.0-skill/loc-mvr-v1.2.0.skill)

```bash
# 1. Download and extract
wget https://github.com/Charpup/game-localization-mvr/releases/download/v1.2.0-skill/loc-mvr-v1.2.0.skill
unzip loc-mvr-v1.2.0.skill

# 2. Verify checksum
sha256sum -c loc-mvr-v1.2.0.skill.sha256

# 3. Follow Quick Start in SKILL.md
cd skill/
python scripts/normalize_guard.py examples/sample_input.csv ...
```

**Or clone the full repository**:

```bash
git clone https://github.com/Charpup/game-localization-mvr.git
cd game-localization-mvr
pip install -r requirements.txt
```

## ✨ v1.2.0 Feature Highlights

### 🧠 Intelligent Model Routing (NEW)
Automatically routes translation requests to the most cost-effective model based on content complexity:
- **Complexity Analysis**: Analyzes text length, placeholders, glossary density, and special characters
- **Cost Optimization**: Uses cheaper models (GPT-3.5, GPT-4.1-nano) for simple text, premium models (GPT-4, Claude Sonnet) for complex content
- **Historical Learning**: Tracks QA failure patterns to improve routing decisions
- **Expected Savings**: 20-40% cost reduction on typical workloads

```python
from src.scripts.model_router import ModelRouter

router = ModelRouter()
model, metrics, cost = router.select_model(
    text="Your text here",
    glossary_terms=["忍者", "攻击"]
)
# Returns optimal model based on complexity analysis
```

### ⚡ Async/Concurrent Execution (NEW)
Achieve 30-50% latency reduction through parallel processing:
- **Async LLM Client**: Concurrent API calls with semaphore-based rate limiting
- **Streaming Pipeline**: Overlapping pipeline stages (normalize → translate → QA → export)
- **Backpressure Handling**: Prevents memory overflow under heavy load
- **Configurable Concurrency**: Per-stage limits optimized for I/O vs CPU-bound operations

```python
from src.scripts.async_adapter import process_csv_async

stats = asyncio.run(process_csv_async(
    input_path="data/input.csv",
    output_path="data/output.csv"
))
# Throughput: ~50-100 rows/sec (vs ~20-30 sync)
```

### 📚 Glossary AI System (NEW)
Intelligent glossary matching and correction:
- **Smart Matcher**: Fuzzy matching with 95%+ auto-approval rate for high-confidence matches
- **Auto-Corrector**: Detects and suggests fixes for glossary violations, spelling errors, case issues
- **Russian Declension Support**: Handles case endings for Russian translations
- **Context Validation**: Disambiguates homonyms using surrounding context

```python
from src.scripts.glossary_matcher import GlossaryMatcher
from src.scripts.glossary_corrector import GlossaryCorrector

# Match glossary terms in text
matcher = GlossaryMatcher()
matches = matcher.find_matches("忍者的攻击力很高")

# Detect and correct violations
corrector = GlossaryCorrector()
suggestions = corrector.detect_violations(translation_text)
```

### 💾 Enhanced Response Caching
SQLite-based persistent cache with advanced features:
- **TTL Support**: Configurable expiration (default 7 days)
- **LRU Eviction**: Automatic cleanup when size limit reached
- **Cache Analytics**: Real-time hit/miss tracking with cost savings calculation
- **50%+ Cost Savings** on repeated translations

```bash
# View cache statistics
python scripts/cache_manager.py --stats

# Clear cache before running
python scripts/translate_llm.py --input data.csv --cache-clear
```

## 📊 Production Proven

- ✅ **30k+ rows validated**: $48.44 cost, 99.87% accuracy
- ✅ **Multi-model support**: GPT-4o, Claude Sonnet, Haiku, Kimi-k2.5
- ✅ **Dockerized**: Consistent environment with API key injection
- ✅ **Response Caching**: 50%+ cost reduction on repeated content
- ✅ **Intelligent Routing**: 20-40% additional cost savings
- ✅ **Async Processing**: 30-50% latency reduction
- ✅ **Glossary AI**: 95%+ auto-approval rate for glossary matches

## 🚀 Quick Start

```bash
# Clone & Setup
git clone https://github.com/Charpup/game-localization-mvr.git
cd game-localization-mvr
cp .env.example .env  # Configure your API keys

# Build Docker (required for LLM calls)
docker build -f Dockerfile.gate -t gate_v2 .

# Option 1: Run with intelligent model routing (recommended)
python scripts/translate_llm.py --input data/tokenized.csv --output data/translated.csv --smart-routing

# Option 2: Run with async processing for maximum speed
python scripts/async_adapter.py --input data/input.csv --output data/output.csv --max-concurrent 10

# Option 3: Run full pipeline with Docker
.\scripts\docker_run.ps1 python -u -m scripts.translate_llm --input data/tokenized.csv --output data/translated.csv
```

## 📈 Performance Numbers

| Metric | v1.1.0 | v1.2.0 | Improvement |
|--------|--------|--------|-------------|
| Throughput (rows/sec) | 20-30 | 50-100 | 2-3x |
| Avg Cost per 1k rows | $1.50 | $0.90-1.20 | 20-40% ↓ |
| Glossary Match Accuracy | 85% | 95%+ | +10% |
| Cache Hit Rate | 60% | 75% | +15% |
| First Translation Latency | 120s | 80s | 33% ↓ |

**Cost Breakdown (per 1k rows)**:
- Traditional Outsourcing: $6-10
- v1.1.0 Baseline: $1.50
- v1.2.0 with Routing + Cache: $0.90-1.20

## 💾 Response Caching

The localization pipeline includes a **smart response caching layer** that can reduce LLM costs by **50%+** on repeated translations.

### Configuration

Edit `config/pipeline.yaml`:

```yaml
cache:
  enabled: true
  ttl_days: 7
  max_size_mb: 100
  location: ".cache/translations.db"
```

### Cache Usage

```bash
# Run with cache (default)
python -m src.scripts.translate_llm --input data/input.csv --output data/output.csv

# Run without cache (bypass lookup)
python -m src.scripts.translate_llm --input data/input.csv --output data/output.csv --no-cache

# Clear cache before running
python -m src.scripts.translate_llm --input data/input.csv --output data/output.csv --cache-clear

# View cache statistics
python -m src.scripts.cache_manager --stats

# View cache size
python -m src.scripts.cache_manager --size

# Clear all cache entries
python -m src.scripts.cache_manager --clear
```

### Cache Metrics

During translation, cache statistics are displayed:

```
📊 Cache Statistics:
   Hits: 150
   Misses: 50
   Hit Rate: 75.00%
   💰 Cost Savings: 75.0% (cache hits = zero cost)
   Cache Size: 12.34 MB / 100 MB
```

## 🧠 Model Routing

Intelligent model selection based on content complexity:

```bash
# Analyze text complexity
python -m src.scripts.model_router --analyze "Your text here"

# Select best model for text
python -m src.scripts.model_router --select "Your text here" --step translate

# View routing statistics
python -m src.scripts.model_router --stats
```

**Routing Decision Factors**:
- Text length (20% weight)
- Placeholder density (25% weight)
- Glossary term density (25% weight)
- Special character density (15% weight)
- Historical failure rate (15% weight)

## ⚡ Async Processing

High-performance async execution for large datasets:

```bash
# Process with async pipeline
python -m src.scripts.async_adapter \
  --input data/large_file.csv \
  --output data/output.csv \
  --max-concurrent 10 \
  --buffer-size 100

# Run benchmark
python -m src.scripts.async_adapter \
  --input data/test.csv \
  --output data/out.csv \
  --benchmark
```

## 🔍 Monitoring & Debugging

### Cost Tracking

Enable LLM call tracing:

```python
from trace_config import setup_trace_path

# At script start
setup_trace_path(output_dir="data/my_test")
# All LLM calls logged to data/my_test/llm_trace.jsonl
```

View cost statistics:

```bash
python -m src.scripts.metrics_aggregator \
  --trace-path data/my_test/llm_trace.jsonl \
  --output data/my_test/metrics_report.md
```

Output example:

```
总 Tokens: 10,145,141
估算费用: $10.87 USD
```

### Progress Monitoring

All long-running tasks display real-time progress:

```
[translate] Batch 10/120 | 250/3000 rows (8.3%) | Δt: 5.5s | Total: 61.1s
```

- **Δt**: Previous batch duration
- **Total**: Elapsed time since task start

## 📚 Documentation

- **[Quick Start Guide](docs/QUICK_START.md)** - 5-minute getting started
- **[API Documentation](docs/API.md)** - Complete API reference
- **[Configuration Guide](docs/CONFIGURATION.md)** - Full configuration options
- **[For LLM Agents](docs/WORKSPACE_RULES.md)** - Agent-specific instructions
- **[中文文档](README_zh.md)** - Chinese documentation

## 🛠️ Troubleshooting

**Q: API Key injection fails?**

A: Use provided Docker scripts:

```powershell
# Windows
.\scripts\docker_run.ps1 python scripts/translate_llm.py ...

# Linux/Mac
./scripts/docker_run.sh python scripts/translate_llm.py ...
```

**Q: Long text causes token limit errors?**

A: Long text (>500 chars) is automatically isolated with `is_long_text=1` flag.

**Q: Costs exceed budget?**

A: Check `metrics_report.md` to identify high-cost stages. Enable model routing and caching for savings.

**Q: Tags corrupted during translation?**

A: HTML/Unity tags are automatically protected during jieba segmentation (v1.1.0+).

**Q: How to update from v1.1.0?**

A: See [CHANGELOG.md](CHANGELOG.md) for migration guide.

## 📄 License

MIT License

---

**Need LLM API?** Try [APIYi](https://api.apiyi.com/register/?aff_code=8Via)
