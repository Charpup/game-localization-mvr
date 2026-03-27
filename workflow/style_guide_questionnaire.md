# 项目启动风格指南问卷（C 里程碑用）

> 用于启动即生成 `data/style_profile.yaml` 和 `workflow/style_guide.generated.md`。
> 请尽量用「中文答案 + 中文关键词」填写，脚本会按规则转入风格 profile。

## project_context

**source_language**: zh-CN  
**target_language**: ru-RU  
**project_code**: naruto_localization_demo  
**franchise**: Naruto  
**official_title_(zh)**: 火影忍者  
**official_title_(ru)**: Наруто  
**genre**: 动作 RPG  
**target_audience**: 12-35 岁  
**key_themes**: 冒险, 团队作战, 升华成长, 能力解锁, 任务系统

## text_tone&_voice

**official_ratio**: 70  
**anime_ratio**: 30  
**preferred_register**: neutral_formal

**forbidden_patterns**: 过度网络化, 俚语轶闻, 机械逐字直译

## register_and_voice

**no_over_localization**: true  
**no_over_literal**: true

- [x] 禁止在系统文案、错误提示中使用梗与二次元台词
- [ ] 允许在剧情对话中使用轻量梗
- [ ] 允许在角色对白中大量口语化

## names_and_nouns

**character_name_policy**: keep_transliterated  
**culture_localization**: preserve

## naming_conventions

**proper_nouns**: hybrid  

## terminology_policy

**forbidden_terms**: 奶妈, 副本, 攻略, bug, issue  
**preferred_terms**: 忍术: Ниндзюцу, 木叶: Коноха, 忍者: ниндзя  
**prohibited_aliases**: 不允许把「木叶」改写为「деревня_树叶」  
**banned_terms**: 随机翻译, 直译, 机翻

## ui_constraints

**button_length**: 18  
**dialogue_length**: 120  
**max_length_expansion**: 30  
**button_line_policy**: 只允许单行按钮  
**length_policy**: balanced  
**abbreviation_policy**: moderate  

## segmentation_and_context

**segmentation_backend_chain**: pkuseg,thulac,lac,jieba  
**domain_hint**: ui  
**named_entity_sample**: 火影, 木叶, 佐助, 鸣人, 卡卡西, 疾风忍者村  
**fallback_if_missing**: heuristic

## forbidden_patterns

**specific_terms**: 符合:..., 不要使用:...,  
**placeholder_rules**: ⟦PH_xx⟧, ⟦TAG_xx⟧, {0}, %s, %d 必须保留  
**narrative_forbidden**: 避免“硬翻”导致歧义, 避免误导式戏谑

## units

**time_unit**: 秒  
**time_unit_target**: секунд  
**currency_unit**: 原石  
**currency_unit_target**: алмазы
