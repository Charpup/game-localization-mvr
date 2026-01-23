#!/usr/bin/env python3
"""
Phase 1 V3: Destructive Batch Test
Full batch stability validation with extended ladder [10,15,20,30,40,50] for all 5 models.
"""
import os
import sys
import json
import csv
import time
import hashlib
import re
from datetime import datetime
from statistics import mean

# Local imports
try:
    from runtime_adapter import LLMClient, LLMError
except ImportError:
    print("❌ FAIL: Cannot import runtime_adapter.")
    sys.exit(1)

# --- Configuration ---
GATE_NAME = "destructive_batch_v3"
TEMPLATES = ["B", "C"]
MODELS = [
    "gpt-4.1-mini",
    "claude-haiku-4-5-20251001",
    "gpt-5.1",
    "gpt-5.2",
    "claude-sonnet-4-5-20250929"
]
BATCH_LADDER = [10, 15, 20, 30, 40, 50]
N_ITERATIONS = 5
INTER_MODEL_COOLDOWN = 30  # seconds
INTER_TEMPLATE_COOLDOWN = 10  # seconds

REPORT_JSON = "reports/destructive_batch_v3_results.json"
REPORT_MD = "reports/destructive_batch_v3_summary.md"
PROGRESS_LOG = "reports/destructive_batch_v3_progress.jsonl"

PLACEHOLDER_PATTERNS = [
    r"\{\d+\}", r"\{[a-zA-Z_][a-zA-Z0-9_]*\}",
    r"%s", r"%d", r"\$\{[^\}]+\}",
    r"\{\{[^\}]+\}\}", r"<[^>]+>", r"\[[^\]]+\]", r"【[^】]+】"
]

SYSTEM_PROMPT = "You MUST return a JSON object with a single key 'items' containing an array of translated objects. Keep string_id and preserve placeholders. No markdown blocks."

