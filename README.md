# Loc-mvr: Game Localization Automation Workflow

<p align="center">
  <strong>LLM-powered translation pipeline replacing traditional outsourcing</strong><br>
  <a href="README_zh.md">中文文档</a>
</p>

## 🎯 Key Features

- **70%+ Cost Reduction**: $1.5/1k rows vs traditional $6-10/1k
- **Hour-level Delivery**: From weeks to hours
- **Quality Control**: Glossary + Style Guide + Dual QA

## 📊 Production Proven

- ✅ **30k+ rows validated**: $48.44 cost, 99.87% accuracy
- ✅ **Multi-model support**: GPT-4o, Claude Sonnet, Haiku
- ✅ **Dockerized**: Consistent environment

## 🚀 Quick Start

```bash
# Clone & Setup
git clone https://github.com/Charpup/game-localization-mvr.git
cd game-localization-mvr
cp .env.example .env  # Configure your API keys

# Build Docker
docker build -t loc-mvr .

# Run Pipeline (see README_zh.md for details)
python scripts/normalize_guard.py data/examples/sample_input.csv ...
```

## 📚 Documentation

- **For Humans**: See full pipeline in [README_zh.md](README_zh.md)
- **For LLM Agents**: See [docs/WORKSPACE_RULES.md](docs/WORKSPACE_RULES.md)

## 📄 License

MIT License

---

**Need LLM API?** Try [APIYi](https://api.apiyi.com/register/?aff_code=8Via)
