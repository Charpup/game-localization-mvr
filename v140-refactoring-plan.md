# loc-mVR v1.4.0 Skill 化改造计划

**版本**: 1.4.0  
**日期**: 2026-02-21  
**状态**: 规划中  

---

## 1. 现状分析

### 1.1 当前结构 (v1.3.0)

```
game-localization-mvr/
├── skill/v1.3.0/                    # Skill 目录
│   ├── SKILL.md                     # Skill 元数据文件
│   ├── config/                      # 配置文件
│   │   ├── glossary/               # 术语表配置
│   │   ├── prompts/                # LLM 提示词模板
│   │   ├── qa_rules/               # QA 规则
│   │   └── workflow/               # 工作流配置
│   ├── scripts/                    # 执行脚本 (100+ 文件)
│   └── requirements.txt            # 依赖
├── src/                            # 源代码
│   ├── config/                     # 与 skill/v1.3.0/config/ 重复
│   ├── scripts/                    # 与 skill/v1.3.0/scripts/ 重复
│   ├── lib/                        # 库代码
│   └── templates/                  # 模板文件
└── tests/                          # 测试
```

### 1.2 现有问题

| 问题类别 | 具体问题 | 影响 |
|---------|---------|------|
| **结构问题** | `src/` 和 `skill/v1.3.0/` 内容重复 | 维护困难，版本混淆 |
| **文档缺失** | 无 `references/` 目录 | Agent 无法按需加载详细参考 |
| **使用指南** | 无 `usage.md` | 用户难以快速上手 |
| **架构文档** | 无 `architecture.md` | 难以理解系统结构 |
| **CLI 入口** | 无统一命令入口 | 操作不便捷 |
| **SKILL.md** | 内容过于简略 | 不符合 OpenClaw 标准 |

### 1.3 与 OpenClaw 标准对比

| 标准项 | OpenClaw 要求 | v1.3.0 状态 | 差距 |
|-------|---------------|------------|------|
| SKILL.md | 完整的前言元数据 + 详细工作流 | ⚠️ 基础元数据，缺少详细说明 | 需重构 |
| scripts/ | 可执行脚本 | ✅ 存在 | 保留 |
| references/ | 按需加载的参考文档 | ❌ 不存在 | 需创建 |
| assets/ | 模板和输出资源 | ❌ 不存在 | 需创建 |
| usage.md | 快速使用指南 | ❌ 不存在 | 需创建 |
| CLI 入口 | 统一命令 | ❌ 不存在 | 需创建 |

---

## 2. 改造清单

### 2.1 必需改动 (P0)

#### 2.1.1 重构 SKILL.md
- [ ] **添加标准 YAML 前言**
  - `name`: `loc-mvr`
  - `version`: `1.4.0`
  - `description`: 包含触发条件和功能说明
  - `compatibility`: Python 3.11+, Linux/macOS/Windows
  
- [ ] **重构 Body 内容**
  - 概述：功能简介和适用场景
  - 快速开始：3 分钟上手指南
  - 核心工作流：翻译、QA、术语管理
  - 脚本索引：所有脚本的分类说明
  - 参考文档索引：链接到 references/

- [ ] **渐进式披露设计**
  - SKILL.md < 500 行
  - 详细内容移入 references/
  - 明确引用关系和加载时机

#### 2.1.2 创建 references/ 目录

```
skill/v1.4.0/references/
├── architecture.md          # 系统架构详解
├── workflow-guide.md        # 完整工作流指南
├── glossary-management.md   # 术语表管理指南
├── qa-rules.md             # QA 规则详解
├── api-reference.md        # 脚本 API 参考
├── troubleshooting.md      # 故障排除指南
└── migration-guide.md      # 版本迁移指南
```

#### 2.1.3 添加 usage.md

位置: `skill/v1.4.0/usage.md`

内容:
- 环境准备
- 快速开始 (3 步)
- 常用命令速查表
- 示例工作流

#### 2.1.4 添加 architecture.md

位置: `skill/v1.4.0/references/architecture.md`

内容:
- 系统架构图
- 模块关系
- 数据流
- 配置层次

#### 2.1.5 创建标准 scripts/ 入口

- [ ] 统一 CLI 入口: `loc-mvr`
- [ ] 命令结构:
  ```
  loc-mvr translate --target-lang en-US --input file.csv
  loc-mvr qa --type soft --input file.csv
  loc-mvr glossary --action compile
  loc-mvr config --validate
  ```

### 2.2 结构优化 (P1)

#### 2.2.1 清理重复内容

- [ ] **迁移策略**
  - `src/scripts/` → `skill/v1.4.0/scripts/` (合并)
  - `src/config/` → `skill/v1.4.0/config/` (合并)
  - `src/lib/` → `skill/v1.4.0/lib/` (创建)
  - `src/templates/` → `skill/v1.4.0/assets/templates/` (迁移)

