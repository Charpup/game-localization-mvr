---
name: loc-mvr
description: "Professional game localization pipeline with placeholder protection, glossary management, and multi-stage quality assurance. Use when: (1) User mentions game localization or translation, (2) Input contains game text with HTML/Unity tags or placeholders like <color=#ff0000> or % d, (3) User needs batch translation with automated QA, (4) CSV file contains Chinese game text to be translated to Russian or other languages"
version: "1.1.0"
license: "MIT License"
---

# Game Localization Pipeline (Loc-mvr)

## Overview

Production-ready localization pipeline for game text (Chinese → Russian/Other):

- **Placeholder Protection**: Freezes HTML/Unity tags during translation
- **Glossary Management**: Automated term extraction and consistent translation
- **Multi-Stage QA**: Rule-based + LLM-powered with auto-repair
- **Cost Control**: ~$1.50-$4/1k rows (verified at 30k scale)

**Production Verified** (30k rows): $48.44 cost, <5 errors, $1.59/1k rows

## Prerequisites

**API Credentials** (Required before execution):

```powershell
# Windows
$env:LLM_API_KEY = "your_key"
$env:LLM_BASE_URL = "https://api.example.com/v1"
```

**Dependencies**:

```bash
pip install -r requirements.txt
```

## Quick Start (5 rows demo)

**Docker Environment (Recommended for Production)**:

```bash
# Set environment variables
export LLM_API_KEY="your_key"
export LLM_BASE_URL="https://api.example.com/v1"

# Run translation in container (example)
docker run --rm -v ${PWD}:/workspace -w /workspace \
  -e LLM_BASE_URL -e LLM_API_KEY \
  gate_v2 python -u -m scripts.translate_llm \
  output/normalized.csv output/translated.csv \
  workflow/style_guide.md glossary/compiled.yaml
```

**Note**: LLM-calling scripts (translate_llm, soft_qa_llm, repair_loop) MUST run in Docker per Rule 12.

**Local Environment (Development Only)**:

**Docker Environment (Recommended for Production)**:

```bash
# Set environment variables
export LLM_API_KEY="your_key"
export LLM_BASE_URL="https://api.example.com/v1"

# Run translation in container (example)
docker run --rm -v ${PWD}:/workspace -w /workspace \
  -e LLM_BASE_URL -e LLM_API_KEY \
  gate_v2 python -u -m scripts.translate_llm \
  output/normalized.csv output/translated.csv \
  workflow/style_guide.md glossary/compiled.yaml
```

**Note**: LLM-calling scripts (translate_llm, soft_qa_llm, repair_loop) MUST run in Docker per Rule 12.

**Local Environment (Development Only)**:

**Docker 环境 (推荐生产使用)**:

```bash
# 设置环境变量
export LLM_API_KEY="your_key"
export LLM_BASE_URL="https://api.example.com/v1"

# 在容器内运行 (以 translate 为例)
docker run --rm -v ${PWD}:/workspace -w /workspace \
  -e LLM_BASE_URL -e LLM_API_KEY \
  gate_v2 python -u -m scripts.translate_llm \
  --input output/normalized.csv --output output/translated.csv \
  --style workflow/style_guide.md --glossary glossary/compiled.yaml
```

**本地环境 (开发调试)**:

```bash
cd skill/

# 1. Normalize
python scripts/normalize_guard.py \
  examples/sample_input.csv \
  output/normalized.csv \
  output/placeholder_map.json \
  workflow/placeholder_schema.yaml

# 2. Translation
python scripts/translate_llm.py \
  --input output/normalized.csv \
  --output output/translated.csv \
  --style workflow/style_guide.md \
  --glossary glossary/compiled.yaml

# 3. QA
python scripts/qa_hard.py \
  output/translated.csv \
  output/placeholder_map.json \
  workflow/placeholder_schema.yaml \
  workflow/forbidden_patterns.txt \
  output/qa_report.json

# 4. Export
python scripts/rehydrate_export.py \
  output/translated.csv \
  output/placeholder_map.json \
  output/final_export.csv
```

## Standard Workflow

**DO NOT SKIP STEPS** - Execute in order.

### Phase 1: Preparation

#### Step 1: Normalization

Masks placeholders like `<color>` or `{0}` to protect them from translation.

```bash
python scripts/normalize_guard.py <input.csv> <draft.csv> <map.json> workflow/placeholder_schema.yaml
```

#### Step 2: Tagging (Optional)

Identifies UI context (e.g., Button, Dialog).

```bash
python scripts/normalize_tagger.py --input <draft.csv> --output <normalized.csv>
```

### Phase 2: Setup

#### Step 3: Style Guide

