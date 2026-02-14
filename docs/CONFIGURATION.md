# Configuration Guide

Complete configuration reference for Game Localization MVR v1.2.0.

## Table of Contents

- [Overview](#overview)
- [Pipeline Configuration](#pipeline-configuration)
- [Cache Configuration](#cache-configuration)
- [Model Routing Configuration](#model-routing-configuration)
- [Glossary AI Configuration](#glossary-ai-configuration)
- [Async/Concurrency Settings](#asyncconcurrency-settings)
- [Environment Variables](#environment-variables)
- [Configuration Examples](#configuration-examples)

---

## Overview

The localization pipeline uses YAML-based configuration files stored in the `config/` directory:

```
config/
├── pipeline.yaml          # Main pipeline configuration
├── model_routing.yaml     # Model routing settings
├── glossary.yaml          # Glossary AI settings
├── cost_monitoring.yaml   # Cost tracking configuration
└── length_rules.yaml      # Text length rules
```

Configuration files are loaded automatically by the respective modules. You can override settings via:
1. Configuration files (persistent)
2. Environment variables (runtime override)
3. Constructor arguments (per-instance override)

---

## Pipeline Configuration

File: `config/pipeline.yaml`

### Async Execution Settings

```yaml
# =============================================================================
# Async Execution Settings
# =============================================================================
async:
  # Master switch for async execution
  enabled: true
  
  # Maximum concurrent LLM calls globally
  # Higher = more parallelism but more memory/CPU usage
  max_concurrent_llm_calls: 10
  
  # Semaphore acquisition timeout (seconds)
  # Prevents indefinite waiting under heavy load
  semaphore_timeout: 60
  
  # Pipeline buffer size between stages
  # Larger buffers allow more overlap but use more memory
  buffer_size: 100
  
  # Maximum worker threads for CPU-bound operations
  max_workers: 4
  
  # Pipeline stages in execution order
  pipeline_stages:
    - normalize
    - translate
    - qa
    - export
  
  # Per-stage concurrency limits
  # Allows fine-tuning based on stage characteristics
  stage_concurrency:
    normalize: 5      # CPU-bound, moderate parallelism
    translate: 10     # IO-bound (LLM calls), high parallelism
    qa: 8             # IO-bound but more complex prompts
    export: 3         # Disk IO, limited parallelism
  
  # Enable streaming pipeline
  # Start next stage before previous completes for better throughput
  enable_streaming: true
  
  # Backpressure handling
  # When enabled, slow consumers block fast producers to prevent OOM
  backpressure_enabled: true
  
  # Maximum queue size for backpressure
  queue_maxsize: 200
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | `true` | Master switch for async execution |
| `max_concurrent_llm_calls` | int | `10` | Global limit on concurrent LLM calls |
| `semaphore_timeout` | int | `60` | Max seconds to wait for semaphore |
| `buffer_size` | int | `100` | Items buffered between pipeline stages |
| `max_workers` | int | `4` | Thread pool size for CPU-bound tasks |
| `enable_streaming` | bool | `true` | Enable pipeline stage overlap |
| `backpressure_enabled` | bool | `true` | Block producers when consumers are slow |
| `queue_maxsize` | int | `200` | Max items in backpressure queue |

### Performance Tuning

```yaml
# =============================================================================
# Performance Tuning
# =============================================================================
performance:
  # Batch size for reading/writing CSV files
  io_batch_size: 1000
  
  # Chunk size for async generators
  generator_chunk_size: 100
  
  # Connection pool settings for aiohttp
  connection_pool:
    total_limit: 100
    limit_per_host: 20
    enable_cleanup_closed: true
    force_close: false
  
  # Timeout settings (seconds)
  timeouts:
    connect: 10
    read: 60
    total: 120
  
  # Retry configuration for failed async operations
  retry:
    max_attempts: 3
    backoff_base: 1.0
    backoff_max: 30.0
```

### Monitoring & Observability

```yaml
# =============================================================================
# Monitoring & Observability
# =============================================================================
monitoring:
  # Enable detailed tracing
  enable_tracing: true
  
  # Trace file path
  trace_path: data/async_trace.jsonl
  
  # Progress reporting interval (seconds)
  progress_interval: 5
  
  # Metrics collection
  collect_metrics:
    latency_histogram: true
    throughput_gauge: true
    queue_depth: true
    semaphore_wait_time: true
```

### Resource Limits

```yaml
# =============================================================================
# Resource Limits
# =============================================================================
resources:
  # Maximum memory usage (MB) - triggers backpressure
  max_memory_mb: 2048
  
  # Maximum open file descriptors
  max_open_files: 100
  
  # Semaphore priority (fairness)
  # When true, acquires are served in FIFO order
  fair_semaphore: true
```

---

## Cache Configuration

File: `config/pipeline.yaml` (under `cache:` section)

```yaml
cache:
  enabled: true
  ttl_days: 7
  max_size_mb: 100
  location: ".cache/translations.db"
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | `true` | Enable/disable caching |
| `ttl_days` | int | `7` | Cache entry lifetime in days |
| `max_size_mb` | int | `100` | Maximum cache size in MB |
| `location` | str | `.cache/translations.db` | SQLite database path |

### Cache Key Generation

Cache keys are generated using:
```
SHA256(source_text + glossary_hash + model_name)
```

This ensures:
- Same text with different glossaries = different cache entries
- Same text with different models = different cache entries
- Changes to glossary or model trigger cache refresh

### LRU Eviction

When cache exceeds `max_size_mb`:
1. Entries are evicted by least recently accessed (LRU)
2. Eviction continues until cache is below 90% of max size
3. Eviction statistics are tracked and reported

### CLI Cache Management

```bash
# View cache statistics
python scripts/cache_manager.py --stats

# View cache size
python scripts/cache_manager.py --size

# Clear all cache entries
python scripts/cache_manager.py --clear
```

---

## Model Routing Configuration

File: `config/model_routing.yaml`

### Main Settings

```yaml
model_routing:
  enabled: true
  default_model: "kimi-k2.5"
  complexity_threshold: 0.7
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `enabled` | bool | `true` | Enable model routing |
| `default_model` | str | `kimi-k2.5` | Fallback model when routing fails |
| `complexity_threshold` | float | `0.7` | Threshold for complex text detection |

### Complexity Analysis Weights

```yaml
  # Complexity analysis weights
  # These determine how much each factor contributes to complexity score
  complexity_weights:
    length: 0.20           # Text length contribution
    placeholder_density: 0.25  # Placeholder density contribution
    special_char_density: 0.15 # Special character density contribution
    glossary_density: 0.25     # Glossary term density contribution
    historical_failure: 0.15   # Historical QA failure rate contribution
```

Weights must sum to 1.0. Adjust based on your content characteristics.

### Length Thresholds

```yaml
  # Length thresholds for complexity scoring
  length_thresholds:
    short: 50      # chars - simple text (score: 0.1)
    medium: 150    # chars - moderate complexity (score: 0.3)
    long: 300      # chars - high complexity (score: 0.6)
    very_long: 500 # chars - very high complexity (score: 0.7+)
```

### Model Definitions

```yaml
  # Available models with routing parameters
  models:
    - name: "gpt-3.5-turbo"
      cost_per_1k: 0.0015
      max_complexity: 0.5
      batch_capable: true
      quality_tier: "medium"
      fallback_to: null
      description: "Cheap model for simple translations"
    
    - name: "gpt-4.1-nano"
      cost_per_1k: 0.001
      max_complexity: 0.4
      batch_capable: true
      quality_tier: "low"
      fallback_to: "gpt-4.1-mini"
      description: "Ultra-cheap for very simple text"
    
    - name: "kimi-k2.5"
      cost_per_1k: 0.012
      max_complexity: 1.0
      batch_capable: true
      quality_tier: "high"
      fallback_to: null
      description: "Primary high-quality model"
```

| Parameter | Type | Description |
|-----------|------|-------------|
| `name` | str | Model identifier |
| `cost_per_1k` | float | Cost per 1K tokens in USD |
| `max_complexity` | float | Maximum complexity this model can handle (0.0-1.0) |
| `batch_capable` | bool | Whether model supports batch processing |
| `quality_tier` | str | `low`, `medium`, or `high` |
| `fallback_to` | str | Model to use if this one fails |

### Step Overrides

```yaml
  # Step-specific routing overrides
  step_overrides:
    translate:
      use_cheaper_for_simple: true
      simple_threshold: 0.3
    
    soft_qa:
      min_quality_tier: "medium"
    
    repair_hard:
      min_quality_tier: "high"
    
    glossary_translate:
      use_cheaper_for_simple: true
      simple_threshold: 0.4
```

Override routing behavior for specific pipeline steps.

### Historical Tracking

```yaml
  # Historical tracking configuration
  history:
    enabled: true
    history_path: "data/model_router_history.json"
    failure_weight: 0.15
    max_history_age_days: 30
```

Tracks QA failure patterns to improve routing decisions over time.

### Cost Tracking

```yaml
  # Cost tracking and reporting
  cost_tracking:
    enabled: true
    trace_path: "data/model_router_trace.jsonl"
    report_interval: 100
```

### Fallback Configuration

```yaml
  # Fallback configuration
  fallback:
    enabled: true
    max_attempts: 2
    trigger_on:
      - timeout
      - network
      - upstream
      - parse
```

---

## Glossary AI Configuration

File: `config/glossary.yaml`

### Glossary Learning System

```yaml
glossary_learning:
  # Master switch - enable/disable learning system
  enabled: true
  
  # Minimum number of feedback entries before auto-approval is considered
  min_feedback_count: 5
  
  # Rate at which confidence is updated (0.0-1.0)
  # Higher values = faster adaptation to new feedback
  confidence_update_rate: 0.1
  
  # Automatically suggest new terms from project data
  auto_suggest_new_terms: true
  
  # Minimum confidence threshold for term discovery
  term_discovery_threshold: 0.8
  
  # Path to store learning data
  learning_data_path: "learning_data/"
```

### Glossary Matching

```yaml
glossary_matching:
  enabled: true
  auto_approve_threshold: 0.95      # Auto-approve above this confidence
  suggest_threshold: 0.90           # Suggest above this confidence
  fuzzy_threshold: 0.90             # Minimum fuzzy match similarity
  context_window: 10                # Words of context to capture
  case_sensitive: false
  preserve_case_check: true
  multi_word_phrase_matching: true
  target_auto_approval_rate: 0.30
  max_false_positive_rate: 0.01
  
  scoring_weights:
    exact_match: 1.00
    fuzzy_match: 0.95
    context_validation: 0.90
    partial_match: 0.70
    case_preservation: 0.05
```

### Glossary Corrections

```yaml
glossary_corrections:
  enabled: true
  suggest_threshold: 0.90           # Minimum confidence to suggest
  auto_apply_threshold: 0.99        # Minimum confidence to auto-apply
  preserve_case: true
  language_rules:
    ru: 'russian_declensions'
  spelling_variants:
    fuzzy_match_threshold: 0.85
```

### TF-IDF Configuration

```yaml
  tfidf:
    min_term_length: 2
    max_term_length: 4
    min_document_frequency: 3
    top_candidates_limit: 50
```

### Pattern Mining

```yaml
  pattern_mining:
    min_occurrences: 3
    extract_brackets: true
    extract_proper_nouns: true
```

### Bayesian Calibration

```yaml
  bayesian_calibration:
    prior_confidence: 0.5
    historical_weight: 0.7
    min_samples_for_reliable_estimate: 10
```

### Weekly Reporting

```yaml
  reporting:
    auto_generate: true
    report_day: 0  # 0=Monday, 6=Sunday
    target_improvement_rate: 5.0
    alert_threshold: 3.0
```

---

## Async/Concurrency Settings

### Semaphore Configuration

Semaphores control concurrent access to resources:

```python
# Global semaphore (all LLM calls)
max_concurrent_llm_calls: 10

# Per-stage semaphores
stage_concurrency:
  normalize: 5      # CPU-bound
  translate: 10     # IO-bound
  qa: 8             # IO-bound, complex
  export: 3         # Disk IO
```

**Guidelines**:
- Set `translate` higher for more parallel LLM calls
- Keep `normalize` moderate (CPU-bound)
- Limit `export` to prevent disk contention

### Backpressure

When `backpressure_enabled: true`:
1. Fast producers block when queue is full
2. Prevents memory overflow
3. Ensures system stability under load

```yaml
backpressure_enabled: true
queue_maxsize: 200
```

**Tuning**:
- Increase `queue_maxsize` for bursty workloads
- Decrease for memory-constrained environments

### Connection Pooling

```yaml
connection_pool:
  total_limit: 100
  limit_per_host: 20
  enable_cleanup_closed: true
  force_close: false
```

| Parameter | Description |
|-----------|-------------|
| `total_limit` | Max total connections across all hosts |
| `limit_per_host` | Max connections per host |
| `enable_cleanup_closed` | Clean up closed connections |
| `force_close` | Force close connections after use |

---

## Environment Variables

### LLM Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_BASE_URL` | API base URL | - |
| `LLM_API_KEY` | API key | - |
| `LLM_API_KEY_FILE` | Path to file containing API key | - |
| `LLM_MODEL` | Default model | `kimi-k2.5` |
| `LLM_TIMEOUT_S` | Request timeout (seconds) | `60` |

### Cache Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `CACHE_ENABLED` | Enable cache | `true` |
| `CACHE_TTL_DAYS` | Cache TTL in days | `7` |
| `CACHE_MAX_SIZE_MB` | Max cache size | `100` |
| `CACHE_LOCATION` | Cache database path | `.cache/translations.db` |

### Model Router

| Variable | Description | Default |
|----------|-------------|---------|
| `MODEL_ROUTER_ENABLED` | Enable routing | `true` |
| `MODEL_ROUTER_HISTORY_PATH` | Failure history path | `data/model_router_history.json` |
| `MODEL_ROUTER_TRACE_PATH` | Routing trace path | `data/model_router_trace.jsonl` |

### Async Adapter

| Variable | Description | Default |
|----------|-------------|---------|
| `ASYNC_ENABLED` | Enable async execution | `true` |
| `ASYNC_MAX_CONCURRENT` | Max concurrent LLM calls | `10` |
| `ASYNC_SEMAPHORE_TIMEOUT` | Semaphore timeout (seconds) | `60` |

### Paths

| Variable | Description | Default |
|----------|-------------|---------|
| `TRACE_PATH` | LLM trace file path | `data/llm_trace.jsonl` |
| `OUTPUT_DIR` | Default output directory | `data/` |

---

## Configuration Examples

### Example 1: High-Throughput Setup

For processing large datasets quickly:

```yaml
# config/pipeline.yaml
async:
  enabled: true
  max_concurrent_llm_calls: 20
  buffer_size: 200
  stage_concurrency:
    normalize: 8
    translate: 20
    qa: 15
    export: 5

performance:
  io_batch_size: 2000
  connection_pool:
    total_limit: 200
    limit_per_host: 50
```

### Example 2: Cost-Optimized Setup

For minimizing API costs:

```yaml
# config/model_routing.yaml
model_routing:
  enabled: true
  complexity_weights:
    length: 0.30
    placeholder_density: 0.20
    special_char_density: 0.10
    glossary_density: 0.20
    historical_failure: 0.20
  
  models:
    - name: "gpt-4.1-nano"
      cost_per_1k: 0.001
      max_complexity: 0.3
      batch_capable: true
      quality_tier: "low"
    
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

# config/pipeline.yaml
cache:
  enabled: true
  ttl_days: 30
  max_size_mb: 500
```

### Example 3: Quality-First Setup

For maximum translation quality:

```yaml
# config/model_routing.yaml
model_routing:
  enabled: true
  complexity_threshold: 0.5  # Lower threshold = more premium model usage
  
  step_overrides:
    translate:
      min_quality_tier: "medium"
    
    soft_qa:
      min_quality_tier: "high"
    
    repair_hard:
      min_quality_tier: "high"

# config/glossary.yaml
glossary_matching:
  auto_approve_threshold: 0.98  # Higher threshold for auto-approval
  fuzzy_threshold: 0.95         # Stricter fuzzy matching
```

### Example 4: Development/Debug Setup

For development and debugging:

```yaml
# config/pipeline.yaml
async:
  enabled: false  # Disable async for easier debugging

monitoring:
  enable_tracing: true
  trace_path: data/debug_trace.jsonl
  collect_metrics:
    latency_histogram: true
    throughput_gauge: true
    queue_depth: true
    semaphore_wait_time: true

# config/model_routing.yaml
model_routing:
  enabled: false  # Disable routing, use default model
```

### Example 5: Docker Environment

For Docker-based deployment:

```yaml
# config/pipeline.yaml
async:
  enabled: true
  max_concurrent_llm_calls: 10

performance:
  connection_pool:
    total_limit: 50
    limit_per_host: 10

resources:
  max_memory_mb: 1024  # Conservative for containers
```

Environment variables:
```bash
# .env
LLM_BASE_URL=https://api.apiyi.com/v1
LLM_API_KEY=${LLM_API_KEY}
LLM_MODEL=kimi-k2.5
LLM_TIMEOUT_S=60
```

---

## Configuration Validation

To validate your configuration:

```python
# Validate model routing config
from scripts.model_router import ModelRouter
router = ModelRouter()
print(f"Models loaded: {list(router.models.keys())}")

# Validate async config
from scripts.async_adapter import load_async_config
config = load_async_config()
print(f"Max concurrent: {config['max_concurrent_llm_calls']}")

# Validate cache config
from scripts.cache_manager import load_cache_config
config = load_cache_config()
print(f"Cache enabled: {config.enabled}")
```

---

*For more information, see the [API Documentation](API.md) and [Quick Start](QUICK_START.md).*
