#!/usr/bin/env python3
"""
Phase 2: Long Text Gate V1
Tests all 5 models with Template A_v2 (long text stress test).
Implements 30s inter-model cooldown for rate limit protection.
"""
import os
import sys
import json
import time
import csv
import re
import hashlib
from datetime import datetime

sys.path.insert(0, '/workspace/scripts')
sys.path.insert(0, 'scripts')

try:
    from runtime_adapter import LLMClient
except ImportError:
    print("ERROR: runtime_adapter not found")
    sys.exit(1)

# ============ Configuration ============
GATE_NAME = "long_text_gate_v1"

MODELS = [
    "gpt-4.1-mini",
    "claude-haiku-4-5-20251001",
    "gpt-5.1",
    "gpt-5.2",
    "claude-sonnet-4-5-20250929"
]

TEMPLATE_FILE = "data/destructive_v1_template_A_v2.csv"
META_FILE = "data/destructive_v1_template_A_v2.meta.json"

BATCH_LADDER = [1, 2, 5, 10]
N_ITERATIONS = 3
TIMEOUT = 300  # 5 minutes
INTER_MODEL_COOLDOWN = 30  # seconds between models

REPORT_JSON = "reports/long_text_gate_v1_results.json"
REPORT_MD = "reports/long_text_gate_v1_summary.md"

SYSTEM_PROMPT = """You MUST return a JSON object with a single key 'items' containing an array of translated objects.
Each object must have 'string_id' and 'translated_ru' fields.
Preserve ALL placeholders exactly as they appear in the source.
Do NOT wrap your response in markdown code blocks."""

# ============ Helper Functions ============
def load_template():
    """Load template data."""
    rows = []
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows

def validate_meta():
    """Validate template metadata."""
    with open(META_FILE, "r", encoding="utf-8") as f:
        meta = json.load(f)
    
    with open(TEMPLATE_FILE, "rb") as f:
        actual_sha = hashlib.sha256(f.read()).hexdigest()
    
    if meta.get("sha256") != actual_sha:
        print(f"WARNING: SHA256 mismatch!")
        print(f"  Expected: {meta.get('sha256')}")
        print(f"  Actual: {actual_sha}")
    
    return meta

def sanitize_json(text):
    """Extract JSON from potentially wrapped response."""
    text = text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) >= 3:
            inner = parts[1].strip()
            if inner.startswith("json"):
                text = inner[4:].strip()
            else:
                text = inner
    return text

def extract_placeholders(text):
    """Extract placeholders from text."""
    patterns = [
        r'\{[^}]+\}',
        r'%[sd]',
        r'<[^>]+>',
        r'\[\[[^\]]+\]\]'
    ]
    found = set()
    for pattern in patterns:
        found.update(re.findall(pattern, str(text)))
    return found

def validate_response(response_text, expected_rows):
    """Validate LLM response structure and content."""
    try:
        text = sanitize_json(response_text)
        data = json.loads(text)
    except json.JSONDecodeError as e:
        return False, f"JSON parse error: {str(e)[:50]}"
    
    if "items" not in data:
        return False, "Missing 'items' key"
    
    items = data["items"]
    if len(items) != len(expected_rows):
        return False, f"Size mismatch: expected {len(expected_rows)}, got {len(items)}"
    
    # Check ID coverage
    expected_ids = {str(r["string_id"]) for r in expected_rows}
    returned_ids = {str(item.get("string_id", "")) for item in items}
    
    if expected_ids != returned_ids:
        missing = expected_ids - returned_ids
        extra = returned_ids - expected_ids
        return False, f"ID mismatch: missing={missing}, extra={extra}"
    
    return True, None

def test_batch(client, model, batch_rows, iteration):
    """Test a single batch translation."""
    payload = {"items": [{"string_id": r["string_id"], "source_zh": r["source_zh"]} for r in batch_rows]}
    user_prompt = json.dumps(payload, ensure_ascii=False)
    
    result = {
        "iteration": iteration,
        "batch_size": len(batch_rows),
        "status": "UNKNOWN",
        "latency_ms": 0,
        "error": None
    }
    
    try:
        t0 = time.time()
        response = client.chat(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            temperature=0,
            metadata={
                "step": "long_text_gate",
                "model_override": model,
                "force_llm": True,
                "allow_fallback": False,
                "retry": 0
            }
        )
        latency = int((time.time() - t0) * 1000)
        result["latency_ms"] = latency
        
        valid, error = validate_response(response.text, batch_rows)
        if valid:
            result["status"] = "PASS"
        else:
            result["status"] = "FAIL"
            result["error"] = error
            
    except Exception as e:
        result["status"] = "FAIL"
        result["error"] = f"{type(e).__name__}: {str(e)[:100]}"
    
    return result

