#!/bin/bash
# Stress Test Resume Script (Phases 7-9)
TEST_DIR="data/Test_Batch/09. Stress test"

# --- Phase 6 Check (Soft QA) ---
echo "--- Checking Phase 6: Soft QA ---"
if [ -f "$TEST_DIR/s5k_qa_soft_report.json" ]; then
    echo "✅ Soft QA Report found."
else
    echo "⚠️ Soft QA Report missing. Running Soft QA..."
    python3 -u scripts/soft_qa_llm.py \
        "$TEST_DIR/s5k_translated.csv" \
        workflow/style_guide.md \
        "$TEST_DIR/s5k_glossary_compiled.yaml" \
        --out_report "$TEST_DIR/s5k_qa_soft_report.json" \
        --out_tasks "$TEST_DIR/s5k_repair_tasks.jsonl" \
        --model claude-haiku-4-5-20251001
fi

# --- Phase 7: Export ---
echo ""
echo "=========================================="
echo "5K-ROW 压力测试 - Phase 7: Export"
echo "=========================================="
python3 scripts/rehydrate_export.py \
    --input "$TEST_DIR/s5k_translated.csv" \
    --placeholder-map "$TEST_DIR/s5k_placeholder_map.json" \
    --output "$TEST_DIR/s5k_final_export.csv"

# --- Phase 8: Metrics ---
echo ""
echo "=========================================="
echo "5K-ROW 压力测试 - Phase 8: Metrics"
echo "=========================================="
# Metrics aggregator usually takes a reports directory. 
# We'll point it to the standard reports dir AND the stress test dir if needed?
# Actually, the runtime adapter logs to 'reports/' by default. 
# We need to aggregate those.
python3 scripts/metrics_aggregator.py \
    --reports-dir reports \
    --output "$TEST_DIR/s5k_metrics_report" \
    --json

# --- Phase 9: Final Report ---
echo ""
echo "=========================================="
echo "5K-ROW 压力测试 - Phase 9: Final Validation"
echo "=========================================="
python3 scripts/finalize_stress_report.py

echo ""
echo "✅ Stress Test Resume Complete"
