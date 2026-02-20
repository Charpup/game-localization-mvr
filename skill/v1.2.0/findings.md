# Skill Packaging Assessment: game-localization-mvr v1.2.0

**Date**: 2026-02-20  
**Assessor**: Subagent Evaluation  
**Scope**: Evaluate v1.2.0 skill packaging status and identify v1.3.0 upgrade requirements  

---

## Executive Summary

The game-localization-mvr v1.2.0 skill is **NOT compliant** with OpenClaw standards. While the compiled `.skill` package (256KB) exists, the source directory `skill/v1.2.0/` lacks critical documentation and has extensive Russian-language hardcoding that prevents easy adaptation to other target languages (e.g., English).

### Key Findings

| Category | Status | Priority |
|----------|--------|----------|
| SKILL.md Documentation | ❌ **MISSING** | CRITICAL |
| Multi-language Framework | ❌ **Hardcoded RU** | CRITICAL |
| Glossary Structure | ⚠️ **RU-Specific** | HIGH |
| QA Rules | ⚠️ **RU-Centric** | HIGH |
| Test Coverage | ✅ **Present** | OK |
| Config Structure | ⚠️ **Needs Refactor** | MEDIUM |

---

## 1. Current Skill Structure Assessment

### 1.1 Directory Structure

```
skill/
├── loc-mvr-v1.2.0.skill              # Compiled skill package (256KB)
├── loc-mvr-v1.2.0.skill.sha256       # SHA256 checksum
└── v1.2.0/                           # Source directory
    ├── config/                       # Configuration files
    │   ├── batch_runtime_v1.json
    │   ├── batch_runtime_v2.json
    │   ├── glossary/                 # Glossary configs (RU-specific)
    │   │   ├── approved.yaml
    │   │   ├── compiled.lock.json
    │   │   ├── compiled.yaml         # 1925 RU terms
    │   │   ├── generic_terms_zh.txt
    │   │   ├── global.yaml           # Global terms with term_ru
    │   │   ├── README.md
    │   │   └── zhCN_ruRU/            # ZH→RU specific
    │   │       ├── base.yaml
    │   │       ├── test_approved_v2.yaml
    │   │       └── test_approved.yaml
    │   ├── pricing_p1.json - pricing_p5.json
    │   ├── pricing_scraped_dump.json
    │   └── workflow/
    │       ├── forbidden_patterns.txt
    │       ├── llm_config.yaml
    │       ├── p3_glossary_approved.yaml
    │       ├── p3_glossary_compiled.lock.json
    │       ├── p3_glossary_compiled.yaml
    │       ├── p3_glossary_new_test.yaml
    │       ├── p3_glossary_proposals.yaml
    │       ├── placeholder_schema.yaml
    │       ├── punctuation_map.yaml   # ZH→RU punctuation rules
    │       ├── smoke_glossary_*.yaml
    │       ├── soft_qa_rubric.yaml    # RU-targeted rubric
    │       ├── style_guide.md         # RU Localization Style Guide
    │       └── style_guide_questionnaire.md
    ├── docs/                          # Empty docs directory
    ├── examples/
    │   └── sample_input.csv
    ├── scripts/                       # 90+ Python scripts
    │   ├── emergency_translate.py
    │   ├── glossary_apply_patch.py
    │   ├── glossary_auto_approve.py
    │   ├── glossary_delta.py
    │   ├── glossary_make_review_queue.py
    │   ├── glossary_review_llm.py
    │   ├── glossary_translate_llm.py
    │   ├── normalize_ingest.py
    │   ├── normalize_tagger.py
    │   ├── normalize_tag_llm.py
    │   ├── soft_qa_llm.py
    │   ├── style_guide_apply.py
    │   ├── style_guide_generate.py
    │   ├── style_guide_score.py
    │   └── ... (many more)
    └── tests/                         # Test suite
        ├── test_extract_terms.py
        ├── test_forbidden_patterns.py
        ├── test_glossary_review.py
        ├── test_glossary_translate_logic.py
        ├── test_metrics_debug.py
        ├── test_normalize.py
        ├── test_normalize_segmentation.py
        ├── test_punctuation.py
        ├── test_qa_hard.py
        └── test_rehydrate.py
```

### 1.2 OpenClaw Standards Compliance

#### ❌ CRITICAL: Missing SKILL.md

The `skill/v1.2.0/SKILL.md` file is **completely missing**. This is a requirement for all OpenClaw skills.

