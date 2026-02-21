# Language Pairs Reference

## Supported Languages

Loc-MVR supports translation between the following 7 languages:

| Code | Language | Script | Region |
|------|----------|--------|--------|
| zh-CN | Chinese (Simplified) | Hanzi | China |
| zh-TW | Chinese (Traditional) | Hanzi | Taiwan |
| ja-JP | Japanese | Kanji/Hiragana/Katakana | Japan |
| ko-KR | Korean | Hangul | South Korea |
| en-US | English | Latin | United States |
| de-DE | German | Latin | Germany |
| fr-FR | French | Latin | France |

## Language Comparison Matrix

| Feature | zh-CN | zh-TW | ja-JP | ko-KR | en-US | de-DE | fr-FR |
|---------|-------|-------|-------|-------|-------|-------|-------|
| Text Length | Medium | Medium | Short | Short | Short | Long | Medium |
| Word Order | SVO | SVO | SOV | SOV | SVO | V2 | SVO |
| Formality | Contextual | Contextual | Explicit | Explicit | Minimal | Formal | Formal |
| Gender | None | None | Minimal | None | Explicit | Explicit | Explicit |
| Pluralization | Contextual | Contextual | None | None | Explicit | Complex | Complex |

## Language-Specific Rules

### Chinese (Simplified) - zh-CN

**Characteristics:**
- No spaces between words
- Context-dependent meaning
- No verb conjugation
- No grammatical gender

**Translation Considerations:**
- Character limit: ~70% of English
- Avoid machine-sounding phrases
- Pay attention to game terminology consistency
- Use 简体中文 for all content

**Special Handling:**
```yaml
zh-CN:
  max_length_ratio: 0.7
  line_breaks: allowed
  placeholder_style: "{name}"
  formality: contextual
```

### Chinese (Traditional) - zh-TW

**Characteristics:**
- Traditional character set (繁體中文)
- Taiwan-specific terminology
- Different gaming slang than Mainland China

**Translation Considerations:**
- Use Taiwan-standard characters (e.g., 裝備 vs 装备)
- Respect Taiwan gaming community conventions
- Different from zh-CN in: vocabulary, some characters

**Special Handling:**
```yaml
zh-TW:
  max_length_ratio: 0.7
  variant: taiwan
  character_set: traditional
```

### Japanese - ja-JP

**Characteristics:**
- Three writing systems: Kanji, Hiragana, Katakana
- SOV (Subject-Object-Verb) word order
- Heavy use of particles
- Multiple politeness levels

**Translation Considerations:**
- Character limit: ~60% of English
- Honorifics matter (です/ます調 for games)
- Katakana for foreign terms
- Furigana support for complex kanji

**Special Handling:**
```yaml
ja-JP:
  max_length_ratio: 0.6
  politeness_level: polite
  katakana_for_loanwords: true
  verb_position: end
```

**Common Issues:**
- Overflow due to text expansion in UI
- Honorific level inconsistency
- Wrong script choice (Kanji vs Katakana)

### Korean - ko-KR

**Characteristics:**
- Hangul alphabet (syllabic blocks)
- SOV word order
- Postpositions (particles)
- Subject/topic markers

**Translation Considerations:**
- Character limit: ~60% of English
- Formal speech (합니다) for most games
- Particles attach to words (no spaces)
- No capitalization

**Special Handling:**
```yaml
ko-KR:
  max_length_ratio: 0.6
  speech_level: formal
  particle_spacing: none
```

### English - en-US

**Characteristics:**
- Subject-Verb-Object order
- Articles (a/an/the)
- Verb conjugation
- Gender-neutral by default

**Translation Considerations:**
- Source or target depending on direction
- Watch for gendered language
- Pluralization rules are complex
- Regional variations (US vs UK)

**Special Handling:**
```yaml
en-US:
  articles: required
  pluralization: complex
  gender_neutral: preferred
  variant: american
```

### German - de-DE

