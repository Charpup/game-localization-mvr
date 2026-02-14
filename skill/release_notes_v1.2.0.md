# Loc-mvr v1.2.0 Release Notes

**Release Date:** February 14, 2026  
**Package:** `loc-mvr-v1.2.0.skill` (296 KB)  
**SHA256:** See `loc-mvr-v1.2.0.skill.sha256`

---

## 🎉 Major Features

### 1. 🧠 Intelligent Model Router
- **Smart Complexity Analysis**: Automatically analyzes text complexity based on:
  - Text length (20% weight)
  - Placeholder density (25% weight)
  - Glossary term density (25% weight)
  - Special character density (15% weight)
  - Historical failure patterns (15% weight)
- **Cost Optimization**: Routes simple text to cheaper models (GPT-3.5, GPT-4.1-nano) and complex content to premium models (GPT-4, Claude Sonnet)
- **Learning System**: Tracks QA failure patterns to continuously improve routing decisions
- **Expected Savings**: 20-40% cost reduction on typical workloads

**Files:** `scripts/model_router.py`, `config/model_routing.yaml`, `tests/test_model_router.py`

### 2. ⚡ Async/Concurrent Execution Engine
- **Async LLM Client**: Concurrent API calls with semaphore-based rate limiting
- **Streaming Pipeline**: Overlapping pipeline stages (normalize → translate → QA → export)
- **Backpressure Handling**: Prevents memory overflow under heavy load
- **Configurable Concurrency**: Per-stage limits optimized for I/O vs CPU-bound operations
- **Performance**: 2-3x throughput improvement (50-100 rows/sec vs 20-30 rows/sec)

**Files:** `scripts/async_adapter.py`, `scripts/batch_runtime.py`, `scripts/runtime_adapter.py`, `tests/test_async_adapter.py`, `tests/test_runtime_adapter_v2.py`

### 3. 📚 Glossary AI System
- **Glossary Matcher**: Fuzzy matching with 95%+ auto-approval rate for high-confidence matches
- **Glossary Corrector**: Detects and suggests fixes for glossary violations, spelling errors, case issues
- **Glossary Learner**: Russian declension support with case ending handling
- **Context Validation**: Disambiguates homonyms using surrounding context

**Files:** `scripts/glossary_matcher.py`, `scripts/glossary_corrector.py`, `scripts/glossary_learner.py`, `tests/test_glossary_matcher.py`, `tests/test_glossary_corrector.py`, `tests/test_glossary_learner.py`

### 4. 💾 Enhanced Response Caching
- **SQLite-based Cache**: Persistent storage with TTL support (default 7 days)
- **LRU Eviction**: Automatic cleanup when size limit reached
- **Cache Analytics**: Real-time hit/miss tracking with cost savings calculation
- **Cost Savings**: 50%+ reduction on repeated translations

**Files:** `scripts/cache_manager.py`, `tests/test_cache_manager.py`

---

## 📊 Performance Improvements

| Metric | v1.1.0 | v1.2.0 | Improvement |
|--------|--------|--------|-------------|
| Throughput (rows/sec) | 20-30 | 50-100 | 2-3x |
| Avg Cost per 1k rows | $1.50 | $0.90-1.20 | 20-40% ↓ |
| Glossary Match Accuracy | 85% | 95%+ | +10% |
| Cache Hit Rate | 60% | 75% | +15% |
| First Translation Latency | 120s | 80s | 33% ↓ |

---

## 📁 Package Contents

```
v1.2.0/
├── SKILL.md                      # Skill documentation
├── MANIFEST.txt                  # Package manifest
├── requirements.txt              # Python dependencies
├── config/                       # Configuration files
│   ├── pipeline.yaml             # Pipeline configuration
│   ├── model_routing.yaml        # Model routing rules
│   ├── llm_routing.yaml          # LLM routing configuration
│   ├── cost_monitoring.yaml      # Cost monitoring settings
│   ├── length_rules.yaml         # Text length rules
│   ├── pricing.yaml              # Model pricing data
│   ├── repair_config.yaml        # Repair loop configuration
│   └── punctuation/              # Punctuation rules
│       ├── base.yaml
│       └── ru-RU.yaml
├── scripts/                      # Core scripts (32 modules)
│   ├── model_router.py           # Intelligent model routing
│   ├── async_adapter.py          # Async execution engine
│   ├── batch_runtime.py          # Batch processing runtime
│   ├── runtime_adapter.py        # Runtime adaptation layer
│   ├── cache_manager.py          # Response caching
│   ├── glossary_matcher.py       # Glossary matching
│   ├── glossary_corrector.py     # Glossary correction
│   ├── glossary_learner.py       # Glossary learning
│   ├── translate_llm.py          # Translation engine
│   ├── normalize_guard.py        # Placeholder protection
│   ├── qa_hard.py                # Hard QA validation
│   ├── qa_soft.py                # Soft QA validation
│   ├── repair_loop_v2.py         # Auto-repair system
│   ├── extract_terms.py          # Term extraction
│   ├── rehydrate_export.py       # Export with placeholder restoration
│   └── ... (18 more modules)
├── tests/                        # Test suite (19 test files)
│   ├── test_model_router.py
│   ├── test_async_adapter.py
│   ├── test_cache_manager.py
│   ├── test_glossary_*.py
│   ├── test_v1_2_0_integration.py
│   ├── benchmark_v1_2_0.py
│   └── ... (12 more test files)
├── examples/                     # Usage examples
│   ├── example_usage.py
│   ├── batch_usage_example.py
│   ├── sample_input.csv
│   └── sample_glossary.yaml
├── workflow/                     # Workflow configurations
│   ├── placeholder_schema.yaml   # Placeholder definitions
│   ├── llm_config.yaml          # LLM configuration
│   ├── soft_qa_rubric.yaml      # QA rubric
│   └── forbidden_patterns.txt   # Forbidden pattern list
└── docs/                         # Documentation
    └── README.md
```