**Required SKILL.md Structure**:
```yaml
---
name: game-localization-mvr
description: |
  Game localization skill for translating Chinese (ZH) game text to
  target languages. Supports configurable language pairs, glossary
  management, and automated QA.
version: 1.2.0
author: localization-team
triggers:
  - "localize game text"
  - "translate zh to"
  - "game localization"
---

# Usage Instructions
...
```

#### ⚠️ Documentation Gaps

| Document | Status | Notes |
|----------|--------|-------|
| SKILL.md | ❌ Missing | Required for skill discovery |
| API Reference | ❌ Missing | No script documentation |
| Setup Guide | ❌ Missing | No installation instructions |
| glossary/README.md | ✅ Present | Basic glossary info |
| style_guide.md | ✅ Present | RU-specific style guide |

---

## 2. Russian-Specific Hardcoded Elements

### 2.1 Language Pair Configuration

**File**: `skill/v1.2.0/config/workflow/llm_config.yaml`
```yaml
language_pair:
  source: "zh-CN"
  target: "ru-RU"  # HARDCODED - should be configurable
```

### 2.2 Glossary Data Structure

**Files**: Multiple glossary YAML files

```yaml
# Pattern found in: global.yaml, compiled.yaml, base.yaml, etc.
entries:
  - term_zh: "确定"
    term_ru: "OK"           # HARDCODED: term_ru field
    status: "approved"
    
  - term_zh: "取消"
    term_ru: "Отмена"       # HARDCODED: Russian translation
    status: "approved"
```

**Problem**: The field name `term_ru` is hardcoded. For multi-language support, this should be:
```yaml
entries:
  - term_source: "确定"
    translations:
      ru-RU: "OK"
      en-US: "Confirm"
      ja-JP: "確定"
```

### 2.3 Punctuation Mapping

**File**: `skill/v1.2.0/config/workflow/punctuation_map.yaml`
```yaml
default_target: ru-RU  # HARDCODED

mappings:
  ru-RU:               # Hardcoded language key
    - source: "【"
      target: "«"      # Russian guillemets
      description: "左方头括号"
```

### 2.4 Soft QA Rubric

**File**: `skill/v1.2.0/config/workflow/soft_qa_rubric.yaml`
```yaml
target: "ru-RU"  # HARDCODED

dimensions:
  - key: style_officialness
    description: "系统文案是否足够官方、清晰、可操作"
  - key: anime_tone
    description: "二次元口语是否适度"
```

### 2.5 Script-Level Hardcoding

**File**: `src/scripts/batch_runtime.py` (copied to skill)
```python
'你是严谨的手游本地化译者（zh-CN → ru-RU）。\n\n'  # HARDCODED
```

**File**: `src/scripts/glossary_translate_llm.py`
```python
"你是术语表译者（zh-CN → ru-RU），为手游项目生成"可落地"的术语对。\n"
"language_pair: zh-CN -> ru-RU\n"  # HARDCODED
```

**File**: `src/scripts/soft_qa_llm.py`
```python
"你是手游本地化软质检（zh-CN → ru-RU）。\n\n"  # HARDCODED
```

**File**: `src/scripts/style_guide_generate.py`
```python
"You are an expert Game Localization Director (zh-CN -> ru-RU)."  # HARDCODED
"你是游戏本地化风格指南专家（zh-CN → ru-RU）。"
```

**File**: `src/scripts/glossary_autopromote.py`
```python
"你是资深手游本地化术语工程师（zh-CN → ru-RU）。\n"  # HARDCODED
```

**File**: `src/scripts/glossary_review_llm.py`
```python
"你是术语表审校（zh-CN → ru-RU）。\n"
"language_pair: zh-CN -> ru-RU\n\n"  # HARDCODED
```

**File**: `src/scripts/translate_refresh.py`
```python
"你是'术语变更刷新器'（zh-CN → ru-RU）。\n"  # HARDCODED
```

**File**: `src/scripts/extract_terms.py`
```python
language_pair = {'source': 'zh-CN', 'target': 'ru-RU'}  # HARDCODED
```

### 2.6 Style Guide

**File**: `skill/v1.2.0/config/workflow/style_guide.md`

The entire style guide is written for Russian localization:
- Section: "RU Localization Style Guide (Consolidated)"
- Russian typography rules (guillemets « »)
- Russian-specific examples: "Confirm" → "ОК" / "Подтвердить"
- Russian anime tone: "Ну что, вперёд!" / "Поехали!"

### 2.7 Directory Structure

```
skill/v1.2.0/config/glossary/
└── zhCN_ruRU/              # Language-pair specific directory
    ├── base.yaml
    ├── test_approved_v2.yaml
    └── test_approved.yaml
```

