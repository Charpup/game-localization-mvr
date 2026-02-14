#!/bin/bash
# Phase 3 Stress Test Helper
TEST_DIR="data/Test_Batch/09. Stress test"

echo "--- Step 3.1: Sampling 500 Terms ---"
python3 -c "
import yaml
import os
path = '$TEST_DIR/s5k_term_candidates.yaml'
if not os.path.exists(path):
    print('Error: Candidates file missing')
    exit(1)
with open(path) as f:
    data = yaml.safe_load(f) or {}
props = data.get('proposals', [])
if len(props) > 500:
    print(f'Sampling 500 terms from {len(props)}')
    data['proposals'] = props[:500]
with open('$TEST_DIR/s5k_term_candidates_sample.yaml', 'w') as f:
    yaml.dump(data, f)
"

echo "--- Step 3.2: Translating Terms ---"
python3 -u scripts/glossary_translate_llm.py \
    --proposals "$TEST_DIR/s5k_term_candidates_sample.yaml" \
    --output "$TEST_DIR/s5k_glossary_translated.yaml" \
    --model claude-haiku-4-5-20251001

echo "--- Step 3.3: Compiling Glossary ---"
python3 scripts/glossary_compile.py \
    "$TEST_DIR/s5k_glossary_translated.yaml" \
    "$TEST_DIR/s5k_glossary_compiled.yaml"

echo "✅ Phase 3 Resumed Successfully"
