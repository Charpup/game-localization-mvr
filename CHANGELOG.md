# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0] - 2025-02-20

### Added
- **Multi-Language Support**: Extended pipeline to support 7 target languages
  - English (en-US) - Full support
  - Russian (ru-RU) - Full support
  - Japanese (ja-JP) - Ready for production
  - Korean (ko-KR) - Ready for production
  - French (fr-FR) - Ready for production
  - German (de-DE) - Ready for production
  - Spanish (es-ES) - Ready for production
- **Quality Assurance Module**: Added automated QA with language-specific rules
  - English QA rules (`src/config/qa_rules/en.yaml`)
  - Soft QA LLM script for post-translation validation
- **Glossary Management**: Smart term extraction and translation system
  - `glossary_translate_llm.py` for terminology-aware translation
  - Language pair configurations in `src/config/language_pairs.yaml`
- **Cost Optimization**: Intelligent model routing and caching mechanisms
- **Prompt Templates**: Language-specific prompt templates
  - English prompts (`src/config/prompts/en/`)
  - Russian prompts (`src/config/prompts/ru/`)

### Changed
- Updated `batch_runtime.py` with improved error handling and progress tracking
- Enhanced model routing for better cost efficiency
- Improved caching strategy for repeated translations

### Fixed
- Resolved timeout issues in batch processing
- Fixed character encoding issues for non-Latin scripts
- Corrected glossary term matching accuracy

## [1.2.0] - 2025-01-15

### Added
- Initial batch translation pipeline
- Basic glossary extraction functionality
- Support for English and Russian translations

### Changed
- Refactored translation engine for better modularity

## [1.1.0] - 2024-12-01

### Added
- Docker support for containerized deployments
- API rate limiting and usage monitoring

### Fixed
- Memory leak in long-running batch processes

## [1.0.0] - 2024-10-15

### Added
- Initial release of Loc-MVR
- Core translation pipeline using LLM models
- Basic configuration system
- Command-line interface

---

## Legend

- ✅ Full - Fully tested and production-ready
- ✅ Ready - Implementation complete, ready for testing
- 🚧 Beta - In development/testing phase
- ⏳ Planned - Scheduled for future release
