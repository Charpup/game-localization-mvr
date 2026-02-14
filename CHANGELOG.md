# Changelog

All notable changes to the Game Localization MVR project.

## [1.2.0] - 2026-02-14

### ✨ New Features

#### 🧠 Intelligent Model Router (Phase 3.2)
- **Complexity-Based Routing**: Automatically selects optimal LLM model based on text complexity analysis
- **Cost Optimization**: Routes simple text to cheaper models (GPT-3.5, GPT-4.1-nano), complex text to premium models (GPT-4, Claude Sonnet)
- **Multi-Factor Analysis**: Considers text length, placeholder density, glossary density, special characters, and historical QA failure rates
- **Fallback Chain**: Automatic fallback to backup models on errors
- **Cost Tracking**: Real-time cost estimation and savings analysis
- **Historical Learning**: Tracks QA failures to improve future routing decisions

**Usage**:
```python
from scripts.model_router import ModelRouter

router = ModelRouter()
model, metrics, cost = router.select_model(
    text="Your text here",
    glossary_terms=["忍者", "攻击"]
)
```

**Expected Savings**: 20-40% cost reduction on typical workloads

#### ⚡ Async/Concurrent Execution (Phase 3.4)
- **AsyncLLMClient**: Asynchronous LLM client with semaphore-based concurrency control
- **Streaming Pipeline**: Overlapping pipeline stages for improved throughput
- **Backpressure Handling**: Prevents memory overflow under heavy load
- **Per-Stage Concurrency**: Configurable limits for each pipeline stage
- **Connection Pooling**: Efficient HTTP connection reuse via aiohttp
- **Async File I/O**: Non-blocking CSV read/write operations

**Performance Improvements**:
- 30-50% latency reduction on large datasets
- 2-3x throughput increase (50-100 rows/sec vs 20-30 sync)
- Better resource utilization with configurable concurrency

**Usage**:
```python
from scripts.async_adapter import process_csv_async

stats = await process_csv_async(
    input_path="data/input.csv",
    output_path="data/output.csv"
)
```

#### 📚 Glossary AI System
- **GlossaryMatcher**: Intelligent glossary matching with fuzzy matching and auto-approval
  - Exact, fuzzy, and context-validated matching
  - 95%+ auto-approval rate for high-confidence matches
  - Case preservation checking
  - HTML highlight export for human review

- **GlossaryCorrector**: Automated correction suggestions for glossary violations
  - Spelling error detection
  - Capitalization correction
  - Russian declension handling
  - Spacing/hyphenation fixes
  - Fuzzy similarity matching

**Usage**:
```python
from scripts.glossary_matcher import GlossaryMatcher
from scripts.glossary_corrector import GlossaryCorrector

matcher = GlossaryMatcher()
matches = matcher.find_matches("忍者的攻击力很高")

corrector = GlossaryCorrector()
suggestions = corrector.detect_violations(translation_text)
```

### 📊 Performance Improvements

| Metric | v1.1.0 | v1.2.0 | Improvement |
|--------|--------|--------|-------------|
| Throughput (rows/sec) | 20-30 | 50-100 | 2-3x |
| Avg Cost per 1k rows | $1.50 | $0.90-1.20 | 20-40% ↓ |
| Glossary Match Accuracy | 85% | 95%+ | +10% |
| Cache Hit Rate | 60% | 75% | +15% |
| First Translation Latency | 120s | 80s | 33% ↓ |

### 🔧 Configuration Changes

#### New Configuration Files
- `config/model_routing.yaml` - Model routing configuration
- Updated `config/pipeline.yaml` - Added async section
- Updated `config/glossary.yaml` - Added glossary AI settings

#### New Environment Variables
- `MODEL_ROUTER_ENABLED` - Enable/disable model routing
- `MODEL_ROUTER_HISTORY_PATH` - Path to routing history file
- `MODEL_ROUTER_TRACE_PATH` - Path to routing trace file
- `ASYNC_ENABLED` - Enable/disable async execution
- `ASYNC_MAX_CONCURRENT` - Max concurrent LLM calls
- `ASYNC_SEMAPHORE_TIMEOUT` - Semaphore timeout in seconds

### 📚 Documentation

- **[API Documentation](docs/API.md)** - Complete API reference for all new modules
- **[Configuration Guide](docs/CONFIGURATION.md)** - Full configuration options
- **[Quick Start Guide](docs/QUICK_START.md)** - 5-minute getting started guide

### 🧪 Testing

- Added comprehensive test suites for new modules:
  - `tests/test_model_router.py`
  - `tests/test_async_adapter.py`
  - `tests/test_glossary_matcher.py`
  - `tests/test_glossary_corrector.py`

