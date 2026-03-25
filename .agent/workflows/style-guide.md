---
description: 项目级风格指南（由 `style_guide_bootstrap.py` 生成）
---

# Project Style Guide (Generated)

- Style guide ID: naruto_localization_demo-ru-RU-style-v1.2
- Style contract version: 1.2
- Governance status: approved
- Owner: Codex
- Approval ref: docs/decisions/ADR-0002-skill-governance-framework.md
- Source: zh-CN -> ru-RU
- Project: naruto_localization_demo / 火影忍者 / Наруто

## 1. Tone

- Official ratio target: 70%
- Anime ratio target: 30%
- Register: neutral_formal
- 禁止过度本地化: 是
- 禁止过度直译: 是
- 系统文案、错误提示、支付/计费文案避免梗化与口语化

## 2. Terminology

- 禁用词/禁译项:
  - 奶妈
  - 副本
  - 攻略
  - bug
  - issue
- 优先译法:
  - 木叶 -> Коноха
  - 忍术 -> Ниндзюцу
  - 忍者 -> ниндзя
- 命名实体处理:
  - 角色名/地名默认保留可读音译
  - 无法确定译法时保守不改
- 禁止项命中时降级：输出建议进入人工确认

## 3. Length

- 按钮: ≤ 18 字符
- 对话/长文: ≤ 120 字符
- 允许扩展上限: 30%
- 允许单行按钮；多行按钮需手工评审

## 4. Placeholder

- 保护 token: `⟦PH_xx⟧`、`⟦TAG_xx⟧`、`{0}`、`%s`、`%d`
- 保护 markup: `<color>`、`\n`、XML/custom tags，位置和数量不可改动
- 禁止改写/删减变量语义

## 5. Content and Style Constraints

- 文本体裁映射:
  - UI/System: 简洁、官方语气、术语优先
  - Dialogue/Narrative: 可允许适度角色化措辞
- 名称与文化位点:
  - 保留关键固有名词，避免强行本地化
- 错误避让:
  - 幽默/双关只在剧情对话允许，不能改变变量含义
  - 遇到风险译法时建议保守输出与原义一致方案

## 6. Terminology Consistency & Priority

- Approved glossary: 强制使用
- Proposed glossary: 参考并优先建议
- Banned terminology: 不得使用，若命中降级到人工确认

## 7. Quality Checklist

- [ ] Approved glossary 全覆盖且无违背
- [ ] 禁用/禁译词命中检测通过
- [ ] `style_profile`/`style_guide.generated.md` 与文档保持一致
- [ ] 占位符与标签完整保留
- [ ] UI 文案长度与模块约束通过