---

## 3. Files Requiring Modification for ZH ➡️ EN Support

### 3.1 Configuration Files

| File | Changes Required |
|------|------------------|
| `config/workflow/llm_config.yaml` | Make `target` configurable; remove hardcoded `ru-RU` |
| `config/workflow/punctuation_map.yaml` | Add `en-US` mappings; make `default_target` configurable |
| `config/workflow/soft_qa_rubric.yaml` | Make `target` configurable; add EN-specific dimensions |
| `config/workflow/style_guide.md` | Create `en-US` variant; make style guide selectable |
| `config/glossary/global.yaml` | Refactor `term_ru` to `translations.en-US` structure |
| `config/glossary/compiled.yaml` | Refactor 1925 entries to multi-language format |
| `config/glossary/zhCN_ruRU/*` | Create `zhCN_enUS` directory; translate terms |

### 3.2 Script Files

| File | Changes Required |
|------|------------------|
| `scripts/batch_runtime.py` | Parameterize language pair in system prompt |
| `scripts/glossary_translate_llm.py` | Accept `--target-lang` parameter; generic prompt template |
| `scripts/soft_qa_llm.py` | Accept `--target-lang` parameter; load language-specific rubric |
| `scripts/style_guide_generate.py` | Parameterize language pair in prompts |
| `scripts/glossary_autopromote.py` | Parameterize language pair in prompts |
| `scripts/glossary_review_llm.py` | Parameterize language pair in prompts |
| `scripts/translate_refresh.py` | Parameterize language pair in prompts |
| `scripts/extract_terms.py` | Accept `target` parameter; remove hardcoded dict |

### 3.3 New Files Required

| File | Purpose |
|------|---------|
| `SKILL.md` | OpenClaw skill documentation (REQUIRED) |
| `config/workflow/style_guide_en.md` | EN-specific style guide |
| `config/glossary/zhCN_enUS/base.yaml` | ZH→EN glossary base |
| `config/glossary/zhCN_enUS/approved.yaml` | ZH→EN approved terms |
| `config/workflow/punctuation_map_en.yaml` | ZH→EN punctuation rules |
| `docs/API.md` | Script API documentation |
| `docs/SETUP.md` | Installation and setup guide |

---

## 4. Multi-language Extensibility Assessment