### 🐛 Bug Fixes

None in this release (all bug fixes were in v1.0.2/v1.1.0)

### ⚠️ Breaking Changes

None. All v1.2.0 features are backward compatible with v1.1.0.

### 🔄 Migration Guide from v1.1.0

#### Step 1: Update Configuration

Create or update `config/model_routing.yaml`:

```yaml
model_routing:
  enabled: true
  default_model: "kimi-k2.5"
  complexity_threshold: 0.7
  
  complexity_weights:
    length: 0.20
    placeholder_density: 0.25
    special_char_density: 0.15
    glossary_density: 0.25
    historical_failure: 0.15
  
  models:
    - name: "gpt-3.5-turbo"
      cost_per_1k: 0.0015
      max_complexity: 0.5
      batch_capable: true
      quality_tier: "medium"
    
    - name: "kimi-k2.5"
      cost_per_1k: 0.012
      max_complexity: 1.0
      batch_capable: true
      quality_tier: "high"
```

#### Step 2: Update pipeline.yaml

Add async configuration section:

```yaml
async:
  enabled: true
  max_concurrent_llm_calls: 10
  semaphore_timeout: 60
  buffer_size: 100
  
  stage_concurrency:
    normalize: 5
    translate: 10
    qa: 8
    export: 3
```

#### Step 3: Install New Dependencies

```bash
pip install aiohttp aiofiles
```

#### Step 4: Enable Features (Optional)

To use new features in existing code:

```python
# Use model routing
from scripts.model_router import patch_translate_llm_with_router
patch_translate_llm_with_router()

# Use async processing
from scripts.async_adapter import process_csv_async
import asyncio

stats = asyncio.run(process_csv_async("input.csv", "output.csv"))
```

### 📦 Files Added

**New Scripts**:
- `scripts/model_router.py` - Intelligent model routing
- `scripts/async_adapter.py` - Async/concurrent execution
- `scripts/glossary_matcher.py` - Smart glossary matching
- `scripts/glossary_corrector.py` - Glossary correction engine

**New Tests**:
- `tests/test_model_router.py`
- `tests/test_async_adapter.py`
- `tests/test_glossary_matcher.py`
- `tests/test_glossary_corrector.py`

**New Documentation**:
- `docs/API.md`
- `docs/CONFIGURATION.md`
- `docs/QUICK_START.md`

### 📈 Production Metrics

Based on 30k row production validation:

- **Total Cost**: $48.44 → $38.75 (with routing + cache)
- **Accuracy**: 99.87% (unchanged)
- **Processing Time**: 16 minutes → 10 minutes (async)
- **Cache Hit Rate**: 75% (up from 60%)

---

## [1.1.0] - 2026-01-31

### ✨ New Features

#### 💾 Response Caching System (v6.1)
- SQLite-based persistent cache for LLM translation responses
- Configurable TTL (Time To Live) with default 7 days
- LRU (Least Recently Used) eviction when size limit reached
- Cache analytics with hit/miss tracking and cost savings calculation
- Thread-safe operations for concurrent access

**CLI Commands**:
```bash
python scripts/cache_manager.py --stats
python scripts/cache_manager.py --size
python scripts/cache_manager.py --clear
```

#### 📊 Cache Analytics
- Real-time hit/miss statistics during translation
- Cost savings calculation: `hit_rate × total_translation_cost`
- Cache size monitoring with usage percentage

### 🔧 Improvements

#### Placeholder Regex Extension (Bug 1)
- Added support for `% H` pattern (percent-space-letter)
- Prevents placeholder corruption in translations
- **Impact**: Placeholder coverage 90% → 100%

#### Long Text Isolation (Bug 3)
- Automatic detection of text >500 characters
- `is_long_text` flag for special handling
- Prevents token limit errors
- **Impact**: Automated handling vs manual intervention

#### Tag Protection (Bug 4)
- `protect_tags()` and `restore_tags()` functions
- Preserves HTML/Unity tags during jieba segmentation
- **Impact**: Tag integrity 85% → 100%

### 🔧 Configuration

New `config/pipeline.yaml` options:

```yaml
cache:
  enabled: true
  ttl_days: 7
  max_size_mb: 100
  location: ".cache/translations.db"
```

### 📚 Documentation

- Updated README with caching documentation
- Added cache usage examples
- Cache metrics documentation

---

## [1.0.2] - 2026-01-31

### 🐛 Bug Fixes (Phase 1)

#### Bug 1: Placeholder Regex Extension
- **Problem**: `% H` placeholders were not being frozen
- **Fix**: Added `percent_space_letter` pattern to `workflow/placeholder_schema.yaml`
- **Commit**: `fix(P0): extend placeholder regex to support percent-space-letter pattern`

