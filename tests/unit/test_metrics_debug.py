import json
import os
import sys
import subprocess

def run_test():
    reports_dir = "reports_test"
    os.makedirs(reports_dir, exist_ok=True)
    
    # Generate test JSONL
    events = [
        {"timestamp": "2026-01-24T06:00:00", "step": "test", "event": "step_start", "total_rows": 10, "batch_size": 5, "model": "gpt-4.1-mini"},
        {"timestamp": "2026-01-24T06:00:05", "step": "test", "event": "batch_complete", "batch_index": 1, "total_batches": 2, "batch_size": 5, "latency_ms": 1000, "status": "SUCCESS"},
        {"timestamp": "2026-01-24T06:00:10", "step": "test", "event": "batch_complete", "batch_index": 2, "total_batches": 2, "batch_size": 5, "latency_ms": 1100, "status": "SUCCESS"},
        {"timestamp": "2026-01-24T06:00:15", "step": "test", "event": "step_complete", "success_count": 10, "failed_count": 0}
    ]
    
    jsonl_path = os.path.join(reports_dir, "test_progress.jsonl")
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
            
    print(f"✅ Generated test logs: {jsonl_path}")
    
    # Run metrics_aggregator.py
    output_md = os.path.join(reports_dir, "metrics_report.md")
    cmd = [
        sys.executable, "scripts/metrics_aggregator.py",
        "--reports-dir", reports_dir,
        "--output", output_md,
        "--json"
    ]
    
    print(f"🚀 Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Metrics aggregation failed:\n{result.stderr}")
        return
        
    print(f"✅ Aggregation output:\n{result.stdout}")
    
    # Verify outputs
    output_json = output_md.replace(".md", ".json")
    if os.path.exists(output_md) and os.path.exists(output_json):
        print(f"✅ Reports found at {output_md}")
        with open(output_md, "r", encoding="utf-8") as f:
            print("\n=== Markdown Report Content ===\n")
            print(f.read())
    else:
        print(f"❌ Reports NOT found: {output_md} or {output_json}")

if __name__ == "__main__":
    run_test()
