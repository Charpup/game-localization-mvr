# Loc-MVR v1.3.0

游戏本地化 MVR (Multi-Language, Validation, Release)  
Game Localization Pipeline with Multi-Language Support

## 🌟 Features

- **Multi-Language**: 7 target languages from Chinese
- **Quality Assurance**: Automated QA with language-specific rules
- **Glossary Management**: Smart term extraction and translation
- **Cost Optimization**: Intelligent model routing and caching

## 🚀 Quick Start

### English Translation
```bash
python scripts/batch_runtime.py --target-lang en-US
```

### Japanese Translation
```bash
python scripts/glossary_translate_llm.py --target-lang ja-JP
```

### Supported Languages

| Language | Code | Status |
|----------|------|--------|
| English | en-US | ✅ Full |
| Russian | ru-RU | ✅ Full |
| Japanese | ja-JP | ✅ Ready |
| Korean | ko-KR | ✅ Ready |
| French | fr-FR | ✅ Ready |
| German | de-DE | ✅ Ready |
| Spanish | es-ES | ✅ Ready |

## 📁 Project Structure

```
src/
├── config/
│   ├── language_pairs.yaml    # Language configuration
│   ├── prompts/
│   │   ├── en/                # English prompts
│   │   └── ru/                # Russian prompts
│   └── qa_rules/
│       └── en.yaml            # English QA rules
└── scripts/
    ├── batch_runtime.py       # Main translation
    ├── glossary_translate_llm.py
    └── soft_qa_llm.py
```

## 🔧 Configuration

Language pairs are defined in `src/config/language_pairs.yaml`.

## 📜 License

MIT License
