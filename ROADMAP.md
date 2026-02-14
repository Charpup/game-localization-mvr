# Development Roadmap - Game Localization MVR

**Last Updated**: 2026-02-14  
**Current Version**: v1.1.0-stable  
**Maintainer**: Charpup + OpenClaw Agent

---

## 🎯 Project Vision

Transform game localization from a weeks-long, expensive outsourcing process into an **hour-level, cost-effective, AI-powered pipeline** that maintains human-level quality through intelligent QA and glossary management.

**Long-term Goal**: Become the industry-standard open-source solution for game localization, supporting all major language pairs with 90%+ cost reduction and 10x speed improvement.

---

## 📊 Current State (v1.1.0-stable)

### ✅ Capabilities

- **Language Support**: ZH-CN → RU-RU (production-ready)
- **Scale**: Validated on 30k+ rows ($48.44 cost, 99.87% accuracy)
- **Pipeline Stages**:
  - Normalization (placeholder freezing, tag protection)
  - Translation (LLM-powered with glossary)
  - Dual QA (Hard rules + Soft LLM review)
  - Dual Repair Loops (automated fixing)
- **Quality Control**:
  - Glossary management with auto-promotion
  - Style guide enforcement
  - Placeholder/tag integrity validation
  - Long text isolation (>500 chars)
- **Monitoring**:
  - Unified LLM trace aggregation
  - Cost tracking per pipeline stage
  - Real-time progress reporting with time deltas
- **Infrastructure**:
  - Dockerized environment (gate_v2 container)
  - Multi-model support (GPT-4o, Claude Sonnet/Haiku)
  - Secure API key injection via ENV

### ⚠️ Known Limitations

- **Single Language Pair**: Only ZH-CN → RU-RU supported
- **Batch Processing Only**: No real-time translation API
- **Manual Glossary Approval**: Proposed terms require human review
- **Limited Context Inference**: UI scene tags are optional, not automatic
- **No Game Engine Integration**: Manual import/export required
- **Test Coverage**: ~60% (core scripts covered, edge cases pending)

---

## 🚀 Short-term Roadmap (v1.2.0 - Q2 2026)

**Target Release**: 2026-04-30  
**Focus**: Feature optimization, performance improvements, enhanced monitoring

### 1. Feature Optimizations

#### 1.1 Glossary Management Enhancements

- **Auto-approval Threshold**: Promote terms with >95% consistency across 100+ occurrences
- **Conflict Resolution UI**: Web-based interface for reviewing conflicting term proposals
- **Domain-specific Glossaries**: Separate glossaries for UI, dialogue, items, skills
- **Glossary Versioning**: Track glossary changes with git-like diff/merge

#### 1.2 Context Inference Improvements

- **Automatic Scene Detection**: Use ML to infer UI context from string patterns
- **Contextual Translation**: Adjust tone based on scene (battle/shop/dialogue)
- **Cross-reference Detection**: Identify related strings for consistency

#### 1.3 Quality Assurance Enhancements

- **Fuzzy Matching QA**: Detect near-duplicate translations with subtle errors
- **Tone Consistency Check**: Ensure formal/informal tone alignment
- **Cultural Adaptation Rules**: Flag culturally inappropriate translations
- **A/B Testing Framework**: Compare translation quality across different prompts/models

### 2. Performance Improvements

#### 2.1 Speed Optimizations

- **Parallel Batch Processing**: Process multiple batches concurrently (2-4x speedup)
- **Smart Caching**: Cache translations for repeated strings (30-50% cost reduction)
- **Incremental Translation**: Only translate changed strings in updates
- **Model Selection Optimization**: Auto-select fastest model for simple strings

#### 2.2 Cost Optimizations

- **Tiered Model Routing**: Use Haiku for simple strings, Sonnet for complex ones
- **Batch Size Optimization**: Dynamic batch sizing based on string complexity
- **Prompt Compression**: Reduce system prompt tokens by 30-40%
- **Fallback to Cheaper Models**: Retry with cheaper models on non-critical failures

### 3. Monitoring & Debugging

#### 3.1 Enhanced Metrics Dashboard

- **Web UI**: Real-time dashboard showing pipeline progress, costs, errors
- **Cost Breakdown**: Per-stage, per-model, per-batch cost visualization
- **Quality Metrics**: Track accuracy, consistency, glossary coverage over time
- **Alert System**: Email/Slack notifications for pipeline failures or cost overruns

#### 3.2 Debugging Tools