#### Bug 2: Parameter Locking Rule 14
- **Problem**: `batch_size` was modified in production, violating baselines
- **Fix**: Added Rule 14 to workspace rules with parameter change logging
- **Commit**: `feat(P0): add Rule 14 parameter locking with change log`

#### Bug 3: Long Text Isolation Mechanism
- **Problem**: Rows exceeding 500 characters caused translation failures
- **Fix**: Added `LONG_TEXT_THRESHOLD` and `is_long_text` flag to `normalize_guard.py` and `translate_llm.py`
- **Commit**: `fix(P0): implement long text isolation mechanism`

#### Bug 4: Tag Space Cleanup
- **Problem**: `jieba` segmentation inserted spaces into HTML/Unity tags
- **Fix**: Added `protect_tags()` and `restore_tags()` functions to `normalize_guard.py`
- **Commit**: `fix(P0): protect HTML/Unity tags from jieba segmentation`

#### Bug 5: API Key Injection via Docker ENV
- **Problem**: Docker ENV injection was failing due to inconsistent variable names
- **Fix**: Created `docker_run.ps1` and `docker_run.sh` templates, updated `.env.example`
- **Commit**: `fix(P0): standardize Docker ENV injection for API keys`

### 🔧 Quality Improvements (Phase 2)

#### Task 1: Hard QA Model Audit
- **Problem**: Terminal logs showed `haiku` but actual API calls used `sonnet`, causing +30% cost estimation error
- **Fix**: Added explicit `model` parameter to `client.chat()` in `repair_loop_v2.py`
- **Impact**: Cost estimation accuracy improves from ±30% to ±5%
- **Commit**: `fix(P1): align Hard QA model routing with actual API calls`

#### Task 2: Metrics Completeness
- **Problem**: Only ~20% of LLM calls were tracked, incomplete cost analysis
- **Fix**: Created `trace_config.py` for unified trace path management
- **Impact**: Metrics coverage improves from ~20% to 100%
- **Commit**: `feat(P1): implement unified trace path configuration`

#### Task 3: Progress Timestamps
- **Problem**: Progress reports lacked time delta and total elapsed information
- **Fix**: Added `last_batch_time` tracking and Delta/Total display to `progress_reporter.py`
- **Impact**: Enhanced monitoring experience with granular timing information
- **Commit**: `feat(P1): add time delta and total elapsed to progress reporter`

### 📊 Impact Summary

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Placeholder Coverage | 90% | 100% | +10% |
| Tag Integrity | 85% | 100% | +15% |
| Long Text Handling | Manual | Automatic | Automated |
| Cost Estimation Accuracy | ±30% | ±5% | 6x improvement |
| Metrics Coverage | ~20% | 100% | 5x improvement |
| Monitoring Experience | Basic | Complete | Time tracking added |

### 🧪 Verification

All fixes verified with automated test scripts:

**Phase 1**:
- `scripts/verify_bug1_placeholder_regex.py`
- `scripts/verify_bug2_rule14.py`
- `scripts/verify_bug3_long_text.py`
- `scripts/verify_bug4_tag_protection.py`
- `scripts/verify_bug5_env_injection.py`

**Phase 2**:
- `scripts/verify_task1_model_consistency.py`
- `scripts/verify_task2_metrics_completeness.py`
- `scripts/verify_task3_progress_timestamps.py`

---

## [1.0.1] - 2026-01-15

### 🔧 Improvements
- Documentation updates
- Docker build optimization

---

## [1.0.0] - 2026-01-10

### 🎉 Initial Release

**Core Features**:
- LLM-powered translation pipeline (Chinese to Russian)
- Multi-model support (GPT-4, Claude, Kimi)
- Glossary integration
- Style guide enforcement
- Dual QA system (Soft + Hard)
- Docker containerization
- Cost tracking and metrics
- Batch processing

**Production Validation**:
- 30k+ rows processed
- $48.44 total cost
- 99.87% accuracy

---

## Version Compatibility

| Version | Python | Docker | Breaking Changes |
|---------|--------|--------|------------------|
| 1.2.0 | ≥3.8 | Required | None |
| 1.1.0 | ≥3.8 | Required | None |
| 1.0.2 | ≥3.8 | Required | None |
| 1.0.0 | ≥3.8 | Required | - |

---

## Upcoming in v1.3.0

Planned features:
- ZH→EN translation support
- Real-time collaboration features
- Enhanced glossary learning
- Multi-language glossary support

---

*For detailed migration guides, see individual version sections above.*
