#!/bin/bash
# Stress Test Resume Script (Phases 5-9) - Fixed
TEST_DIR="data/Test_Batch/09. Stress test"

echo "=========================================="
echo "5K-ROW 压力测试 - Phase 5: Hard QA"
echo "=========================================="
# Hard QA failed before, so we run it now.
# Usage: python qa_hard.py <csv_path> <map_path> <report_path>
python3 scripts/qa_hard.py \
    "$TEST_DIR/s5k_translated.csv" \
    "$TEST_DIR/s5k_placeholder_map.json" \
    "$TEST_DIR/s5k_qa_hard_report.json"

echo "=========================================="
echo "5K-ROW 压力测试 - Phase 6: Soft QA"
echo "=========================================="
if [ -f "$TEST_DIR/s5k_qa_soft_report.json" ]; then
    echo "✅ Soft QA Report found (skipping re-run)."
else
    python3 -u scripts/soft_qa_llm.py \
        "$TEST_DIR/s5k_translated.csv" \
        workflow/style_guide.md \
        "$TEST_DIR/s5k_glossary_compiled.yaml" \
        --out_report "$TEST_DIR/s5k_qa_soft_report.json" \
        --out_tasks "$TEST_DIR/s5k_repair_tasks.jsonl" \
        --model claude-haiku-4-5-20251001
fi

echo "=========================================="
echo "5K-ROW 压力测试 - Phase 7: Export"
echo "=========================================="
# Fixed args: positional
# python rehydrate_export.py input output map
# Wait, check source: argparse usually.
# Output from previous run suggests: rehydrate_export.py <translated_csv> <placeholder_map_json> <final_csv> [--overwrite]

python3 scripts/rehydrate_export.py \
    "$TEST_DIR/s5k_translated.csv" \
    "$TEST_DIR/s5k_placeholder_map.json" \
    "$TEST_DIR/s5k_final_export.csv"

echo "=========================================="
echo "5K-ROW 压力测试 - Phase 8: Metrics"
echo "=========================================="
python3 scripts/metrics_aggregator.py \
    --reports-dir reports \
    --output "$TEST_DIR/s5k_metrics_report" \
    --json

echo "=========================================="
echo "5K-ROW 压力测试 - Phase 9: Final Validation"
echo "=========================================="
python3 scripts/finalize_stress_report.py

echo "✅ Stress Test Resume Fixed Complete"