- **Interactive Repair Mode**: Web UI for manually fixing QA failures
- **Translation Diff Viewer**: Compare translations across different runs
- **Trace Replay**: Re-run specific batches with different parameters
- **Error Pattern Analysis**: Automatically identify common failure patterns

---

## 🌍 Medium-term Roadmap (v2.0.0 - Q3 2026)

**Target Release**: 2026-09-30  
**Focus**: Multi-language expansion, advanced glossary, API service

### 1. ZH-CN → EN-US Translation Support

#### 1.1 Core Implementation

- **New Language Pair Config**: Add `zh-cn_to_en-us` routing in `llm_routing.yaml`
- **English-specific QA Rules**:
  - Article usage validation (a/an/the)
  - Plural form consistency
  - Tense agreement checks
- **English Style Guide**: Create `style_guides/en_us_game_translation.md`
- **Glossary Bootstrap**: Extract 500+ common game terms from existing projects

#### 1.2 Cultural Adaptation

- **Idiom Translation**: Handle Chinese idioms → English equivalents
- **Name Localization**: Transliterate character names appropriately
- **Measurement Units**: Convert Chinese units (斤/里) to Western equivalents
- **Cultural References**: Flag and adapt culturally-specific content

#### 1.3 Validation

- **10k Row Test**: Validate on 10k row dataset from real game project
- **Native Speaker Review**: Hire 2-3 native English speakers for quality audit
- **Comparison Benchmark**: Compare against professional translation agency

### 2. Multi-language Framework

#### 2.1 Language Pair Matrix

Support for additional language pairs:

- ZH-CN → JA-JP (Japanese)
- ZH-CN → KO-KR (Korean)
- ZH-CN → ES-ES (Spanish)
- EN-US → ZH-CN (reverse translation)

#### 2.2 Unified Pipeline Architecture

- **Language-agnostic Core**: Refactor scripts to support any language pair
- **Per-language Plugins**: Modular QA rules, style guides, glossaries
- **Automatic Language Detection**: Infer source language from input
- **Multi-target Translation**: Translate to multiple languages in one run

### 3. Advanced Glossary Management

#### 3.1 Glossary Intelligence

- **Contextual Glossary**: Different translations for same term in different contexts
- **Glossary Inheritance**: Base glossary + IP-specific overrides
- **Glossary Suggestions**: AI-powered term extraction from reference materials
- **Glossary Validation**: Detect inconsistencies and suggest corrections

#### 3.2 Collaborative Glossary Editing

- **Web-based Editor**: Multi-user glossary editing with role-based access
- **Change Tracking**: Full audit log of glossary modifications
- **Review Workflow**: Propose → Review → Approve → Publish pipeline
- **Import/Export**: Support for TBX, TMX, Excel formats

---

## 🔮 Long-term Vision (v3.0.0+ - 2027+)

### 1. Real-time Translation API

**Goal**: Provide REST API for on-demand translation

```bash
POST /api/v1/translate
{
  "source_lang": "zh-CN",
  "target_lang": "ru-RU",
  "strings": ["你好", "世界"],
  "glossary_id": "naruto_ip",
  "style": "casual"
}

Response:
{
  "translations": ["Привет", "Мир"],
  "cost_usd": 0.002,
  "latency_ms": 450
}
```

**Features**:

- Sub-second latency for <100 strings
- Automatic glossary application
- Streaming support for long texts
- Webhook callbacks for async processing

### 2. Game Engine Integration

#### 2.1 Unity Plugin

- **Asset Import**: Directly import CSV/JSON from Unity projects
- **In-editor Preview**: Preview translations in Unity Editor
- **Hot Reload**: Update translations without restarting game
- **Localization Manager**: GUI for managing multiple language versions

#### 2.2 Unreal Engine Plugin

- **Localization Dashboard**: Integrate with Unreal's localization system
- **Blueprint Nodes**: Translation nodes for Blueprint scripting
- **Live Translation**: Translate strings during gameplay (dev mode)

#### 2.3 Godot Plugin

- **CSV Integration**: Direct integration with Godot's CSV localization
- **Translation Editor**: In-engine translation management
- **Export Automation**: One-click export to localization pipeline

### 3. Full Multi-directional Translation Matrix

Support for **N × M language pairs** (any source → any target):

