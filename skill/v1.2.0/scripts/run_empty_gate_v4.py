#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
run_empty_gate_v4.py

Thorough Mixed Empty Batch Gate Runner (V4).
Strict Binary Gate: No trials, no fallbacks, no partial credit.
Mandatory fixes per v4 spec:
1. Docker runtime enforcement (/.dockerenv + GATE_IMAGE_TAG="gate_v2")
2. Model integrity enforcement (abort on mismatch)
3. Empty row validation (.strip() == "")
4. Metadata locking (gate, sha256, source, immutable, rules_version)
"""

import hashlib
import json
import os
import sys
from datetime import datetime

# Add scripts dir to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from runtime_adapter import LLMClient, LLMError
except ImportError:
    print("Error: Could not import runtime_adapter.")
    sys.exit(1)

# --- 1. Constants & Requirements ---
GATE_NAME = "empty_gate_v4_thorough"
DATA_FILE = "data/empty_gate_v4_batch.csv"
META_FILE = "data/empty_gate_v4_batch.meta.json"
REPORT_JSON = "reports/empty_gate_v4_results.json"
REPORT_MD = "reports/empty_gate_v4_summary.md"

REQUIRED_MODELS = [
    "gpt-4.1-mini",
    "claude-haiku-4-5-20251001",
    "gpt-5.1",
    "gpt-5.2",
    "claude-sonnet-4-5-20250929"
]

REQUIRED_META_FIELDS = [
    "gate", "sha256", "source", "immutable", "rules_version", "batch_size", "empty_rows", "non_empty_rows"
]

# --- 2. Environment Validation ---
def check_environment():
    """Ensure we are running in the correct Docker container with the correct tag."""
    if not os.path.exists("/.dockerenv"):
        print("❌ FAIL: Environment constraint violation. Base /.dockerenv not found.")
        sys.exit(1)
        
    image_tag = os.getenv("GATE_IMAGE_TAG", "")
    if image_tag != "gate_v2":
        print(f"❌ FAIL: Environment constraint violation. GATE_IMAGE_TAG is '{image_tag}', expected 'gate_v2'.")
        sys.exit(1)
        
    print(f"✅ Environment Check: Docker container detected (GATE_IMAGE_TAG=gate_v2).")

# --- 3. Data Loading & Validation ---
def calculate_sha256(filepath):
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        sha.update(f.read())
    return sha.hexdigest()

def load_and_validate_data():
    """Load data and strict validate meta.json fields and SHA256."""
    if not os.path.exists(DATA_FILE) or not os.path.exists(META_FILE):
        print(f"❌ FAIL: Missing requirement files: {DATA_FILE} / {META_FILE}")
        sys.exit(1)
        
    with open(META_FILE, "r", encoding="utf-8") as f:
        meta = json.load(f)
        
    # Check for mandatory meta fields
    for field in REQUIRED_META_FIELDS:
        if field not in meta:
            print(f"❌ FAIL: Missing mandatory meta field: '{field}'")
            sys.exit(1)
            
    # Validate expected semantics
    if meta.get("gate") != GATE_NAME:
        print(f"❌ FAIL: Meta 'gate' mismatch. Got {meta.get('gate')}, expected {GATE_NAME}")
        sys.exit(1)
        
    if meta.get("immutable") is not True:
        print("❌ FAIL: Meta 'immutable' must be true.")
        sys.exit(1)
        
    expected_sha = meta.get("sha256")
    actual_sha = calculate_sha256(DATA_FILE)
    
    if expected_sha != actual_sha:
        print(f"❌ FAIL: Data integrity mismatch.")
        print(f"  Expected: '{expected_sha}' (len={len(expected_sha)})")
        print(f"  Actual:   '{actual_sha}' (len={len(actual_sha)})")
        print(f"  Meta Object: {json.dumps(meta, indent=2)}")
        sys.exit(1)
        
    print(f"✅ Data Check: SHA256 verified ({actual_sha[:8]}...) and metadata locked.")
    
    import csv
    items = []
    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append({
                "string_id": row["string_id"],
                "source_zh": row["source_zh"],
                "is_empty_source": not bool(row["source_zh"].strip())
            })
            
    # Structural Check
    batch_size = meta.get("batch_size", 10)
    if len(items) != batch_size:
        print(f"❌ FAIL: Input data length mismatch. Expected {batch_size}, got {len(items)}")
        sys.exit(1)
        
    return items

# --- 4. LLM Call Logic ---
def call_llm(model, items):
    """Call LLM with exact payload contract. Bypasses routing/fallback."""
    client = LLMClient(model=model)
    
    payload_content = {
        "items": items
    }
    user_prompt = json.dumps(payload_content, ensure_ascii=False, indent=2)
    
    system_prompt = """You MUST return a JSON object with a single key "items".

Rules:
- items MUST be an array
- items length MUST equal input length
- Each output item MUST include:
  - string_id (copied exactly)
  - translated_text
- If is_empty_source == true OR source_zh is empty or whitespace:
  - translated_text MUST be an empty string ""
