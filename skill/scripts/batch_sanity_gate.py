#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
batch_sanity_gate.py

A rigorous gatekeeper to validate LLM capabilities for batch translation.
Generates or loads a fixed 50-row sample and runs trials to measure:
- JSON validity
- N->N completion capability
- ID coverage
- Latency and Cost

Usage:
  python scripts/batch_sanity_gate.py --models gpt-4.1 gpt-4.1-mini
  python scripts/batch_sanity_gate.py --regen --seed 42
"""

import argparse
import csv
import hashlib
import json
import os
import random
import time
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

try:
    from runtime_adapter import LLMClient, LLMError
except ImportError:
    print("ERROR: runtime_adapter.py not found.")
    sys.exit(1)

# Default Gate Constants
GATE_SAMPLE_PATH = "data/gate_sample.csv"
GATE_RESULTS_PATH = "data/gate_results.json"
DEFAULT_MODELS = ["claude-sonnet-4-5-20250929", "gpt-4.1", "gpt-4.1-mini"]
BATCH_SIZE = 10
TRIALS_PER_MODEL = 3
TARGET_SAMPLE_SIZE = 50

# Pass Criteria
PASS_CRITERIA = {
    "n_to_n_rate": 0.99,
    "id_coverage_rate": 0.99,
    "json_valid_rate": 0.99
}

@dataclass
class GateMetrics:
    model: str
    trials: int
    total_batches: int
    json_valid_count: int
    n_to_n_count: int
    total_ids_sent: int
    total_ids_received: int
    total_latency_ms: int
    p95_latency_ms: int
    errors: List[str]
    sample_sha256: str
    status: str = "PENDING"
    
    @property
    def json_valid_rate(self) -> float:
        return self.json_valid_count / self.total_batches if self.total_batches > 0 else 0.0
    
    @property
    def n_to_n_rate(self) -> float:
        return self.n_to_n_count / self.total_batches if self.total_batches > 0 else 0.0

    @property
    def id_coverage_rate(self) -> float:
        return self.total_ids_received / self.total_ids_sent if self.total_ids_sent > 0 else 0.0
        
    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.total_batches if self.total_batches > 0 else 0.0

def generate_sample_data(path: str, seed: int):
    """Generate fixed distribution sample data."""
    print(f"Generating new sample data at {path} with seed {seed}...")
    random.seed(seed)
    
    # Distribution: 50 rows total
    # 20 UI (Short)
    # 15 Dialogue (Medium)
    # 5 System (Technical)
    # 5 Empty
    # 5 Placeholders
    
    data = []
    
    # UI
    for i in range(20):
        data.append({
            "string_id": f"UI_{i+1:03d}",
            "source_zh": f"这是UI文本测试_{i+1}",
            "type": "UI"
        })
        
    # Dialogue
    for i in range(15):
        data.append({
            "string_id": f"DIA_{i+1:03d}",
            "source_zh": f"这是对话文本测试_{i+1}，用于检查长句子的翻译完整性。",
            "type": "Dialogue"
        })
        
    # System
    for i in range(5):
        data.append({
            "string_id": f"SYS_{i+1:03d}",
            "source_zh": f"System_Error_{i+1}: ⟦PH_0⟧ connection failed.",
            "type": "System"
        })
        
    # Empty
    for i in range(5):
        data.append({
            "string_id": f"EMP_{i+1:03d}",
            "source_zh": "",
            "type": "Empty"
        })
        
    # Placeholders Only
    for i in range(5):
        data.append({
            "string_id": f"PHO_{i+1:03d}",
            "source_zh": f"⟦PH_{i}⟧",
            "type": "Placeholder"
        })
        
    # Shuffle
    random.shuffle(data)
    
    # Write
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["string_id", "source_zh", "type"])
        writer.writeheader()
        writer.writerows(data)
        
    print(f"Generated {len(data)} rows.")

def calculate_file_hash(path: str) -> str:
    """Calculate SHA256 of a file."""
    sha256_hash = hashlib.sha256()
    with open(path, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def load_sample_data(path: str) -> List[Dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def build_prompt(batch: List[Dict[str, str]]) -> str:
    """Build standardized batch prompt (Contract v6)."""
    # Simplified prompt for gate check
    items = [{"string_id": r["string_id"], "tokenized_zh": r["source_zh"]} for r in batch]
    return json.dumps(items, ensure_ascii=False)

PROMPT_SYSTEM = """你是自动化测试助手。
Requirements:
1. Input is a JSON array of items.
2. Output MUST be a pure JSON array of translations.
3. Each output item MUST have "string_id" and "target_ru".
4. Count of output items MUST match count of input items exactly.
5. All "string_id"s from input MUST be present in output.
6. Empty source -> Empty target.
7. Placeholders ⟦PH_x⟧ MUST be preserved.
8. Do NOT wrap output in any object key (like "result": [...]). Return array directly.

