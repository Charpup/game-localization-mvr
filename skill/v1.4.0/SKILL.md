---
name: loc-mvr
description: |
  Game Localization MVR - Professional multi-language translation pipeline
  for Chinese (Simplified) to 7 target languages (EN, RU, JA, KO, FR, DE, ES).

  Use this skill when:
  - Translating game content from Chinese to multiple languages
  - Managing game localization glossaries and terminology
  - Running quality assurance on translated game text
  - Batch processing localization files with AI assistance
  - Need language-specific translation rules and validation

  Supports: English, Russian, Japanese, Korean, French, German, Spanish.
---

# Loc-MVR - Multi-Language Game Localization

## Quick Start

```bash
# Translate to English
loc-mvr translate --target-lang en-US --input texts.csv

# Manage glossary
loc-mvr glossary --action translate --proposals terms.yaml

# Run QA
loc-mvr qa --input translated.csv --style-guide guide.md
```

## Core Commands

See [usage.md](usage.md) for detailed command reference.

## Architecture

See [architecture.md](architecture.md) for system design.

## Language Support

See [language-pairs.md](language-pairs.md) for language-specific details.
