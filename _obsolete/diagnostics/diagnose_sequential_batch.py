#!/usr/bin/env python3
"""
Step 3: Sequential Batch Test (batch_size=10, 30s interval)
Tests if rate limiting or concurrent load is causing failures.
"""
import os
import sys
import json
import time
import csv
from datetime import datetime

sys.path.insert(0, '/workspace/scripts')
sys.path.insert(0, 'scripts')

try:
    from runtime_adapter import LLMClient
except ImportError:
    print("ERROR: runtime_adapter not found")
    sys.exit(1)

FAILED_MODELS = [
    "claude-haiku-4-5-20251001",
    "gpt-5.1",
    "gpt-5.2",
    "claude-sonnet-4-5-20250929"
]
CONTROL_MODEL = "gpt-4.1-mini"
BATCH_SIZE = 10
INTER_MODEL_DELAY = 30  # seconds

TEMPLATE_FILE = "data/destructive_v1_template_B.csv"
SYSTEM_PROMPT = "You MUST return a JSON object with a single key 'items' containing an array of translated objects. Keep string_id and preserve placeholders. No markdown blocks."

def load_batch():
    """Load first BATCH_SIZE rows from template B."""
    rows = []
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= BATCH_SIZE:
                break
            rows.append(row)
    return rows

def test_batch(client, model_name, batch_items):
    """Test batch translation."""
    result = {
        "status": "UNKNOWN",
        "latency_ms": 0,
        "error": None,
        "response_valid": False
    }
    
    payload = {"items": batch_items}
    user_prompt = json.dumps(payload, ensure_ascii=False)
    
    try:
        t0 = time.time()
        response = client.chat(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            temperature=0,
            metadata={
                "step": "diagnose_sequential_batch",
                "model_override": model_name,
                "force_llm": True,
                "allow_fallback": False,
                "retry": 0
            }
        )
        latency = int((time.time() - t0) * 1000)
        
        result["latency_ms"] = latency
        result["provider_model"] = response.model
        
        # Validate response
        try:
            # Try to extract JSON from markdown if present
            text = response.text.strip()
            if text.startswith("```"):
                parts = text.split("```")
                if len(parts) >= 3:
                    inner = parts[1].strip()
                    if inner.startswith("json"):
                        text = inner[4:].strip()
                    else:
                        text = inner
            
            data = json.loads(text)
            if "items" in data and len(data["items"]) == len(batch_items):
                result["status"] = "PASS"
                result["response_valid"] = True
                result["items_returned"] = len(data["items"])
            else:
                result["status"] = "FAIL"
                result["error"] = f"Size mismatch: expected {len(batch_items)}, got {len(data.get('items', []))}"
        except json.JSONDecodeError as e:
            result["status"] = "FAIL"
            result["error"] = f"JSON parse failure: {str(e)[:50]}"
            result["response_preview"] = response.text[:100] if response.text else "EMPTY"
            
    except Exception as e:
        result["status"] = "FAIL"
        result["error"] = f"{type(e).__name__}: {str(e)[:150]}"
    
    return result

def main():
    print("=" * 60)
    print("STEP 3: Sequential Batch Test (batch_size=10, 30s interval)")
    print("=" * 60)
    
    if not os.path.exists(TEMPLATE_FILE):
        print(f"ERROR: {TEMPLATE_FILE} not found")
        sys.exit(1)
    
    batch_items = load_batch()
    print(f"Loaded {len(batch_items)} items from {TEMPLATE_FILE}")
    
    client = LLMClient()
    results = {}
    
    # Test control model first
    print(f"\n[CONTROL] Testing {CONTROL_MODEL} (batch_size={BATCH_SIZE})...")
    results[CONTROL_MODEL] = test_batch(client, CONTROL_MODEL, batch_items)
    print(f"  -> {results[CONTROL_MODEL]['status']} ({results[CONTROL_MODEL].get('latency_ms', 0)}ms)")
    if results[CONTROL_MODEL]["error"]:
        print(f"  -> Error: {results[CONTROL_MODEL]['error']}")
    
    # Test failed models with 30s delay
    for model in FAILED_MODELS:
        print(f"\n[WAITING] 30s delay before testing {model}...")
        time.sleep(INTER_MODEL_DELAY)
        print(f"[TEST] Testing {model} (batch_size={BATCH_SIZE})...")
        results[model] = test_batch(client, model, batch_items)
        print(f"  -> {results[model]['status']} ({results[model].get('latency_ms', 0)}ms)")
        if results[model]["error"]:
            print(f"  -> Error: {results[model]['error']}")
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results.values() if r["status"] == "PASS")
    print(f"Passed: {passed}/{len(results)}")
    
    # Save results
    output = {
        "step": "sequential_batch",
        "batch_size": BATCH_SIZE,
        "inter_model_delay_s": INTER_MODEL_DELAY,
        "timestamp": datetime.now().isoformat(),
        "results": results
    }
    
    os.makedirs("reports", exist_ok=True)
    with open("reports/diagnosis_step3_sequential_batch.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print("\nResults saved to reports/diagnosis_step3_sequential_batch.json")

if __name__ == "__main__":
    main()
