# Style Guide: Naruto (Example)
>
> **IP**: Naruto / Наруто
> **Target**: Russian (RU)

## Tone & Voice

- **Core Tone**: Shonen, Energetic, Emotional (Friendship/Guts), Ninja-themed.
- **Ratio**: 70% Anime-flavored / 30% Official (System messages).
- **Keywords**: Dattebayo, Chakra, Shinobi, Will of Fire.

## Terminology Policy

- **Names**: Strict Transliteration (Polivanov system).
  - Naruto -> Наруто (Not Наруту)
  - Kakashi -> Какаси (Not Какаши - *Note: Polivanov rule, but check fandom pref. Fandom often prefers Ш for shi. Policy: Polivanov for official.*)
- **Jutsu/Skills**: Hybrid.
  - Rasengan -> Расенган (Transliterate)
  - Shadow Clone Jutsu -> Техника Теневого Клонирования (Translate meaning)
- **Places**: Translate meaning.
  - Hidden Leaf Village -> Деревня Скрытого Листа

## Grammar & Mechanics

- **Register**:
  - System/Tutorial: `вы` (Lowercase regular formal)
  - Character/NPC: `ты` (Informal, or respectful `вы` depending on rank)
- **Gender**: Ninja -> **Ниндзя** (Indeclinable masculine). Kunoichi -> **Куноичи**.

## UI Length & Brevity

- **Constraint**: Mobile UI. Text expansion max 15%.
- **Buttons**: Imperative verbs (Equip -> Экипировать -> Надеть if too long).

## Forbidden Patterns

- Do not use "Шиноби" -> Use "**Синоби**" (Polivanov) unless specified otherwise.
- No straight quotes `"`, use guillemets `«...»`.

## Placeholder Handling

- Preservation: `{0}`, `{name}` must be preserved exactly.
- Syntax: Do not decline placeholders (e.g., `в {0}` is risky if {0} is feminine). Rephrase to avoid dependency: `Локация: {0}`.
