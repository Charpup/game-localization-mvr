#!/bin/bash
# Stress Test Phase 5-9 Helper
TEST_DIR="data/Test_Batch/09. Stress test"

echo "=========================================="
echo "5K-ROW 压力测试 - Phase 5: Hard QA"
echo "=========================================="
python3 scripts/qa_hard.py \
    "$TEST_DIR/s5k_translated.csv" \
    "$TEST_DIR/s5k_placeholder_map.json" \
    "$TEST_DIR/s5k_qa_hard_report.json"

echo "--- Hard QA Summary ---"
python3 -c "
import json
import os
path = '$TEST_DIR/s5k_qa_hard_report.json'
if os.path.exists(path):
    with open(path) as f:
        r = json.load(f)
    print(f'Total Errors: {r.get(\"total_errors\", 0)}')
    print(f'Status: {\"PASS\" if not r.get(\"has_errors\") else \"FAIL\"}')
else:
    print('Error: Report file missing')
"

echo "=========================================="
echo "5K-ROW 压力测试 - Phase 6: Soft QA"
echo "=========================================="
# Using Haiku for cost efficiency in stress test
python3 -u scripts/soft_qa_llm.py \
    "$TEST_DIR/s5k_translated.csv" \
    workflow/style_guide.md \
    "$TEST_DIR/s5k_glossary_compiled.yaml" \
    --out_report "$TEST_DIR/s5k_qa_soft_report.json" \
    --out_tasks "$TEST_DIR/s5k_repair_tasks.jsonl" \
    --model claude-haiku-4-5-20251001

echo "=========================================="
echo "5K-ROW 压力测试 - Phase 7: Export"
echo "=========================================="
python3 scripts/rehydrate_export.py \
    --input "$TEST_DIR/s5k_translated.csv" \
    --placeholder-map "$TEST_DIR/s5k_placeholder_map.json" \
    --output "$TEST_DIR/s5k_final_export.csv"

echo "=========================================="
echo "5K-ROW 压力测试 - Phase 8: Metrics"
echo "=========================================="
python3 scripts/metrics_aggregator.py \
    --reports-dir reports \
    --output "$TEST_DIR/s5k_metrics_report" \
    --json

echo "=========================================="
echo "5K-ROW 压力测试 - Phase 9: Final Report"
echo "=========================================="
# Final report generator
python3 -c "
import json
import os
from datetime import datetime

test_dir = '$TEST_DIR'
report = {
    'test_name': '5K-Row Stress Test',
    'timestamp': datetime.now().isoformat(),
    'environment': 'Docker gate_v2',
    'data_source': 'stress_test_5k-row.csv',
    'results': {},
    'performance': {},
    'go_nogo_40k': None
}

artifacts = {
    'normalization': 's5k_draft.csv',
    'glossary': 's5k_glossary_compiled.yaml',
    'translation': 's5k_translated.csv',
    'hard_qa': 's5k_qa_hard_report.json',
    'soft_qa': 's5k_qa_soft_report.json',
    'export': 's5k_final_export.csv'
}

for phase, artifact in artifacts.items():
    path = f'{test_dir}/{artifact}'
    report['results'][phase] = {
        'status': 'PASS' if os.path.exists(path) else 'FAIL',
        'artifact': artifact
    }

if os.path.exists(f'{test_dir}/s5k_qa_hard_report.json'):
    with open(f'{test_dir}/s5k_qa_hard_report.json') as f:
        hard = json.load(f)
    report['results']['hard_qa']['errors'] = hard.get('total_errors', 0)

if os.path.exists(f'{test_dir}/s5k_qa_soft_report.json'):
    with open(f'{test_dir}/s5k_qa_soft_report.json') as f:
        soft = json.load(f)
    s = soft.get('summary', {})
    report['results']['soft_qa']['major'] = s.get('major', 0)
    report['results']['soft_qa']['minor'] = s.get('minor', 0)
    report['results']['soft_qa']['rows'] = s.get('rows_processed', 0)

metrics_path = f'{test_dir}/s5k_metrics_report.json'
if os.path.exists(metrics_path):
    with open(metrics_path) as f:
        metrics = json.load(f)
    ms = metrics['summary']
    report['performance'] = {
        'total_latency_s': ms['total_latency_ms'] / 1000,
        'total_tokens': ms['total_tokens'],
        'estimated_cost_usd': ms['estimated_cost_usd'],
        'rows_per_second': 5000 / (ms['total_latency_ms'] / 1000) if ms['total_latency_ms'] > 0 else 0
    }
    scale = 8
    est_time = ms['total_latency_ms'] / 1000 * scale / 60
    est_cost = ms['estimated_cost_usd'] * scale
    report['estimate_40k'] = {
        'time_min': round(est_time, 1),
        'cost_usd': round(est_cost, 4),
        'tokens': ms['total_tokens'] * scale
    }
    if est_time < 120 and est_cost < 5:
        report['go_nogo_40k'] = 'GO'
    elif est_time < 180 and est_cost < 10:
        report['go_nogo_40k'] = 'CAUTION'
    else:
        report['go_nogo_40k'] = 'NO-GO'

with open(f'{test_dir}/s5k_final_validation_report.json', 'w') as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print('✅ Final Validation Report Generated')
"

echo "✅ Stress Test Phase 5-9 Complete"
