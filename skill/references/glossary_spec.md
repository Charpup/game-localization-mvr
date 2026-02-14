# Glossary Specification

## Overview

This document outlines the lifecycle of the Terminology Management system, defining how terms are extracted, approved, compiled, and maintained across project iterations.

## 1. Glossary Lifecycle

The glossary flows through 5 distinct states:

1. **Extraction**: `extract_terms.py` scans source text for potential terms (Proper Nouns, UI Elements).
    - *Output*: `term_candidates.yaml` (Raw proposals)
2. **Manual Approval**: Linguists review candidates.
    - *Action*: Move valid terms to `approved.yaml`.
3. **Compilation**: `glossary_compile.py` optimizes for LLM consumption.
    - *Output*: `compiled.yaml` (Injection-ready format)
4. **Autopromote**: `glossary_autopromote.py` identifies high-confidence translations from `repair_loop`.
    - *Output*: `glossary_proposals.yaml`
5. **Patching**: `glossary_apply_patch.py` merges proposals into the master list.

## 2. Structure Comparison

| Feature | `approved.yaml` (Master) | `compiled.yaml` (Runtime) |
| :--- | :--- | :--- |
| **Format** | Human-readable YAML | Optimized JSON/YAML |
| **Content** | Full metadata (pos, comments) | Only `src` -> `tgt` pairs |
| **Scope** | All terms | Context-relevant subset (optional) |
| **Example** | `term: "Menu"<br>zh: "菜单"<br>ru: "Меню"` | `{"菜单": "Меню"}` |

## 3. Autopromote Logic

The system automatically suggests new terms when:

1. **Consistency**: A phrase is translated identically >3 times across the file.
2. **Repair Validation**: A repair action stabilizes a translation that passed Hard QA.
3. **Frequency**: The term appears in >1% of rows.

**Scoring**:

- Base Score: 1.0
- +0.5 per consistent occurrence
- +2.0 if derived from successful repair

## 4. Round 2 Refresh (Incremental)

To avoid re-translating the entire file when glossary terms change:

1. **Delta Calculation**: Identify rows containing *newly changed* glossary terms.
2. **Targeted Refresh**: Only re-translate those specific rows using the new glossary.
3. **Merge**: Update the master CSV with refreshed rows.

## Quick Commands

```bash
# Compile master glossary for runtime use
python scripts/glossary_compile.py --approved glossary/approved.yaml --out_compiled glossary/compiled.yaml

# Apply approved proposals to master
python scripts/glossary_apply_patch.py --master glossary/approved.yaml --patch glossary/proposals.yaml
```

## Common Pitfalls

- **Trap 1**: **Editing Compiled File**.
  - **Consequence**: Changes lost on next compile.
  - **Fix**: Always edit `approved.yaml`.
- **Trap 2**: **Context Collision**.
  - **Consequence**: "File" (noun) translated as "File" (verb) wrongly.
  - **Fix**: Use `context` field in `approved.yaml` to disambiguate (e.g., `scope: UI`).
