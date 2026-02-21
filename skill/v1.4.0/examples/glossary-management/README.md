# Glossary Management Example

## loc-mVR v1.4.0 术语表管理示例

## 示例 1: 创建术语表

### 基础术语表

```yaml
# basic_glossary.yaml
meta:
  name: "游戏核心术语表"
  version: "1.0.0"
  source_lang: zh-CN
  target_lang: en-US

domains:
  - gameplay
  - ui
  - story

terms:
  # 游戏玩法术语
  - id: term_001
    source: "生命值"
    target: "HP"
    domain: gameplay
    status: approved
    
  - id: term_002
    source: "魔法值"
    target: "MP"
    domain: gameplay
    status: approved
    
  - id: term_003
    source: "经验值"
    target: "EXP"
    domain: gameplay
    status: approved
    
  # UI 术语
  - id: term_101
    source: "开始游戏"
    target: "Start Game"
    domain: ui
    status: approved
    
  - id: term_102
    source: "设置"
    target: "Settings"
    domain: ui
    status: approved
```

## 示例 2: 术语表验证

### 验证命令

```bash
# 验证术语表格式
python -m skill.v1.4.0.scripts.cli glossary validate \
  --input basic_glossary.yaml

# 详细验证报告
python -m skill.v1.4.0.scripts.cli glossary validate \
  --input basic_glossary.yaml \
  --verbose \
  --report validation_report.json
```

### 验证规则

```yaml
# validation_rules.yaml
rules:
  - id: required_fields
    check: [source, target, domain]
    severity: error
    
  - id: unique_source
    check: duplicate_source
    severity: error
    
  - id: target_format
    pattern: "^[A-Za-z0-9\s_-]+$"
    severity: warning
```

## 示例 3: 术语表合并

### 多文件术语表

```
glossaries/
├── core_terms.yaml      # 核心玩法
├── ui_terms.yaml        # 界面术语
├── story_terms.yaml     # 剧情术语
└── merged/
```

### 合并脚本

```bash
#!/bin/bash
# merge_glossaries.sh

OUTPUT="glossaries/merged/complete_glossary.yaml"

python -m skill.v1.4.0.scripts.cli glossary merge \
  --inputs "glossaries/core_terms.yaml" \
  --inputs "glossaries/ui_terms.yaml" \
  --inputs "glossaries/story_terms.yaml" \
  --output "$OUTPUT" \
  --strategy union

echo "Merged glossary created: $OUTPUT"
```

## 示例 4: 术语表检查

### 检查翻译一致性

```bash
# 检查译文是否使用了正确的术语
python -m skill.v1.4.0.scripts.cli glossary check \
  --translation translated.csv \
  --glossary glossary.yaml \
  --report consistency_report.json
```

### 检查报告示例

```json
{
  "summary": {
    "total_terms": 50,
    "terms_found": 45,
    "violations": 3
  },
  "violations": [
    {
      "term": "生命值",
      "expected": "HP",
      "found": "Health Points",
      "location": "row_123",
      "severity": "warning"
    }
  ]
}
```

## 示例 5: 术语表版本管理

### 版本控制工作流

```bash
# 1. 创建术语表分支
git checkout -b glossary-update-v1.1

# 2. 修改术语表
vim glossaries/core_terms.yaml

# 3. 验证更改
python -m skill.v1.4.0.scripts.cli glossary validate \
  --input glossaries/core_terms.yaml

# 4. 检查影响范围
python -m skill.v1.4.0.scripts.cli glossary impact \
  --glossary glossaries/core_terms.yaml \
  --translation data/current_translation.csv

# 5. 提交更改
git add glossaries/core_terms.yaml
git commit -m "Update core terms: add 5 new gameplay terms"
```

## 示例 6: 术语表编译

### 编译配置

```yaml
# compile_config.yaml
input:
  - path: glossaries/source/
    pattern: "*.yaml"
    
output:
  path: glossaries/compiled.yaml
  format: yaml
  
options:
  deduplicate: true
  sort_by: source
  include_metadata: true
```

### 编译命令

```bash
python -m skill.v1.4.0.scripts.cli glossary compile \
  --config compile_config.yaml \
  --output compiled_glossary.yaml
```

## 最佳实践

1. **术语 ID 规范**: 使用 `domain_number` 格式 (e.g., `ui_001`, `gameplay_025`)
2. **状态管理**: 使用 `draft` → `review` → `approved` 工作流
3. **版本控制**: 每次修改更新 `meta.version`
4. **定期审查**: 每月运行一次一致性检查

## 常见问题

### Q: 术语冲突如何解决？

A: 使用优先级系统：
```yaml
terms:
  - source: "火"
    target: "Fire"      # 通用翻译
    domain: generic
    priority: 1
    
  - source: "火"
    target: "Flame"     # 特定场景
    domain: magic_system
    priority: 2         # 优先级更高
```

### Q: 如何处理多义词？

A: 添加上下文信息：
```yaml
terms:
  - source: "击"
    target: "Strike"
    context: "combat_action"
    example: "造成一次强力的击"
```
