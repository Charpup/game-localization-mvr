#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_validation.py

Run N-row validation on a model that passed Dual Gate.
Outputs translation CSV and detailed metrics with deterministic scoring.

Scoring Formula (documented):
  score = 100 - (missing_rate*40 + escalation_rate*30 + parse_error_rate*20 + cost_norm*10)
  cost_norm = min(cost_usd / baseline_cost, 1.0)
  baseline_cost = $0.10 per 100 rows (adjustable)

Usage:
  python scripts/run_validation.py --model gpt-4.1-mini --rows 300
  python scripts/run_validation.py --model claude-sonnet-4-5-20250929 --rows 1000 --api-key-path ...
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import yaml
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from runtime_adapter import LLMClient, LLMError
except ImportError:
    print("ERROR: runtime_adapter.py not found.")
    sys.exit(1)

# Constants
BATCH_SIZE = 10
VALID_ROW_COUNTS = [100, 300, 500, 1000]

# Scoring weights (must sum to 100)
SCORE_WEIGHTS = {
    "missing_rate": 40,
    "escalation_rate": 30,
    "parse_error_rate": 20,
    "cost_norm": 10,
}

# Baseline cost for normalization ($ per 100 rows)
BASELINE_COST_PER_100_ROWS = 0.10


def calculate_sha256(path: str) -> str:
    """Calculate SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def load_validation_data(path: str) -> List[Dict[str, str]]:
    """Load validation CSV data."""
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def resolve_api_credentials(args) -> None:
    """Resolve API credentials."""
    default_key_path = "data/attachment/api_key.txt"
    
    key_path = args.api_key_path or os.environ.get("LLM_API_KEY_FILE") or default_key_path
    if os.path.exists(key_path):
        os.environ["LLM_API_KEY_FILE"] = key_path
    elif not os.environ.get("LLM_API_KEY"):
        print(f"ERROR: API key not found: {key_path}")
        sys.exit(1)


def load_pricing() -> Dict[str, Dict[str, float]]:
    """Load pricing configuration."""
    pricing_path = "config/pricing.yaml"
    if os.path.exists(pricing_path):
        with open(pricing_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


def estimate_cost(model: str, input_tokens: int, output_tokens: int, pricing: Dict) -> float:
    """Estimate cost in USD."""
    model_pricing = pricing.get("models", {}).get(model, {})
    input_rate = model_pricing.get("input_per_1M", 0.5) / 1_000_000
    output_rate = model_pricing.get("output_per_1M", 1.5) / 1_000_000
    return input_tokens * input_rate + output_tokens * output_rate


SYSTEM_PROMPT = """你是自动化测试助手。
Requirements:
1. Input is a JSON array of items.
2. Output MUST be a pure JSON array of translations.
3. Each output item MUST have "string_id" and "target_ru".
4. Count of output items MUST match count of input items exactly.
5. All "string_id"s from input MUST be present in output.
6. Empty source -> Empty target.
7. Placeholders ⟦PH_x⟧ MUST be preserved.
8. Do NOT wrap output in any object key. Return array directly.

