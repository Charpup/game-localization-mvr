# API Documentation

Complete API reference for the Game Localization MVR v1.2.0.

## Table of Contents

- [Cache Manager API](#cache-manager-api)
- [Model Router API](#model-router-api)
- [Async Adapter API](#async-adapter-api)
- [Glossary Matcher API](#glossary-matcher-api)
- [Glossary Corrector API](#glossary-corrector-api)

---

## Cache Manager API

SQLite-based persistent cache for LLM translation responses.

### Classes

#### `CacheConfig`

Configuration settings for the cache manager.

```python
@dataclass
class CacheConfig:
    enabled: bool = True          # Master switch for caching
    ttl_days: int = 7             # Cache entry lifetime in days
    max_size_mb: int = 100        # Maximum cache size in MB
    location: str = ".cache/translations.db"  # Database file path
```

#### `CacheStats`

Cache performance statistics.

```python
@dataclass
class CacheStats:
    hits: int = 0                 # Number of cache hits
    misses: int = 0               # Number of cache misses
    evictions: int = 0            # Number of LRU evictions
    total_size_bytes: int = 0     # Total cache size in bytes
    
    @property
    def hit_rate(self) -> float   # Returns hit rate as float (0.0-1.0)
    @property
    def miss_rate(self) -> float  # Returns miss rate as float (0.0-1.0)
```

#### `CacheManager`

Main cache manager class.

```python
class CacheManager:
    def __init__(self, config: Optional[CacheConfig] = None)
    
    # Core operations
    def get(self, source_text: str, glossary_hash: Optional[str] = None, 
            model_name: str = "default") -> Tuple[bool, Optional[str]]
    # Returns: (cache_hit, translated_text or None)
    
    def set(self, source_text: str, translated_text: str,
            glossary_hash: Optional[str] = None, 
            model_name: str = "default") -> bool
    
    # Statistics and management
    def get_stats(self) -> CacheStats
    def get_size(self) -> Dict[str, Any]
    def clear(self) -> int  # Returns number of entries removed
    def close(self) -> None
    
    # Context manager support
    def __enter__(self) -> CacheManager
    def __exit__(self, exc_type, exc_val, exc_tb) -> None
```

### Functions

#### `load_cache_config`

Load cache configuration from YAML file.

```python
def load_cache_config(config_path: str = "config/pipeline.yaml") -> CacheConfig
```

#### `get_cache_manager`

Get or create global cache manager instance (singleton).

```python
def get_cache_manager(config_path: str = "config/pipeline.yaml") -> CacheManager
```

### Usage Examples

```python
from scripts.cache_manager import CacheManager, CacheConfig

# Basic usage
config = CacheConfig(enabled=True, ttl_days=7, max_size_mb=100)
cache = CacheManager(config)

# Store translation
cache.set("Hello", "Привет", glossary_hash="abc123", model_name="gpt-4")

# Retrieve translation
hit, translation = cache.get("Hello", glossary_hash="abc123", model_name="gpt-4")
if hit:
    print(f"Cached: {translation}")

# Get statistics
stats = cache.get_stats()
print(f"Hit rate: {stats.hit_rate:.2%}")

# Get size info
size_info = cache.get_size()
print(f"Cache size: {size_info['total_mb']:.2f} MB")

# Clear cache
removed = cache.clear()
print(f"Removed {removed} entries")

# Context manager
with CacheManager(config) as cache:
    cache.set("test", "translation")
```

### CLI Usage

```bash
# View cache statistics
python scripts/cache_manager.py --stats

# View cache size
python scripts/cache_manager.py --size

# Clear all cache entries
python scripts/cache_manager.py --clear

# Use custom config
python scripts/cache_manager.py --stats --config config/custom.yaml
```

---

## Model Router API

Intelligent model routing for cost/quality optimization.

### Classes

#### `ComplexityMetrics`

Text complexity analysis results.

```python
@dataclass
class ComplexityMetrics:
    text_length: int = 0              # Total text length in characters
    char_count: int = 0               # Character count (no spaces)
    word_count: int = 0               # Word count
    cjk_count: int = 0                # CJK (Chinese/Japanese/Korean) char count
    placeholder_count: int = 0        # Number of placeholders found
    placeholder_density: float = 0.0  # Placeholders per 100 chars
    special_char_count: int = 0       # Special character count
    special_char_density: float = 0.0 # Special chars per 100 chars
    glossary_term_count: int = 0      # Glossary terms found
    glossary_term_density: float = 0.0 # Glossary terms per 100 chars
    sentence_count: int = 0           # Estimated sentence count
    avg_word_length: float = 0.0      # Average word length
    complexity_score: float = 0.0     # Overall complexity (0.0-1.0)
```

#### `RoutingDecision`

Record of a model routing decision.

```python
@dataclass
class RoutingDecision:
    timestamp: str
    text_hash: str
    text_preview: str
    step: str
    selected_model: str
    complexity_metrics: ComplexityMetrics
    complexity_score: float
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    estimated_cost: float = 0.0
```

#### `ModelConfig`

Configuration for a routable model.

```python
@dataclass
class ModelConfig:
    name: str                    # Model identifier
    cost_per_1k: float          # Cost per 1K tokens (USD)
    max_complexity: float = 1.0  # Maximum complexity this model can handle
    batch_capable: bool = True   # Whether model supports batch processing
    quality_tier: str = "medium" # low, medium, high
    fallback_to: Optional[str] = None  # Fallback model name
```

#### `ComplexityAnalyzer`

Analyzes text complexity for routing decisions.

```python
class ComplexityAnalyzer:
    def __init__(self, weights: Optional[Dict[str, float]] = None)
    
    def analyze(self, text: str, 
                glossary_terms: Optional[List[str]] = None) -> ComplexityMetrics
    
    def record_failure(self, text: str, failure_type: str = "qa_fail")
    def record_success(self, text: str)
    def get_historical_failure_rate(self, text: str) -> float
```

**Default Complexity Weights**:
- `length`: 0.20 (20%)
- `placeholder_density`: 0.25 (25%)
- `special_char_density`: 0.15 (15%)
- `glossary_density`: 0.25 (25%)
- `historical_failure`: 0.15 (15%)

#### `ModelRouter`

Main model routing class.

```python
class ModelRouter:
    def __init__(self, 
                 config_path: Optional[str] = None,
                 llm_client: Optional[Any] = None,
                 analyzer: Optional[ComplexityAnalyzer] = None)
    
    # Core routing
    def analyze_complexity(self, text: str, 
                          glossary_terms: Optional[List[str]] = None) -> ComplexityMetrics
    
    def select_model(self, text: str,
                    step: str = "translate",
                    glossary_terms: Optional[List[str]] = None,
                    force_model: Optional[str] = None,
                    is_batch: bool = False) -> Tuple[str, ComplexityMetrics, float]
    # Returns: (selected_model, complexity_metrics, estimated_cost)
    
    def select_model_for_batch(self, texts: List[str],
                              step: str = "translate",
                              glossary_terms: Optional[List[str]] = None,
                              force_model: Optional[str] = None) -> Tuple[str, float, List[ComplexityMetrics]]
    # Returns: (selected_model, batch_complexity_score, list_of_metrics)
    
    def translate_with_routing(self, text: str,
                              system_prompt: str,
                              step: str = "translate",
                              glossary_terms: Optional[List[str]] = None,
                              force_model: Optional[str] = None,
                              **llm_kwargs) -> Dict[str, Any]
    
    # Statistics and reporting
    def get_routing_stats(self) -> Dict[str, Any]
    def get_cost_comparison(self, baseline_model: str = "kimi-k2.5") -> Dict[str, Any]
    def save_routing_history(self, path: Optional[str] = None)
```

### Functions

#### `patch_translate_llm_with_router`

Monkey-patch translate_llm module to use intelligent routing.

```python
def patch_translate_llm_with_router(translate_llm_module=None) -> Optional[ModelRouter]
```

### Usage Examples

```python
from scripts.model_router import ModelRouter, ComplexityAnalyzer

# Initialize router
router = ModelRouter()

# Analyze text complexity
metrics = router.analyze_complexity(
    text="忍者的攻击力很高，暴击伤害也很强。",
    glossary_terms=["忍者", "攻击", "暴击"]
)
print(f"Complexity score: {metrics.complexity_score:.2f}")

# Select best model for text
model, metrics, cost = router.select_model(
    text="Your text here",
    step="translate",
    glossary_terms=["term1", "term2"]
)
print(f"Selected: {model} (cost: ${cost:.6f})")

# Batch routing
texts = ["Text 1", "Text 2", "Text 3"]
model, complexity, all_metrics = router.select_model_for_batch(
    texts, step="translate", glossary_terms=[]
)

# Translate with automatic routing
result = router.translate_with_routing(
    text="Hello world",
    system_prompt="You are a translator.",
    step="translate"
)
print(f"Result: {result['text']}")
print(f"Model used: {result['model']}")

# Get routing statistics
stats = router.get_routing_stats()
print(f"Total routings: {stats['total_routings']}")
print(f"Model distribution: {stats['model_distribution']}")

# Cost comparison vs baseline
comparison = router.get_cost_comparison(baseline_model="kimi-k2.5")
print(f"Savings: {comparison['savings_percent']}%")
```

### CLI Usage

```bash
# Analyze text complexity
python scripts/model_router.py -a "Your text here"

# Select model for text
python scripts/model_router.py -s "Your text here" --step translate

# View routing statistics
python scripts/model_router.py --stats

# Load glossary for analysis
python scripts/model_router.py -a "Text" --glossary glossary/compiled.yaml
```

---

## Async Adapter API

Asynchronous/concurrent execution for lower latency processing.

### Classes

#### `AsyncLLMResult`

Result of an async LLM call.

```python
@dataclass
class AsyncLLMResult:
    text: str                       # Response text
    latency_ms: int                # Response latency in milliseconds
    raw: Optional[dict] = None     # Raw API response
    request_id: Optional[str] = None
    usage: Optional[dict] = None   # Token usage info
    model: Optional[str] = None    # Model used
    
    def to_sync_result(self) -> LLMResult  # Convert to sync result
```

#### `AsyncLLMClient`

Asynchronous LLM client with concurrency control.

```python
class AsyncLLMClient:
    def __init__(self,
                 base_url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 model: Optional[str] = None,
                 timeout_s: Optional[int] = None,
                 max_concurrent: Optional[int] = None,
                 config: Optional[Dict[str, Any]] = None)
    
    # Core methods
    async def chat(self, system: str, user: str,
                   temperature: Optional[float] = None,
                   max_tokens: Optional[int] = None,
                   response_format: Optional[Dict[str, Any]] = None,
                   metadata: Optional[Dict[str, Any]] = None,
                   timeout: Optional[int] = None,
                   semaphore: Optional[asyncio.Semaphore] = None) -> AsyncLLMResult
    
    async def batch_chat(self,
                        prompts: List[Dict[str, Any]],
                        max_concurrent: Optional[int] = None,
                        progress_callback: Optional[Callable[[int, int], None]] = None
                        ) -> List[AsyncLLMResult]
    
    async def close(self) -> None
    
    # Context manager
    async def __aenter__(self) -> AsyncLLMClient
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None
```

#### `AsyncFileIO`

Async file I/O operations.

```python
class AsyncFileIO:
    @staticmethod
    async def read_csv_async(file_path: str, 
                            encoding: str = 'utf-8') -> List[Dict[str, Any]]
    
    @staticmethod
    async def write_csv_async(file_path: str,
                             rows: List[Dict[str, Any]],
                             fieldnames: Optional[List[str]] = None,
                             encoding: str = 'utf-8') -> None
    
    @staticmethod
    async def read_jsonl_async(file_path: str,
                              encoding: str = 'utf-8') -> List[Dict[str, Any]]
    
    @staticmethod
    async def write_jsonl_async(file_path: str,
                               rows: List[Dict[str, Any]],
                               encoding: str = 'utf-8') -> None
```

#### `PipelineStage`

Base class for pipeline stages.

```python
class PipelineStage(Generic[T]):
    def __init__(self, name: str, concurrency: int = 5)
    
    async def start(self) -> None
    async def stop(self) -> None
    async def process(self, data: T) -> T  # Override in subclasses
    async def put(self, item: PipelineItem) -> None
    async def get(self) -> PipelineItem
```

#### `AsyncPipeline`

Streaming pipeline for concurrent stage execution.

```python
class AsyncPipeline(Generic[T]):
    def __init__(self, buffer_size: int = 100, 
                 backpressure_enabled: bool = True)
    
    def add_stage(self, name: str, stage: PipelineStage) -> None
    
    async def start(self) -> None
    async def stop(self) -> None
    
    async def process_stream(
        self,
        input_items: AsyncGenerator[T, None],
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> AsyncGenerator[PipelineItem[T], None]
    
    async def process_batch(self, items: List[T]) -> List[PipelineItem[T]]
```

### Functions

#### `load_async_config`

Load async configuration from YAML.

```python
def load_async_config(config_path: Optional[str] = None) -> Dict[str, Any]
```

#### `process_csv_async`

Main async entry point for CSV processing.

```python
async def process_csv_async(
    input_path: str,
    output_path: str,
    config: Optional[Dict[str, Any]] = None,
    progress_callback: Optional[Callable[[str, int, int], None]] = None,
    llm_client: Optional[AsyncLLMClient] = None
) -> Dict[str, Any]
```

Returns statistics dict with:
- `start_time`, `end_time`
- `total_rows`, `processed_rows`, `failed_rows`
- `total_duration_seconds`, `rows_per_second`

#### `benchmark_async_vs_sync`

Benchmark async vs synchronous processing.

```python
async def benchmark_async_vs_sync(
    prompts: List[Dict[str, Any]],
    max_concurrent: int = 10
) -> Dict[str, Any]
```

#### `batch_chat`

Synchronous wrapper for async batch processing (backward compatibility).

```python
def batch_chat(prompts: List[Dict[str, Any]],
               max_concurrent: int = 10,
               **kwargs) -> List[LLMResult]
```

### Usage Examples

```python
import asyncio
from scripts.async_adapter import (
    AsyncLLMClient, AsyncFileIO, process_csv_async,
    benchmark_async_vs_sync
)

# Basic async client usage
async def translate_single():
    async with AsyncLLMClient(max_concurrent=10) as client:
        result = await client.chat(
            system="You are a translator.",
            user="Translate: Hello",
            metadata={"step": "translate"}
        )
        print(f"Translated in {result.latency_ms}ms")
        return result.text

# Batch processing with progress
async def translate_batch():
    prompts = [
        {"system": "Translate to Russian.", "user": f"Text {i}", 
         "metadata": {"step": "translate"}}
        for i in range(100)
    ]
    
    def on_progress(completed, total):
        print(f"Progress: {completed}/{total}")
    
    async with AsyncLLMClient() as client:
        results = await client.batch_chat(prompts, progress_callback=on_progress)
    
    return results

# Process CSV file
async def process_file():
    def progress(stage, completed, total):
        print(f"[{stage}] {completed}/{total}")
    
    stats = await process_csv_async(
        input_path="data/input.csv",
        output_path="data/output.csv",
        progress_callback=progress
    )
    
    print(f"Processed {stats['processed_rows']} rows")
    print(f"Duration: {stats['total_duration_seconds']:.2f}s")
    print(f"Throughput: {stats['rows_per_second']:.2f} rows/sec")

# Benchmark
async def run_benchmark():
    test_prompts = [
        {"system": "Translate.", "user": f"Text {i}"}
        for i in range(20)
    ]
    
    results = await benchmark_async_vs_sync(test_prompts, max_concurrent=10)
    print(f"Speedup: {results['speedup_factor']}x")
    print(f"Latency reduction: {results['latency_reduction_percent']}%")

# Run
asyncio.run(process_file())
```

### CLI Usage

```bash
# Process CSV with async pipeline
python scripts/async_adapter.py -i data/input.csv -o data/output.csv

# With custom concurrency
python scripts/async_adapter.py -i input.csv -o output.csv -c 15 -b 200

# Run benchmark
python scripts/async_adapter.py -i test.csv -o out.csv --benchmark
```

---

## Glossary Matcher API

Intelligent glossary matching with fuzzy matching and auto-approval.

### Classes

#### `MatchResult`

Result of a glossary match.

```python
@dataclass
class MatchResult:
    source_term: str              # Source glossary term
    target_term: str              # Target translation
    found_text: str              # Text found in content
    confidence: float            # Match confidence (0.0-1.0)
    match_type: str              # 'exact', 'fuzzy', 'context_validated', 'partial'
    context_before: str = ""     # Context before match
    context_after: str = ""      # Context after match
    position: int = 0            # Match position in text
    length: int = 0              # Match length
    auto_approved: bool = False  # Whether match is auto-approved
    requires_review: bool = False
    case_preserved: bool = True
    confidence_breakdown: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict
```

#### `GlossaryMatcher`

Main glossary matching class.

```python
class GlossaryMatcher:
    def __init__(self, config_path: Optional[str] = None)
    
    # Load glossary data
    def load_glossary(self, glossary_data: Dict[str, str]) -> None
    def load_glossary_from_yaml(self, yaml_path: str) -> None
    
    # Find matches
    def find_matches(self, text: str, target_lang: str = 'ru') -> List[MatchResult]
    
    # Batch processing
    def process_batch(self, texts: List[str],
                     translations: Optional[List[str]] = None) -> Dict
    
    # Export results
    def export_jsonl(self, matches: List[MatchResult], output_path: str) -> None
    def export_csv(self, matches: List[MatchResult], output_path: str) -> None
    def export_highlight_html(self, texts: List[str],
                             matches: List[MatchResult],
                             output_path: str) -> None
```

### Configuration Options

Default configuration (via `config/glossary.yaml`):

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

### Usage Examples

```python
from scripts.glossary_matcher import GlossaryMatcher, MatchResult

# Initialize matcher
matcher = GlossaryMatcher()

# Load glossary
sample_glossary = {
    "攻击": "Атака",
    "伤害": "Урон",
    "忍者": "Ниндзя",
    "生命": "Здоровье",
    "暴击": "Критический удар"
}
matcher.load_glossary(sample_glossary)

# Or load from YAML
matcher.load_glossary_from_yaml("glossary/compiled.yaml")

# Find matches in text
text = "忍者的攻击力很高，暴击伤害也很强。"
matches = matcher.find_matches(text)

for match in matches:
    print(f"Found: {match.source_term} -> {match.target_term}")
    print(f"Confidence: {match.confidence:.2%}")
    print(f"Auto-approved: {match.auto_approved}")
    print(f"Match type: {match.match_type}")

# Batch processing
texts = [
    "忍者的攻击力很高。",
    "点击确定按钮。",
    "PlayStation游戏机。"
]
results = matcher.process_batch(texts)

print(f"Metrics: {results['metrics']}")
# Includes: total_matches, auto_approval_rate, review_rate, average_confidence

# Export to various formats
matcher.export_jsonl(matches, "reports/matches.jsonl")
matcher.export_csv(matches, "reports/matches.csv")
matcher.export_highlight_html(texts, matches, "reports/highlights.html")
```

---

## Glossary Corrector API

Intelligent correction suggestions for glossary violations.

### Classes

#### `CorrectionRule` (Enum)

Types of correction rules.

```python
class CorrectionRule(Enum):
    SPELLING = "spelling"                    # Spelling errors
    CAPITALIZATION = "capitalization"        # Case errors
    CASE_ENDING = "case_ending"              # Russian declensions
    SPACING = "spacing"                      # Spacing/hyphenation issues
    DIRECT_REPLACEMENT = "direct_replacement"
    CONTEXT_DEPENDENT = "context_dependent"
```

#### `CorrectionSuggestion`

A single correction suggestion.

```python
@dataclass
class CorrectionSuggestion:
    text_id: str
    original: str                    # Original (incorrect) text
    suggested: str                   # Suggested correction
    confidence: float               # Confidence score (0.0-1.0)
    rule: str                       # Rule that triggered correction
    context: str                    # Surrounding context
    position: int = 0               # Position in text
    term_zh: str = ""              # Chinese source term
    term_ru_expected: str = ""     # Expected Russian translation
    alternative_suggestions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]
```

#### `GlossaryEntry`

Glossary entry with term information.

```python
@dataclass
class GlossaryEntry:
    term_zh: str
    term_ru: str
    scope: str = "general"
    status: str = "approved"
    tags: List[str] = field(default_factory=list)
    variations: List[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'GlossaryEntry'
```

#### `RussianDeclensionHelper`

Helper for Russian declensions and case endings.

```python
class RussianDeclensionHelper:
    # Detect which grammatical case a word is in
    @classmethod
    def detect_case(cls, word: str, base_form: str) -> Optional[str]
    
    # Generate correct form preserving case
    @classmethod
    def get_correct_form(cls, incorrect_form: str, correct_base: str,
                        target_case: Optional[str] = None) -> str
    
    # Normalize word for fuzzy comparison
    @classmethod
    def normalize_for_comparison(cls, word: str) -> str
```

#### `GlossaryCorrector`

Main glossary correction engine.

```python
class GlossaryCorrector:
    def __init__(self, config_path: Optional[str] = None)
    
    # Configuration
    def load_config(self) -> bool
    def load_glossary(self, glossary_path: str) -> bool
    
    # Detection
    def detect_violations(self, text: str, text_id: str = "") -> List[CorrectionSuggestion]
    
    # Correction
    def apply_corrections(self, text: str,
                         suggestions: List[CorrectionSuggestion],
                         auto_apply_threshold: Optional[float] = None) -> str
    
    # Batch processing
    def process_csv(self, csv_path: str,
                   text_column: str = 'target_text',
                   id_column: str = 'string_id') -> List[CorrectionSuggestion]
    
    # Export and reporting
    def save_suggestions(self, suggestions: List[CorrectionSuggestion],
                        output_path: str) -> bool
    def get_stats(self) -> Dict
    def print_summary(self) -> None
```

### Configuration Options

Default configuration (via `config/glossary.yaml`):

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

### Usage Examples

```python
from scripts.glossary_corrector import GlossaryCorrector, CorrectionSuggestion

# Initialize corrector
corrector = GlossaryCorrector(config_path="config/glossary.yaml")

# Load glossary
corrector.load_glossary("glossary/compiled.yaml")

# Detect violations in text
text = "Ханкок использует свои силы."  # Misspelled: should be Хэнкок
suggestions = corrector.detect_violations(text, text_id="row_123")

for suggestion in suggestions:
    print(f"Issue: '{suggestion.original}' -> '{suggestion.suggested}'")
    print(f"Rule: {suggestion.rule}")
    print(f"Confidence: {suggestion.confidence:.2%}")
    print(f"Context: {suggestion.context}")

# Apply high-confidence corrections automatically
corrected_text = corrector.apply_corrections(
    text, suggestions, auto_apply_threshold=0.95
)

# Process CSV file
suggestions = corrector.process_csv(
    csv_path="data/translations.csv",
    text_column="target_text",
    id_column="string_id"
)

# Filter by confidence
high_confidence = [s for s in suggestions if s.confidence >= 0.95]

# Save suggestions
corrector.save_suggestions(suggestions, "corrections.jsonl")

# Print summary
corrector.print_summary()
```

### CLI Usage

```bash
# Generate correction suggestions
python scripts/glossary_corrector.py data/translations.csv \
  --glossary glossary/compiled.yaml \
  --output corrections.jsonl \
  --suggest-corrections

# Process with custom config
python scripts/glossary_corrector.py data.csv \
  --config config/glossary.yaml \
  --text-column target_text \
  --id-column string_id

# Auto-apply high-confidence corrections
python scripts/glossary_corrector.py data.csv \
  --auto-apply \
  --apply-threshold 0.99
```

---

## Common Patterns

### Combining Multiple APIs

```python
from scripts.cache_manager import CacheManager
from scripts.model_router import ModelRouter
from scripts.glossary_matcher import GlossaryMatcher
from scripts.async_adapter import AsyncLLMClient
import asyncio

async def translate_with_full_features(text: str) -> str:
    # Initialize components
    cache = CacheManager()
    router = ModelRouter()
    matcher = GlossaryMatcher()
    matcher.load_glossary_from_yaml("glossary/compiled.yaml")
    
    # Check cache first
    hit, cached = cache.get(text, model_name="gpt-4")
    if hit:
        return cached
    
    # Find glossary terms for complexity analysis
    matches = matcher.find_matches(text)
    glossary_terms = [m.source_term for m in matches]
    
    # Select optimal model
    model, metrics, cost = router.select_model(
        text, glossary_terms=glossary_terms
    )
    
    # Translate with async client
    async with AsyncLLMClient() as client:
        result = await client.chat(
            system="You are a translator.",
            user=text,
            metadata={"step": "translate", "model_override": model}
        )
    
    # Cache result
    cache.set(text, result.text, model_name="gpt-4")
    
    return result.text
```

---

*For more information, see the [Configuration Guide](CONFIGURATION.md) and [Quick Start](QUICK_START.md).*
