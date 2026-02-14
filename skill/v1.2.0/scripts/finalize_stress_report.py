import json
import os
from datetime import datetime

TEST_DIR = "data/Test_Batch/09. Stress test"

def main():
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

    # 1. Check Output Artifacts
    for phase, artifact in artifacts.items():
        path = os.path.join(TEST_DIR, artifact)
        exists = os.path.exists(path)
        report['results'][phase] = {
            'status': 'PASS' if exists else 'FAIL',
            'artifact': artifact
        }
        if not exists:
            print(f"❌ Missing artifact: {path}")

    # 2. Add QA Details
    hard_qa_path = os.path.join(TEST_DIR, 's5k_qa_hard_report.json')
    if os.path.exists(hard_qa_path):
        with open(hard_qa_path, 'r', encoding='utf-8') as f:
            hard = json.load(f)
        report['results']['hard_qa']['errors'] = hard.get('total_errors', 0)

    soft_qa_path = os.path.join(TEST_DIR, 's5k_qa_soft_report.json')
    if os.path.exists(soft_qa_path):
        with open(soft_qa_path, 'r', encoding='utf-8') as f:
            soft = json.load(f)
        s = soft.get('summary', {})
        report['results']['soft_qa']['major'] = s.get('major', 0)
        report['results']['soft_qa']['minor'] = s.get('minor', 0)
        report['results']['soft_qa']['rows'] = s.get('rows_processed', 0)

    # 3. Add Performance Metrics & 40k Estimate
    metrics_path = os.path.join(TEST_DIR, 's5k_metrics_report.json')
    if os.path.exists(metrics_path):
        with open(metrics_path, 'r', encoding='utf-8') as f:
            metrics = json.load(f)
        
        ms = metrics.get('summary', {})
        total_latency_ms = ms.get('total_latency_ms', 0)
        total_tokens = ms.get('total_tokens', 0)
        cost_usd = ms.get('estimated_cost_usd', 0)
        
        report['performance'] = {
            'total_latency_s': total_latency_ms / 1000,
            'total_tokens': total_tokens,
            'estimated_cost_usd': cost_usd,
            'rows_per_second': 5000 / (total_latency_ms / 1000) if total_latency_ms > 0 else 0
        }

        # Extrapolation to 40k
        # Assuming linear scaling (8x of 5k)
        scale = 8.0 
        est_time_s = (total_latency_ms / 1000) * scale
        est_cost = cost_usd * scale
        
        report['estimate_40k'] = {
            'time_min': round(est_time_s / 60, 1),
            'cost_usd': round(est_cost, 4),
            'tokens': int(total_tokens * scale)
        }

        # Validation Logic
        # Targets: < 2 hours (120 min), < $5 USD
        if round(est_time_s / 60) < 120 and est_cost < 5.0:
            report['go_nogo_40k'] = 'GO'
        elif round(est_time_s / 60) < 180 and est_cost < 10.0:
            report['go_nogo_40k'] = 'CAUTION'
        else:
            report['go_nogo_40k'] = 'NO-GO'
            
    # 4. Save Report
    out_path = os.path.join(TEST_DIR, 's5k_final_validation_report.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
        
    print(f"✅ Report generated: {out_path}")
    print(f"   40k Forecast: {report.get('go_nogo_40k', 'UNKNOWN')}")
    if report.get('estimate_40k'):
        est = report['estimate_40k']
        print(f"   Time: ~{est['time_min']} min, Cost: ~${est['cost_usd']}")

if __name__ == "__main__":
    main()
