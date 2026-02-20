---
name: loc-mvr
version: 1.3.0
description: |
  Game Localization MVR - Multi-language translation pipeline supporting
  Chinese to English, Russian, Japanese, Korean, French, German, and Spanish.
  
  Usage: Use when translating game content from Chinese to multiple target languages.
---

# Loc-MVR v1.3.0 - Multi-Language Game Localization

## Overview

Loc-MVR is a professional game localization pipeline supporting multiple target languages:
- 🇺🇸 English (en-US)
- 🇷🇺 Russian (ru-RU)  
- 🇯🇵 Japanese (ja-JP)
- 🇰🇷 Korean (ko-KR)
- 🇫🇷 French (fr-FR)
- 🇩🇪 German (de-DE)
- 🇪🇸 Spanish (es-ES)

## Quick Start

```bash
# English translation
python scripts/batch_runtime.py --target-lang en-US

# Japanese translation
python scripts/glossary_translate_llm.py --target-lang ja-JP
```

## Core Scripts

| Script | Purpose | Multi-Language |
|--------|---------|----------------|
| batch_runtime.py | Main translation pipeline | ✅ |
| glossary_translate_llm.py | Glossary translation | ✅ |
| soft_qa_llm.py | Quality assurance | ✅ |

## Configuration

Language pairs are defined in `src/config/language_pairs.yaml`.
Prompt templates are in `src/config/prompts/{lang}/`.

## Requirements

- Python 3.11+
- Dependencies: see requirements.txt
