#!/usr/bin/env python3
"""
Step 2: Single Call Test (batch_size=1)
Tests LLM Router with a realistic translation task but minimal batch size.
"""
import os
import sys
import json
import time
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

# Realistic single-item batch (from Template B)
SAMPLE_ITEM = {
    "string_id": "test_diag_001",
    "source_zh": "你好，这是一个测试。请帮我翻译成俄语。"
}

SYSTEM_PROMPT = "You MUST return a JSON object with a single key 'items' containing an array of translated objects. Keep string_id and preserve placeholders. No markdown blocks."

def test_single_batch(client, model_name):
    """Test single item batch translation."""
    result = {
        "status": "UNKNOWN",
        "latency_ms": 0,
        "error": None,
        "response_valid": False
    }
    
    payload = {"items": [SAMPLE_ITEM]}
    user_prompt = json.dumps(payload, ensure_ascii=False)
    
    try:
        t0 = time.time()
        response = client.chat(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            temperature=0,
            metadata={
                "step": "diagnose_single_call",
                "model_override": model_name,
                "force_llm": True,
                "allow_fallback": False,
                "retry": 0
            }
        )
        latency = int((time.time() - t0) * 1000)
        
        result["latency_ms"] = latency
        result["provider_model"] = response.model
        
        # Validate response structure
        try:
            data = json.loads(response.text)
            if "items" in data and len(data["items"]) == 1:
                result["status"] = "PASS"
                result["response_valid"] = True
            else:
                result["status"] = "FAIL"
                result["error"] = "Invalid JSON structure"
        except json.JSONDecodeError:
            result["status"] = "FAIL"
            result["error"] = "JSON parse failure"
            
    except Exception as e:
        result["status"] = "FAIL"
        result["error"] = f"{type(e).__name__}: {str(e)[:150]}"
    
    return result

def main():
    print("=" * 60)
    print("STEP 2: Single Call Test (batch_size=1, Translation Task)")
    print("=" * 60)
    
    client = LLMClient()
    results = {}
    
    # Test control model first
    print(f"\n[CONTROL] Testing {CONTROL_MODEL}...")
    results[CONTROL_MODEL] = test_single_batch(client, CONTROL_MODEL)
    print(f"  -> {results[CONTROL_MODEL]['status']} ({results[CONTROL_MODEL].get('latency_ms', 0)}ms)")
    if results[CONTROL_MODEL]["error"]:
        print(f"  -> Error: {results[CONTROL_MODEL]['error']}")
    
    # Test failed models with 5s delay
    for model in FAILED_MODELS:
        print(f"\n[TEST] Testing {model}...")
        time.sleep(5)
        results[model] = test_single_batch(client, model)
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
        "step": "single_call",
        "timestamp": datetime.now().isoformat(),
        "results": results
    }
    
    os.makedirs("reports", exist_ok=True)
    with open("reports/diagnosis_step2_single_call.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print("\nResults saved to reports/diagnosis_step2_single_call.json")

if __name__ == "__main__":
    main()