| Source ↓ / Target → | ZH-CN | EN-US | RU-RU | JA-JP | KO-KR | ES-ES | FR-FR | DE-DE |
|---------------------|-------|-------|-------|-------|-------|-------|-------|-------|
| **ZH-CN**           | -     | ✅    | ✅    | ✅    | ✅    | ✅    | 🔄    | 🔄    |
| **EN-US**           | ✅    | -     | ✅    | ✅    | ✅    | ✅    | 🔄    | 🔄    |
| **RU-RU**           | ✅    | ✅    | -     | 🔄    | 🔄    | 🔄    | 🔄    | 🔄    |
| **JA-JP**           | ✅    | ✅    | 🔄    | -     | ✅    | 🔄    | 🔄    | 🔄    |
| **KO-KR**           | ✅    | ✅    | 🔄    | ✅    | -     | 🔄    | 🔄    | 🔄    |

Legend: ✅ Supported | 🔄 Planned | - N/A

### 4. Advanced Features

#### 4.1 Machine Learning Enhancements

- **Custom Translation Models**: Fine-tune models on game-specific data
- **Quality Prediction**: Predict translation quality before human review
- **Automatic Post-editing**: AI-powered correction of common errors
- **Transfer Learning**: Leverage translations from similar games

#### 4.2 Workflow Automation

- **CI/CD Integration**: GitHub Actions for automatic translation on commits
- **Version Control Integration**: Track translation changes alongside code
- **Automated Testing**: Regression tests for translation quality
- **Release Management**: Automatic packaging for different platforms

#### 4.3 Analytics & Insights

- **Translation Memory**: Build corpus from all translated projects
- **Cost Forecasting**: Predict costs for new projects based on historical data
- **Quality Trends**: Track translation quality improvements over time
- **Bottleneck Analysis**: Identify and optimize pipeline bottlenecks

---

## 🛠️ Technical Debt & Refactoring

### Priority 1 (v1.2.0)

- [ ] **Test Coverage**: Increase from 60% to 90%
  - Add unit tests for all core scripts
  - Add integration tests for full pipeline
  - Add regression tests for known bugs
- [ ] **Code Documentation**: Add docstrings to all functions
- [ ] **Type Hints**: Add Python type hints throughout codebase
- [ ] **Error Handling**: Standardize error handling and logging

### Priority 2 (v2.0.0)

- [ ] **Modular Architecture**: Refactor monolithic scripts into modules
- [ ] **Configuration Management**: Centralize all config in YAML files
- [ ] **Database Integration**: Move from JSON files to SQLite/PostgreSQL
- [ ] **API Layer**: Create clean API abstraction for LLM calls

### Priority 3 (v3.0.0)

- [ ] **Microservices**: Split pipeline into independent services
- [ ] **Kubernetes Deployment**: Support for cloud-native deployment
- [ ] **Observability**: Add OpenTelemetry tracing and metrics
- [ ] **Security Audit**: Third-party security review and hardening

---

## 🤖 OpenClaw Agent Handoff Requirements

### 1. Required Context & Documentation

#### 1.1 Must-Read Documents (Priority Order)

1. **[README.md](README.md)**: Project overview and quick start
2. **[README_zh.md](README_zh.md)**: Detailed Chinese documentation
3. **[docs/WORKSPACE_RULES.md](docs/WORKSPACE_RULES.md)**: Agent-specific rules (CRITICAL)
4. **[.agent/rules/localization-mvr-rules.md](.agent/rules/localization-mvr-rules.md)**: Workflow rules
5. **[docs/localization_pipeline_workflow.md](docs/localization_pipeline_workflow.md)**: Pipeline phases
6. **[RELEASE_NOTES.md](RELEASE_NOTES.md)**: Recent changes and bug fixes
7. **This ROADMAP.md**: Development direction

#### 1.2 Key Concepts to Understand

- **Placeholder Freezing**: Why and how placeholders are tokenized
- **Dual QA System**: Hard rules (blocking) vs Soft QA (advisory)
- **Repair Loops**: Automated fixing vs manual intervention
- **Glossary Lifecycle**: Proposed → Approved → Applied
- **Docker Enforcement (Rule 12)**: Why LLM calls must run in containers
- **Parameter Locking (Rule 14)**: Never modify locked parameters without approval
- **Trace Aggregation**: How LLM calls are tracked for cost analysis

### 2. Development Environment Setup

#### 2.1 Prerequisites

```bash
# Required tools
- Python 3.9+
- Docker Desktop
- Git
- PowerShell 7+ (Windows) or Bash (Linux/Mac)

# Optional but recommended
- VSCode with Python extension
- Docker Compose
- Make (for automation)
```

#### 2.2 Initial Setup

```bash
# 1. Clone repository
git clone https://github.com/Charpup/game-localization-mvr.git
cd game-localization-mvr

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env to add your LLM API keys

# 4. Build Docker image
docker build -f Dockerfile.gate -t gate_v2 .

# 5. Run verification tests
python -m pytest tests/ -v

# 6. Run 1k row regression test
cd data/regression_tests/1k_test
bash run_test.sh
```

