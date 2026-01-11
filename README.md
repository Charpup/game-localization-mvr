# Game Localization MVR (Minimum Viable Rules)

A comprehensive workflow system for managing game localization with validation, QA, and multi-format export capabilities.

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install pyyaml

# 2. Normalize input (freeze placeholders)
python scripts/normalize_guard.py data/input.csv data/draft.csv data/placeholder_map.json workflow/placeholder_schema.yaml

# 3. Translate the tokenized text (manual or AI)
# Edit draft.csv and add translations

# 4. Run QA validation
python scripts/qa_hard.py data/translated.csv data/placeholder_map.json workflow/placeholder_schema.yaml workflow/forbidden_patterns.txt data/qa_report.json

# 5. Rehydrate and export
python scripts/rehydrate_export.py data/translated.csv data/placeholder_map.json data/final.csv
```

## 📋 Features

- **Token-based placeholder freezing** - Safely handle `{0}`, `%s`, `<color>` tags
- **4-layer QA validation** - Token matching, tag balance, forbidden patterns, new placeholders
- **Strict rehydration** - Fail-fast on errors, no silent fixes
- **Comprehensive testing** - Unit tests + end-to-end workflow validation
- **Multi-format support** - 16 placeholder patterns including Unity, C#, printf

## 📁 Project Structure

```
loc-mvr/
├── config/                        # Configuration files
│   └── pricing.yaml               # LLM pricing (multiplier + per-1M modes)
├── data/                          # Localization data files
│   ├── input.csv                  # Source strings
│   ├── draft.csv                  # Tokenized strings
│   ├── translated.csv             # LLM translations
│   ├── repaired.csv               # QA-fixed translations
│   ├── final.csv                  # Final output
│   ├── placeholder_map.json       # Token mappings
│   ├── llm_trace.jsonl            # LLM call traces
│   ├── metrics_summary.json       # Cost/usage metrics
│   └── metrics_report.md          # Human-readable report
├── glossary/                      # Hierarchical glossary
│   ├── global.yaml                # Universal terms
│   └── zhCN_ruRU/                 # Language-pair specific
│       └── base.yaml              # Core game terms
├── workflow/                      # Configuration
│   ├── placeholder_schema.yaml    # Placeholder patterns (16 types)
│   ├── forbidden_patterns.txt     # QA forbidden patterns (28 rules)
│   ├── llm_config.yaml            # LLM settings & rules
│   ├── soft_qa_rubric.yaml        # Soft QA scoring rubric
│   ├── punctuation_map.yaml       # Punctuation conversion
│   └── style_guide.md             # Localization guidelines
├── scripts/                       # Core scripts
│   ├── runtime_adapter.py         # LLM client with tracing (v1.1)
│   ├── normalize_guard.py         # Freeze placeholders → tokens
│   ├── translate_llm.py           # LLM translation with glossary
│   ├── soft_qa_llm.py             # Soft QA scoring
│   ├── qa_hard.py                 # Hard validation (blocker)
│   ├── repair_loop.py             # Automated repair
│   ├── rehydrate_export.py        # Restore tokens → placeholders
│   ├── metrics_aggregator.py      # Cost & usage analytics
│   ├── glossary_autopromote.py    # Term extraction flywheel
│   ├── glossary_apply_patch.py    # Apply reviewed patches
│   └── test_*.py                  # Test scripts
├── docs/                          # Documentation
│   ├── WORKSPACE_RULES.md         # Mandatory workflow rules
│   ├── normalize_guard_usage.md
│   ├── qa_hard_usage.md
│   ├── rehydrate_export_usage.md
│   └── demo.md
└── .agent/workflows/              # Agentic workflows
    ├── loc-translate.md           # /loc_translate
    ├── loc-soft-qa.md             # /loc_soft_qa
    ├── loc-repair-loop.md         # /loc_repair_loop
    ├── loc-metrics.md             # /loc_metrics
    └── loc-glossary-autopromote.md # /loc_glossary_autopromote
