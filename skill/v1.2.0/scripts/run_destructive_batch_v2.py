import os
import sys
import json
import csv
import time
import hashlib
import re
from datetime import datetime
from statistics import mean, median

# Local imports
try:
    from runtime_adapter import LLMClient, LLMError
except ImportError:
    print("❌ FAIL: Cannot import runtime_adapter. Ensure path is correct.")
    sys.exit(1)

# --- 1. Constants & Requirements ---
GATE_NAME = "destructive_batch_v2"
POOL_FILE = "data/normalized_pool_v1.csv"
TEMPLATES = ["B", "C"]
REQUIRED_MODELS = [
    "claude-haiku-4-5-20251001",
    "gpt-5.1",
    "gpt-5.2",
    "claude-sonnet-4-5-20250929"
]
BATCH_SIZES = [10, 15, 20]
ITERATIONS_PER_CONFIG = 5  # N=5
REPORT_JSON = "reports/destructive_batch_v2_results.json"
REPORT_MD = "reports/destructive_batch_v2_summary.md"

PLACEHOLDER_PATTERNS = [
    r"\{\d+\}", r"\{[a-zA-Z_][a-zA-Z0-9_]*\}",
    r"%s", r"%d", r"\$\{[^\}]+\}",
    r"\{\{[^\}]+\}\}", r"<[^>]+>", r"\[[^\]]+\]",
    r"【[^】]+】"
]

# --- 2. Environment & Meta Validation ---
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

def calculate_sha256(filepath):
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()

def validate_assets():
    """Verify all template CSVs against their meta.json."""
    for t in TEMPLATES:
        csv_path = f"data/destructive_v1_template_{t}.csv"
        meta_path = f"data/destructive_v1_template_{t}.meta.json"
        
        if not os.path.exists(csv_path) or not os.path.exists(meta_path):
            print(f"❌ FAIL: Missing requirement files for template {t}")
            sys.exit(1)
            
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
            
        # Hard check for source_dataset_id
        if meta.get("source_dataset_id") != "normalized_pool_v1":
             print(f"❌ FAIL: Template {t} source_dataset_id mismatch. Expected 'normalized_pool_v1'.")
             sys.exit(1)
             
        # SHA256 verification
        expected_sha = meta.get("sha256")
        actual_sha = calculate_sha256(csv_path)
        if expected_sha != actual_sha:
            print(f"❌ FAIL: Integrity mismatch for template {t}. SHA256 error.")
            sys.exit(1)
            
    print("✅ Asset Check: All templates verified (SHA256 & Source ID).")

# --- 3. Validation Logic ---
def extract_placeholders(text: str) -> set[str]:
    ph = set()
    for pat in PLACEHOLDER_PATTERNS:
        ph |= set(re.findall(pat, text or ""))
    return ph

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