Translate to Russian (mock or real)."""

def run_batch_trial(client: LLMClient, batch: List[Dict[str, str]], model: str) -> Dict[str, Any]:
    """Run a single batch trial."""
    user_prompt = build_prompt(batch)
    input_ids = {r["string_id"] for r in batch}
    
    start_ts = time.time()
    try:
        # Force generic 'translate' step but override model to test specific one
        # Use is_batch=False here to bypass the router's capability check logic we are about to add,
        # because we WANT to test the model even if it's marked unfit.
        result = client.chat(
            system=PROMPT_SYSTEM,
            user=user_prompt,
            temperature=0.0,
            metadata={"step": "gate_test", "model_override": model, "is_batch": False}
        )
        latency_ms = result.latency_ms
        raw_text = result.text.strip()
        
        # Validation
        is_json_valid = False
        parsed = []
        try:
            # Flexible parsing to catch common wrapping errors
            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError:
                # Try finding array [ ... ]
                import re
                m = re.search(r'\[.*\]', raw_text, re.DOTALL)
                if m:
                    parsed = json.loads(m.group(0))
            
            if isinstance(parsed, list):
                is_json_valid = True
            elif isinstance(parsed, dict):
                 # Check for wrapped results
                 for k in ["results", "items", "data", "translations"]:
                     if k in parsed and isinstance(parsed[k], list):
                         parsed = parsed[k]
                         is_json_valid = True
                         break
        except Exception:
            pass
            
        output_ids = set()
        if is_json_valid:
            for item in parsed:
                if isinstance(item, dict) and "string_id" in item:
                    output_ids.add(item["string_id"])
        
        n_input = len(batch)
        n_output = len(parsed) if is_json_valid else 0
        is_n_to_n = (n_input == n_output)
        
        # Strict subset check
        missing_ids = input_ids - output_ids
        unexpected_ids = output_ids - input_ids
        
        return {
            "success": True,
            "latency_ms": latency_ms,
            "json_valid": is_json_valid,
            "n_to_n": is_n_to_n,
            "input_count": n_input,
            "output_count": n_output,
            "missing_count": len(missing_ids),
            "unexpected_count": len(unexpected_ids),
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "latency_ms": 0,
            "json_valid": False,
            "n_to_n": False,
            "input_count": len(batch),
            "output_count": 0,
            "missing_count": len(batch),
            "unexpected_count": 0,
            "error": str(e)
        }

def evaluate_model(model: str, rows: List[Dict[str, str]], sample_sha: str) -> GateMetrics:
    print(f"Testing model: {model}...")
    client = LLMClient()
    
    # Split into batches
    batches = [rows[i:i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
    total_batches = len(batches) * TRIALS_PER_MODEL
    
    metrics = GateMetrics(
        model=model,
        trials=TRIALS_PER_MODEL,
        total_batches=total_batches,
        json_valid_count=0,
        n_to_n_count=0,
        total_ids_sent=0,
        total_ids_received=0,
        total_latency_ms=0,
        p95_latency_ms=0,
        errors=[],
        sample_sha256=sample_sha
    )
    
    latencies = []
    
    for trial in range(TRIALS_PER_MODEL):
        print(f"  Trial {trial+1}/{TRIALS_PER_MODEL}...")
        for batch in batches:
            res = run_batch_trial(client, batch, model)
            
            metrics.total_ids_sent += res["input_count"]
            
            if res["success"]:
                metrics.total_latency_ms += res["latency_ms"]
                latencies.append(res["latency_ms"])
                
                if res["json_valid"]:
                    metrics.json_valid_count += 1
                
                if res["n_to_n"] and res["missing_count"] == 0:
                     metrics.n_to_n_count += 1
                
                metrics.total_ids_received += (res["input_count"] - res["missing_count"])
            else:
                metrics.errors.append(res["error"])
                
    # Calculate P95
    if latencies:
        latencies.sort()
        p95_idx = int(len(latencies) * 0.95)
        metrics.p95_latency_ms = latencies[min(p95_idx, len(latencies)-1)]
        
    # Determine Status
    passed = (
        metrics.n_to_n_rate >= PASS_CRITERIA["n_to_n_rate"] and
        metrics.id_coverage_rate >= PASS_CRITERIA["id_coverage_rate"] and
        metrics.json_valid_rate >= PASS_CRITERIA["json_valid_rate"]
    )
    metrics.status = "PASS" if passed else "FAIL"
    
    return metrics

def main():
    parser = argparse.ArgumentParser(description="Batch Sanity Gate")
    parser.add_argument("--models", nargs="+", default=DEFAULT_MODELS, help="List of models to test")
    parser.add_argument("--regen", action="store_true", help="Regenerate sample data")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for generation")
    args = parser.parse_args()
    
    # 1. Prepare Data
    if args.regen or not os.path.exists(GATE_SAMPLE_PATH):
        generate_sample_data(GATE_SAMPLE_PATH, args.seed)
        
    sample_sha = calculate_file_hash(GATE_SAMPLE_PATH)
    print(f"Sample Data SHA256: {sample_sha}")
    
    rows = load_sample_data(GATE_SAMPLE_PATH)
    print(f"Loaded {len(rows)} rows for testing.")
    
    # 2. Run Tests
    results = {}
    print(f"Starting gate for models: {args.models}")
    
    for model in args.models:
        metrics = evaluate_model(model, rows, sample_sha)
        results[model] = asdict(metrics)
        
    # 3. Save Results
    with open(GATE_RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to {GATE_RESULTS_PATH}")
    
    # 4. Print Summary
    print("\n" + "="*80)
    print(f"{'MODEL':<30} | {'STATUS':<6} | {'N->N':<6} | {'ID_COV':<6} | {'ValidJSON':<9} | {'AvgLat':<6}")
    print("-" * 80)
    
    for model, m in results.items():
        # Calculate rates from counts
        total = m['total_batches']
        json_rate = m['json_valid_count'] / total if total > 0 else 0
        id_cov = m['total_ids_received'] / m['total_ids_sent'] if m['total_ids_sent'] > 0 else 0
        n_n_rate = m['n_to_n_count'] / total if total > 0 else 0
        
        avg_lat = m['total_latency_ms'] / total if total > 0 else 0
        
        print(f"{model:<30} | {m['status']:<6} | {n_n_rate:.0%} | {id_cov:.0%}   | {json_rate:.0%}     | {avg_lat:.0f}ms")
        
    print("="*80)

if __name__ == "__main__":
    main()