```

## 🔄 Workflow

```
┌─────────────┐
│  input.csv  │ Source strings with placeholders
└──────┬──────┘
       │ normalize_guard.py
       ▼
┌─────────────┐     ┌──────────────────┐
│  draft.csv  │────▶│ placeholder_map  │
└──────┬──────┘     └──────────────────┘
       │ (Translation)
       ▼
┌──────────────┐
│translated.csv│ Tokenized translations
└──────┬───────┘
       │ qa_hard.py
       ▼
┌──────────────┐
│ qa_report.json│ Must pass (has_errors: false)
└──────┬───────┘
       │ rehydrate_export.py
       ▼
┌─────────────┐
│  final.csv  │ Ready for game integration
└─────────────┘
```

## 📖 Core Scripts

### 1. normalize_guard.py

Freezes placeholders into tokens to protect them during translation.

**Example**:
```
欢迎 {0} 来到游戏！ → 欢迎 ⟦PH_1⟧ 来到游戏！
<color=#FF00FF>稀有</color> → ⟦TAG_2⟧稀有⟦TAG_1⟧
```

### 2. qa_hard.py

Validates translations with 4 error types:
- **token_mismatch**: Missing or extra tokens
- **tag_unbalanced**: Unmatched opening/closing tags
- **forbidden_hit**: Matches forbidden patterns (TODO, etc.)
- **new_placeholder_found**: Unfrozen placeholders detected

### 3. rehydrate_export.py

Restores tokens back to original placeholders. **Strict mode**: fails immediately on unknown tokens.

## 🧪 Testing

```bash
# Run all tests
python scripts/test_normalize.py
python scripts/test_qa_hard.py
python scripts/test_rehydrate.py

# End-to-end workflow test
python scripts/test_e2e_workflow.py
```

## 📊 Test Results

- ✅ normalize_guard.py: 7 strings, 11 placeholders frozen
- ✅ qa_hard.py: 0 errors on good translations, 8 errors detected on bad translations
- ✅ rehydrate_export.py: 11 tokens restored, unknown tokens rejected
- ✅ End-to-end workflow: All steps passed

## 🎯 Supported Placeholder Types

| Type | Pattern | Example | Token |
|------|---------|---------|-------|
| C# numbered | `{0}`, `{1}` | `{0}` | `⟦PH_1⟧` |
| C# named | `{playerName}` | `{level}` | `⟦PH_2⟧` |
| Printf | `%s`, `%d`, `%f` | `%d` | `⟦PH_3⟧` |
| Unity color | `<color=#FF00FF>` | `<color=#FF00FF>` | `⟦TAG_1⟧` |
| Unity close | `</color>` | `</color>` | `⟦TAG_2⟧` |
| Escape seq | `\n`, `\t` | `\n` | `⟦PH_7⟧` |

## 📝 Requirements

- Python 3.7+
- PyYAML

## 🔧 Configuration

### Customize Placeholder Patterns

Edit `workflow/placeholder_schema.yaml`:

```yaml
placeholder_patterns:
  - name: "custom_pattern"
    pattern: '\[\w+\]'
    type: "PH"
    description: "Custom square bracket placeholders"
```

### Customize Forbidden Patterns

Edit `workflow/forbidden_patterns.txt`:

```
# Add your project-specific forbidden patterns
\[待翻译\]
\[TBD\]
```

## 📚 Documentation

- [Normalize Guard Usage](docs/normalize_guard_usage.md)
- [QA Hard Usage](docs/qa_hard_usage.md)
- [Rehydrate Export Usage](docs/rehydrate_export_usage.md)
- [Complete Demo](docs/demo.md)

## 🤝 Contributing

Contributions are welcome! Please ensure:
1. All tests pass
2. Add tests for new features
3. Update documentation

## 📄 License

MIT License - feel free to use in your projects

## 🙏 Acknowledgments

Built for game localization teams who need reliable, automated quality assurance.
