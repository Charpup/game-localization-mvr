# Loc-MVR v1.3.0

游戏本地化 MVR (Multi-Language, Validation, Release)  
Game Localization Pipeline with Multi-Language Support

## 🌟 功能特性

- **多语言支持**: 从中文翻译到 7 种目标语言
- **质量保证**: 基于语言特定规则的自动化 QA
- **术语管理**: 智能术语提取与翻译
- **成本优化**: 智能模型路由与缓存机制

## 🚀 快速开始

### 英语翻译
```bash
python scripts/batch_runtime.py --target-lang en-US
```

### 日语翻译
```bash
python scripts/glossary_translate_llm.py --target-lang ja-JP
```

### 支持的语言

| 语言 | 代码 | 状态 |
|------|------|------|
| 英语 | en-US | ✅ 完整支持 |
| 俄语 | ru-RU | ✅ 完整支持 |
| 日语 | ja-JP | ✅ 已就绪 |
| 韩语 | ko-KR | ✅ 已就绪 |
| 法语 | fr-FR | ✅ 已就绪 |
| 德语 | de-DE | ✅ 已就绪 |
| 西班牙语 | es-ES | ✅ 已就绪 |

## 📁 项目结构

```
src/
├── config/
│   ├── language_pairs.yaml    # 语言配置
│   ├── prompts/
│   │   ├── en/                # 英语提示词
│   │   └── ru/                # 俄语提示词
│   └── qa_rules/
│       └── en.yaml            # 英语 QA 规则
└── scripts/
    ├── batch_runtime.py       # 主翻译脚本
    ├── glossary_translate_llm.py  # 术语翻译
    └── soft_qa_llm.py         # 软 QA 检查
```

## 🔧 配置说明

语言对在 `src/config/language_pairs.yaml` 中定义。

当前支持的语言对：
- zh-cn → ru-ru (中文 → 俄语)
- zh-cn → en-us (中文 → 英语)
- zh-cn → ja-jp (中文 → 日语)

## 🛠️ 开发

### 安装依赖
```bash
pip install -r requirements.txt
```

### 运行测试
```bash
pytest tests/
```

### 代码覆盖率
```bash
pytest --cov=src tests/
```

## 📜 许可证

MIT License

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📮 联系方式

如有问题或建议，请通过 GitHub Issues 联系我们。
