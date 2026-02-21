# API Reference

## Core Functions

### Translation Module

#### `translate_batch(items, target_lang, options={})`

Batch translate multiple items.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `items` | List[Dict] | Yes | List of items with `id`, `text`, and optional `context` |
| `target_lang` | str | Yes | Target language code (e.g., "en-US") |
| `options` | Dict | No | Translation options |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `source_lang` | str | None | Source language (auto-detect if not provided) |
| `glossary` | Dict | None | Glossary terms for consistency |
| `style_guide` | str | None | Style guide reference |
| `temperature` | float | 0.3 | LLM temperature |
| `batch_size` | int | 100 | Items per batch |
| `parallel` | bool | False | Enable parallel processing |

**Returns:**

```python
{
    "success": True,
    "results": [
        {
            "id": "item_001",
            "original": "原始文本",
            "translated": "Original Text",
            "confidence": 0.95,
            "warnings": []
        }
    ],
    "stats": {
        "total": 100,
        "success": 98,
        "failed": 2
    }
}
```

**Example:**

```python
from loc_mvr import translate_batch

items = [
    {"id": "item_1", "text": "你好", "context": "Greeting"},
    {"id": "item_2", "text": "谢谢", "context": "Thanks"}
]

result = translate_batch(
    items=items,
    target_lang="en-US",
    options={"temperature": 0.2}
)
```

---

#### `translate_single(text, target_lang, source_lang=None, context=None)`

Translate a single text item.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `text` | str | Yes | Text to translate |
| `target_lang` | str | Yes | Target language code |
| `source_lang` | str | No | Source language code |
| `context` | str | No | Context for translation |

**Returns:**

```python
{
    "translated": "Translated text",
    "source_lang": "zh-CN",
    "confidence": 0.94,
    "alternatives": ["Alt 1", "Alt 2"]
}
```

---

### Glossary Module

#### `extract_terms(input_file, options={})`

Extract key terms from source content.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `input_file` | str | Yes | Path to input CSV file |
| `options` | Dict | No | Extraction options |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `min_frequency` | int | 3 | Minimum occurrences to be considered |
| `max_terms` | int | 100 | Maximum terms to extract |
| `include_context` | bool | True | Include usage context |

**Returns:**

```python
{
    "terms": [
        {
            "term": "装备",
            "frequency": 45,
            "contexts": ["武器装备", "装备强化"],
            "category": "noun"
        }
    ],
    "total_extracted": 50
}
```

---

#### `translate_glossary(terms, target_lang, options={})`

Translate glossary terms.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `terms` | List[Dict] | Yes | List of terms to translate |
| `target_lang` | str | Yes | Target language code |
| `options` | Dict | No | Translation options |

**Returns:**

```python
{
    "translations": [
        {
            "source": "装备",
            "target": "Equipment",
            "confidence": 0.98,
            "notes": "Game equipment"
        }
    ]
}
```

---

#### `validate_glossary(glossary, content_file)`

Validate glossary consistency in content.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `glossary` | Dict | Yes | Glossary dictionary |
| `content_file` | str | Yes | Path to content file |

**Returns:**

```python
{
    "issues": [
        {
            "type": "inconsistent_translation",
            "term": "装备",
            "found": ["Equipment", "Gear", "Item"],
            "recommended": "Equipment",
            "locations": ["line 23", "line 45"]
        }
    ],
    "coverage": 0.85
}
```

---

### QA Module

#### `run_qa(input_file, options={})`

Run quality assurance on translated content.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `input_file` | str | Yes | Path to translated CSV |
| `options` | Dict | No | QA options |

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `style_guide` | str | None | Path to style guide |
| `glossary` | str | None | Path to glossary YAML |
| `checks` | List[str] | All | Specific checks to run |
| `severity` | str | "info" | Minimum severity level |

**Checks Available:**
- `terminology`: Glossary consistency
- `grammar`: Grammar and spelling
- `style`: Style guide compliance
- `length`: UI length constraints
- `placeholders`: Placeholder integrity
- `formatting`: Formatting consistency

**Returns:**

```python
{
    "summary": {
        "total_issues": 15,
        "error": 2,
        "warning": 8,
        "info": 5
    },
    "issues": [
        {
            "id": "item_001",
            "severity": "error",
            "type": "missing_placeholder",
            "message": "Placeholder {name} missing in translation",
            "suggestion": "Add {name} to translation"
        }
    ],
    "score": 0.87
}
```

---

#### `check_terminology(text, glossary)`

Check text against glossary for consistency.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `text` | str | Yes | Text to check |
| `glossary` | Dict | Yes | Glossary dictionary |

**Returns:**

```python
{
    "violations": [
        {
            "source_term": "装备",
            "expected": "Equipment",
            "found": "Gear",
            "position": 23
        }
    ],
    "pass": False
}
```

---

### Config Module

#### `load_config(config_path=None)`

Load configuration from files.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `config_path` | str | No | Custom config path |

**Returns:**

```python
{
    "language_pairs": [...],
    "models": {...},
    "prompts": {...},
    "paths": {...}
}
```

---

#### `get_prompt(prompt_type, lang)`

Get prompt template for specific language.

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `prompt_type` | str | Yes | Type: "translate", "review", "qa" |
| `lang` | str | Yes | Language code |

**Returns:**

```python
"You are a professional translator..."
```

---

## Error Handling

### Error Types

| Error | Code | Description |
|-------|------|-------------|
| `ConfigError` | 100 | Configuration issues |
| `ParseError` | 200 | Input parsing errors |
| `TranslationError` | 300 | Translation failures |
| `GlossaryError` | 400 | Glossary operations |
| `QAError` | 500 | QA processing errors |
| `APIError` | 600 | External API errors |

### Error Response Format

```python
{
    "success": False,
    "error": {
        "code": 300,
        "type": "TranslationError",
        "message": "Failed to translate batch",
        "details": {
            "item_id": "item_001",
            "reason": "Rate limit exceeded"
        }
    }
}
```

### Exception Classes

```python
class LocMVRError(Exception):
    """Base exception"""
    code = 0

class ConfigError(LocMVRError):
    """Configuration error"""
    code = 100

class ParseError(LocMVRError):
    """Parsing error"""
    code = 200

class TranslationError(LocMVRError):
    """Translation error"""
    code = 300

class GlossaryError(LocMVRError):
    """Glossary error"""
    code = 400

class QAError(LocMVRError):
    """QA error"""
    code = 500

class APIError(LocMVRError):
    """External API error"""
    code = 600
```

---

## Return Value Standards

### Success Response

All successful operations return:

```python
{
    "success": True,
    "data": {...},  # Operation-specific data
    "meta": {
        "timestamp": "2024-01-15T10:30:00Z",
        "version": "1.4.0"
    }
}
```

### Error Response

All errors return:

```python
{
    "success": False,
    "error": {
        "code": int,
        "type": str,
        "message": str,
        "details": dict  # Optional additional info
    },
    "meta": {
        "timestamp": "2024-01-15T10:30:00Z",
        "version": "1.4.0"
    }
}
```

---

## Rate Limiting

| Endpoint | Limit | Window |
|----------|-------|--------|
| translate_batch | 100 | 1 minute |
| translate_single | 60 | 1 minute |
| extract_terms | 30 | 1 minute |
| run_qa | 50 | 1 minute |

**Rate Limit Response:**

```python
{
    "success": False,
    "error": {
        "code": 429,
        "type": "RateLimitError",
        "message": "Rate limit exceeded",
        "details": {
            "retry_after": 30
        }
    }
}
```
