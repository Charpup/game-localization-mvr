# Loc-MVR v1.3.0 Release Notes

## 🎉 Multi-Language Support

Loc-MVR now supports 7 target languages from Chinese (Simplified):

- 🇺🇸 English (en-US)
- 🇷🇺 Russian (ru-RU)
- 🇯🇵 Japanese (ja-JP)
- 🇰🇷 Korean (ko-KR)
- 🇫🇷 French (fr-FR)
- 🇩🇪 German (de-DE)
- 🇪🇸 Spanish (es-ES)

## ✨ New Features

### Multi-Language Framework
- Configuration-based language switching via `--target-lang`
- Dynamic prompt loading from `src/config/prompts/{lang}/`
- Language-specific QA rules
- Backwards compatible (Russian default)

### Core Scripts Updated
- **batch_runtime.py**: Multi-language batch translation
- **glossary_translate_llm.py**: 7-language glossary support
- **soft_qa_llm.py**: Language-aware quality assurance

### Usage

```bash
# English translation
python scripts/batch_runtime.py --target-lang en-US

# Japanese translation
python scripts/glossary_translate_llm.py --target-lang ja-JP
```

## 🔧 Changes

- Added `language_pairs.yaml` with 3 language pairs
- Created EN/RU prompt templates
- Added EN QA rules configuration
- Refactored core scripts for multi-language
- Added 7 language code support

## 📦 Assets

- Source code (zip)
- Source code (tar.gz)
- `loc-mvr-v1.3.0.skill` - OpenClaw skill package

## 🔗 Links

- Full Changelog: v1.2.0...v1.3.0
- Documentation: README.md
