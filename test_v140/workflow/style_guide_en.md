# EN Localization Style Guide (Naruto-themed)

> [!NOTE]
> Source: Adapted from RU style guide for EN localization
> Target: English (en-US)
> Theme: Naruto

---

## 1. Register and Tone

### 1.1 Official System Content (Default)

- **Style**: Clear, direct, and actionable
- **Tone**: Professional yet engaging
- **Preference**: Short imperative sentences, standard UI terminology
- **Examples**:
  - "Confirm" → "Confirm"
  - "Cancel" → "Cancel"
  - "Network error" → "Network Error"
  - "Please try again later" → "Please try again later."

### 1.2 Anime/Themed Style (Limited Use)

- **Applicability**: Event titles, character dialogue, flavor text
- **Restriction**: Forbidden in system critical tips, errors, payment
- **Allowed**: 
  - "Let's go!" / "Here we go!"
  - "Believe it!" (Naruto reference)
  - "Dattebayo!" → "Believe it!" (localized catchphrase)
- **Forbidden**: Excessive slang, memes, outdated internet language

---

## 2. Terminology Consistency

### 2.1 Glossary Priority

- **Approved terms** in `glossary.yaml` are **mandatory**
- **Missing terms**: Use literal translations; do not invent aliases
- **Proper Nouns**: 
  - Translate: Hidden Leaf Village, Chakra, Jutsu
  - Keep Romanized: Naruto, Sasuke, Konoha (if established)

### 2.2 Key Naruto Terms

| Chinese | English | Notes |
|---------|---------|-------|
| 查克拉 | Chakra | Keep original |
| 忍术 | Ninjutsu / Jutsu | Context-dependent |
| 体术 | Taijutsu | Keep original |
| 幻术 | Genjutsu | Keep original |
| 血继限界 | Kekkei Genkai | Keep original |
| 尾兽 | Tailed Beast | Translate |
| 人柱力 | Jinchuriki | Keep original |
| 木叶隐村 | Hidden Leaf Village | Translate |
| 火影 | Hokage | Keep original |
| 暗部 | ANBU | Keep original |

---

## 3. Formatting and Placeholders

### 3.1 Placeholder Rules (CRITICAL)

**MUST preserve exactly**:
- `{0}`, `{1}`, `%s`, `%d` - Positional arguments
- `⟦PH_xx⟧`, `⟦TAG_xx⟧` - Custom placeholders
- `<color=...>`, `\n`, `<b>`, `</b>` - Markup tags

**Examples**:
- ✅ "{0} earned {1} Chakra" → "{0} earned {1} Chakra"
- ❌ "{0} earned {1} Chakra" → "Player earned 100 Chakra"

### 3.2 Variable Semantics

Never change units or meaning:
- "%d seconds" ≠ "%d minutes"
- "%s damage" ≠ "%s healing"

---

## 4. Punctuation and Typography

### 4.1 Quotes

- **UI Text**: Use straight quotes `"text"` or none
- **Dialogue**: Use curly quotes "text" for emphasis
- **Terms**: Use 'term' for first mention

### 4.2 Spacing

- Space after commas: "Hello, world"
- Space after colons in lists: "Requirements: item 1, item 2"
- No space before punctuation

### 4.3 Special Characters

- **Ellipsis**: Use `...` (3 dots) for truncation
- **Em-dash**: Use `—` for breaks in dialogue
- **Apostrophe**: Use `'` (straight)

---

## 5. UI and Length Constraints

| Element Type | Target Length | Strategy |
|-------------|---------------|----------|
| **Buttons/Tabs** | ≤ 12-15 chars | Short words, abbreviate if needed |
| **Titles** | ≤ 25 chars | Concise, impactful |
| **Descriptions** | ≤ 100 chars | Clear, no fluff |
| **Tooltips** | ≤ 80 chars | Essential info only |
| **Notifications** | ≤ 120 chars | Complete sentences |

### 5.1 Abbreviation Strategy

When space is tight:
- "Experience" → "EXP"
- "Chakra Points" → "CP" (if context clear)
- "Attack Power" → "ATK"

---

## 6. Naruto-Specific Guidelines

### 6.1 Character Names

**Keep Romanized** (established usage):
- Naruto Uzumaki
- Sasuke Uchiha
- Sakura Haruno
- Kakashi Hatake

**Translate Descriptive Titles**:
- 拷贝忍者 → Copy Ninja
- 忍者之神 → God of Shinobi

### 6.2 Jutsu Names

**Format**: [Descriptor] [Type] / [Effect]

Examples:
- 火遁·豪火球之术 → Fire Style: Fireball Jutsu
- 螺旋丸 → Rasengan (keep original)
- 千鸟 → Chidori (keep original)

### 6.3 Village Names

**Pattern**: Hidden [Element] Village

- 木叶隐村 → Hidden Leaf Village
- 砂隐村 → Hidden Sand Village
- 雾隐村 → Hidden Mist Village
- 岩隐村 → Hidden Stone Village
- 云隐村 → Hidden Cloud Village

---

## 7. Quality Checklist

Before finalizing:
- [ ] All placeholders preserved
- [ ] Glossary terms used correctly
- [ ] UI length constraints met
- [ ] Naruto terms consistent
- [ ] No Chinese brackets 【】
- [ ] Proper nouns handled correctly

---

*Style Guide for Naruto-themed Game Localization - EN Version*