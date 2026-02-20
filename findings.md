# Findings: Loc-MVR ZH ➡️ EN Assessment

**Date**: 2026-02-20  
**Current Version**: v1.2.0 (ZH ➡️ RU)  
**Target**: v1.3.0 (ZH ➡️ EN + Multi-Language)

---

## 1. Skill Packaging Status

### Current State ✅
- **Package**: skill/loc-mvr-v1.2.0.skill (256KB)
- **Structure**: Follows OpenClaw standards
- **Documentation**: SKILL.md present
- **Tests**: 22 test files included
- **Status**: Production-ready for ZH ➡️ RU

### Upgrade Requirements for v1.3.0
- [ ] Multi-language configuration system
- [ ] Language-specific prompt templates
- [ ] Dynamic language pair loading
- [ ] EN-specific QA rules

---

## 2. Russian Language Hardcoding Analysis

### Critical Files with Hardcoded Russian

| File | Line | Content |
|------|------|---------|
| batch_runtime.py | - | '你是严谨的手游本地化译者（zh-CN → ru-RU）。' |
| extract_terms.py | - | language_pair = {'source': 'zh-CN', 'target': 'ru-RU'} |
| glossary_compile.py | - | --language_pair zh-CN->ru-RU (default) |
| glossary_translate_llm.py | - | "你是术语表译者（zh-CN → ru-RU）" |
| soft_qa_llm.py | - | "你是手游本地化软质检（zh-CN → ru-RU）。" |
| style_guide_generate.py | - | "You are an expert Game Localization Director (zh-CN -> ru-RU)" |
| glossary_autopromote.py | - | --language_pair default="zh-CN->ru-RU" |
| glossary_review_llm.py | - | "language_pair: zh-CN -> ru-RU" |
| translate_refresh.py | - | "你是'术语变更刷新器'（zh-CN → ru-RU）。" |
| llm_config.yaml | - | target: "ru-RU" # 可修改为其他目标语言 |

### Pattern Analysis
1. **System Prompts**: 9 files have Russian-specific system prompts
2. **Language Pairs**: 6 files hardcode "zh-CN->ru-RU"
3. **Comments**: Multiple files mention "俄语" (Russian language)
4. **Configuration**: llm_config.yaml notes target can be changed

---

## 3. ZH ➡️ EN Implementation Strategy

### Option A: Configuration-Based (Recommended)
- Add `--target-lang` parameter to all scripts
- Create `config/language_pairs.yaml`
- Load prompts from templates based on language
- Minimal code changes, maximum flexibility

### Option B: Template System
- Create `templates/prompts/en/` directory
- Create `templates/prompts/ru/` directory
- Scripts load appropriate template based on config
- More maintainable for future languages

### Option C: Hardcoded EN Version (Quick)
- Replace all ru-RU with en-US
- Quick but not scalable
- Not recommended

---

## 4. Files Requiring Modification

### High Priority (Core Translation)
1. `batch_runtime.py` - Main translation loop
2. `glossary_translate_llm.py` - Glossary translation
3. `soft_qa_llm.py` - QA validation
4. `extract_terms.py` - Term extraction

### Medium Priority (Support)
5. `glossary_compile.py` - Glossary compilation
6. `glossary_autopromote.py` - Auto-promotion
7. `glossary_review_llm.py` - Review system
8. `style_guide_generate.py` - Style guide

### Low Priority (Utilities)
9. `translate_refresh.py` - Refresh logic
10. `llm_config.yaml` - Configuration

---

## 5. EN-Specific Considerations

### Language Differences
| Aspect | Russian | English |
|--------|---------|---------|
| Grammar | Complex cases | Simpler |
| Length | +30% vs ZH | -10% vs ZH |
| QA Rules | Case ending check | Grammar check |
| Glossary | Declension needed | Pluralization |

### Required EN Features
- [ ] English grammar validation
- [ ] Pluralization handling
- [ ] Article usage (a/an/the)
- [ ] Capitalization rules
- [ ] EN-specific forbidden patterns

---

## 6. Task Breakdown for v1.3.0

### Phase 1: Framework (2-3 days)
- [ ] Create language configuration system
- [ ] Implement dynamic prompt loading
- [ ] Update core translation scripts

### Phase 2: EN Support (2-3 days)
- [ ] Create EN prompt templates
- [ ] Implement EN QA rules
- [ ] Add EN glossary support

### Phase 3: Testing (1-2 days)
- [ ] Unit tests for multi-language
- [ ] Integration tests for EN
- [ ] Validation pipeline

### Phase 4: Release (1 day)
- [ ] Skill packaging
- [ ] Documentation update
- [ ] GitHub release

---

## 7. Recommendation

**Proceed with Option A (Configuration-Based)**:
- Clean architecture
- Future-proof for more languages
- Aligns with existing config pattern
- Estimated effort: 6-8 days

**Status**: ✅ Ready to begin Phase 1