### 4.1 Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Current v1.2.0 Architecture              │
├─────────────────────────────────────────────────────────────┤
│  Source: zh-CN ────────► Target: ru-RU (HARDCODED)          │
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │ Glossary    │    │ Translation │    │ QA Rules    │     │
│  │ (term_ru)   │    │ (ru-RU)     │    │ (ru-RU)     │     │
│  └─────────────┘    └─────────────┘    └─────────────┘     │
└─────────────────────────────────────────────────────────────┘
```

### 4.2 Recommended v1.3.0 Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Proposed v1.3.0 Architecture             │
├─────────────────────────────────────────────────────────────┤
│  Source: zh-CN ────────► Target: Configurable               │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Language Configuration                  │   │
│  │  config.language_pair = {source: "zh-CN", target: X} │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│          ┌───────────────┼───────────────┐                  │
│          ▼               ▼               ▼                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │ Glossary    │  │ Translation │  │ QA Rules    │         │
│  │ (generic)   │  │ (generic)   │  │ (generic)   │         │
│  │ translations│  │ prompts load│  │ rubrics load│         │
│  │ [lang]      │  │ target-lang │  │ target-lang │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│          │               │               │                  │
│          └───────────────┴───────────────┘                  │
│                          │                                  │
│          ┌───────────────┼───────────────┐                  │
│          ▼               ▼               ▼                  │
│      ru-RU             en-US             ja-JP              │
│   (existing)        (new target)      (future)              │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 Extensibility Score

| Component | Current Score | Max | Notes |
|-----------|--------------|-----|-------|
| Glossary System | 2/10 | 10 | Hardcoded `term_ru` field |
| Translation Engine | 3/10 | 10 | Prompts hardcoded for RU |
| QA System | 4/10 | 10 | Rubric hardcoded for RU |
| Punctuation Mapping | 5/10 | 10 | Structure supports multiple languages |
| Config System | 6/10 | 10 | YAML-based but not generic |
| **Overall** | **4/10** | 10 | Requires significant refactoring |

---

## 5. Upgrade Recommendations for v1.3.0

### 5.1 Phase 1: Documentation (Critical)

1. **Create SKILL.md**
   - Add YAML frontmatter with metadata
   - Document all triggers and usage patterns
   - Include examples for ZH→EN and ZH→RU

2. **Create docs/API.md**
   - Document all script entry points
   - Document configuration options
   - Include usage examples

### 5.2 Phase 2: Multi-Language Framework (Critical)

1. **Refactor Glossary Structure**
   ```yaml
   # FROM (v1.2.0)
   - term_zh: "确定"
     term_ru: "OK"
     status: "approved"
   
   # TO (v1.3.0)
   - term_source: "确定"
     translations:
       ru-RU: "OK"
       en-US: "Confirm"
       ja-JP: "確定"
     status: "approved"
   ```

2. **Create Language-Agnostic Prompts**
   ```python
   # FROM (v1.2.0)
   "你是术语表译者（zh-CN → ru-RU）"
   
   # TO (v1.3.0)
   f"你是术语表译者（{source_lang} → {target_lang}）"
   ```

3. **Add Language-Specific Config Loading**
   ```python
   def load_style_guide(target_lang: str) -> str:
       path = f"config/workflow/style_guide_{target_lang}.md"
       return load_file(path)
   ```

### 5.3 Phase 3: ZH ➡️ EN Implementation (High Priority)

1. **Create EN-specific Assets**
   - `config/workflow/style_guide_en.md`
   - `config/glossary/zhCN_enUS/base.yaml`
   - `config/workflow/punctuation_map_en.yaml`

2. **Update QA Rules**
   - Add EN-specific forbidden patterns
   - Add EN grammar validation
   - Update length constraints for EN

### 5.4 Phase 4: Testing & Validation (Medium Priority)

1. **Add Language Parameter Tests**
   - Test all scripts with `--target-lang en-US`
   - Test glossary loading for different languages
   - Test punctuation mapping for EN

2. **Create Integration Tests**
   - End-to-end ZH→EN translation test
   - Multi-language glossary compilation test

### 5.5 Phase 5: Packaging (Medium Priority)

1. **Update Skill Packaging**
   - Include new EN assets in package
   - Update skill metadata
   - Create installation verification script

2. **GitHub Release**
   - Tag v1.3.0
   - Create release notes
   - Update README with multi-language usage

---

## 6. Estimated Effort

| Task Category | Files | Estimated Hours |
|--------------|-------|-----------------|
| Documentation | 3 | 4 |
| Glossary Refactoring | 10+ | 8 |
| Script Updates | 15+ | 12 |
| EN Assets Creation | 5 | 6 |
| Testing | 10+ | 8 |
| Packaging | 3 | 2 |
| **Total** | **~50** | **~40 hours** |

---

## 7. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Breaking changes to existing RU workflow | High | High | Maintain backward compatibility; keep ru-RU as default |
| Glossary migration errors | Medium | High | Create migration script; validate before/after counts |
| EN quality below RU standard | Medium | Medium | Use same QA pipeline; iterate on style guide |
| Script compatibility issues | Low | Medium | Comprehensive test coverage |

---

## 8. Recommendations

### Immediate Actions (Before v1.3.0)

1. ✅ **Create SKILL.md** - Required for OpenClaw compliance
2. ✅ **Freeze v1.2.0** - Tag current state as final RU-only version
3. ✅ **Create branch** - Work on `reorg/v1.3.0-structure`

### v1.3.0 Development Order

1. **Week 1**: Documentation + Framework Design
2. **Week 2**: Glossary Refactoring + Script Updates
3. **Week 3**: EN Assets + Testing
4. **Week 4**: Packaging + Release

### Long-term Improvements

- Consider adopting ISO 639-1 language codes consistently
- Implement language-specific QA rule plugins
- Add support for non-Asian source languages (EN→ES, etc.)

---

## Appendix A: File Inventory

### Scripts (90+ files in skill/v1.2.0/scripts/)

**Core Translation**:
- `emergency_translate.py`
- `translate_refresh.py`
- `glossary_translate_llm.py`

**QA & Validation**:
- `soft_qa_llm.py`
- `test_qa_hard.py`
- `forbidden_patterns.txt`

**Glossary Management**:
- `glossary_apply_patch.py`
- `glossary_auto_approve.py`
- `glossary_delta.py`
- `glossary_make_review_queue.py`
- `glossary_review_llm.py`

**Batch Processing**:
- `batch_sanity_gate.py`
- `run_dual_gates.py`
- `run_validation.py`

**Utilities**:
- `normalize_ingest.py`
- `normalize_tagger.py`
- `extract_terms.py`

### Configuration Files (20+ files)

See Section 3.1 for full list.

---

**Report Generated**: 2026-02-20  
**Next Review**: Upon completion of v1.3.0 planning phase
