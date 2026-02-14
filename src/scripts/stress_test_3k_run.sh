#!/bin/bash
# 3k Full Pipeline Stress Test
# Input: data/Test_Batch/10._full-pipeline_press_test_3k-row/full_pipeline_press_test_3k-row.csv

# Base vars
BATCH_DIR="data/Test_Batch/10._full-pipeline_press_test_3k-row"
INPUT_CSV="$BATCH_DIR/full_pipeline_press_test_3k-row.csv"
MODEL="claude-haiku-4-5-20251001"

echo "=== Phase 0: Environment ==="
mkdir -p "$BATCH_DIR/reports"
export LLM_TRACE_PATH="$BATCH_DIR/reports/llm_trace.jsonl"

echo "=== Phase 1: Normalization (Rule+LLM) ==="
python3 -u scripts/normalize_tag_llm.py \
    --input "$INPUT_CSV" \
    --output "$BATCH_DIR/3k_tagged.csv" \
    --length-rules "config/length_rules.yaml" \
    --model "$MODEL"

echo "=== Phase 2: Term Extraction ==="
python3 scripts/extract_terms.py \
    --input "$BATCH_DIR/3k_tagged.csv" \
    --output "$BATCH_DIR/3k_term_candidates.yaml"

echo "=== Phase 3: Glossary Translate & Compile ==="
# Sampling for speed in stress test
python3 -c "
import yaml
with open('$BATCH_DIR/3k_term_candidates.yaml') as f:
    d = yaml.safe_load(f) or {}
props = d.get('proposals', [])
if len(props) > 300:
    d['proposals'] = props[:300]
    with open('$BATCH_DIR/3k_term_candidates_sample.yaml', 'w') as f:
        yaml.dump(d, f)
"

python3 -u scripts/glossary_translate_llm.py \
    --proposals "$BATCH_DIR/3k_term_candidates_sample.yaml" \
    --output "$BATCH_DIR/3k_glossary_translated.yaml" \
    --model "$MODEL"

python3 scripts/glossary_compile.py \
    "$BATCH_DIR/3k_glossary_translated.yaml" \
    "$BATCH_DIR/3k_glossary_compiled.yaml"

echo "=== Phase 4: Translation (with Length Constraints) ==="
python3 -u scripts/translate_llm.py \
    --input "$BATCH_DIR/3k_tagged.csv" \
    --output "$BATCH_DIR/3k_translated.csv" \
    --glossary "$BATCH_DIR/3k_glossary_compiled.yaml" \
    --style "workflow/style_guide.md" \
    --checkpoint "$BATCH_DIR/3k_translate_checkpoint.json" \
    --model "$MODEL"

echo "=== Phase 5: Hard QA & Repair Loop ==="
# 1. QA Hard Check
python3 scripts/qa_hard.py \
    "$BATCH_DIR/3k_translated.csv" \
    "data/placeholder_map.json" \
    "config/schema_v2.yaml" \
    "config/forbidden.txt" \
    "$BATCH_DIR/3k_qa_hard_report.json"

# 2. Repair Loop
# Hard QA failures need repair
python3 -u scripts/repair_loop.py \
    --input "$BATCH_DIR/3k_translated.csv" \
    --tasks "$BATCH_DIR/3k_qa_hard_report.json" \
    --output "$BATCH_DIR/3k_repaired_hard.csv" \
    --output-dir "$BATCH_DIR/reports" \
    --qa-type hard

echo "=== Phase 6: Soft QA ==="
python3 -u scripts/soft_qa_llm.py \
    --input "$BATCH_DIR/3k_repaired_hard.csv" \
    --output "$BATCH_DIR/3k_qa_soft_report.json" \
    --model "$MODEL"

# 3. Repair Loop (Soft)
python3 -u scripts/repair_loop.py \
    --input "$BATCH_DIR/3k_repaired_hard.csv" \
    --tasks "$BATCH_DIR/3k_qa_soft_report.json" \
    --output "$BATCH_DIR/3k_final.csv" \
    --output-dir "$BATCH_DIR/reports" \
    --qa-type soft

echo "=== Phase 7: Export ==="
python3 scripts/rehydrate_export.py \
    --input "$BATCH_DIR/3k_final.csv" \
    --output "$BATCH_DIR/3k_export_package.csv"

echo "✅ 3k Stress Test Complete"