### 3. Testing & Validation Procedures

#### 3.1 Before Making Changes

- [ ] Read relevant workflow documentation
- [ ] Check if parameters are locked (Rule 14)
- [ ] Review recent commits for context
- [ ] Run existing tests to establish baseline

#### 3.2 After Making Changes

- [ ] Run unit tests: `pytest tests/ -v`
- [ ] Run 1k regression test: `cd data/regression_tests/1k_test && bash run_test.sh`
- [ ] Check metrics: `python scripts/metrics_aggregator.py --trace-path <path>`
- [ ] Verify Docker compliance: Ensure LLM scripts run in container
- [ ] Update documentation if behavior changes

#### 3.3 Before Committing

- [ ] Run `git status` to review changes
- [ ] Ensure no sensitive data (API keys) in commits
- [ ] Write descriptive commit message following convention:

  ```
  <type>(<scope>): <subject>
  
  Types: feat, fix, docs, refactor, test, chore
  Scope: P0, P1, skill, pipeline, qa, etc.
  ```

- [ ] Update RELEASE_NOTES.md if user-facing change

### 4. Common Development Tasks

#### 4.1 Adding a New Language Pair

1. Create language pair config in `config/llm_routing.yaml`
2. Add QA rules in `workflow/qa_rules_<lang>.yaml`
3. Create style guide in `style_guides/<lang>_game_translation.md`
4. Bootstrap glossary with common terms
5. Run 1k row validation test
6. Document in README.md

#### 4.2 Adding a New Pipeline Stage

1. Create script in `scripts/<stage_name>.py`
2. Add workflow in `.agent/workflows/loc-<stage>.md`
3. Update `docs/localization_pipeline_workflow.md`
4. Add trace logging via `trace_config.py`
5. Create verification script in `scripts/verify_<stage>.py`
6. Add to full pipeline workflow

#### 4.3 Fixing a Bug

1. Create verification script: `scripts/verify_bug<N>_<name>.py`
2. Implement fix in relevant script
3. Run verification script to confirm fix
4. Add regression test to prevent recurrence
5. Update RELEASE_NOTES.md with bug details
6. Commit with `fix(P0):` or `fix(P1):` prefix

### 5. Communication Guidelines

#### 5.1 When to Ask for User Approval

- **Always**: Modifying locked parameters (Rule 14)
- **Always**: Changing core pipeline logic
- **Always**: Adding new dependencies or Docker images
- **Recommended**: Adding new language pairs or major features
- **Optional**: Bug fixes, documentation updates, test additions

#### 5.2 How to Report Progress

- Use task boundaries to show progress
- Create walkthrough.md after completing major work
- Update task.md checklist as you progress
- Provide evidence (terminal logs, test results, file diffs)

#### 5.3 How to Handle Uncertainty

- **Don't guess**: If unsure about a rule or parameter, ask
- **Check history**: Review git log and RELEASE_NOTES.md for context
- **Run tests**: Validate assumptions with automated tests
- **Document assumptions**: If you make a decision, explain why

---

## 📈 Success Metrics

### v1.2.0 Targets

- **Cost Reduction**: $1.5/1k → $1.0/1k (33% improvement)
- **Speed**: 3k rows in 45min → 30min (50% improvement)
- **Accuracy**: 99.87% → 99.95% (reduce errors by 50%)
- **Test Coverage**: 60% → 90%
- **Glossary Auto-approval**: 0% → 30% of proposed terms

### v2.0.0 Targets

- **Language Pairs**: 1 → 5 (ZH-CN → EN/RU/JA/KO/ES)
- **Translation Memory**: 0 → 100k+ strings
- **API Latency**: N/A → <500ms for 100 strings
- **User Adoption**: 1 project → 10+ projects

### v3.0.0 Targets

- **Language Matrix**: 5 → 64 pairs (8×8 matrix)
- **Game Engine Integrations**: 0 → 3 (Unity/Unreal/Godot)
- **Community Contributors**: 1 → 20+
- **Industry Adoption**: Indie games → AA/AAA studios

---

## 🤝 Contributing

This project is maintained by **Charpup** with assistance from **OpenClaw Agent**.

For questions, suggestions, or collaboration:

- **GitHub Issues**: <https://github.com/Charpup/game-localization-mvr/issues>
- **Email**: <goodbigatree@gmail.com>

---

**Last Updated**: 2026-02-14  
**Next Review**: 2026-04-30 (v1.2.0 release)
