#!/bin/bash
# Stress Test Phase 3 & 4 Helper (Fixed Quoting)
TEST_DIR="data/Test_Batch/09. Stress test"

echo "--- Phase 3: Glossary ---"
# Step 3.1: Sampling (using python with environment variable for path)
export TEST_DIR_ENV="$TEST_DIR"
python3 -c "
import yaml
import os
test_dir = os.getenv('TEST_DIR_ENV')
path = os.path.join(test_dir, 's5k_term_candidates.yaml')
if not os.path.exists(path):
    print(f'Error: Candidates file missing at {path}')
    exit(1)
with open(path) as f:
    data = yaml.safe_load(f) or {}
props = data.get('proposals', [])
if len(props) > 500:
    print(f'Sampling 500 terms from {len(props)}')
    data['proposals'] = props[:500]
out_path = os.path.join(test_dir, 's5k_term_candidates_sample.yaml')
with open(out_path, 'w') as f:
    yaml.dump(data, f)
"

# Step 3.2: Translate
python3 -u scripts/glossary_translate_llm.py \
    --proposals "$TEST_DIR/s5k_term_candidates_sample.yaml" \
    --output "$TEST_DIR/s5k_glossary_translated.yaml" \
    --model claude-haiku-4-5-20251001

# Step 3.3: Compile
python3 scripts/glossary_compile.py \
    "$TEST_DIR/s5k_glossary_translated.yaml" \
    "$TEST_DIR/s5k_glossary_compiled.yaml"

echo "--- Phase 4: Translation ---"
# Use a specific checkpoint for the stress test
python3 -u scripts/translate_llm.py \
    --input "$TEST_DIR/s5k_draft.csv" \
    --output "$TEST_DIR/s5k_translated.csv" \
    --style workflow/style_guide.md \
    --glossary "$TEST_DIR/s5k_glossary_compiled.yaml" \
    --checkpoint "$TEST_DIR/s5k_translate_checkpoint.json" \
    --model claude-haiku-4-5-20251001

echo "✅ Stress Test Phase 3 & 4 Complete"