# --- Progress Logging ---
def log_progress(event_type, data):
    """Log progress event to JSONL and terminal."""
    event = {
        "timestamp": datetime.now().isoformat(),
        "event": event_type,
        "data": data
    }
    os.makedirs("reports", exist_ok=True)
    with open(PROGRESS_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")
    
    if event_type == "iteration_complete":
        d = data
        print(f"    Iter {d['iteration']}/{d['total_iterations']}: {d['status']} ({d['latency_ms']}ms)")
    elif event_type == "batch_complete":
        d = data
        print(f"  [Batch {d['batch_size']}] {d['status']} ({d['pass_count']}/{d['total_iterations']}) Avg: {d.get('avg_latency_ms', 0)}ms")
    elif event_type == "template_complete":
        d = data
        print(f"[Template {d['template']} Complete] Max Pass: {d['max_pass']}")
    elif event_type == "model_complete":
        d = data
        print(f"✅ [Model Complete] {d['model']} -> Overall Max: {d['overall_max']}")

# --- Environment & Validation ---
def check_environment():
    if not os.path.exists("/.dockerenv"):
        print("❌ FAIL: Not in Docker container.")
        sys.exit(1)
    image_tag = os.getenv("GATE_IMAGE_TAG", "")
    if image_tag != "gate_v2":
        print(f"❌ FAIL: GATE_IMAGE_TAG is '{image_tag}', expected 'gate_v2'.")
        sys.exit(1)
    print(f"✅ Environment: Docker (gate_v2)")

def calculate_sha256(filepath):
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()

def validate_assets():
    for t in TEMPLATES:
        csv_path = f"data/destructive_v1_template_{t}.csv"
        meta_path = f"data/destructive_v1_template_{t}.meta.json"
        if not os.path.exists(csv_path) or not os.path.exists(meta_path):
            print(f"❌ FAIL: Missing files for template {t}")
            sys.exit(1)
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        if meta.get("source_dataset_id") != "normalized_pool_v1":
            print(f"❌ FAIL: Template {t} source_dataset_id mismatch.")
            sys.exit(1)
        expected_sha = meta.get("sha256")
        actual_sha = calculate_sha256(csv_path)
        if expected_sha != actual_sha:
            print(f"❌ FAIL: SHA256 mismatch for template {t}")
            sys.exit(1)
    print("✅ Assets: All templates verified.")

def extract_placeholders(text):
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

def validate_batch(response_text, input_items):
    clean_text = sanitize_json(response_text)
    try:
        data = json.loads(clean_text)
    except:
        match = re.search(r'\{.*\}', clean_text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
            except:
                return False, "JSON Parse Failure"
        else:
            return False, "JSON Parse Failure"
    
    if not isinstance(data, dict) or "items" not in data:
        return False, "Missing 'items' key"
    
    out_items = data["items"]
    if len(out_items) != len(input_items):
        return False, f"Length Mismatch: {len(input_items)} vs {len(out_items)}"
    
    for i, in_item in enumerate(input_items):
        if i >= len(out_items):
            break
        out_item = out_items[i]
        if str(in_item["string_id"]) != str(out_item.get("string_id", "")):
            return False, f"ID Mismatch at row {i}"
    
    return True, "PASS"

# --- Main Execution ---
def main():
    print(f"{'='*60}")
    print(f"Phase 1 V3: {GATE_NAME}")
    print(f"Models: {len(MODELS)}, Templates: {TEMPLATES}, Ladder: {BATCH_LADDER}")
    print(f"{'='*60}")
    
    check_environment()
    validate_assets()
    
    # Clear progress log
    if os.path.exists(PROGRESS_LOG):
        os.remove(PROGRESS_LOG)
    
    client = LLMClient()
    results = {}
    
    for model_idx, model in enumerate(MODELS):
        if model_idx > 0:
            print(f"\n[COOLDOWN] Waiting {INTER_MODEL_COOLDOWN}s before next model...")
            time.sleep(INTER_MODEL_COOLDOWN)
        
        print(f"\n{'='*60}")
        print(f"Testing Model: {model}")
        print(f"{'='*60}")
        
        model_results = {"templates": {}, "max_pass_batch_size_overall": 0}
        
        for t_idx, t in enumerate(TEMPLATES):
            if t_idx > 0:
                print(f"\n[Template Cooldown] Waiting {INTER_TEMPLATE_COOLDOWN}s...")
                time.sleep(INTER_TEMPLATE_COOLDOWN)
            
            print(f"\n--- Template {t} ---")
            
            csv_path = f"data/destructive_v1_template_{t}.csv"
            all_rows = []
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    all_rows.append(row)
            
            template_results = {}
            template_max_pass = 0
            
            for bsize in BATCH_LADDER:
                print(f"\n  Batch Size: {bsize}")
                
                success_count = 0
                latencies = []
                fail_reason = None
                
                max_iters = min(N_ITERATIONS, len(all_rows) // bsize)
                
                for i in range(max_iters):
                    start_idx = i * bsize
                    batch_items = all_rows[start_idx:start_idx + bsize]
                    
                    user_prompt = json.dumps({"items": batch_items}, ensure_ascii=False)
                    
                    try:
                        t0 = time.time()
                        res = client.chat(
                            system=SYSTEM_PROMPT,
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
                        latency = int((time.time() - t0) * 1000)
                        
                        if res.model != model:
                            fail_reason = f"Model integrity: {res.model}"
                            log_progress("iteration_complete", {
                                "model": model, "template": t, "batch_size": bsize,
                                "iteration": i+1, "total_iterations": max_iters,
                                "status": "FAIL", "latency_ms": latency
                            })
                            break
                        
                        passed, reason = validate_batch(res.text, batch_items)
                        if passed:
                            success_count += 1
                            latencies.append(latency)
                            log_progress("iteration_complete", {
                                "model": model, "template": t, "batch_size": bsize,
                                "iteration": i+1, "total_iterations": max_iters,
                                "status": "PASS", "latency_ms": latency
                            })
                        else:
                            fail_reason = reason
                            log_progress("iteration_complete", {
                                "model": model, "template": t, "batch_size": bsize,
                                "iteration": i+1, "total_iterations": max_iters,
                                "status": "FAIL", "latency_ms": latency
                            })
                            break
                            
                    except Exception as e:
                        fail_reason = f"{type(e).__name__}: {str(e)[:80]}"
                        log_progress("iteration_complete", {
                            "model": model, "template": t, "batch_size": bsize,
                            "iteration": i+1, "total_iterations": max_iters,
                            "status": "FAIL", "latency_ms": 0
                        })
                        break
                    
                    time.sleep(2)  # Small delay between iterations
                
                avg_latency = int(mean(latencies)) if latencies else 0
                
                if success_count == max_iters:
                    template_results[str(bsize)] = {
                        "status": "PASS",
                        "iterations": max_iters,
                        "avg_latency_ms": avg_latency,
                        "max_latency_ms": max(latencies) if latencies else 0
                    }
                    template_max_pass = bsize
                    log_progress("batch_complete", {
                        "model": model, "template": t, "batch_size": bsize,
                        "status": "PASS", "pass_count": success_count,
                        "total_iterations": max_iters, "avg_latency_ms": avg_latency
                    })
                else:
                    template_results[str(bsize)] = {
                        "status": "FAIL",
                        "reason": fail_reason or "Iteration failed"
                    }
                    log_progress("batch_complete", {
                        "model": model, "template": t, "batch_size": bsize,
                        "status": "FAIL", "pass_count": success_count,
                        "total_iterations": max_iters, "avg_latency_ms": avg_latency
                    })
                    break  # Stop escalation
            
            model_results["templates"][t] = {
                "results": template_results,
                "max_pass": template_max_pass
            }
            log_progress("template_complete", {
                "model": model, "template": t, "max_pass": template_max_pass
            })
        
        # Overall = min(B, C)
        max_b = model_results["templates"].get("B", {}).get("max_pass", 0)
        max_c = model_results["templates"].get("C", {}).get("max_pass", 0)
        model_results["max_pass_batch_size_overall"] = min(max_b, max_c)
        
        results[model] = model_results
        log_progress("model_complete", {
            "model": model, "overall_max": model_results["max_pass_batch_size_overall"]
        })
    
    # --- Save Reports ---
    final_output = {
        "gate": GATE_NAME,
        "timestamp": datetime.now().isoformat(),
        "batch_ladder": BATCH_LADDER,
        "models": results
    }
    
    os.makedirs("reports", exist_ok=True)
    with open(REPORT_JSON, "w", encoding="utf-8") as f:
        json.dump(final_output, f, indent=2)
    print(f"\n✅ Saved {REPORT_JSON}")
    
    # Markdown Summary
    md_lines = [
        f"# Destructive Batch V3 Summary",
        f"",
        f"**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Batch Ladder**: {BATCH_LADDER}",
        f"",
        f"| Model | Overall Max | Temp B | Temp C | Status |",
        f"|-------|-------------|--------|--------|--------|"
    ]
    
    for model in MODELS:
        mdata = results.get(model, {})
        max_o = mdata.get("max_pass_batch_size_overall", 0)
        max_b = mdata.get("templates", {}).get("B", {}).get("max_pass", 0)
        max_c = mdata.get("templates", {}).get("C", {}).get("max_pass", 0)
        status = "✅ QUALIFIED" if max_o >= 10 else "❌ FAIL"
        md_lines.append(f"| {model} | **{max_o}** | {max_b} | {max_c} | {status} |")
    
    with open(REPORT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")
    print(f"✅ Saved {REPORT_MD}")
    
    # Final Summary
    print(f"\n{'='*60}")
    print("FINAL SUMMARY")
    print(f"{'='*60}")
    for model in MODELS:
        max_o = results.get(model, {}).get("max_pass_batch_size_overall", 0)
        print(f"  {model}: {max_o}")

if __name__ == "__main__":
    main()
