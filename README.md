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

A: 已修复。`<color=#ff0000>` 等标签在 jieba 分词前会被保护。

## 📚 Documentation

- **For Humans**: See full pipeline in [README_zh.md](README_zh.md)
- **For LLM Agents**: See [docs/WORKSPACE_RULES.md](docs/WORKSPACE_RULES.md)

## 📄 License

MIT License

---

**Need LLM API?** Try [APIYi](https://api.apiyi.com/register/?aff_code=8Via)
