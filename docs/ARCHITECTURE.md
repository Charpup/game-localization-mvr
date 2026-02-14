# Architecture Documentation

## Overview

Game Localization MVR is a Python-based localization pipeline that uses LLM models to translate game content. The system is designed to be modular, extensible, and production-ready.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         Game Localization MVR                           │
├─────────────────────────────────────────────────────────────────────────┤
│  Input Layer                                                            │
│  ├── CSV Parser (normalize_ingest.py)                                   │
│  └── Placeholder Tokenizer (normalize_guard.py)                         │
├─────────────────────────────────────────────────────────────────────────┤
│  Processing Layer                                                       │
│  ├── Translation (translate_llm.py)                                     │
│  │   ├── Model Router                                                   │
│  │   ├── Async Adapter                                                  │
│  │   └── Cache Manager                                                  │
│  ├── Glossary System                                                    │
│  │   ├── Glossary Matcher (glossary_matcher.py)                         │
│  │   ├── Glossary Corrector (glossary_corrector.py)                     │
│  │   └── Glossary Learner (glossary_learner.py)                         │
│  └── QA Validation                                                      │
│      ├── QA Hard (qa_hard.py)                                           │
│      └── QA Soft (qa_soft.py)                                           │
├─────────────────────────────────────────────────────────────────────────┤
│  Output Layer                                                           │
│  └── Rehydrate Export (rehydrate_export.py)                             │
└─────────────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
game-localization-mvr/
├── docs/                    # Documentation
│   ├── QUICK_START.md      # Getting started guide
│   ├── API.md              # API reference
│   ├── CONFIGURATION.md    # Configuration options
│   └── ARCHITECTURE.md     # This file
│
├── src/                     # Source code
│   ├── scripts/            # Core processing scripts
│   │   ├── normalize_guard.py
│   │   ├── translate_llm.py
│   │   ├── qa_hard.py
│   │   ├── rehydrate_export.py
│   │   ├── model_router.py
│   │   ├── async_adapter.py
│   │   ├── cache_manager.py
│   │   ├── glossary_matcher.py
│   │   ├── glossary_corrector.py
│   │   └── ...
│   ├── config/             # Configuration files
│   │   ├── pipeline.yaml
│   │   ├── model_routing.yaml
│   │   └── glossary.yaml
│   └── lib/                # Shared libraries
│       └── text.py
│
├── tests/                   # Test suite
│   ├── unit/               # Unit tests
│   ├── integration/        # Integration tests
│   ├── benchmarks/         # Performance tests
│   └── fixtures/           # Test data
│
├── examples/                # Example data
│   └── sample_input.csv
│
└── skill/                   # Skill distribution
    └── loc-mvr-v1.2.0.skill
```

## Core Components

### 1. Normalization Pipeline

**Purpose**: Prepare input data for translation by tokenizing placeholders and validating structure.

**Key Files**:
- `normalize_ingest.py` - CSV ingestion and validation
- `normalize_guard.py` - Placeholder tokenization
- `normalize_tagger.py` - Content tagging
- `normalize_tag_llm.py` - LLM-based content analysis

**Data Flow**:
```
Raw CSV → Parse → Tokenize Placeholders → Validate → Draft CSV + Map
```

### 2. Translation Engine

**Purpose**: Translate tokenized content using LLM models with intelligent routing.

**Key Files**:
- `translate_llm.py` - Main translation orchestrator
- `model_router.py` - Intelligent model selection
- `async_adapter.py` - Concurrent processing
- `cache_manager.py` - Response caching

**Features**:
- Multi-model support (GPT-4, Claude, Kimi)
- Complexity-based routing
- Async/concurrent execution
- Persistent caching

### 3. Glossary System

**Purpose**: Ensure consistent terminology usage across translations.

**Key Files**:
- `glossary_matcher.py` - Term matching
- `glossary_corrector.py` - Violation detection
- `glossary_learner.py` - Pattern learning
- `glossary_compile.py` - Glossary compilation

**Features**:
- Fuzzy matching
- Auto-correction suggestions
- Russian declension support
- Context-aware disambiguation

### 4. QA System

**Purpose**: Validate translation quality through automated checks.

**Key Files**:
- `qa_hard.py` - Automated rule-based validation
- `qa_soft.py` - LLM-based quality assessment
- `confidence_scorer.py` - Confidence scoring

**Validation Types**:
- Placeholder preservation
- Glossary compliance
- Length constraints
- Format consistency

### 5. Export System

**Purpose**: Rehydrate tokens and export final translations.

**Key Files**:
- `rehydrate_export.py` - Token restoration and export

## Data Models

### Input Format

```csv
id,source_text,target_lang
1,"Hello {player_name}",zh-CN
2,"Attack power: {value}",zh-CN
```

### Intermediate Format

```csv
id,source_text,target_lang,tokenized_text
1,"Hello {player_name}",zh-CN,"Hello __PH_1__"
2,"Attack power: {value}",zh-CN,"Attack power: __PH_2__"
```

### Placeholder Map

```json
{
  "__PH_1__": "{player_name}",
  "__PH_2__": "{value}"
}
```

### Output Format

```csv
id,source_text,target_lang,translated_text
1,"Hello {player_name}",zh-CN,"你好 {player_name}"
2,"Attack power: {value}",zh-CN,"攻击力: {value}"
```

## Configuration System

Configuration is managed through YAML files in `src/config/`:

### Pipeline Configuration

```yaml
pipeline:
  stages:
    - normalize
    - translate
    - qa
    - export
  
  cache:
    enabled: true
    ttl_days: 7
    max_size_mb: 100