Translate to Russian."""


def build_prompt(batch: List[Dict[str, str]]) -> str:
    """Build batch prompt."""
    items = []
    for r in batch:
        source = r.get("source_zh", "") or r.get("tokenized_zh", "") or ""
        items.append({"string_id": r.get("string_id", ""), "tokenized_zh": source})
    return json.dumps(items, ensure_ascii=False)


def run_batch(
    client: LLMClient,
    batch: List[Dict[str, str]],
    model: str,
) -> Dict[str, Any]:
    """Run a single batch and return results."""
    user_prompt = build_prompt(batch)
    input_ids = {r.get("string_id", "") for r in batch}
    
    start_time = time.time()
    try:
        result = client.chat(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            temperature=0.0,
            metadata={"step": "validation", "model_override": model, "is_batch": False}
        )
        latency_ms = result.latency_ms
        raw_text = result.text.strip()
        
        # Parse response
        parsed = []
        parse_error = False
        
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, dict):
                for key in ["results", "items", "data", "translations"]:
                    if key in parsed and isinstance(parsed[key], list):
                        parsed = parsed[key]
                        break
            if not isinstance(parsed, list):
                parse_error = True
                parsed = []
        except json.JSONDecodeError:
            match = re.search(r'\[.*\]', raw_text, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                except:
                    parse_error = True
            else:
                parse_error = True
        
        # Extract translations
        translations = {}
        output_ids = set()
        for item in parsed:
            if isinstance(item, dict) and "string_id" in item:
                sid = item["string_id"]
                output_ids.add(sid)
                translations[sid] = item.get("target_ru", "")
        
        missing_ids = input_ids - output_ids
        
        # Estimate tokens
        input_chars = len(SYSTEM_PROMPT) + len(user_prompt)
        output_chars = len(raw_text)
        input_tokens = input_chars // 4
        output_tokens = output_chars // 4
        
        return {
            "success": True,
            "translations": translations,
            "missing_ids": list(missing_ids),
            "parse_error": parse_error,
            "latency_ms": latency_ms,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "error": None,
        }
        
    except Exception as e:
        return {
            "success": False,
            "translations": {},
            "missing_ids": list(input_ids),
            "parse_error": True,
            "latency_ms": int((time.time() - start_time) * 1000),
            "input_tokens": 0,
            "output_tokens": 0,
            "error": str(e),
        }


def compute_score(metrics: Dict[str, float]) -> float:
    """
    Compute deterministic validation score.
    
    Formula:
      score = 100 - (missing_rate*40 + escalation_rate*30 + parse_error_rate*20 + cost_norm*10)
      
    Higher score = better. Perfect = 100, Worst = 0.
    """
    penalty = 0.0
    penalty += metrics.get("missing_rate", 0) * SCORE_WEIGHTS["missing_rate"]
    penalty += metrics.get("escalation_rate", 0) * SCORE_WEIGHTS["escalation_rate"]
    penalty += metrics.get("parse_error_rate", 0) * SCORE_WEIGHTS["parse_error_rate"]
    penalty += metrics.get("cost_norm", 0) * SCORE_WEIGHTS["cost_norm"]
    
    return max(0.0, 100.0 - penalty)


def run_validation(
    client: LLMClient,
    rows: List[Dict[str, str]],
    model: str,
    pricing: Dict,
) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    """Run validation on all rows."""
    batches = [rows[i:i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
    
    output_rows = []
    total_missing = 0
    total_escalated = 0
    total_parse_errors = 0
    total_latency_ms = 0
    total_input_tokens = 0
    total_output_tokens = 0
    latencies = []
    errors = []
    
    print(f"Running {len(batches)} batches...")
    
    for i, batch in enumerate(batches):
        print(f"  Batch {i+1}/{len(batches)}...", end=" ", flush=True)
        
        result = run_batch(client, batch, model)
        
        total_latency_ms += result["latency_ms"]
        total_input_tokens += result["input_tokens"]
        total_output_tokens += result["output_tokens"]
        latencies.append(result["latency_ms"])
        
        if result["parse_error"]:
            total_parse_errors += 1
        
        if result["error"]:
            errors.append(result["error"])
        
        # Build output rows
        for row in batch:
            sid = row.get("string_id", "")
            source = row.get("source_zh", "") or row.get("tokenized_zh", "") or ""
            
            if sid in result["translations"]:
                target = result["translations"][sid]
                output_rows.append({
                    "string_id": sid,
                    "source_zh": source,
                    "target_ru": target,
                    "status": "translated",
                })
            else:
                total_missing += 1
                output_rows.append({
                    "string_id": sid,
                    "source_zh": source,
                    "target_ru": "",
                    "status": "missing",
                })
        
        status = "✓" if not result["missing_ids"] and not result["parse_error"] else "!"
        print(f"{status} ({result['latency_ms']}ms)")
    
    # Calculate metrics
    total_rows = len(rows)
    total_batches = len(batches)
    
    missing_rate = total_missing / total_rows if total_rows > 0 else 0
    escalation_rate = total_escalated / total_rows if total_rows > 0 else 0
    parse_error_rate = total_parse_errors / total_batches if total_batches > 0 else 0
    
    # Cost estimation
    cost_usd = estimate_cost(model, total_input_tokens, total_output_tokens, pricing)
    baseline_cost = BASELINE_COST_PER_100_ROWS * (total_rows / 100)
    cost_norm = min(cost_usd / baseline_cost, 1.0) if baseline_cost > 0 else 0
    
    # Latency stats
    latencies.sort()
    avg_latency = total_latency_ms / total_batches if total_batches > 0 else 0
    p95_idx = min(int(len(latencies) * 0.95), len(latencies) - 1) if latencies else 0
    p95_latency = latencies[p95_idx] if latencies else 0
    
    metrics = {
        "total_rows": total_rows,
        "total_batches": total_batches,
        "missing_count": total_missing,
        "missing_rate": missing_rate,
        "escalation_count": total_escalated,
        "escalation_rate": escalation_rate,
        "parse_error_count": total_parse_errors,
        "parse_error_rate": parse_error_rate,
        "avg_latency_ms": avg_latency,
        "p95_latency_ms": p95_latency,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "cost_usd": cost_usd,
        "cost_norm": cost_norm,
        "errors": errors,
    }
    
    # Compute score
    metrics["score"] = compute_score(metrics)
    
    return output_rows, metrics


def write_output_csv(rows: List[Dict[str, str]], path: str) -> None:
    """Write output CSV."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["string_id", "source_zh", "target_ru", "status"])
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Run N-row validation")
    parser.add_argument("--model", required=True, help="Model to test")
    parser.add_argument("--rows", type=int, default=300, choices=VALID_ROW_COUNTS,
                        help="Number of rows (must match validation set)")
    parser.add_argument("--input", help="Input CSV (default: data/validation_<rows>_v1.csv)")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size")
    parser.add_argument("--api-key-path", help="Path to API key file")
    parser.add_argument("--output-dir", default="data", help="Output directory for CSV")
    parser.add_argument("--report-dir", default="reports", help="Output directory for report")
    args = parser.parse_args()
    
    global BATCH_SIZE
    BATCH_SIZE = args.batch_size
    
    # Resolve paths
    input_path = args.input or f"data/validation_{args.rows}_v1.csv"
    if not os.path.exists(input_path):
        print(f"ERROR: Validation set not found: {input_path}")
        print(f"Run: python scripts/build_validation_set.py --rows {args.rows}")
        sys.exit(1)
    
    # Resolve credentials
    resolve_api_credentials(args)
    
    # Load data
    print(f"Loading validation set from {input_path}...")
    rows = load_validation_data(input_path)
    input_sha = calculate_sha256(input_path)
    print(f"Loaded {len(rows)} rows (SHA: {input_sha[:16]}...)")
    
    # Load pricing
    pricing = load_pricing()
    
    # Initialize client
    client = LLMClient()
    
    print(f"\n{'='*60}")
    print(f"Validation Runner")
    print(f"Model: {args.model}")
    print(f"Rows: {len(rows)}")
    print(f"Batch Size: {BATCH_SIZE}")
    print(f"{'='*60}\n")
    
    # Run validation
    output_rows, metrics = run_validation(client, rows, args.model, pricing)
    
    # Generate outputs
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_safe = args.model.replace("/", "_").replace(":", "_")
    
    output_csv = os.path.join(args.output_dir, f"validation_{args.rows}_output_{model_safe}.csv")
    report_json = os.path.join(args.report_dir, f"validation_{args.rows}_{model_safe}_{date_str}.json")
    
    # Write CSV
    write_output_csv(output_rows, output_csv)
    print(f"\nOutput CSV: {output_csv}")
    
    # Write report
    report = {
        "model": args.model,
        "input_path": input_path,
        "input_sha256": input_sha,
        "timestamp": datetime.now().isoformat(),
        "scoring_formula": "score = 100 - (missing_rate*40 + escalation_rate*30 + parse_error_rate*20 + cost_norm*10)",
        "baseline_cost_per_100_rows": BASELINE_COST_PER_100_ROWS,
        "metrics": metrics,
    }
    
    os.makedirs(args.report_dir, exist_ok=True)
    with open(report_json, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"Report: {report_json}")
    
    # Print summary
    print(f"\n{'='*60}")
    print("VALIDATION RESULTS")
    print(f"{'-'*60}")
    print(f"Score:          {metrics['score']:.1f}/100")
    print(f"Missing Rate:   {metrics['missing_rate']:.1%}")
    print(f"Escalation:     {metrics['escalation_rate']:.1%}")
    print(f"Parse Errors:   {metrics['parse_error_rate']:.1%}")
    print(f"Avg Latency:    {metrics['avg_latency_ms']:.0f}ms")
    print(f"P95 Latency:    {metrics['p95_latency_ms']:.0f}ms")
    print(f"Cost Est:       ${metrics['cost_usd']:.4f}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
