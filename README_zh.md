# Loc-mvr: 游戏本地化自动化工作流

<p align="center">
  <strong>LLM 驱动的翻译流水线，替代传统外包</strong><br>
  <a href="README.md">English Documentation</a>
</p>

## 🎯 Skill 快速开始

**下载预打包的 Skill**（推荐首次使用）：

[![下载 Skill](https://img.shields.io/badge/下载-Skill_v1.2.0-blue?style=for-the-badge)](https://github.com/Charpup/game-localization-mvr/releases/download/v1.2.0/loc-mvr-v1.2.0.skill)

```bash
# 1. 下载并解压
wget https://github.com/Charpup/game-localization-mvr/releases/download/v1.2.0/loc-mvr-v1.2.0.skill
unzip loc-mvr-v1.2.0.skill

# 2. 验证校验和
sha256sum -c loc-mvr-v1.2.0.skill.sha256

# 3. 按照 SKILL.md 快速开始
cd skill/
python scripts/normalize_guard.py examples/sample_input.csv ...
```

**或者克隆完整仓库**：

```bash
git clone https://github.com/Charpup/game-localization-mvr.git
cd game-localization-mvr
pip install -r requirements.txt
```

## ✨ v1.2.0 功能亮点

### 🧠 智能模型路由（新增）
根据内容复杂度自动选择最具成本效益的模型：
- **复杂度分析**：分析文本长度、占位符、术语表密度和特殊字符
- **成本优化**：简单文本使用更便宜的模型（GPT-3.5、GPT-4.1-nano），复杂内容使用高级模型（GPT-4、Claude Sonnet）
- **历史学习**：跟踪 QA 失败模式以改进路由决策
- **预期节省**：典型工作负载节省 20-40% 成本

```python
from scripts.model_router import ModelRouter

router = ModelRouter()
model, metrics, cost = router.select_model(
    text="Your text here",
    glossary_terms=["忍者", "攻击"]
)
# 返回基于复杂度分析的最佳模型
```

### ⚡ 异步/并发执行（新增）
通过并行处理实现 30-50% 延迟降低：
- **异步 LLM 客户端**：基于信号量的并发 API 调用速率限制
- **流式流水线**：重叠的流水线阶段（标准化 → 翻译 → QA → 导出）
- **背压处理**：防止高负载下的内存溢出
- **可配置并发**：针对 I/O 与 CPU 密集型操作优化的每阶段限制

```python
from scripts.async_adapter import process_csv_async

stats = asyncio.run(process_csv_async(
    input_path="data/input.csv",
    output_path="data/output.csv"
))
# 吞吐量：~50-100 行/秒（同步模式 ~20-30）
```

### 📚 术语表 AI 系统（新增）
智能术语表匹配和纠错：
- **智能匹配器**：模糊匹配，高置信度匹配自动审批率达 95%+
- **自动纠错器**：检测并建议修复术语表违规、拼写错误、大小写问题
- **俄语变格支持**：处理俄语翻译的变格词尾
- **上下文验证**：使用周围上下文消除同形异义词歧义

```python
from scripts.glossary_matcher import GlossaryMatcher
from scripts.glossary_corrector import GlossaryCorrector

# 匹配文本中的术语表术语
matcher = GlossaryMatcher()
matches = matcher.find_matches("忍者的攻击力很高")

# 检测并纠正违规
corrector = GlossaryCorrector()
suggestions = corrector.detect_violations(translation_text)
```

### 💾 增强响应缓存
基于 SQLite 的持久缓存，具有高级功能：
- **TTL 支持**：可配置过期时间（默认 7 天）
- **LRU 淘汰**：达到大小限制时自动清理
- **缓存分析**：实时命中/未命中跟踪及成本节省计算
- **重复翻译节省 50%+ 成本**

```bash
# 查看缓存统计
python scripts/cache_manager.py --stats

# 运行前清除缓存
python scripts/translate_llm.py --input data.csv --cache-clear
```

## 📊 生产验证

- ✅ **30k+ 行生产验证**：成本 $48.44，准确率 99.87%
- ✅ **多模型支持**：GPT-4o、Claude Sonnet、Haiku、Kimi-k2.5
- ✅ **Docker 容器化**：通过 API 密钥注入保证环境一致性
- ✅ **响应缓存**：重复内容节省 50%+ 成本
- ✅ **智能路由**：额外节省 20-40% 成本
- ✅ **异步处理**：延迟降低 30-50%
- ✅ **术语表 AI**：术语表匹配自动审批率达 95%+

## 🚀 快速开始

```bash
# 克隆与设置
git clone https://github.com/Charpup/game-localization-mvr.git
cd game-localization-mvr
cp .env.example .env  # 配置你的 API 密钥

# 构建 Docker（LLM 调用需要）
docker build -f Dockerfile.gate -t gate_v2 .

# 选项 1：使用智能模型路由运行（推荐）
python scripts/translate_llm.py --input data/tokenized.csv --output data/translated.csv --smart-routing

# 选项 2：使用异步处理以获得最大速度
python scripts/async_adapter.py --input data/input.csv --output data/output.csv --max-concurrent 10

# 选项 3：使用 Docker 运行完整流水线
.\scripts\docker_run.ps1 python -u -m scripts.translate_llm --input data/tokenized.csv --output data/translated.csv
```

## 📈 性能数据

| 指标 | v1.1.0 | v1.2.0 | 改进 |
|------|--------|--------|------|
| 吞吐量（行/秒） | 20-30 | 50-100 | 2-3x |
| 平均每千行成本 | $1.50 | $0.90-1.20 | 20-40% ↓ |
| 术语表匹配准确率 | 85% | 95%+ | +10% |
| 缓存命中率 | 60% | 75% | +15% |
| 首次翻译延迟 | 120s | 80s | 33% ↓ |

**成本明细（每千行）**：
- 传统外包：$6-10
- v1.1.0 基线：$1.50
- v1.2.0 路由+缓存：$0.90-1.20

## 💾 响应缓存

本地化流水线包含**智能响应缓存层**，可在重复翻译上降低 **50%+** 的 LLM 成本。

### 配置

编辑 `config/pipeline.yaml`：

```yaml
cache:
  enabled: true
  ttl_days: 7
  max_size_mb: 100
  location: ".cache/translations.db"
```

### 缓存使用

```bash
# 使用缓存运行（默认）
python scripts/translate_llm.py --input data/input.csv --output data/output.csv

# 不使用缓存（绕过查找）
python scripts/translate_llm.py --input data/input.csv --output data/output.csv --no-cache

# 运行前清除缓存
python scripts/translate_llm.py --input data/input.csv --output data/output.csv --cache-clear

# 查看缓存统计
python scripts/cache_manager.py --stats

# 查看缓存大小
python scripts/cache_manager.py --size

# 清除所有缓存条目
python scripts/cache_manager.py --clear
```

### 缓存指标

翻译期间显示缓存统计：

```
📊 缓存统计：
   命中：150
   未命中：50
   命中率：75.00%
   💰 成本节省：75.0%（缓存命中 = 零成本）
   缓存大小：12.34 MB / 100 MB
```

## 🧠 模型路由

基于内容复杂度的智能模型选择：

```bash
# 分析文本复杂度
python scripts/model_router.py --analyze "Your text here"

# 为文本选择最佳模型
python scripts/model_router.py --select "Your text here" --step translate

# 查看路由统计
python scripts/model_router.py --stats
```

**路由决策因素**：
- 文本长度（20% 权重）
- 占位符密度（25% 权重）
- 术语表术语密度（25% 权重）
- 特殊字符密度（15% 权重）
- 历史失败率（15% 权重）

## ⚡ 异步处理

大型数据集的高性能异步执行：

```bash
# 使用异步流水线处理
python scripts/async_adapter.py \
  --input data/large_file.csv \
  --output data/output.csv \
  --max-concurrent 10 \
  --buffer-size 100

# 运行基准测试
python scripts/async_adapter.py \
  --input data/test.csv \
  --output data/out.csv \
  --benchmark
```

## 🔍 监控与调试

### 成本跟踪

启用 LLM 调用跟踪：

```python
from trace_config import setup_trace_path

# 脚本启动时
setup_trace_path(output_dir="data/my_test")
# 所有 LLM 调用记录到 data/my_test/llm_trace.jsonl
```

查看成本统计：

```bash
python scripts/metrics_aggregator.py \
  --trace-path data/my_test/llm_trace.jsonl \
  --output data/my_test/metrics_report.md
```

输出示例：

```
总 Tokens: 10,145,141
估算费用: $10.87 USD
```

### 进度监控

所有长时间运行的任务显示实时进度：

```
[translate] Batch 10/120 | 250/3000 rows (8.3%) | Δt: 5.5s | Total: 61.1s
```

- **Δt**：上一批次持续时间
- **Total**：任务开始以来的运行时间

## 📚 文档

- **[快速入门指南](docs/QUICK_START.md)** - 5 分钟上手
- **[API 文档](docs/API.md)** - 完整 API 参考
- **[配置指南](docs/CONFIGURATION.md)** - 完整配置选项
- **[LLM Agent 指南](docs/WORKSPACE_RULES.md)** - Agent 专用说明
- **[English](README.md)** - 英文文档

## 🛠️ 故障排除

**Q: API 密钥注入失败？**

A: 使用提供的 Docker 脚本：

```powershell
# Windows
.\scripts\docker_run.ps1 python scripts/translate_llm.py ...

# Linux/Mac
./scripts/docker_run.sh python scripts/translate_llm.py ...
```

**Q: 长文本导致令牌限制错误？**

A: 长文本（>500 字符）会自动标记 `is_long_text=1` 标志进行隔离。

**Q: 成本超出预算？**

A: 查看 `metrics_report.md` 识别高成本阶段。启用模型路由和缓存以节省成本。

**Q: 翻译过程中标签损坏？**

A: HTML/Unity 标签在 jieba 分词期间自动保护（v1.1.0+）。

**Q: 如何从 v1.1.0 升级？**

A: 查看 [CHANGELOG.md](CHANGELOG.md) 了解迁移指南。

## 📄 许可证

MIT 许可证

---

**需要 LLM API？** 试试 [APIYi](https://api.apiyi.com/register/?aff_code=8Via)