```

### Model Routing

```yaml
routing:
  models:
    - name: gpt-4
      threshold: 0.8
    - name: gpt-3.5
      threshold: 0.5
  
  complexity_weights:
    length: 0.20
    placeholders: 0.25
    glossary: 0.25
    special_chars: 0.15
    history: 0.15
```

## Execution Models

### Synchronous Execution

Default mode suitable for small to medium datasets.

```python
from src.scripts.translate_llm import Translator

translator = Translator(model="gpt-4")
result = translator.translate_batch(records)
```

### Asynchronous Execution

Optimized for large datasets with I/O-bound operations.

```python
from src.scripts.async_adapter import process_csv_async

stats = await process_csv_async(
    input_path="data/input.csv",
    output_path="data/output.csv",
    max_concurrent=10
)
```

### Docker Execution

Containerized execution for consistent environments.

```bash
docker build -t loc-mvr .
docker run --env-file .env loc-mvr python -m src.scripts.translate_llm ...
```

## Extension Points

### Adding a New Model

1. Add model configuration to `src/config/model_routing.yaml`
2. Implement model client in `src/scripts/runtime_adapter.py`
3. Update pricing in `src/config/pricing.yaml`

### Adding a New QA Rule

1. Define rule in `src/config/pipeline.yaml`
2. Implement validator in `src/scripts/qa_hard.py` or `src/scripts/qa_soft.py`
3. Add test case in `tests/unit/`

### Adding a New Pipeline Stage

1. Create script in `src/scripts/`
2. Add stage to pipeline config
3. Update `Makefile` target
4. Add integration test

## Performance Characteristics

| Metric | Value |
|--------|-------|
| Throughput (sync) | 20-30 rows/sec |
| Throughput (async) | 50-100 rows/sec |
| Cache hit rate | 60-75% |
| Model routing savings | 20-40% |
| Glossary match accuracy | 95%+ |

## Error Handling

The system uses a multi-layer error handling strategy:

1. **Validation Layer**: Input validation with detailed error messages
2. **Retry Layer**: Exponential backoff for transient failures
3. **Fallback Layer**: Model fallback on API failures
4. **Checkpoint Layer**: Progress persistence for resumability

## Monitoring

### Metrics Collection

```python
from src.scripts.metrics_aggregator import aggregate_metrics

metrics = aggregate_metrics(trace_path="data/llm_trace.jsonl")
```

### Cost Tracking

Real-time cost estimation based on token usage and model pricing.

### Progress Reporting

Progress indicators with ETA calculation for long-running operations.

## Security Considerations

- API keys stored in environment variables
- No sensitive data in logs
- Input validation to prevent injection attacks
- Rate limiting to prevent API abuse

## Deployment Patterns

### Single Machine

```bash
make install
make pipeline
```

### Docker

```bash
make docker-build
make docker-run
```

### CI/CD

```yaml
- name: Run Tests
  run: make test

- name: Build Skill
  run: make skill-package
```

## Future Enhancements

- [ ] Distributed processing support
- [ ] Web UI for monitoring
- [ ] Real-time collaboration features
- [ ] Additional language pairs
- [ ] Custom model fine-tuning
