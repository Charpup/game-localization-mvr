#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
run_empty_gate_v3_mixed.py

Strict runner for Mixed Empty Batch Gate (MEBG).
Enforces:
1. LLM Call (No local short-circuit)
2. JSON Array Output
3. Empty Row Contract (Empty Input -> Empty Output)
4. ID Coverage 1.0

Usage:
    python scripts/run_empty_gate_v3_mixed.py --models gpt-4.1-mini --trials 3
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime
from collections import defaultdict

# Add scripts dir to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from runtime_adapter import LLMClient, LLMError
except ImportError:
    print("Error: Could not import runtime_adapter. Make sure you are in the project root or scripts dir.")
    sys.exit(1)

BATCH_SIZE = 10
INPUT_FILE = "data/empty_gate_v3_mixed.csv"
REPORT_DIR = "reports"

def load_data(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Input file not found: {filepath}")
    
    rows = []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows

def build_prompt(batch, batch_idx):
    """Build prompt containing ALL rows (including empty)."""
    
    items = []
    for row in batch:
        items.append({
            "string_id": row["string_id"],
            "source_zh": row["source_zh"]
        })
        
    system_prompt = """You are a localization engine.
Translate the following JSON array of strings from Chinese to English.
Returns a JSON object with a key "translations" containing an array of objects.
Each object must have keys: "string_id", "translated_text".
Keep "string_id" exactly as is.

CRITICAL RULES:
1. If "source_zh" is empty or whitespace, "translated_text" MUST be exactly "" (empty string).
2. Do not add any extra keys.
3. Output strictly valid JSON.
"""
    
    user_prompt = json.dumps(items, ensure_ascii=False, indent=2)
    return system_prompt, user_prompt, items

def validate_response(response_text, input_items):
    """
    Strict validation of response.
    Returns: (is_valid, error_msg, stats)
    stats = {id_match: bool, empty_correct: bool, len_match: bool}
    """
    try:
        raw_data = json.loads(response_text)
    except json.JSONDecodeError:
        return False, "Invalid JSON", {}
        
    # Unwrap if dict
    if isinstance(raw_data, dict):
        # Look for "translations" or first list value
        if "translations" in raw_data and isinstance(raw_data["translations"], list):
            data = raw_data["translations"]
        else:
            # Fallback: find any list
            found = False
            for v in raw_data.values():
                if isinstance(v, list):
                    data = v
                    found = True
                    break
            if not found:
                return False, f"Top level is dict keys={list(raw_data.keys())}, expected 'translations' list", {}
    elif isinstance(raw_data, list):
        data = raw_data
    else:
        return False, "Top level is not a list or dict wrapper", {}

        
    # Stats
    len_match = len(data) == len(input_items)
    
    input_ids = {item["string_id"] for item in input_items}
    output_ids = {item.get("string_id") for item in data if isinstance(item, dict)}
    id_match = (input_ids == output_ids)
    
    # Empty Row Contract Check
    empty_correct = True
    empty_errors = []
    
    input_map = {item["string_id"]: item for item in input_items}
    
    for out_item in data:
        if not isinstance(out_item, dict): 
            continue
            
        sid = out_item.get("string_id")
        if sid not in input_map:
            continue
            
        in_item = input_map[sid]
        src_text = in_item.get("source_zh", "").strip()
        trans_text = out_item.get("translated_text")
        
        if not src_text: # Empty Source
            if trans_text != "":
                empty_correct = False
                empty_errors.append(f"{sid}: Expected '', got '{trans_text}'")
                
    error_msg = ""
    if not len_match: error_msg += f"Length mismatch (In:{len(input_items)}, Out:{len(data)}); "
    if not id_match: error_msg += f"ID mismatch ({len(output_ids)}/{len(input_ids)}); "
    if not empty_correct: error_msg += f"Empty contract violation: {'; '.join(empty_errors[:3])}..."
    
    is_valid = len_match and id_match and empty_correct
    
    return is_valid, error_msg, {
        "length_match_pass": len_match,
        "id_coverage_pass": id_match,
        "empty_rows_empty_text_pass": empty_correct
    }

def run_trial(model, rows, trial_idx):
    """Run full dataset for one trial."""
    client = LLMClient(model=model)
    
    stats = {
        "total_batches": 0,
        "failed_batches": 0,
        "llm_call_count": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "json_top_level_array_pass": True, # Aggregate
        "length_match_pass": True,
        "id_coverage_pass": True,
        "empty_rows_empty_text_pass": True,
        "errors": []
    }
    
    # Process in batches
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i:i+BATCH_SIZE]
        batch_idx = i // BATCH_SIZE
        stats["total_batches"] += 1
        
        sys_prompt, user_prompt, input_items = build_prompt(batch, i)
        
        try:
            # Force LLM Call
            result = client.chat(
                system=sys_prompt, 
                user=user_prompt,
                temperature=0, # Strict
                response_format={"type": "json_object"},
                metadata={"step": "empty_gate_mixed", "batch_idx": batch_idx, "force_llm": True}
            )
            
            stats["llm_call_count"] += 1
            if result.usage:
                stats["prompt_tokens"] += result.usage.get("prompt_tokens", 0)
                stats["completion_tokens"] += result.usage.get("completion_tokens", 0)
                
            is_valid, err_msg, batch_valid_stats = validate_response(result.text, input_items)
            
            if not is_valid:
                stats["failed_batches"] += 1
                stats["errors"].append(f"Batch {batch_idx}: {err_msg}")
                # Update aggregate flags
                if not batch_valid_stats.get("length_match_pass", False): stats["length_match_pass"] = False
                if not batch_valid_stats.get("id_coverage_pass", False): stats["id_coverage_pass"] = False
                if not batch_valid_stats.get("empty_rows_empty_text_pass", False): stats["empty_rows_empty_text_pass"] = False
                if "Invalid JSON" in err_msg or "Top level" in err_msg: stats["json_top_level_array_pass"] = False
                
        except LLMError as e:
            stats["failed_batches"] += 1
            stats["errors"].append(f"Batch {batch_idx} LLM Error: {str(e)}")
            stats["json_top_level_array_pass"] = False # Treat error as json fail effectively
            
        print(f"[{model}] Trial {trial_idx+1} Batch {batch_idx+1}/{len(rows)//BATCH_SIZE + 1} - {'PASS' if is_valid else 'FAIL'}")
        
    return stats

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--trials", type=int, default=3)
    args = parser.parse_args()
    
    print(f"Loading data from {INPUT_FILE}...")
    try:
        rows = load_data(INPUT_FILE)
    except FileNotFoundError:
        print("Data file not found. Please run scripts/build_mixed_gate.py first.")
        sys.exit(1)
        
    print(f"Loaded {len(rows)} rows. Batch size {BATCH_SIZE}.")
    
    results = {}
    
    for model in args.models:
        print(f"\n=== Testing Model: {model} ===")
        model_results = []
        for t in range(args.trials):
            print(f"  Trial {t+1}/{args.trials}...")
            trial_stats = run_trial(model, rows, t)
            model_results.append(trial_stats)
            
        results[model] = model_results
        
    # Save Results
    os.makedirs(REPORT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = os.path.join(REPORT_DIR, f"empty_gate_v3_mixed_results_{ts}.json")
    
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print(f"\nDetailed JSON report saved to {report_file}")
    
    # Generate Summary MD
    summary_file = os.path.join(REPORT_DIR, f"empty_gate_v3_mixed_summary_{ts}.md")
    with open(summary_file, "w", encoding="utf-8") as f:
        f.write("# Empty Gate V3 (Mixed) Summary\n\n")
        f.write(f"Date: {ts}\n\n")
        f.write("| Model | Trial | Pass/Fail | Empty Contract | ID Match | JSON Valid | LLM Calls |\n")
        f.write("|---|---|---|---|---|---|---|\n")
        
        for model in args.models:
            for i, res in enumerate(results[model]):
                is_pass = (res["failed_batches"] == 0)
                status = "✅ PASS" if is_pass else "❌ FAIL"
                f.write(f"| {model} | {i+1} | {status} | {res['empty_rows_empty_text_pass']} | {res['id_coverage_pass']} | {res['json_top_level_array_pass']} | {res['llm_call_count']} |\n")

    print(f"Summary markdown saved to {summary_file}")
    # Print summary to console
    print("\nSummary:")
    with open(summary_file, "r", encoding="utf-8") as f:
        print(f.read())

if __name__ == "__main__":
    main()
