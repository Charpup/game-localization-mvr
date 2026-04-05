# Project Style Guide (Generated)

_Canonical generated guide. Keep this file, `workflow/style_guide.md`, and `.agent/workflows/style-guide.md` in sync._

- Style guide ID: naruto_localization_demo-ru-RU-style-v1.3
- Style contract version: 1.3
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
- UI 美术字批次默认目标: `2.3x` 中文清洗后长度
- UI 美术字人工复核红线: `2.5x` 中文清洗后长度
- 美术字优先用短名词、常见手游缩写、数字标签（如 `x10` / `x1`）
- 活动/宣传位可接受 `донат`、`ивент`、`гача` 等本土手游术语；支付/系统位不默认启用
- 单字/双字 badge 走 approved compact mapping；没有短译时不自由展开，直接进入人工复核
- `slogan_long` 不按短标签规则误杀：先守 `2.6x` banner 压缩线，再看 `3.2x` 和行数预算

## 4. Placeholder

- 保护 token: `⟦PH_xx⟧`、`⟦TAG_xx⟧`、`{0}`、`%s`、`%d`
- 保护 markup: `<color>`、`\n`、XML/custom tags，位置和数量不可改动
- 禁止改写/删减变量语义

## 5. Content and Style Constraints

- 文本体裁映射:
  - UI/System: 简洁、官方语气、术语优先
  - Dialogue/Narrative: 可允许适度角色化措辞
- UI Art 压缩策略:
  - 先删冗余修饰，再缩短结构，不先改 IP 核心名词
  - 可接受常见写法: `OK`、`PvP`、`PvE`、`VIP`、`БП`
  - 高风险短写如 `Настр.`、`Ивент` 只在空间不够时使用，并进入人工复核
  - 类别合同:
    - `badge_micro_*`: 只能用已批准的极短词或缩写；没有 compact mapping 直接进人工队列
    - `label_generic_short`: 用短名词，不做解释性双名词扩写
    - `title_name_short`: 保核心名词/专名，优先删泛词
    - `promo_short`: 可用俄区手游促销短写，如 `Хит`、`Топ`、`БП`、`x10`、`x1`
    - `item_skill_name`: 保留关键专名或核心技能词，不补全说明语
    - `slogan_long`: 压成 banner headline，保专名、变量和原始行数预算
  - `badge_micro_*`: dictionary-only / approved abbreviation-only，禁止解释性翻译
  - `label_generic_short`: noun-only，先砍修饰语，避免双名词直译结构
  - `title_name_short`: headline style，保核心名词或音译，优先删泛词
  - `promo_short`: 允许 `Хит`、`Топ`、`БП`、`x10`、`x1` 等俄区手游 promo shorthand
  - `item_skill_name`: 保 IP 核心名词，压缩系统词和泛修饰词
  - `slogan_long`: 压成 banner headline，保专名、变量和行数预算，不写成完整说明句
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
- [ ] UI 美术字超过 `2.3x` 的行进入缩写/压缩复核
- [ ] UI 美术字超过 `2.5x` 或语义压缩风险行进入人工 review queue
- [ ] `badge_micro_*` 未命中批准短译时，不得放行 freeform 长译
- [ ] `slogan_long` 不得增加行数；增加行数直接进入 `line_budget_overflow`
- [ ] UI 美术字优先命中 compact glossary；soft QA 不得把 compact term 推回长译