**Characteristics:**
- Compound words (very long)
- Three genders (der/die/das)
- Case system (nominative, accusative, dative, genitive)
- Verb-second (V2) word order

**Translation Considerations:**
- Character limit: ~130% of English (expand!)
- UI overflow is common
- Formal "Sie" vs informal "du"
- Compound nouns need careful handling

**Special Handling:**
```yaml
de-DE:
  max_length_ratio: 1.3
  formality: formal
  compound_handling: split_allowed
  case_system: full
```

**Common Issues:**
- Text overflow in UI elements
- Gender agreement errors
- Wrong case usage

### French - fr-FR

**Characteristics:**
- Gendered nouns (le/la)
- Liaison between words
- Accented characters (é, è, ê, ç)
- Formal "vous" vs informal "tu"

**Translation Considerations:**
- Character limit: ~115% of English
- Gender agreement throughout
- Contractions (du, des, au, aux)
- French-specific punctuation (espace insécable)

**Special Handling:**
```yaml
fr-FR:
  max_length_ratio: 1.15
  formality: context_dependent
  accents: required
  punctuation: french_style
```

## Best Practices

### General Guidelines

1. **Consistency**: Use established terminology
2. **Context**: Always provide context for translators
3. **Length**: Respect UI constraints
4. **Culturalization**: Adapt, don't just translate

### Game-Specific Terms

| English | zh-CN | zh-TW | ja-JP | ko-KR | de-DE | fr-FR |
|---------|-------|-------|-------|-------|-------|-------|
| Health | 生命值 | 生命值 | HP/体力 | 체력 | Gesundheit | Santé |
| Mana | 法力值 | 法力值 | MP/魔力 | 마나 | Mana | Mana |
| Quest | 任务 | 任務 | クエスト | 퀘스트 | Quest | Quête |
| Inventory | 背包 | 背包 | インベントリ | 인벤토리 | Inventar | Inventaire |
| Level Up | 升级 | 升級 | レベルアップ | 레벨 업 | Aufstieg | Montée de niveau |

### Localization Testing Checklist

- [ ] All text fits within UI elements
- [ ] Special characters display correctly
- [ ] Text direction is correct (LTR/RTL)
- [ ] Fonts support all required characters
- [ ] Date/time formats are localized
- [ ] Number formats use correct separators
- [ ] Currency symbols are correct

## Common Issues and Solutions

### Issue: Text Overflow in UI

**Solutions:**
1. Use abbreviations where acceptable
2. Shorten text while maintaining meaning
3. Enable text scrolling or wrapping
4. Increase UI element size (if possible)

### Issue: Inconsistent Terminology

**Solutions:**
1. Maintain and enforce glossary
2. Use translation memory
3. Regular QA checks
4. Context notes for translators

### Issue: Cultural Inappropriateness

**Solutions:**
1. Cultural review by native speakers
2. Regional content adaptation
3. Avoid idioms and cultural references
4. Test with target audience

### Issue: Character Encoding Problems

**Solutions:**
1. Use UTF-8 throughout
2. Verify font support
3. Test on target platforms
4. Handle fallback fonts

## Language Pair Recommendations

### High Quality (Recommended)
- zh-CN → en-US
- ja-JP → en-US
- ko-KR → en-US
- en-US → de-DE
- en-US → fr-FR

### Medium Quality (Requires Review)
- zh-TW → ja-JP
- ko-KR → zh-CN
- de-DE → fr-FR

### Requires Special Attention
- Any involving Arabic, Hebrew (RTL)
- Southeast Asian languages (complex scripts)
- CJK languages (character density)

## Configuration Example

```yaml
language_pairs:
  - pair: zh-CN-en-US
    model: gpt-4
    temperature: 0.3
    max_tokens: 2048
    
  - pair: en-US-de-DE
    model: gpt-4
    temperature: 0.3
    length_adjustment: 1.3
    
  - pair: en-US-ja-JP
    model: gpt-4
    temperature: 0.2
    politeness: polite
```
