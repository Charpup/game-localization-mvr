#!/usr/bin/env python3
"""
Focused diagnostic for claude-sonnet-4-5-20250929 after network optimization.
Runs all 3 diagnostic steps for this single model.
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

TARGET_MODEL = "claude-sonnet-4-5-20250929"
TEMPLATE_FILE = "data/destructive_v1_template_B.csv"
SYSTEM_PROMPT = "You MUST return a JSON object with a single key 'items' containing an array of translated objects. Keep string_id and preserve placeholders. No markdown blocks."

def load_batch(size):
    rows = []
    with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if i >= size: break
            rows.append(row)
    return rows

def sanitize_json(text):
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

def step1_direct_api(client):
    """Step 1: Simple single call."""
    print("\n[STEP 1] Direct API Test...")
    try:
        t0 = time.time()
        response = client.chat(
            system="You are a test assistant.",
            user="Reply with exactly one word: Hello",
            temperature=0,
            metadata={"step": "diagnose_sonnet_step1", "model_override": TARGET_MODEL, "force_llm": True, "allow_fallback": False, "retry": 0}
        )
        latency = int((time.time() - t0) * 1000)
        print(f"  -> PASS ({latency}ms) - Response: {response.text[:30]}")
        return {"status": "PASS", "latency_ms": latency, "response": response.text[:50]}
    except Exception as e:
        print(f"  -> FAIL: {e}")
        return {"status": "FAIL", "error": str(e)[:150]}

def step2_single_call(client):
    """Step 2: Single item translation."""
    print("\n[STEP 2] Single Call Test (batch=1)...")
    payload = {"items": [{"string_id": "test_001", "source_zh": "你好，这是一个测试。"}]}
    try:
        t0 = time.time()
        response = client.chat(
            system=SYSTEM_PROMPT,
            user=json.dumps(payload, ensure_ascii=False),
            temperature=0,
            metadata={"step": "diagnose_sonnet_step2", "model_override": TARGET_MODEL, "force_llm": True, "allow_fallback": False, "retry": 0}
        )
        latency = int((time.time() - t0) * 1000)
        data = json.loads(sanitize_json(response.text))
        if "items" in data and len(data["items"]) == 1:
            print(f"  -> PASS ({latency}ms)")
            return {"status": "PASS", "latency_ms": latency}
        else:
            print(f"  -> FAIL: Invalid structure")
            return {"status": "FAIL", "error": "Invalid JSON structure"}
    except Exception as e:
        print(f"  -> FAIL: {e}")
        return {"status": "FAIL", "error": str(e)[:150]}

def step3_batch_test(client):
    """Step 3: Batch size 10 test."""
    print("\n[STEP 3] Batch Test (batch=10)...")
    batch_items = load_batch(10)
    payload = {"items": batch_items}
    try:
        t0 = time.time()
        response = client.chat(
            system=SYSTEM_PROMPT,
            user=json.dumps(payload, ensure_ascii=False),
            temperature=0,
            metadata={"step": "diagnose_sonnet_step3", "model_override": TARGET_MODEL, "force_llm": True, "allow_fallback": False, "retry": 0}
        )
        latency = int((time.time() - t0) * 1000)
        data = json.loads(sanitize_json(response.text))
        if "items" in data and len(data["items"]) == 10:
            print(f"  -> PASS ({latency}ms) - Items returned: 10")
            return {"status": "PASS", "latency_ms": latency, "items_returned": 10}
        else:
            print(f"  -> FAIL: Size mismatch")
            return {"status": "FAIL", "error": f"Size mismatch: got {len(data.get('items', []))}"}
    except Exception as e:
        print(f"  -> FAIL: {e}")
        return {"status": "FAIL", "error": str(e)[:150]}

def main():
    print("=" * 60)
    print(f"Focused Diagnostic for {TARGET_MODEL}")
    print("=" * 60)
    
    client = LLMClient()
    results = {}
    
    results["step1_direct_api"] = step1_direct_api(client)
    time.sleep(5)
    
    results["step2_single_call"] = step2_single_call(client)
    time.sleep(5)
    
    results["step3_batch_10"] = step3_batch_test(client)
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results.values() if r["status"] == "PASS")
    print(f"Passed: {passed}/3")
    
    overall = "PASS" if passed == 3 else "FAIL"
    print(f"Overall: {overall}")
    
    output = {
        "model": TARGET_MODEL,
        "timestamp": datetime.now().isoformat(),
        "overall": overall,
        "results": results
    }
    
    os.makedirs("reports", exist_ok=True)
    with open("reports/diagnosis_sonnet_retest.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print("\nResults saved to reports/diagnosis_sonnet_retest.json")

if __name__ == "__main__":
    main()
