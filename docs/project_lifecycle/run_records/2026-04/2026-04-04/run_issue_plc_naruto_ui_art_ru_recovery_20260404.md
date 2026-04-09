# run_issue

- run_id: `plc_naruto_ui_art_ru_recovery_20260404`
- scope: `naruto_ui_art_ru_recovery`
- status: `captured`

## Trigger
- the live batch finished operationally but failed semantically:
  - `3002` hard-QA length failures
  - `3189` review-queue rows
  - failure family concentrated in short UI-art labels rather than long-tail outliers

## Root Cause Summary
- UI-art rows were translated with category-blind prose defaults rather than compact mobile-game label rules
- `soft_qa_llm.py` preferred general approved glossary terms even when UI-art compact forms existed
- `qa_hard.py` used a uniform overflow heuristic and had no badge compact-only or slogan line-budget policy
- compiled glossary artifacts dropped compact metadata, preventing reliable runtime precedence

## Bounded Recovery Decision
- keep the global hard invariants unchanged
- add `ui_art_category` in prep and preserve it through review surfaces
- move compact glossary precedence into translate + soft QA runtime logic
- change hard-QA severity to category-aware target/review bands
- validate the recovery slice with focused tests first, then a stratified canary
