# Game Localization MVR (Minimum Viable Rules) v2.1

A robust, automated workflow system for game localization with strict validation, AI translation/repair, glossary management, and multi-format export.

> **Core Principle**: Input rows == Output rows ALWAYS. No silent data loss.

---

## 🤖 For AI Coding Agents

**Quick Commands for Agents:**

```bash
# 1. Verify LLM connectivity (MUST run first)
python scripts/llm_ping.py

# 2. Validate workflow configuration (dry-run)
python scripts/translate_llm.py input.csv output.csv workflow/style_guide.md glossary/compiled.yaml --dry-run

# 3. Run E2E test
python scripts/test_e2e_workflow.py
```

**Environment Variables (REQUIRED):**

```bash
LLM_BASE_URL=https://api.example.com/v1
LLM_API_KEY=sk-your-key
LLM_MODEL=gpt-4.1-mini
LLM_TRACE_PATH=data/llm_trace.jsonl
```

**Key Rules for Agents:**

1. **Never hardcode API keys** - Use environment variables only
2. **Run `llm_ping.py` first** - Fail-fast if LLM unavailable
3. **Check WORKSPACE_RULES.md** - See `docs/WORKSPACE_RULES.md` for hard constraints
4. **Row preservation is P0** - Empty source rows must be preserved with `status=skipped_empty`
5. **Glossary is mandatory** - `glossary/compiled.yaml` must exist before translation

---

## 🚀 Pipeline Overview

```
Input CSV → Normalize → Translate → QA_Hard → Repair → Export
                ↓
            Glossary (required)
```

| Step | Script | Purpose | Blocking? |
|------|--------|---------|-----------|
| 0 | `llm_ping.py` | 🔌 LLM connectivity check | YES |
| 1 | `normalize_guard.py` | 🧊 Freeze placeholders → tokens | YES |
| 2-4 | `extract_terms.py` → `glossary_compile.py` | 📖 Build glossary | YES |
| 5 | `translate_llm.py` | 🤖 AI Translation | YES |
| 6 | `qa_hard.py` | 🛡️ Validate tokens/patterns | YES |
| 7 | `repair_loop.py` | 🔧 Auto-repair hard errors | - |
| 8 | `soft_qa_llm.py` | 🧠 Quality review | - |
| 10 | `rehydrate_export.py` | 💧 Restore tokens → placeholders | YES |

---

## 📁 Project Structure

```
loc-mvr/
├── config/
│   ├── llm_routing.yaml    # Model routing per step
│   └── pricing.yaml        # Cost calculation
├── glossary/
│   ├── compiled.yaml       # Active glossary (generated)
│   └── generic_terms_zh.txt # Blacklist for extraction
├── scripts/
│   ├── llm_ping.py         # ★ Run first - connectivity check
│   ├── normalize_guard.py  # Step 1: Placeholder freezing
│   ├── translate_llm.py    # Step 5: Translation
│   ├── qa_hard.py          # Step 6: Hard validation
│   ├── repair_loop.py      # Step 7: Auto-repair
│   └── runtime_adapter.py  # LLM client with routing
├── workflow/
│   ├── style_guide.md      # Translation style rules
│   ├── forbidden_patterns.txt
│   └── placeholder_schema.yaml
└── docs/
    └── WORKSPACE_RULES.md  # ★ Hard constraints for agents
```

---

## 🔧 Quick Start (Human)

### 1. Setup

```bash
git clone https://github.com/Charpup/game-localization-mvr.git
cd game-localization-mvr
pip install pyyaml requests jieba
```

### 2. Configure LLM

```powershell
# Windows PowerShell
$env:LLM_BASE_URL="https://api.apiyi.com/v1"
$env:LLM_API_KEY="sk-your-key"
$env:LLM_MODEL="gpt-4.1-mini"
```

### 3. Run Pipeline

```bash
# Verify LLM
python scripts/llm_ping.py

# Normalize → Translate → QA → Export
python scripts/normalize_guard.py input.csv normalized.csv map.json workflow/placeholder_schema.yaml
python scripts/translate_llm.py normalized.csv translated.csv workflow/style_guide.md glossary/compiled.yaml
python scripts/qa_hard.py translated.csv qa_report.json map.json
python scripts/rehydrate_export.py translated.csv map.json final.csv
```

---

## ⚡ Key Features

- **Row Preservation**: Empty rows kept with `status=skipped_empty`
- **Drift Guard**: Refresh stage blocks non-placeholder text changes
- **Progress Reporting**: `--progress_every N` for translation progress
- **Router-based Models**: Configure per-step models in `llm_routing.yaml`
- **LLM Tracing**: All calls logged to `LLM_TRACE_PATH` for billing

---

## 📋 Testing

```bash
# Unit tests
python scripts/test_normalize.py
python scripts/test_qa_hard.py
python scripts/test_rehydrate.py

# E2E test (small dataset)
python scripts/test_e2e_workflow.py

# Dry-run validation
python scripts/translate_llm.py input.csv out.csv style.md glossary.yaml --dry-run
```

---

## 📄 License

MIT License. Built for game localization automation.

---

## 🔗 Links

- **Workspace Rules**: [docs/WORKSPACE_RULES.md](docs/WORKSPACE_RULES.md)
- **Demo Walkthrough**: [docs/demo.md](docs/demo.md)
