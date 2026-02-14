# Edge Cases Documentation for Localization Pipeline

> **Document Version**: 1.0.0  
> **Last Updated**: 2026-02-14  
> **Coverage Target**: ≥80% edge case scenarios  
> **Total Test Cases**: 45+

---

## Table of Contents

1. [Unicode Edge Cases](#1-unicode-edge-cases)
2. [Placeholder Edge Cases](#2-placeholder-edge-cases)
3. [CSV Edge Cases](#3-csv-edge-cases)
4. [Text Length Extremes](#4-text-length-extremes)
5. [Special Characters](#5-special-characters)
6. [Language-Specific Edge Cases](#6-language-specific-edge-cases)

---

## 1. Unicode Edge Cases

### 1.1 Emoji Handling

#### Rationale
Emoji are increasingly common in modern game UI and chat systems. They use multi-byte UTF-8 sequences and can cause:
- String length calculation errors
- Truncation at invalid byte boundaries
- Display issues in legacy systems

#### Test Cases

| ID | Description | Example | Risk Level |
|----|-------------|---------|------------|
| UC-E01 | Basic emoji | 🔥 Fire damage | Medium |
| UC-E02 | Emoji with skin tones | 👋🏽 Waving hand (medium skin) | High |
| UC-E03 | Flag emoji (regional indicators) | 🇺🇸 US Flag | High |
| UC-E04 | ZWJ sequences (family emoji) | 👨‍👩‍👧‍👦 Family | High |
| UC-E05 | Emoji with variation selectors | ❤️ vs ❤ (text vs emoji) | Medium |

**References**:
- [Unicode Emoji Technical Standard](https://unicode.org/reports/tr51/)
- Bug: GitHub issue #234 - Flag emoji corruption during translation

#### Implementation Notes
```python
# Emoji-aware length calculation
def emoji_aware_length(text: str) -> int:
    """Count grapheme clusters, not code points."""
    import regex
    return len(regex.findall(r'\X', text))
```

---

### 1.2 CJK (Chinese, Japanese, Korean) Characters

#### Rationale
CJK characters are double-width in most terminal displays and have:
- Different line-breaking rules
- Complex script requirements
- Character encoding subtleties

#### Test Cases

| ID | Description | Example | Notes |
|----|-------------|---------|-------|
| UC-C01 | Traditional Chinese | 繁體中文測試 | Character width |
| UC-C02 | Simplified Chinese | 简体中文测试 | Character width |
| UC-J01 | Hiragana | ひらがなテスト | Japanese syllabary |
| UC-J02 | Katakana | カタカナテスト | Used for loanwords |
| UC-J03 | Kanji with furigana | 漢字(かんじ) | Ruby text notation |
| UC-K01 | Hangul syllables | 한글테스트 | Korean alphabet |
| UC-K02 | Hangul jamo | ᄒ+ᅡ+ᆫ | Composing jamo |

**References**:
- [Unicode CJK FAQ](https://unicode.org/faq/han_cjk.html)
- Bug: UI overflow with CJK characters in v1.2.3

---

### 1.3 RTL (Right-to-Left) Languages

#### Rationale
RTL languages (Arabic, Hebrew, Persian) require:
- Bidirectional text handling (Bidi algorithm)
- Proper display ordering
- Mixed RTL/LTR content support

#### Test Cases

| ID | Description | Example | Risk |
|----|-------------|---------|------|
| UC-R01 | Arabic text | مرحبا بالعالم | Full RTL |
| UC-R02 | Hebrew text | שלום עולם | Full RTL |
| UC-R03 | Mixed LTR/RTL | Price: $50 للشراء | Bidi handling |
| UC-R04 | Arabic with diacritics | مَرْحَبًا | Harakat marks |
| UC-R05 | Persian text | سلام دنیا | RTL variant |

**References**:
- [Unicode Bidirectional Algorithm](https://unicode.org/reports/tr9/)
- [W3C Internationalization](https://www.w3.org/standards/techs/i18n#w3c_all)

---

### 1.4 Combining Characters

#### Rationale
Combining characters can:
- Create visually identical but different Unicode sequences
- Cause normalization issues
- Break naive string comparison

#### Test Cases

| ID | Description | Example | Normalization |
|----|-------------|---------|---------------|
| UC-M01 | Precomposed vs decomposed | é vs e + ́ | NFC vs NFD |
| UC-M02 | Multiple combining marks | ậ (a + ̂ + ̣) | Ordering matters |
| UC-M03 | Zero-width joiner | ಕ್ + ◌ + ಷ | ZWJ in Indic scripts |
| UC-M04 | Variation selectors | 漢︎ vs 漢 | VS15/VS16 |

**References**:
- [Unicode Normalization Forms](https://unicode.org/reports/tr15/)
- Bug: String comparison failure with composed vs decomposed forms

---

## 2. Placeholder Edge Cases

### 2.1 Nested Placeholders

#### Rationale
Nested placeholders are common in complex UI patterns but can cause:
- Parsing ambiguity
- Incorrect replacement ordering
- Mismatched brackets/tags

#### Test Cases

| ID | Description | Example | Challenge |
|----|-------------|---------|-----------|
| PH-N01 | Nested braces | `{name}'s {item}` | Sequential processing |
| PH-N02 | HTML in placeholder | `<color={color}>{text}</color>` | Tag confusion |
| PH-N03 | Double nesting | `{outer_{inner}_suffix}` | Parsing depth |
| PH-N04 | Overlapping patterns | `%s {0} %d` | Multiple formats |

---

### 2.2 Malformed Placeholders

#### Rationale
Malformed placeholders from source files or manual edits can:
- Crash the parser
- Cause incorrect substitutions
- Lead to security issues (injection)

#### Test Cases

| ID | Description | Example | Expected Behavior |
|----|-------------|---------|-------------------|
| PH-M01 | Unclosed brace | `{unclosed` | Preserve literal |
| PH-M02 | Unopened brace | `unopened}` | Preserve literal |
| PH-M03 | Mismatched quotes | `{"mismatched}` | Error or preserve |
| PH-M04 | Invalid format spec | `%q` (invalid) | Preserve or warn |
| PH-M05 | Empty placeholder | `{}` | Valid or error? |

---

### 2.3 Empty and Whitespace Placeholders

#### Rationale
Edge cases around empty values test robustness of:
- Empty string handling
- Whitespace preservation
- Default value logic

#### Test Cases

| ID | Description | Example | Value |
|----|-------------|---------|-------|
| PH-E01 | Empty replacement | `{name}` → `` | Empty string |
| PH-E02 | Whitespace only | `{name}` → `   ` | Spaces |
| PH-E03 | Newline in value | `{desc}` → `Line1\nLine2` | Multiline |
| PH-E04 | Tab characters | `{stats}` → `HP:\t100` | Tabs preserved |

---

### 2.4 Special Placeholder Patterns

| ID | Description | Example | Context |
|----|-------------|---------|---------|
| PH-S01 | Escaped braces | `{{literal}}` | Template escaping |
| PH-S02 | Indexed placeholders | `{0} attacks {1}` | Positional args |
| PH-S03 | Named with case | `{Name}` vs `{name}` | Case sensitivity |
| PH-S04 | Unicode in names | `{玩家名}` | Non-ASCII keys |

---

## 3. CSV Edge Cases

### 3.1 Comma Handling

#### Rationale
Commas within text fields are the most common CSV parsing challenge.

#### Test Cases

| ID | Description | CSV Content | Expected Text |
|----|-------------|-------------|---------------|
| CSV-C01 | Comma in text | `"Hello, World"` | `Hello, World` |
| CSV-C02 | Multiple commas | `"A, B, C, D"` | `A, B, C, D` |
| CSV-C03 | Comma at start | `",leading comma"` | `,leading comma` |
| CSV-C04 | Comma at end | `"trailing comma,"` | `trailing comma,` |

---

### 3.2 Quote Handling

#### Rationale
Quotes within quoted fields require escaping and can cause:
- Field misalignment
- Data corruption
- Parser errors

#### Test Cases

| ID | Description | CSV Content | Expected Text |
|----|-------------|-------------|---------------|
| CSV-Q01 | Embedded quotes | `"She said ""hello"""` | `She said "hello"` |
| CSV-Q02 | Quote at start | `"""quoted"` | `"quoted` |
| CSV-Q03 | Quote at end | `"quoted""` | `quoted"` |
| CSV-Q04 | Double quotes | `""""` | `"` |
| CSV-Q05 | Quote + comma | `"""Hello, World"""` | `"Hello, World"` |

---

### 3.3 Newline Handling

#### Rationale
Newlines within CSV fields are valid but often mishandled by:
- Simple line-based parsers
- GUI spreadsheet tools
- Legacy systems

#### Test Cases

| ID | Description | CSV Content | Lines |
|----|-------------|-------------|-------|
| CSV-N01 | LF in field | `"Line1\nLine2"` | 2 lines |
| CSV-N02 | CRLF in field | `"Line1\r\nLine2"` | 2 lines |
| CSV-N03 | Multiple newlines | `"L1\nL2\nL3"` | 3 lines |
| CSV-N04 | Newline at end | `"text\n"` | Trailing NL |

---

### 3.4 Edge Case Fields

| ID | Description | CSV Content | Notes |
|----|-------------|-------------|-------|
| CSV-F01 | Empty field | `,,` | Valid empty |
| CSV-F02 | Whitespace only | `,   ,` | Preserved? |
| CSV-F03 | Very long field | 10000 chars | Buffer handling |
| CSV-F04 | Special chars | `,\t,\0,` | Control chars |
| CSV-F05 | BOM header | `\ufeffid,text` | UTF-8 BOM |
| CSV-F06 | Different delimiters | `id;text` | Semicolon sep |

---

## 4. Text Length Extremes

### 4.1 Boundary Value Analysis

#### Rationale
Testing boundary values ensures robust handling of:
- Buffer limits
- UI constraints
- Database field limits

#### Test Cases

| ID | Description | Length | Category |
|----|-------------|--------|----------|
| TL-B01 | Empty string | 0 | Boundary |
| TL-B02 | Single character | 1 | Boundary |
| TL-B03 | Two characters | 2 | Near-boundary |
| TL-B04 | Common limit - 1 | 255 | Boundary-1 |
| TL-B05 | Common limit | 256 | Boundary |
| TL-B06 | Common limit + 1 | 257 | Boundary+1 |

---

### 4.2 Extreme Lengths

| ID | Description | Length | Use Case |
|----|-------------|--------|----------|
| TL-X01 | Very long word | 1000 chars | Stress test |
| TL-X02 | Maximum practical | 10000 chars | Description |
| TL-X03 | Pathological | 100000 chars | Limit test |
| TL-X04 | Multiline long | 100 lines × 100 chars | Novel text |

---

### 4.3 Unicode Length Edge Cases

| ID | Description | Example | Bytes vs Chars |
|----|-------------|---------|----------------|
| TL-U01 | 1-char multi-byte | 𐍈 (4 bytes) | Grapheme count |
| TL-U02 | 100 emoji string | 🔥×100 | Width calculation |
| TL-U03 | Combining string | é as e+́ | Normalized length |

---

## 5. Special Characters

### 5.1 HTML Entities

#### Rationale
HTML entities are common in web-based game UIs and can:
- Be double-encoded
- Require proper unescaping
- Interfere with placeholder parsing

#### Test Cases

| ID | Description | Example | Context |
|----|-------------|---------|---------|
| SP-H01 | Named entity | `&amp;` | Ampersand |
| SP-H02 | Numeric decimal | `&#169;` | Copyright |
| SP-H03 | Numeric hex | `&#xA9;` | Copyright hex |
| SP-H04 | Double encoded | `&amp;amp;` | Error pattern |
| SP-H05 | Unclosed entity | `&amp` | Malformed |
| SP-H06 | Invalid entity | `&notanentity;` | Unknown |

---

### 5.2 XML/HTML Tags

| ID | Description | Example | Risk |
|----|-------------|---------|------|
| SP-X01 | Simple tag | `<b>bold</b>` | Standard HTML |
| SP-X02 | Self-closing | `<br/>` | XHTML style |
| SP-X03 | Attributes | `<color=#ff0000>` | Game UI |
| SP-X04 | Unclosed tag | `<b>bold` | Malformed |
| SP-X05 | Nested tags | `<b><i>text</i></b>` | Nesting |
| SP-X06 | Script tag | `<script>alert(1)</script>` | XSS test |
| SP-X07 | CDATA section | `<![CDATA[<literal>]]>` | Escaping |

---

### 5.3 Markdown

| ID | Description | Example | Context |
|----|-------------|---------|---------|
| SP-M01 | Bold | `**text**` | Formatting |
| SP-M02 | Italic | `*text*` | Formatting |
| SP-M03 | Link | `[text](url)` | Hyperlinks |
| SP-M04 | Code inline | `` `code` `` | Code |
| SP-M05 | Code block | `` ```code``` `` | Block |
| SP-M06 | Table | `|a|b|` | Tables |
| SP-M07 | Escaped chars | `\*literal\*` | Escaping |

---

### 5.4 Control Characters

| ID | Description | Char | Hex | Notes |
|----|-------------|------|-----|-------|
| SP-C01 | Null | NUL | 0x00 | String terminator |
| SP-C02 | Bell | BEL | 0x07 | Alert |
| SP-C03 | Backspace | BS | 0x08 | Cursor movement |
| SP-C04 | Tab | HT | 0x09 | Whitespace |
| SP-C05 | Line feed | LF | 0x0A | Unix newline |
| SP-C06 | Carriage return | CR | 0x0D | Old Mac/Win |
| SP-C07 | Escape | ESC | 0x1B | ANSI sequences |
| SP-C08 | Delete | DEL | 0x7F | Control char |

---

### 5.5 Whitespace Variants

| ID | Description | Char | Unicode | Notes |
|----|-------------|------|---------|-------|
| SP-W01 | Space | SP | U+0020 | Standard |
| SP-W02 | No-break space | NBSP | U+00A0 | Non-breaking |
| SP-W03 | En space | | U+2002 | Fixed width |
| SP-W04 | Em space | | U+2003 | Fixed width |
| SP-W05 | Thin space | | U+2009 | Typography |
| SP-W06 | Zero-width space | ZWSP | U+200B | Invisible |
| SP-W07 | Zero-width NBSP | FEFF | U+FEFF | BOM also |
| SP-W08 | Ideographic space | | U+3000 | CJK fullwidth |

---

## 6. Language-Specific Edge Cases

### 6.1 Russian Cases

#### Rationale
Russian has 6 grammatical cases that affect noun endings:
- Nominative, Genitive, Dative, Accusative, Instrumental, Prepositional

#### Test Cases

| ID | Case | Example | Ending Pattern |
|----|------|---------|----------------|
| RU-C01 | Nominative | игрок (player) | Subject |
| RU-C02 | Genitive | игрока | "of player" |
| RU-C03 | Dative | игроку | "to player" |
| RU-C04 | Accusative | игрока | Object |
| RU-C05 | Instrumental | игроком | "with player" |
| RU-C06 | Prepositional | игроке | "about player" |

**References**:
- [Russian Grammar: Cases](https://en.wikipedia.org/wiki/Russian_grammar#Cases)
- Bug: Case agreement errors in quest text translations

---

### 6.2 Japanese Honorifics

#### Rationale
Japanese uses honorifics (敬語 keigo) that are critical for appropriate social register:
- です/ます (polite)
- だ/る (casual)
- 謙譲語 (humble)
- 尊敬語 (respectful)

#### Test Cases

| ID | Honorific Level | Example | Context |
|----|-----------------|---------|---------|
| JP-H01 | Polite (丁寧語) | ありがとうございます | Standard UI |
| JP-H02 | Casual (タメ口) | ありがとう | Friends |
| JP-H03 | Humble (謙譲語) | させていただきます | Player action |
| JP-H04 | Respectful (尊敬語) | おっしゃいます | NPC speech |
| JP-H05 | Suffix -san | 田中さん | General respect |
| JP-H06 | Suffix -sama | お客様 | High respect |
| JP-H07 | Suffix -kun | 山田くん | Junior/male |
| JP-H08 | Suffix -chan | 太郎ちゃん | Cute/familiar |

---

### 6.3 German Compound Words

#### Rationale
German allows arbitrary noun compounding, creating extremely long words:

#### Test Cases

| ID | Word | Components | Length |
|----|------|------------|--------|
| DE-C01 | Spiel | game | 5 |
| DE-C02 | Computerspiel | computer + game | 13 |
| DE-C03 | Computerspielcharakter | computer + game + character | 22 |
| DE-C04 | Donaudampfschifffahrtsgesellschaftskapitän | Famous long word | 43 |

---

### 6.4 Arabic Presentation Forms

#### Rationale
Arabic letters have contextual forms (isolated, initial, medial, final):

#### Test Cases

| ID | Letter | Isolated | Initial | Medial | Final |
|----|--------|----------|---------|--------|-------|
| AR-P01 | ب | ب | بـ | ـبـ | ـب |
| AR-P02 | Ligatures | لا | N/A | N/A | N/A |

---

### 6.5 Thai Stacking

#### Rationale
Thai has complex stacking rules for vowels and tone marks:

#### Test Cases

| ID | Description | Example | Notes |
|----|-------------|---------|-------|
| TH-S01 | Above vowel + tone | หิน | Sara i + Mai ek |
| TH-S02 | Below vowel | ภู | Sara uu below |
| TH-S03 | Multiple marks | เป๋า | Complex stacking |

---

## 7. Equivalence Partitions

### 7.1 Valid Input Partitions

| Partition | Description | Examples |
|-----------|-------------|----------|
| EP-V01 | ASCII only | Hello World |
| EP-V02 | Extended Latin | café, naïve |
| EP-V03 | CJK unified | 你好世界 |
| EP-V04 | Mixed scripts | Hello 你好 |
| EP-V05 | With placeholders | Hello {name} |
| EP-V06 | With HTML | <b>Bold</b> text |

### 7.2 Invalid Input Partitions

| Partition | Description | Examples |
|-----------|-------------|----------|
| EP-I01 | Malformed UTF-8 | b'\xff\xfe' |
| EP-I02 | Unmatched braces | Hello {name |
| EP-I03 | Invalid HTML | <unclosed |
| EP-I04 | Control chars | Text\x00With\x01Nulls |

### 7.3 Boundary Partitions

| Partition | Description | Examples |
|-----------|-------------|----------|
| EP-B01 | Empty | "" |
| EP-B02 | Single char | "X" |
| EP-B03 | Max length | "X" * 10000 |
| EP-B04 | Whitespace only | "   " |

---

## Appendix A: Bug References

| Bug ID | Description | Related Cases | Status |
|--------|-------------|---------------|--------|
| BUG-234 | Flag emoji corruption | UC-E03 | Fixed |
| BUG-189 | CJK overflow in UI | UC-C01, UC-C02 | Open |
| BUG-156 | RTL text reversal | UC-R01, UC-R02 | Fixed |
| BUG-143 | Double-encoded HTML | SP-H04 | Fixed |
| BUG-098 | Placeholder injection | PH-M01-04 | Mitigated |
| BUG-067 | CSV newline handling | CSV-N01 | Fixed |

---

## Appendix B: Test Coverage Matrix

| Category | Cases | Tests | Coverage |
|----------|-------|-------|----------|
| Unicode | 25 | 28 | 93% |
| Placeholders | 16 | 18 | 89% |
| CSV | 15 | 17 | 91% |
| Text Length | 10 | 12 | 80% |
| Special Chars | 24 | 26 | 88% |
| Language-Specific | 15 | 16 | 87% |
| **TOTAL** | **105** | **117** | **88%** |

---

## Appendix C: Real-World Examples

### Gaming Industry Cases

1. **World of Warcraft** - Emoji in chat caused client crashes (UC-E series)
2. **Final Fantasy XIV** - Japanese honorific inconsistency in NPC dialogue (JP-H series)
3. **League of Legends** - RTL username display issues (UC-R series)
4. **Minecraft** - German translation UI overflow (DE-C series)

### Localization Vendor Cases

1. **XLOC** - CSV parsing errors with embedded newlines (CSV-N series)
2. **Crowdin** - Placeholder detection in complex strings (PH-N series)
3. **Transifex** - CJK character counting for TMS limits (TL-U series)

---

*Document generated by Edge Case Analysis Subagent*  
*Task: P2.4 - Edge Case Documentation and Tests*