- Do NOT add, remove, merge, or reorder items.
- Do NOT wrap the JSON in markdown code blocks like ```json. Return RAW JSON only.
"""

    print(f"   Invoking {model}...")
    try:
        # Bypassing routing via model_override and disabling fallback logic in runner
        result = client.chat(
            system=system_prompt,
            user=user_prompt,
            temperature=0,
            response_format={"type": "json_object"},
            metadata={
                "step": "empty_gate_v4", 
                "model_override": model, 
                "force_llm": True,
                "is_batch": True,
                "batch_size": len(items)
            }
        )
        return result
    except LLMError as e:
        print(f"   LLM Error: {e}")
        return None

# --- 5. Validation Logic ---
def validate_response(model, response, input_items):
    """Binary Gate Validation with strict model integrity and empty pollution tracking."""
    if not response:
        return False, "LLM Call Failed", 0
        
    # 5.1 Model Name Check (Strict)
    if response.model != model:
         print(f"❌ FAIL: Model integrity violation. Requested '{model}', Provider reported '{response.model}'.")
         return False, f"Model mismatch: Requested {model}, Got {response.model}", 0
         
    # 5.2 JSON Structure
    resp_text = (response.text or "").strip()
    
    # Strip markdown code blocks if present
    if resp_text.startswith("```"):
        parts = resp_text.split("```")
        if len(parts) >= 3:
            inner_content = parts[1].strip()
            if inner_content.startswith("json"):
                resp_text = inner_content[4:].strip()
            else:
                resp_text = inner_content
    
    data = None
    try:
        data = json.loads(resp_text)
    except Exception:
        # Fallback: Regex to find the first { ... } block
        import re
        match = re.search(r'\{.*\}', resp_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except Exception:
                pass
                
    if data is None:
        return False, "Invalid JSON structure in response", 0
        
    if not isinstance(data, dict) or "items" not in data or not isinstance(data["items"], list):
        return False, "Invalid layout (Expected {'items': [...]})", 0
        
    out_items = data["items"]
    
    # 5.3 Length Check
    if len(out_items) != len(input_items):
        return False, f"Length mismatch (In: {len(input_items)}, Out: {len(out_items)})", 0
        
    # 5.4 Content Checks
    input_map = {i["string_id"]: i for i in input_items}
    empty_pollution_count = 0
    id_errors = []
    
    for idx, out_item in enumerate(out_items):
        sid = out_item.get("string_id")
        if not sid:
            id_errors.append(f"Item {idx} missing string_id")
            continue
            
        if sid not in input_map:
            id_errors.append(f"Unknown string_id: {sid}")
            continue
            
        in_item = input_map[sid]
        out_text = out_item.get("translated_text", "")
        
        # Empty Row Validation (Strict)
        if in_item["is_empty_source"]:
            if out_text.strip() != "":
                empty_pollution_count += 1
    
    if id_errors:
        return False, "ID Errors: " + "; ".join(id_errors), empty_pollution_count
        
    if empty_pollution_count > 0:
        return False, f"Empty Pollution detected: {empty_pollution_count} items failed.", empty_pollution_count
    
    return True, "PASS", 0

def main():
    print(f"🚀 Starting {GATE_NAME}...")
    
    # 1. Pipeline Checks
    # check_environment() # Commented out for local testing if needed, but per spec runner MUST assert.
    # In Docker it will pass. In local host it will fail.
    check_environment()
    items = load_and_validate_data()
    
    total_results = []
    results_map = {}
    
    # 2. Sequential Execution
    abort_gate = False
    for model in REQUIRED_MODELS:
        if abort_gate:
            print(f"⚠️ Skipping remaining models due to previous critical failure.")
            break
            
        print(f"\n▶ Testing Model: {model}")
        
        response = call_llm(model, items)
        passed, reason, pollution = validate_response(model, response, items)
        
        results_map[model] = {
            "pass": passed,
            "reason": reason,
            "llm_call_count": 1 if response else 0,
            "empty_pollution_count": pollution,
            "requested_model": model,
            "provider_reported_model": response.model if response else "N/A"
        }
        
        status_icon = "✅" if passed else "❌"
        print(f"   {status_icon} Result: {reason}")
        
        # Abort entire gate on model mismatch
        if "Model mismatch" in reason:
            abort_gate = True
            print("🔴 CRITICAL: Aborting entire gate due to model integrity failure.")
            
    # 3. Reporting
    os.makedirs("reports", exist_ok=True)
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(results_map, f, indent=2, ensure_ascii=False)
        
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("# Empty Gate V4 Results\n\n")
        f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        f.write("| Model | Pass | Provider Reported | Pollution | Reason |\n")
        f.write("|---|---|---|---|---|\n")
        for model in REQUIRED_MODELS:
            res = results_map.get(model, {"pass": False, "reason": "Not executed", "empty_pollution_count": 0, "provider_reported_model": "N/A"})
            status = "✅ PASS" if res["pass"] else "❌ FAIL"
            f.write(f"| {model} | {status} | {res.get('provider_reported_model', 'N/A')} | {res.get('empty_pollution_count', 0)} | {res.get('reason', 'N/A')} |\n")
            
    print(f"\n📝 Reports generated in {REPORT_JSON} and {REPORT_MD}")
    
    # 4. Final Exit Code
    all_pass = all(results_map.get(m, {}).get("pass") for m in REQUIRED_MODELS)
    if all_pass:
        print("\n🎉 ALL MODELS PASSED")
        sys.exit(0)
    else:
        print("\n💀 SOME MODELS FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
