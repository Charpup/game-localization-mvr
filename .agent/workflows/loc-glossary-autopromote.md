---
description: 用生产 evidence 自动提取术语提案（含 style profile 风险降级）
---

# /loc-glossary-autopromote 工作流

根据 `data/translated.csv` 与 `data/repaired.csv` 的修订差异，输出可复用术语提案。

该流程已接入 `data/style_profile.yaml`，命中禁译/偏好规则时会自动打标，送人工确认。

## 执行命令

### 基础流程

```bash
python scripts/glossary_autopromote.py \
  --before data/translated.csv \
  --after data/repaired.csv \
  --style workflow/style_guide.md \
  --style-profile data/style_profile.yaml \
  --glossary data/glossary.yaml \
  --language_pair "zh-CN->ru-RU" \
  --scope "project_default"
```

### 含 soft QA 任务

```bash
python scripts/glossary_autopromote.py \
  --before data/translated.csv \
  --after data/repaired.csv \
  --style workflow/style_guide.md \
  --style-profile data/style_profile.yaml \
  --glossary data/glossary.yaml \
  --soft_tasks data/repair_tasks.jsonl \
  --language_pair "zh-CN->ru-RU" \
  --scope "ip_naruto" \
  --min_support 3 \
  --max_rows 500 \
  --out_proposals data/glossary_proposals.yaml \
  --out_patch data/glossary_patch.yaml
```

### 参数要点

| 参数 | 说明 |
|---|---|
| `--before` | 修订前 CSV（通常为 `translated.csv`） |
| `--after` | 修订后 CSV（通常为 `repaired.csv`） |
| `--style` | 风格指南（markdown） |
| `--style-profile` | 项目风格策略文件，驱动禁译/偏好降级 |
| `--glossary` | 当前生效 glossary |
| `--soft_tasks` | 可选，术语方向提示任务 |
| `--min_support` | 提案支持次数阈值 |
| `--max_rows` | 防护上限 |

## 输出

### glossary_proposals.yaml

示例：

```yaml
meta:
  version: 2
  language_pair: "zh-CN->ru-RU"
  scope: "ip_naruto"
proposals:
  - term_zh: "忍术"
    term_ru: "Ниндзюцу"
    status: "proposed"
    confidence: 0.92
    support: 12
    style_profile:
      requires_manual_confirmation: true
      notes:
        - preferred translation mismatch
```

### glossary_patch.yaml

```yaml
op: "append_entries"
target_glossary: "data/glossary.yaml"
entries:
  - term_zh: "忍术"
    term_ru: "Ниндзюцу"
    status: "proposed"
    confidence: 0.92
    notes: "autopromote support=12 scope=ip_naruto"
    requires_manual_confirmation: false
```

## 复核与应用

1. 打开 `data/glossary_proposals.yaml`
2. 核验 `style_profile.requires_manual_confirmation` 为 true 的项
3. 确认后运行：

```bash
python scripts/glossary_apply_patch.py \
  --patch data/glossary_patch.yaml \
  --backup
```

## 冲突处理

- 与 `approved` 术语冲突的提案会被排除到 `conflicts`
- 触发风格降级项（禁译/偏好不一致）不允许自动上链，必须人工确认