```bash
python scripts/style_guide_generate.py --output workflow/style_guide.md
```

#### Step 4: Term Extraction

```bash
python scripts/extract_terms.py <normalized.csv> --out data/term_candidates.yaml
```

#### Step 5: Glossary Compilation

```bash
python scripts/glossary_compile.py --approved glossary/approved.yaml --out_compiled glossary/compiled.yaml
```

### Phase 3: Translation & Hard QA

#### Step 6: Batch Translation

**Parameters (LOCKED by Rule 14)**: `batch_size=50`, `temperature=0.3`. Do NOT modify.

```bash
python scripts/translate_llm.py --input <normalized.csv> --output <translated.csv> --style workflow/style_guide.md --glossary glossary/compiled.yaml
```

#### Step 7: Hard QA

Checks for placeholder mismatches and forbidden patterns.

```bash
python scripts/qa_hard.py <translated.csv> <map.json> workflow/placeholder_schema.yaml workflow/forbidden_patterns.txt <qa_report.json>
```

#### Step 8: Repair Loop (Hard)

Auto-fixes issues flagged in `qa_report.json`.

```bash
python scripts/repair_loop.py --input <translated.csv> --report <qa_report.json> --mode repair_hard --out_csv <repaired_v1.csv>
```

### Phase 4: Soft QA & Export

#### Step 9: Soft QA Audit

Checks for tone, fluency, and style violations.

```bash
python scripts/soft_qa_llm.py <repaired_v1.csv> --out_tasks <repair_tasks.jsonl>
```

#### Step 10: Repair Loop (Soft)

Fixes linguistic issues.

```bash
python scripts/repair_loop.py --input <repaired_v1.csv> --tasks <repair_tasks.jsonl> --mode repair_soft_major --out_csv <repaired_final.csv>
```

#### Step 11: Rehydration (Export)

Restores original placeholders.

```bash
python scripts/rehydrate_export.py <repaired_final.csv> <map.json> <final_export.csv>
```

### Phase 5: Lifecycle

#### Step 12: Glossary Autopromote

```bash
python scripts/glossary_autopromote.py --before <translated.csv> --after <repaired_final.csv>
```

#### Step 13: Round 2 Refresh (Incremental)

```bash
python scripts/glossary_delta.py --old <old.yaml> --new <new.yaml>
python scripts/translate_refresh.py --input <final.csv> --glossary <new.yaml> --out_csv <refreshed.csv>
```

#### Step 14: Metrics

```bash
python scripts/metrics_aggregator.py --trace data/llm_trace.jsonl --out_md reports/metrics_report.md
```

## Troubleshooting

### Issue 1: API Key Not Found

**Error**: `Missing LLM_API_KEY`
**Fix**:

```powershell
$env:LLM_API_KEY = "your_key"
```

### Issue 2: Token Limit Exceeded

**Error**: `maximum context length exceeded`
**Cause**: Long text not isolated
**Fix**: Re-run `normalize_guard.py` (ensures `is_long_text` column exists)

### Issue 3: Placeholder Leakage

**Error**: `new_placeholder_found > 0`
**Fix**: Add missing pattern to `workflow/placeholder_schema.yaml`

### Issue 4: Model Routing Confusion

**Symptom**: Terminal shows "haiku", API charges "sonnet"
**Fix**: Upgrade to `v1.0.2-p1-quality` or later

### Issue 5: Metrics Incomplete

**Symptom**: `llm_trace.jsonl` missing phases or `metrics_report.md` shows unknown steps > 10%
**Diagnosis**:

```bash
# Check if trace path is configured
python -c "from scripts import trace_config; print(trace_config.get_trace_path())"
# Expected output: data/llm_trace.jsonl
# If output is 'None' or default default, might need explicit setup
```

**Fix**: Add at the start of your script:

```python
from scripts import trace_config
trace_config.setup_trace_path('data/llm_trace.jsonl')
```

### Issue 6: Docker Container Not Used

**Symptom**: Script runs but violates Rule 12 (container enforcement)
**Fix**: Always use Docker for LLM-calling scripts:

```bash
# Wrong (local execution)
python scripts/translate_llm.py input.csv output.csv

# Correct (container execution)
docker run --rm -v ${PWD}:/workspace -w /workspace \
  -e LLM_BASE_URL -e LLM_API_KEY \
  gate_v2 python -u -m scripts.translate_llm input.csv output.csv
```

## References

For detailed specifications:

- **[QA Rules](references/qa_rules.md)**: Hard QA validation logic
- **[Glossary Spec](references/glossary_spec.md)**: Term extraction workflow
- **[Metrics Guide](references/metrics_guide.md)**: Cost tracking and optimization
