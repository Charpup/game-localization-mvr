## 🔧 Hotfix Summary

Critical improvements to Docker usage guidance and troubleshooting.

**This release supersedes v1.1.0** - Please use v1.1.0-patch2 for production.

---

## 🎯 What's New in v1.1.0-patch2

### Critical Fixes (from v1.1.0)

- ✅ **Docker Examples Added**: Quick Start now includes container runtime examples (Rule 12 compliance)
- ✅ **Trace Diagnostics**: Issue 5 expanded with `trace_config` check commands
- ✅ **Container Enforcement**: New Issue 6 explains Docker requirement for LLM scripts
- ✅ **Typo Fixes**: Corrected "AQ"→"QA" and "Optmized"→"Optimized"

### Improvements (from v1.1.0-patch1)

- 🧹 **Clean Quick Start**: Removed duplicate Docker examples (3→1)
- 🚀 **Unified Workflow**: Docker example now runs all 4 steps in single command
- 📝 **Encoding Fix**: Removed UTF-8 corruption in documentation

### Enhancements

- 📦 **README Badge**: Direct Skill download link with verification guide
- 🐛 **Issue Templates**: Structured Bug Report and Feature Request forms

---

## 📦 Installation

### Option 1: Download Pre-packaged Skill (Recommended)

```bash
# Download
wget https://github.com/Charpup/game-localization-mvr/releases/download/v1.1.0-patch2/loc-mvr-v1.1.0-patch2.skill

# Verify checksum
wget https://github.com/Charpup/game-localization-mvr/releases/download/v1.1.0-patch2/loc-mvr-v1.1.0-patch2.skill.sha256
sha256sum -c loc-mvr-v1.1.0-patch2.skill.sha256

# Extract and use
unzip loc-mvr-v1.1.0-patch2.skill
cd skill/
```

### Option 2: Clone Full Repository

```bash
git clone https://github.com/Charpup/game-localization-mvr.git
cd game-localization-mvr
git checkout v1.1.0-patch2
pip install -r requirements.txt
```

---

## 🚀 Quick Start

**Docker (All-in-One)**:

```bash
# Set credentials
export LLM_API_KEY="your_key"
export LLM_BASE_URL="https://api.example.com/v1"

# Run complete workflow in container
docker run --rm -v ${PWD}:/workspace -w /workspace \
  -e LLM_BASE_URL -e LLM_API_KEY \
  gate_v2 bash -c "
  python -u scripts/normalize_guard.py \
    examples/sample_input.csv output/normalized.csv \
    output/placeholder_map.json workflow/placeholder_schema.yaml &&
  python -u scripts/translate_llm.py \
    output/normalized.csv output/translated.csv \
    workflow/style_guide.md glossary/compiled.yaml &&
  python -u scripts/qa_hard.py \
    output/translated.csv output/qa_report.json \
    output/placeholder_map.json &&
  python -u scripts/rehydrate_export.py \
    output/translated.csv output/placeholder_map.json \
    output/final_export.csv
"
```

See `SKILL.md` for complete workflow (14 steps).

---

## 📊 Production Metrics (Verified at 30k rows)

| Metric | Value | Target |
|--------|-------|--------|
| **Cost** | $1.59/1k rows | <$2.00 |
| **Quality** | <5 errors/30k | <1% error rate |
| **Speed** | ~4h for 30k rows | - |
| **Repair Rate** | 98.9% (Hard QA) | >95% |

---

## 📚 Documentation

- **[SKILL.md](skill/SKILL.md)**: Complete workflow guide
- **[QA Rules](skill/references/qa_rules.md)**: Hard QA logic & repair strategies
- **[Glossary Spec](skill/references/glossary_spec.md)**: Term management lifecycle
- **[Metrics Guide](skill/references/metrics_guide.md)**: Cost optimization formulas

---

## 🐛 Reporting Issues

Use our [Bug Report Template](https://github.com/Charpup/game-localization-mvr/issues/new?template=bug_report.yml) for structured issue reporting.

---

## 🙏 Credits

Built with [Claude](https://claude.ai) for game localization automation.
