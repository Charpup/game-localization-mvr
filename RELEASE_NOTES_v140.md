# Loc-MVR v1.4.0 Release Notes

## 🎉 Skill 化改造完成

v1.4.0 是完全符合 Anthropic Skill-Creator 标准的 skill 包。

### ✨ 主要改进

#### 1. 标准 Skill 结构
```
skill/v1.4.0/
├── SKILL.md              # 标准元数据 (无 version 字段)
├── scripts/
│   ├── core/            # 核心翻译脚本 (13个)
│   ├── utils/           # 工具库
│   ├── cli.py           # CLI 入口
│   └── ...
├── references/          # 详细文档 (6个)
│   ├── usage.md
│   ├── architecture.md
│   ├── language-pairs.md
│   ├── api-reference.md
│   ├── testing.md
│   └── troubleshooting.md
├── lib/                 # 库代码
├── config/              # 配置文件
└── examples/            # 示例工作流
```

#### 2. CLI 入口
```bash
loc-mvr translate --target-lang en-US --input data.csv
loc-mvr glossary --action translate --proposals terms.yaml
loc-mvr qa --input translated.csv
```

#### 3. 渐进式披露
- Level 1: SKILL.md (快速了解)
- Level 2: references/*.md (详细文档)
- Level 3: examples/ (实践示例)

### 📊 合规性评分

| 项目 | v1.3.0 | v1.4.0 |
|------|--------|--------|
| Frontmatter | 6/10 | 10/10 |
| Body | 10/10 | 10/10 |
| References | 5/10 | 10/10 |
| Disclosure | 3/10 | 10/10 |
| Scripts | 6/10 | 10/10 |
| **总分** | **30/50** | **50/50** |

### 🔧 技术改进

- 101 个脚本分类整理到 5 个目录
- 统一配置加载 (config_loader.py)
- 输入验证 (validator.py)
- 6 个 reference 文档
- 3 个示例工作流

### 📦 Assets

- `loc-mvr-v1.4.0.skill.tar.gz` - Skill 包
- Source code

### 🔄 迁移指南

v1.3.0 → v1.4.0:
```bash
# 旧方式 (仍然支持)
python skill/v1.3.0/scripts/batch_runtime.py

# 新方式 (推荐)
loc-mvr translate --target-lang en-US
```
