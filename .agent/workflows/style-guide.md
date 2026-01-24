---
description: 翻译风格指导 (Consolidated Version)
---

# RU Localization Style Guide (Consolidated)

> [!NOTE]
> Source: `.agent/workflows/style-guide.md` (Naruto-themed project context)
> Last Sync: 2026-01-24

## 1. Register and Tone (语域与口吻)

### 1.1 Official System Content (官方系统文案 - 默认)

- **Style**: Clear, direct, and actionable.
- **Tone**: Professional and friendly.
- **Preference**: Short imperative sentences and standard UI terminology.
- **Examples**:
  - "Confirm" → "ОК" / "Подтвердить"
  - "Cancel" → "Отмена"
  - "Network error" → "Ошибка сети"
  - "Please try again later" → "Повторите попытку позже."

### 1.2 Anime/Themed Style (二次元口语 - 少量使用)

- **Applicability**: Event titles, lightweight tips, character dialogue.
- **Restriction**: Forbidden in system critical tips, errors, or payment-related strings.
- **Allowed**: Short exclamations like "Ну что, вперёд!" / "Поехали!"
- **Forbidden**: Excessive slang or ephemeral internet memes.

## 2. Terminology Consistency (术语一致性)

- **Glossary First**: Approved terms in `glossary.yaml` (status: approved) are **mandatory**.
- **Missing Terms**: Use literal and conservative translations; do not invent aliases.
- **Proper Nouns**: Do not translate character names or specific location names unless they have established localized forms (e.g., Hidden Leaf Village).

## 3. Formatting and Placeholders (格式与占位符)

- **Placeholder Guard (CRITICAL)**: Always preserve placeholders (`{0}`, `%s`, `⟦PH_xx⟧`, `⟦TAG_xx⟧`, etc.) exactly as they appear in the tokenized source.
- **Variable Semantics**: Do not change the meaning of units (e.g., "%d seconds" must not become "%d minutes").
- **Tags**: Keep `<color=...>`, `\n`, and other markup intact.

## 4. Punctuation and Typography (标点与排版)

- **Quotes**: Prefer Russian "Guillemets": « »
- **Ellipsis**: Use the single character `…` or maintain system consistency with `...`.
- **Spacing**: Ensure a space after colons and commas: `:`
- **Symbols**: Avoid Chinese brackets 【 】; use `« »` or list format `X: ...` in Russian.

## 5. UI and Length Constraints (UI 与长度限制)

| Element Type | Target Length (Characters) | Strategy |
| :--- | :--- | :--- |
| **Buttons/Tabs** | ≤ 14–18 | Use concise words; prioritize readability. |
| **System Tips** | Fit in one screen | Avoid complex subordinate clauses. |
| **Text Overflow** | Respect `max_length` | Prioritize information accuracy, then compress. |

## 6. Quality Checklist

- [ ] All placeholders and tags preserved exactly.
- [ ] Terminology matched with approved glossary entries.
- [ ] No Chinese brackets 【 】 or leftover CJK characters.
- [ ] Russian punctuation (quotes, spacing) followed.
- [ ] Tone appropriate for the content type (System vs Dialogue).
- [ ] Length constraints respected.
