# Task Plan: Loc-MVR ZH ➡️ EN Multi-Language Support

**Project**: game-localization-mvr  
**Current Version**: v1.2.0 (ZH ➡️ RU)  
**Target Version**: v1.3.0 (ZH ➡️ EN + Multi-Language Framework)  
**Mode**: TriadDev + Full Speed Auto-Pilot  
**Started**: 2026-02-20  

---

## Phase 1: Assessment & Planning

### 1.1 Skill Packaging Evaluation
- [ ] Evaluate current v1.2.0 skill structure
- [ ] Identify skill upgrade requirements
- [ ] Plan skill packaging for v1.3.0

### 1.2 ZH ➡️ EN Feature Analysis
- [ ] Review translate_llm.py for language hardcoding
- [ ] Identify Russian-specific logic
- [ ] Design multi-language framework
- [ ] Plan configuration-based language switching

### 1.3 Version Roadmap Definition
**v1.3.0 Goals:**
- ZH ➡️ EN translation support
- Multi-language framework (configurable)
- Language-specific glossary support
- EN-specific QA rules

---

## Phase 2: Design & Implementation

### 2.1 Multi-Language Framework
- [ ] Refactor translate_llm.py for language parameter
- [ ] Create language-specific configs
- [ ] Update glossary system for multi-language
- [ ] Add language detection/preservation

### 2.2 ZH ➡️ EN Specific Features
- [ ] EN-specific style guide support
- [ ] English grammar validation
- [ ] EN-specific forbidden patterns
- [ ] Length rule adjustments for EN

### 2.3 QA & Testing
- [ ] Update qa_hard.py for EN rules
- [ ] Create EN test cases
- [ ] Validation pipeline for EN

---

## Phase 3: Integration & Packaging

### 3.1 Skill Packaging v1.3.0
- [ ] Package as OpenClaw skill
- [ ] Update SKILL.md documentation
- [ ] Create installation guide

### 3.2 GitHub Release
- [ ] Push to reorg/v1.3.0-structure
- [ ] Create PR to main
- [ ] Release v1.3.0

---

## Success Criteria

1. ✅ ZH ➡️ EN translation working
2. ✅ Multi-language framework in place
3. ✅ Skill package v1.3.0 created
4. ✅ GitHub release published
5. ✅ Documentation updated

---

**Status**: 🔄 PLANNING PHASE