def validate_batch(model_name, response_text, input_items, report_model):
    """
    Validates batch response.
    Returns (Success, Reason, OrderMatch)
    """
    # Sanitize
    clean_text = sanitize_json(response_text)
    
    try:
        data = json.loads(clean_text)
    except Exception:
        # Retry regex fallback
        match = re.search(r'\{.*\}', clean_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except:
                return False, "JSON Parse Failure", False
        else:
            return False, "JSON Parse Failure", False

    if not isinstance(data, dict) or "items" not in data or not isinstance(data["items"], list):
        return False, "Invalid Structure (Missing 'items')", False
        
    out_items = data["items"]
    
    # Length Check
    if len(out_items) != len(input_items):
        return False, f"Length Mismatch: In {len(input_items)}, Out {len(out_items)}", False
        
    # Order & ID Check
    order_match = True
    id_mismatch = []
    placeholder_failures = 0
    
    for i, in_item in enumerate(input_items):
        if i >= len(out_items): break
        out_item = out_items[i]
        
        in_id = in_item["string_id"]
        out_id = out_item.get("string_id")
        
        if in_id != out_id:
            order_match = False
            id_mismatch.append(f"Row {i}: {in_id} vs {out_id}")
            
        # Placeholder Check (Diagnostic)
        in_ph = extract_placeholders(in_item["source_zh"])
        out_text = out_item.get("translated_text", "")
        out_ph = extract_placeholders(out_text)
        
        if not in_ph.issubset(out_ph):
            placeholder_failures += 1

    if id_mismatch:
        return False, f"ID/Order Error: {'; '.join(id_mismatch[:3])}", False
    
    if placeholder_failures > (len(input_items) * 0.3): # 30% Threshold
        return False, f"Heavy Placeholder Loss: {placeholder_failures} items", True
        
    return True, "PASS", True

# --- 4. Main Execution Loop ---
def main():
    print(f"🚀 Starting {GATE_NAME}...")
    check_environment()
    validate_assets()
    
    client = LLMClient()
    results = {}
    
    for model in REQUIRED_MODELS:
        print(f"\n▶ Testing Model: {model}")
        model_results = {"templates": {}, "max_pass_batch_size_overall": 0, "fail_reason": None}
        abort_model = False
        
        for t in TEMPLATES:
            if abort_model: break
            
            csv_path = f"data/destructive_v1_template_{t}.csv"
            all_rows = []
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader: all_rows.append(row)
                
            template_results = {}
            template_max_pass = 0
            
            for bsize in BATCH_SIZES:
                # We do NOT break the template loop here unless it's a fatal abort
                print(f"   [Temp {t}] Batch Size: {bsize}...", end=" ", flush=True)
                
                config_success_count = 0
                latencies = []
                tokens = []
                fail_reason = None
                
                # N=5 iterations
                for i in range(ITERATIONS_PER_CONFIG):
                    start_idx = (i * bsize) % len(all_rows)
                    if start_idx + bsize > len(all_rows):
                        batch_items = all_rows[-bsize:]
                    else:
                        batch_items = all_rows[start_idx : start_idx + bsize]
                    
                    user_prompt = json.dumps({"items": batch_items}, ensure_ascii=False)
                    system_prompt = "You MUST return a JSON object with a single key 'items' containing an array of translated objects. Keep string_id and preserve placeholders. No markdown blocks."
                    
                    try:
                        res = client.chat(
                            system=system_prompt,
                            user=user_prompt,
                            temperature=0,
                            metadata={
                                "step": GATE_NAME,
                                "model_override": model,
                                "force_llm": True,
                                "allow_fallback": False,
                                "retry": 0
                            }
                        )
                        # Hard Model Integrity Check
                        if res.model != model:
                            print(f"\n❌ FAIL: Model integrity violation. Requested '{model}', Got '{res.model}'")
                            abort_model = True
                            fail_reason = f"Model Integrity Violation: {res.model}"
                            break
                        
                        passed, reason, _ = validate_batch(model, res.text, batch_items, res.model)
                        if passed:
                            config_success_count += 1
                            latencies.append(res.latency_ms)
                            if res.usage:
                                tokens.append(res.usage.get("total_tokens", 0))
                        else:
                            fail_reason = reason
                            break
                            
                    except Exception as e:
                        fail_reason = f"Exception: {str(e)[:50]}"
                        break
                
                if config_success_count == ITERATIONS_PER_CONFIG:
                    print("✅ PASS")
                    template_max_pass = bsize
                    template_results[str(bsize)] = {
                        "status": "PASS",
                        "p95_latency_ms": sorted(latencies)[-1] if latencies else 0,
                        "avg_tokens": int(mean(tokens)) if tokens else 0
                    }
                else:
                    print(f"❌ FAIL ({fail_reason or 'Iteration failed'})")
                    template_results[str(bsize)] = {
                        "status": "FAIL",
                        "reason": fail_reason or "Iteration failure"
                    }
                    model_results["fail_reason"] = fail_reason
                    # If failed at the SMALLEST size, no need to try other sizes for this template
                    # and no need to try other templates because min(B, C) will be 0 anyway.
                    if bsize == BATCH_SIZES[0]:
                        abort_model = True 
                    break # Stop escalation for THIS template
            
            model_results["templates"][t] = {
                "results": template_results,
                "max_pass": template_max_pass
            }
            # Only abort and stop templates if it's fatal or impossible to qualify
            if abort_model: break
            
        # Overall max pass is min(max_pass_B, max_pass_C)
        if "B" in model_results["templates"] and "C" in model_results["templates"]:
            max_b = model_results["templates"]["B"]["max_pass"]
            max_c = model_results["templates"]["C"]["max_pass"]
            model_results["max_pass_batch_size_overall"] = min(max_b, max_c)
        else:
            model_results["max_pass_batch_size_overall"] = 0
            
        results[model] = model_results

    # --- 5. Output Management ---
    final_output = {
        "gate": GATE_NAME,
        "timestamp": datetime.now().isoformat(),
        "models": results
    }
    
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2)
        
    print(f"\n✅ Created {REPORT_JSON}")
    
    # Markdown Summary
    md_lines = [
        f"# {GATE_NAME.replace('_', ' ').title()} Summary",
        f"\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "\n| Model | Overall Max Batch | Temp B (JSON) | Temp C (PH) | Status |",
        "|---|---|---|---|---|"
    ]
    
    for model, mdata in results.items():
        max_o = mdata.get("max_pass_batch_size_overall", 0)
        max_b = mdata["templates"].get("B", {}).get("max_pass", 0)
        max_c = mdata["templates"].get("C", {}).get("max_pass", 0)
        status = "✅ QUALIFIED" if max_o >= 10 else "❌ FAIL"
        md_lines.append(f"| {model} | **{max_o}** | {max_b} | {max_c} | {status} |")
        
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")
        
    print(f"✅ Created {REPORT_MD}")

if __name__ == "__main__":
    main()
