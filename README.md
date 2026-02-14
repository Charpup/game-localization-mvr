# Loc-mvr: Game Localization Automation Workflow

<p align="center">
  <strong>LLM-powered translation pipeline replacing traditional outsourcing</strong><br>
  <a href="README_zh.md">中文文档</a>
</p>

## 🎯 Quick Start with Skill

**Download the pre-packaged Skill** (Recommended for first-time users):

[![Download Skill](https://img.shields.io/badge/Download-Skill_v1.1.0--stable-blue?style=for-the-badge)](https://github.com/Charpup/game-localization-mvr/releases/download/v1.1.0-stable/loc-mvr-v1.1.0-stable.skill)

```bash
# 1. Download and extract
unzip loc-mvr-v1.1.0-stable.skill

# 2. Verify checksum
sha256sum -c loc-mvr-v1.1.0-stable.skill.sha256

# 3. Follow Quick Start in SKILL.md
cd skill/
python scripts/normalize_guard.py examples/sample_input.csv ...
```

**Or clone the full repository**:

```bash
git clone https://github.com/Charpup/game-localization-mvr.git
cd game-localization-mvr
pip install -r requirements.txt
```

## 🎯 Key Features

- **70%+ Cost Reduction**: $1.5/1k rows vs traditional $6-10/1k
- **Hour-level Delivery**: From weeks to hours
- **Quality Control**: Glossary + Style Guide + Dual QA
- **Production Proven**: 30k+ rows validated at 99.87% accuracy
- **Robust Error Handling**: Long text isolation, tag protection, placeholder freezing

## 📊 Production Proven

- ✅ **30k+ rows validated**: $48.44 cost, 99.87% accuracy
- ✅ **Multi-model support**: GPT-4o, Claude Sonnet, Haiku
- ✅ **Dockerized**: Consistent environment (Rule 12 compliance)
- ✅ **Recent Improvements (v1.1.0)**:
  - Placeholder regex extension (% H pattern)
  - Long text isolation (>500 chars)
  - Tag protection during jieba segmentation
  - Unified trace path for 100% metrics coverage
  - Enhanced progress reporting with time deltas

## 🚀 Quick Start

```bash
# Clone & Setup
git clone https://github.com/Charpup/game-localization-mvr.git
cd game-localization-mvr
cp .env.example .env  # Configure your API keys

# Build Docker (required for LLM calls per Rule 12)
docker build -f Dockerfile.gate -t gate_v2 .

# Run Pipeline (see README_zh.md for details)
# Example: Full pipeline with Docker
.\scripts\docker_run.ps1 python -u -m scripts.translate_llm --input data/tokenized.csv --output data/translated.csv
```

## 🔍 监控与调试

### 成本追踪

启用 LLM 调用追踪:

```python
from trace_config import setup_trace_path

# 在脚本开始时调用
setup_trace_path(output_dir="data/my_test")

# 之后所有 LLM 调用都会记录到 data/my_test/llm_trace.jsonl
```

查看成本统计:

```bash
python scripts/metrics_aggregator.py --trace-path data/my_test/llm_trace.jsonl --output data/my_test/metrics_report.md
```

输出示例:

```
总 Tokens: 10,145,141
估算费用: $10.87 USD
```

### 进度监控

所有长时任务自动显示实时进度:

```
[translate] Batch 10/120 | 250/3000 rows (8.3%) | Δt: 5.5s | Total: 61.1s
```

- **Δt**: 上一个批次耗时
- **Total**: 从任务开始的总耗时

### 常见问题

**Q: API Key 注入失败?**

A: 使用提供的 Docker 启动脚本:

```powershell
# Windows
.\scripts\docker_run.ps1 python scripts/translate_llm.py ...
```

**Q: 长文本导致 token limit 错误?**

A: 已自动隔离处理。>500 字符的文本会被标记 `is_long_text=1` 并单独处理。

**Q: 成本超出预算?**

A: 检查 `metrics_report.md` 定位高成本阶段。

**Q: 标签被分词破坏?**

A: 已修复 (v1.1.0)。`<color=#ff0000>` 等标签在 jieba 分词前会被保护。

**Q: 如何查看开发路线图?**

A: 参见 [ROADMAP.md](ROADMAP.md) 了解短期/中期/长期计划，包括 ZH→EN 翻译支持。

## 📚 Documentation

- **For Humans**: See full pipeline in [README_zh.md](README_zh.md)
- **For LLM Agents**: See [docs/WORKSPACE_RULES.md](docs/WORKSPACE_RULES.md)

## 📄 License

MIT License

---

**Need LLM API?** Try [APIYi](https://api.apiyi.com/register/?aff_code=8Via)
