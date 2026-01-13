# Game Localization MVR (Minimum Viable Rules) v2.0

A robust, automated workflow system for managing game localization with strict validation, AI translation/repair, and multi-format export capabilities.

> **Key Features**: Token freezing, Hard/Soft QA, Auto-repair Loop, Round2 Refresh, Cost Tracking.

---

## 🤖 Agent Deployment Instructions

**For Vibe Coding Agents / AI Deployments:**

### 1. Environment Setup
Target OS: Windows (preferred) or Linux. Python 3.8+ required.

```bash
# Clone repository
git clone https://github.com/Charpup/game-localization-mvr.git
cd game-localization-mvr

# Install dependencies
pip install pyyaml requests
```

### 2. Configuration
Set environment variables for LLM access (OpenAI-compatible API):

```powershell
# Windows PowerShell
$env:LLM_BASE_URL="https://api.apiyi.com/v1"
$env:LLM_API_KEY="sk-your-api-key"
$env:LLM_MODEL="gpt-4o-mini"
$env:LLM_TIMEOUT_S="60"
```

### 3. Quick Verification
Run the dry-run test suite to verify the environment:
```bash
python scripts/test_llm_dry_run.py
```

---

## 🚀 Human Quick Start

### 1. Prepare Data
Ensure your input CSV has columns: `string_id`, `source_zh`, `target_ru` (optional).
See `data/fixtures/input_valid.csv` for example.

### 2. Run Pipeline Steps

#### Step 1: Normalize (Freeze Placeholders)
```bash
python scripts/normalize_guard.py input.csv temp_normalized.csv placeholder_map.json workflow/placeholder_schema.yaml
```

#### Step 5: Translate
```bash
python scripts/translate_llm.py temp_normalized.csv translated.csv workflow/style_guide.md glossary/compiled.yaml
```

#### Step 6-7: QA & Repair (Hard)
```bash
python scripts/qa_hard.py translated.csv qa_report.json placeholder_map.json
python scripts/repair_loop.py translated.csv qa_report.json repair_tasks.jsonl workflow/style_guide.md glossary/compiled.yaml --out_csv repaired.csv
```

#### Step 10: Export (Rehydrate)
```bash
python scripts/rehydrate_export.py repaired.csv placeholder_map.json final_output.csv
```

---

## 🔄 Full Pipeline Overview

| Step | Script | Purpose |
|------|--------|---------|
| **1** | `normalize_guard.py` | 🧊 Freeze tags/placeholders into tokens (`⟦PH_1⟧`) |
| **2-4** | (Manual/Pre-process) | Glossary check & extraction |
| **5** | `translate_llm.py` | 🤖 AI Translation with glossary & style guide |
| **6** | `qa_hard.py` | 🛡️ **Blocker**: Validate forbidden patterns & tokens |
| **7** | `repair_loop.py` | 🔧 Auto-repair hard errors |
| **8** | `soft_qa_llm.py` | 🧠 AI Quality Check (nuance, tone, glossary) |
| **9** | `repair_loop.py` | 🔧 Auto-repair major soft issues |
| **10** | `rehydrate_export.py` | 💧 Restore tokens to original placeholders |
| **11** | `metrics_aggregator.py` | 💰 Calculate costs & token usage |
| **12** | `glossary_autopromote.py` | 📖 Extract new terms from translation |
| **13** | `translate_refresh.py` | ♻️ Round 2: Update translations affected by glossary changes |

---

## 📁 Project Structure

```text
loc-mvr/
├── config/              # Configuration (pricing, routing)
├── data/                # Data storage (ignored by git usually)
│   └── Test_Batch/      # Test datasets
├── docs/                # Usage documentation
├── glossary/            # Glossary files (YAML)
├── scripts/             # Core Python scripts
│   ├── runtime_adapter.py  # LLM Client & Router
│   ├── translate_llm.py    # Main translation script
│   ├── repair_loop.py      # Repair logic
│   └── ...
└── workflow/            # Workflow rules
    ├── forbidden_patterns.txt
    ├── placeholder_schema.yaml
    └── style_guide.md
```

## 🔧 Configuration

- **Routing**: `config/llm_routing.yaml` - Configure which model handles which step.
- **Pricing**: `config/pricing.yaml` - Set token costs for metrics.
- **Rules**: `workflow/` - Customize forbidden patterns and style guides.

## 🧪 Testing

Run specific test suites:

```bash
python scripts/test_normalize.py
python scripts/test_rehydrate.py
python scripts/test_e2e_workflow.py  # Small E2E test
```

## 📄 License

MIT License. Built for game localization automation.
