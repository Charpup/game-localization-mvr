# Loc-mvr: 游戏本地化自动化工作流

<p align="center">
  <strong>LLM 驱动的游戏翻译 Pipeline，替代传统外包流程</strong>
</p>

## 🎯 核心价值

- **降低成本 70%+**: 替代翻译公司，$1.5/千行 vs 传统 $6-10/千行
- **提升效率**: 周级 → 小时级交付
- **质量可控**: Glossary + Style Guide + 双重 QA

## 📊 生产验证

- ✅ **30k+ 行生产任务**: 成本 $48.44，质量达标率 99.87%
- ✅ **多模型支持**: GPT-4o, Claude Sonnet, Haiku
- ✅ **Docker 容器化**: 环境一致性保证

## 🚀 快速开始

### 环境准备

```bash
# 克隆仓库
git clone https://github.com/Charpup/game-localization-mvr.git
cd game-localization-mvr

# 配置 API Key
cp .env.example .env
# 编辑 .env 填入你的 API Key

# 构建 Docker 镜像
docker build -t loc-mvr .
```

### 运行完整 Pipeline

```bash
# 1. 标准化处理
python scripts/normalize_guard.py data/examples/sample_input.csv \
  data/normalized.csv data/placeholder_map.json workflow/placeholder_schema.yaml

# 2. 提取术语候选
python scripts/glossary_extract.py data/normalized.csv glossary/candidates.csv

# 3. 翻译 (需配置 LLM API)
python scripts/translate_llm.py data/normalized.csv data/translated.csv \
  workflow/style_guide.md glossary/compiled.yaml

# 4. 质量检查
python scripts/qa_hard.py data/translated.csv data/qa_report.json \
  data/placeholder_map.json

# 5. 最终导出
python scripts/rehydrate_export.py data/translated.csv \
  data/placeholder_map.json data/final_export.csv
```

## 📚 文档导航

- **人类用户**: 查看 [docs/workflow.md](docs/workflow.md) 了解完整流程
- **LLM Agent**: 查看 [docs/WORKSPACE_RULES.md](docs/WORKSPACE_RULES.md) 获取执行约束

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

---

**需要 LLM API?** 推荐 [APIYi](https://api.apiyi.com/register/?aff_code=8Via)