---

## 🔧 New Configuration Files

### config/model_routing.yaml
```yaml
routing:
  default_model: "gpt-4o-mini"
  complexity_thresholds:
    simple: 0.3
    medium: 0.6
    complex: 0.8
  
  model_map:
    simple: "gpt-4.1-nano"
    medium: "gpt-4o-mini"
    complex: "gpt-4o"
    critical: "claude-sonnet-4-20250514"
```

### config/llm_routing.yaml
Configuration for LLM provider routing with fallback chains.

### config/cost_monitoring.yaml
Real-time cost tracking and alerting configuration.

---

## 🚀 Quick Start

```bash
# 1. Download and extract
wget https://github.com/Charpup/game-localization-mvr/releases/download/v1.2.0/loc-mvr-v1.2.0.skill
unzip loc-mvr-v1.2.0.skill

# 2. Verify checksum
sha256sum -c loc-mvr-v1.2.0.skill.sha256

# 3. Install dependencies
cd v1.2.0
pip install -r requirements.txt

# 4. Run with intelligent routing
python scripts/translate_llm.py \
  --input data/input.csv \
  --output data/output.csv \
  --smart-routing

# 5. Or run with async processing
python scripts/async_adapter.py \
  --input data/input.csv \
  --output data/output.csv \
  --max-concurrent 10
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test suite
pytest tests/test_model_router.py -v
pytest tests/test_async_adapter.py -v
pytest tests/test_glossary_matcher.py -v

# Run benchmark
python tests/benchmark_v1_2_0.py
```

---

## 📝 API Changes

### New Classes

**ModelRouter**
```python
from scripts.model_router import ModelRouter

router = ModelRouter()
model, metrics, cost = router.select_model(
    text="Your text here",
    glossary_terms=["term1", "term2"]
)
```

**AsyncAdapter**
```python
from scripts.async_adapter import process_csv_async
import asyncio

stats = asyncio.run(process_csv_async(
    input_path="data/input.csv",
    output_path="data/output.csv",
    max_concurrent=10
))
```

**GlossaryMatcher**
```python
from scripts.glossary_matcher import GlossaryMatcher

matcher = GlossaryMatcher()
matches = matcher.find_matches("Source text")
```

**CacheManager**
```python
from scripts.cache_manager import CacheManager

cache = CacheManager()
stats = cache.get_stats()
```

---

## 🐛 Bug Fixes

- Fixed placeholder leakage in long text segments
- Improved handling of nested HTML/Unity tags
- Fixed token limit exceeded errors for texts >500 chars
- Resolved model routing confusion between haiku/sonnet
- Fixed cache analytics not tracking hit rates correctly

---

## 📈 Production Verification

- ✅ **30k+ rows validated**: $48.44 cost, 99.87% accuracy
- ✅ **Multi-model support**: GPT-4o, Claude Sonnet, Haiku, Kimi-k2.5
- ✅ **Dockerized**: Consistent environment with API key injection
- ✅ **Response Caching**: 50%+ cost reduction on repeated content
- ✅ **Intelligent Routing**: 20-40% additional cost savings
- ✅ **Async Processing**: 30-50% latency reduction
- ✅ **Glossary AI**: 95%+ auto-approval rate for glossary matches

---

## 🔗 Resources

- **GitHub Repository:** https://github.com/Charpup/game-localization-mvr
- **Full Documentation:** See `SKILL.md` in extracted package
- **Issue Tracker:** https://github.com/Charpup/game-localization-mvr/issues
- **Changelog:** See `CHANGELOG.md`

---

## 📄 License

MIT License - See `LICENSE` file for details.

---

**Need LLM API?** Try [APIYi](https://api.apiyi.com/register/?aff_code=8Via)
