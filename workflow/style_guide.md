# Game Localization Style Guide

## General Principles

### Tone and Voice
- Maintain a friendly and engaging tone
- Use active voice whenever possible
- Keep language clear and concise

### Terminology
- Use consistent terminology across all strings
- Refer to the game glossary for approved terms
- Do not translate proper nouns (character names, locations, etc.)

## Formatting Rules

### Placeholders
- **Always preserve placeholders** in the exact format: `{placeholder_name}`
- Placeholders can be reordered to fit target language grammar
- Never translate placeholder names
- Example: `"Hello {player_name}!"` → `"你好 {player_name}!"`

### Punctuation
- Use target language punctuation conventions
- For Chinese: use full-width punctuation (。！？)
- For Japanese: use full-width punctuation (。！？)
- Maintain ellipsis style: English (...) vs Chinese (……)

### Length Constraints
- **Critical**: Respect `max_length` field in all translations
- Account for font rendering differences
- Test UI to ensure text fits properly

## Language-Specific Guidelines

### Chinese (Simplified)
- Use simplified characters only
- Prefer modern, natural expressions
- Avoid overly formal or literary language
- Use Arabic numerals for numbers

### Chinese (Traditional)
- Use traditional characters
- Consider regional differences (Taiwan vs Hong Kong)
- Maintain appropriate formality level

## Quality Checklist

- [ ] All placeholders preserved
- [ ] Length constraints respected
- [ ] No forbidden patterns used
- [ ] Terminology consistent with glossary
- [ ] Grammar and spelling correct
- [ ] Natural and fluent in target language
- [ ] Context appropriate
