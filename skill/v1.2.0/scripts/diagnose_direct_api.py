#!/usr/bin/env python3
"""
Step 1: Direct API Test (using runtime_adapter)
Tests if models are accessible at the Provider level with minimal call.
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
SIMPLE_PROMPT = "Reply with exactly one word: Hello"

def test_model_direct(client, model_name):
    """Direct API call to a single model with minimal payload."""
    result = {
        "status": "UNKNOWN",
        "latency_ms": 0,
        "error": None,
        "response_preview": None
    }
    
    try:
        t0 = time.time()
        response = client.chat(
            system="You are a test assistant.",
            user=SIMPLE_PROMPT,
            temperature=0,
            metadata={
                "step": "diagnose_direct_api",
                "model_override": model_name,
                "force_llm": True,
                "allow_fallback": False,
                "retry": 0
            }
        )
        latency = int((time.time() - t0) * 1000)
        
        result["status"] = "PASS"
        result["latency_ms"] = latency
        result["response_preview"] = response.text[:50] if response.text else "NO_CONTENT"
        result["provider_model"] = response.model
        
    except Exception as e:
        result["status"] = "FAIL"
        result["error"] = f"{type(e).__name__}: {str(e)[:150]}"
    
    return result

def main():
    print("=" * 60)
    print("STEP 1: Direct API Test (Single Call, No Batch)")
    print("=" * 60)
    
    client = LLMClient()
    results = {}
    
    # Test control model first
    print(f"\n[CONTROL] Testing {CONTROL_MODEL}...")
    results[CONTROL_MODEL] = test_model_direct(client, CONTROL_MODEL)
    status = results[CONTROL_MODEL]['status']
    latency = results[CONTROL_MODEL].get('latency_ms', 0)
    print(f"  -> {status} ({latency}ms)")
    if results[CONTROL_MODEL]["error"]:
        print(f"  -> Error: {results[CONTROL_MODEL]['error']}")
    
    # Test failed models with 5s delay between each
    for model in FAILED_MODELS:
        print(f"\n[TEST] Testing {model}...")
        time.sleep(5)  # Rate limit protection
        results[model] = test_model_direct(client, model)
        status = results[model]['status']
        latency = results[model].get('latency_ms', 0)
        print(f"  -> {status} ({latency}ms)")
        if results[model]["error"]:
            print(f"  -> Error: {results[model]['error']}")
    
    # Output summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for r in results.values() if r["status"] == "PASS")
    print(f"Passed: {passed}/{len(results)}")
    
    # Save results
    output = {
        "step": "direct_api",
        "timestamp": datetime.now().isoformat(),
        "results": results
    }
    
    os.makedirs("reports", exist_ok=True)
    with open("reports/diagnosis_step1_direct_api.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)
    
    print("\nResults saved to reports/diagnosis_step1_direct_api.json")

if __name__ == "__main__":
    main()