- [ ] **删除重复项**
  - 删除 `src/` 目录（内容已迁移）
  - 保留 `tests/` 在项目根目录

#### 2.2.2 创建 assets/ 目录

```
skill/v1.4.0/assets/
├── templates/
│   ├── style_guides/
│   │   ├── bleach.md
│   │   ├── naruto.md
│   │   └── one_piece.md
│   └── config_template.yaml
├── samples/
│   └── sample_input.csv
└── schemas/
    └── config_schema.json
```

#### 2.2.3 标准化 config/ 结构

```
skill/v1.4.0/config/
├── language_pairs.yaml          # 语言对配置
├── glossary/                    # 术语表
│   ├── approved.yaml
│   ├── compiled.yaml
│   └── global.yaml
├── prompts/                     # 提示词模板
│   ├── en/
│   │   ├── batch_translate_system.txt
│   │   ├── glossary_translate_system.txt
│   │   └── soft_qa_system.txt
│   └── ru/
│       ├── batch_translate_system.txt
│       └── glossary_translate_system.txt
├── qa_rules/                    # QA 规则
│   └── en.yaml
└── workflow/                    # 工作流配置
    ├── llm_config.yaml
    ├── soft_qa_rubric.yaml
    └── style_guide.md
```

### 2.3 功能增强 (P2)

#### 2.3.1 CLI 入口 `loc-mvr`

- [ ] **创建 CLI 脚本**: `skill/v1.4.0/scripts/cli.py`
- [ ] **命令解析**: 使用 argparse
- [ ] **子命令**:
  - `translate`: 翻译工作流
  - `qa`: QA 检查
  - `glossary`: 术语表管理
  - `config`: 配置管理
  - `validate`: 验证输入

#### 2.3.2 优化配置加载

- [ ] **配置分层**
  ```python
  # 优先级: 命令行 > 环境变量 > 项目配置 > 用户配置 > 默认配置
  config = load_config(
      default='config/default.yaml',
      user='~/.loc-mvr/config.yaml',
      project='./.loc-mvr.yaml',
      env='LOC_MVR_',
      cli=args
  )
  ```

- [ ] **配置验证**
  - 使用 JSON Schema 验证
  - 友好的错误提示

#### 2.3.3 添加示例工作流

- [ ] **创建 examples/ 目录**
  ```
  skill/v1.4.0/examples/
  ├── basic-translation/
  │   ├── README.md
  │   ├── input.csv
  │   └── run.sh
  ├── batch-processing/
  │   ├── README.md
  │   └── process.sh
  └── glossary-management/
      ├── README.md
      └── manage.sh
  ```

- [ ] **示例脚本**
  - 基础翻译示例
  - 批量处理示例
  - 术语表管理示例

---

## 3. 目标结构 (v1.4.0)

```
game-localization-mvr/
├── skill/
│   ├── v1.3.0/                    # 旧版本 (保留)
│   └── v1.4.0/                    # 新版本
│       ├── SKILL.md               # 标准 Skill 文件
│       ├── usage.md               # 快速使用指南
│       ├── requirements.txt       # Python 依赖
│       ├── config/                # 配置文件
│       │   ├── language_pairs.yaml
│       │   ├── glossary/
│       │   ├── prompts/
│       │   ├── qa_rules/
│       │   └── workflow/
│       ├── scripts/               # 执行脚本
│       │   ├── cli.py            # CLI 入口
│       │   ├── batch_runtime.py
│       │   ├── glossary_translate_llm.py
│       │   ├── soft_qa_llm.py
│       │   └── ...
│       ├── lib/                   # 库代码 (从 src/lib/ 迁移)
│       │   └── ...
│       ├── references/            # 参考文档
│       │   ├── architecture.md
│       │   ├── workflow-guide.md
│       │   ├── glossary-management.md
│       │   ├── api-reference.md
│       │   └── troubleshooting.md
│       ├── assets/                # 资源文件
│       │   ├── templates/
│       │   ├── samples/
│       │   └── schemas/
│       └── examples/              # 示例工作流
│           ├── basic-translation/
│           ├── batch-processing/
│           └── glossary-management/
├── tests/                         # 测试 (项目级)
└── docs/                          # 项目文档 (可选)
```

---

## 4. 实施计划

### 4.1 阶段划分

| 阶段 | 任务 | 预估时间 | 依赖 |
|-----|------|---------|------|
| **Phase 1** | 结构准备 | 2h | - |
| **Phase 2** | 文档重构 | 3h | Phase 1 |
| **Phase 3** | 功能增强 | 2h | Phase 2 |
| **Phase 4** | 测试验证 | 1h | Phase 3 |

### 4.2 详细步骤

#### Phase 1: 结构准备 (2h)

