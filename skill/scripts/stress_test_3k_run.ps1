
# 3k Regression Test - PowerShell Orchestrator
# Executes full localization pipeline for 3k row dataset

$S = "data/regression_tests/3k_test"
$DataSrc = "data/Test_Batch/11. post-production_returning_test/test_input_3k-row.csv"
$Model = "claude-haiku-4-5-20251001"

echo "=== 3k Test Start ==="

# 0. Setup
if (!(Test-Path $S)) { New-Item -ItemType Directory -Force -Path $S }
if (!(Test-Path "$S/reports")) { New-Item -ItemType Directory -Force -Path "$S/reports" }

# Copy input if not exists (already done manually, but strict check)
if (!(Test-Path "$S/input.csv")) {
    Copy-Item $DataSrc "$S/input.csv"
}

$env:LLM_TRACE_PATH = "$S/llm_trace.jsonl"
$env:LLM_API_KEY = "sk-2Ks9TvuDvfZzFkwID6Cb43EcEeCd40929e8eFe1dE5604080"
$env:LLM_BASE_URL = "https://api.apiyi.com/v1"

# 1. Normalization (Ingest -> Guard)
echo "`n=== Phase 1: Normalization ==="
python scripts/normalize_ingest.py --input "$S/input.csv" --output "$S/source_raw.csv"
python scripts/normalize_guard.py "$S/source_raw.csv" "$S/normalized.csv" "$S/placeholder_map.json" "workflow/placeholder_schema.yaml"

# 2. Key Term Extraction
echo "`n=== Phase 2: Term Extraction ==="
# python scripts/extract_terms.py --input "$S/normalized.csv" --output "$S/term_candidates.yaml"

# 3. Glossary (Skipped/Simplified for Regression - Using compiled 3k glossary if avail, or empty)
# Linking to existing 3k compiled glossary to save time/cost as per plan
$GlossaryPath = "data/Test_Batch/10._full-pipeline_press_test_3k-row/3k_glossary_compiled.yaml"
if (!(Test-Path $GlossaryPath)) {
    echo "Warning: Pre-compiled glossary not found. Using empty."
    $GlossaryPath = ""
}
else {
    echo "Using pre-compiled glossary: $GlossaryPath"
}

# 4. Translation
echo "`n=== Phase 4: Translation (LLM) ==="
.\scripts\docker_run.ps1 python -u scripts/translate_llm.py `
    --input "$S/normalized.csv" `
    --output "$S/translated.csv" `
    --glossary "$GlossaryPath" `
    --style "workflow/style_guide.md" `
    --model "$Model" `
    --batch_size 50

# 5. Hard QA
echo "`n=== Phase 5: Hard QA ==="
python scripts/qa_hard.py `
    "$S/translated.csv" `
    "$S/placeholder_map.json" `
    "workflow/placeholder_schema.yaml" `
    "workflow/forbidden_patterns.txt" `
    "$S/qa_hard_report.json"

# 6. Hard Repair
echo "`n=== Phase 6: Repair Loop (Hard) ==="
.\scripts\docker_run.ps1 python -u scripts/repair_loop_v2.py `
    --input "$S/translated.csv" `
    --tasks "$S/qa_hard_report.json" `
    --output "$S/repaired_hard.csv" `
    --output-dir "$S/" `
    --qa-type hard

# 7. Soft QA
echo "`n=== Phase 7: Soft QA ==="
.\scripts\docker_run.ps1 python -u scripts/soft_qa_llm.py `
    --input "$S/repaired_hard.csv" `
    --out_tasks "$S/repair_tasks_soft.jsonl" `
    --model "$Model"

# 8. Soft Repair
echo "`n=== Phase 8: Repair Loop (Soft) ==="
.\scripts\docker_run.ps1 python -u scripts/repair_loop_v2.py `
    --input "$S/repaired_hard.csv" `
    --tasks "$S/repair_tasks_soft.jsonl" `
    --output "$S/final_content.csv" `
    --output-dir "$S/" `
    --qa-type soft

# 9. Export
echo "`n=== Phase 9: Export ==="
python scripts/rehydrate_export.py `
    "$S/final_content.csv" `
    "$S/placeholder_map.json" `
    "$S/final.csv"

# 10. Metrics
echo "`n=== Phase 10: Metrics ==="
python scripts/metrics_aggregator.py `
    --trace-path "$S/llm_trace.jsonl" `
    --output "$S/metrics_report.md"

echo "`n✅ 3k Test Script Finished"