def test_model(client, model, all_rows):
    """Test a single model across all batch sizes."""
    print(f"\n{'='*60}")
    print(f"Testing Model: {model}")
    print(f"{'='*60}")
    
    model_result = {
        "template_A_v2": {
            "results": {},
            "max_pass": 0
        }
    }
    
    for batch_size in BATCH_LADDER:
        print(f"\n  Batch Size: {batch_size}")
        
        batch_results = []
        all_passed = True
        
        # Calculate max iterations without overlapping
        max_iters = min(N_ITERATIONS, len(all_rows) // batch_size)
        
        for i in range(max_iters):
            start_idx = i * batch_size
            end_idx = start_idx + batch_size
            batch_rows = all_rows[start_idx:end_idx]
            
            result = test_batch(client, model, batch_rows, i + 1)
            batch_results.append(result)
            
            status = result["status"]
            latency = result["latency_ms"]
            print(f"    Iteration {i+1}: {status} ({latency}ms)")
            
            if result["error"]:
                print(f"      Error: {result['error']}")
            
            if status != "PASS":
                all_passed = False
                break
            
            # Small delay between iterations
            time.sleep(2)
        
        # Aggregate results for this batch size
        latencies = [r["latency_ms"] for r in batch_results if r["status"] == "PASS"]
        
        if all_passed and len(latencies) == max_iters:
            model_result["template_A_v2"]["results"][str(batch_size)] = {
                "status": "PASS",
                "iterations": max_iters,
                "avg_latency_ms": int(sum(latencies) / len(latencies)) if latencies else 0,
                "max_latency_ms": max(latencies) if latencies else 0
            }
            model_result["template_A_v2"]["max_pass"] = batch_size
            print(f"    => PASS (avg: {model_result['template_A_v2']['results'][str(batch_size)]['avg_latency_ms']}ms)")
        else:
            error_msg = batch_results[-1].get("error", "Unknown error") if batch_results else "No iterations"
            model_result["template_A_v2"]["results"][str(batch_size)] = {
                "status": "FAIL",
                "iterations_attempted": len(batch_results),
                "reason": error_msg
            }
            print(f"    => FAIL: Stopping batch escalation")
            break
    
    model_result["max_batch_size_long_text"] = model_result["template_A_v2"]["max_pass"]
    return model_result

def generate_summary_md(results):
    """Generate markdown summary."""
    lines = [
        f"# Long Text Gate V1 Summary",
        f"",
        f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"| Model | Max Long Text Batch | Ladder (1/2/5/10) | Status |",
        f"|-------|---------------------|-------------------|--------|"
    ]
    
    for model in MODELS:
        if model not in results["models"]:
            continue
        
        model_data = results["models"][model]
        max_batch = model_data.get("max_batch_size_long_text", 0)
        
        # Build ladder string
        ladder_parts = []
        for bs in BATCH_LADDER:
            bs_result = model_data["template_A_v2"]["results"].get(str(bs), {})
            if bs_result.get("status") == "PASS":
                ladder_parts.append("✅")
            elif bs_result.get("status") == "FAIL":
                ladder_parts.append("❌")
            else:
                ladder_parts.append("⏭️")
        ladder_str = "/".join(ladder_parts)
        
        status = "PASS" if max_batch > 0 else "FAIL"
        
        lines.append(f"| {model} | **{max_batch}** | {ladder_str} | {status} |")
    
    return "\n".join(lines)

def main():
    print(f"{'='*60}")
    print(f"Phase 2: {GATE_NAME}")
    print(f"{'='*60}")
    
    # Validate environment
    if not os.path.exists(TEMPLATE_FILE):
        print(f"ERROR: {TEMPLATE_FILE} not found")
        sys.exit(1)
    
    if not os.path.exists(META_FILE):
        print(f"ERROR: {META_FILE} not found")
        sys.exit(1)
    
    meta = validate_meta()
    print(f"Template: {meta.get('template_type')}, Rows: {meta.get('total_rows')}")
    
    all_rows = load_template()
    print(f"Loaded {len(all_rows)} rows")
    
    client = LLMClient()
    
    results = {
        "gate": GATE_NAME,
        "timestamp": datetime.now().isoformat(),
        "template_meta": meta,
        "models": {}
    }
    
    for i, model in enumerate(MODELS):
        if i > 0:
            print(f"\n[COOLDOWN] Waiting {INTER_MODEL_COOLDOWN}s before next model...")
            time.sleep(INTER_MODEL_COOLDOWN)
        
        results["models"][model] = test_model(client, model, all_rows)
    
    # Save JSON report
    os.makedirs("reports", exist_ok=True)
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved results to {REPORT_JSON}")
    
    # Save MD summary
    md_content = generate_summary_md(results)
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"Saved summary to {REPORT_MD}")
    
    # Print summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for model in MODELS:
        max_batch = results["models"][model].get("max_batch_size_long_text", 0)
        print(f"  {model}: max_batch_size_long_text = {max_batch}")

if __name__ == "__main__":
    main()