```bash
# 1. 创建 v1.4.0 目录结构
mkdir -p skill/v1.4.0/{config/{glossary,prompts/{en,ru},qa_rules,workflow},scripts,lib,references,assets/{templates,samples,schemas},examples}

# 2. 迁移 config (从 v1.3.0)
cp -r skill/v1.3.0/config/* skill/v1.4.0/config/

# 3. 迁移 scripts (从 v1.3.0, 去重)
rsync -av --ignore-existing skill/v1.3.0/scripts/ skill/v1.4.0/scripts/

# 4. 迁移 lib (从 src/lib)
cp -r src/lib/* skill/v1.4.0/lib/

# 5. 迁移 assets
cp -r src/templates/* skill/v1.4.0/assets/templates/
```

#### Phase 2: 文档重构 (3h)

1. **编写 SKILL.md** (1h)
   - YAML 前言
   - 概述
   - 快速开始
   - 核心工作流
   - 参考文档索引

2. **编写 usage.md** (30min)
   - 环境准备
   - 快速开始
   - 命令速查

3. **编写 references/** (1.5h)
   - architecture.md
   - workflow-guide.md
   - api-reference.md
   - troubleshooting.md

#### Phase 3: 功能增强 (2h)

1. **创建 CLI 入口** (1h)
   ```python
   # scripts/cli.py
   # 实现 loc-mvr 命令
   ```

2. **优化配置加载** (30min)
   ```python
   # lib/config_loader.py
   # 分层配置加载
   ```

3. **创建示例工作流** (30min)
   - examples/basic-translation/
   - examples/batch-processing/

#### Phase 4: 测试验证 (1h)

1. **结构验证**
   - 检查目录结构
   - 验证文件完整性

2. **功能验证**
   - 测试 CLI 入口
   - 测试核心脚本
   - 验证配置加载

3. **打包验证**
   ```bash
   # 打包 skill
   tar -czf skill/v1.4.0/loc-mvr-1.4.0.skill.tar.gz skill/v1.4.0/
   sha256sum skill/v1.4.0/loc-mvr-1.4.0.skill.tar.gz > skill/v1.4.0/loc-mvr-1.4.0.skill.tar.gz.sha256
   ```

---

## 5. 工作量预估

| 类别 | 任务数 | 预估时间 | 优先级 |
|-----|-------|---------|-------|
| **必需改动** | 5 | 4h | P0 |
| **结构优化** | 3 | 2h | P1 |
| **功能增强** | 3 | 2h | P2 |
| **测试验证** | 3 | 1h | P0 |
| **总计** | 14 | **~8h** | - |

---

## 6. 验收标准

### 6.1 结构检查

- [ ] v1.4.0 目录结构符合规划
- [ ] SKILL.md 存在且包含标准 YAML 前言
- [ ] references/ 目录包含所有必需文档
- [ ] assets/ 目录包含模板和样本
- [ ] examples/ 目录包含示例工作流

### 6.2 功能检查

- [ ] `loc-mvr --help` 正常输出
- [ ] `loc-mvr translate --help` 正常输出
- [ ] 核心脚本可在 v1.4.0 环境中运行
- [ ] 配置加载正常工作

### 6.3 文档检查

- [ ] SKILL.md < 500 行
- [ ] usage.md 包含快速开始指南
- [ ] references/architecture.md 包含架构图
- [ ] 所有文档链接有效

### 6.4 打包检查

- [ ] 生成 `loc-mvr-1.4.0.skill.tar.gz`
- [ ] 生成对应的 `.sha256` 校验文件
- [ ] 包大小合理 (< 50MB)

---

## 7. 风险与缓解

| 风险 | 可能性 | 影响 | 缓解措施 |
|-----|-------|------|---------|
| 脚本兼容性问题 | 中 | 高 | 全面测试后再切换 |
| 配置迁移错误 | 低 | 中 | 备份 v1.3.0 配置 |
| 文档遗漏 | 中 | 低 | 使用检查清单逐项验证 |
| 时间超支 | 低 | 低 | 按阶段交付，优先 P0 |

---

## 8. 附录

### 8.1 参考资源

- [OpenClaw Skill Creator Guide](/root/.openclaw/skills/anthropic/references/skill-creator/openclaw-adapted/skill-creator-guide-openclaw.md)
- [OpenClaw Skill Template](/root/.openclaw/skills/anthropic/references/skill-creator/openclaw-adapted/skill-template-openclaw.md)
- [AGENTS.md](/root/.openclaw/workspace/AGENTS.md) - Skill Creation Workflow 章节

### 8.2 相关文件

- 当前 SKILL.md: `skill/v1.3.0/SKILL.md`
- 项目 README: `README.md`
- 项目 README (中文): `README_zh.md`

---

**计划制定**: 2026-02-21  
**计划版本**: 1.0  
**下次审查**: v1.4.0 开发启动时
