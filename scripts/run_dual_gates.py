#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_dual_gates.py

Unified runner for Contract Gate, Reality Gate, and Empty Gate.
Implements strict 3/3 trial pass semantics.

Usage:
  python scripts/run_dual_gates.py --models gpt-4.1-mini claude-sonnet-4-5-20250929
  python scripts/run_dual_gates.py --models gpt-5.2-pro --api-key-path data/attachment/api_key.txt
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Dict, Any, Optional

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from runtime_adapter import LLMClient, LLMError
except ImportError:
    print("ERROR: runtime_adapter.py not found.")
    sys.exit(1)

# Gate file paths
GATE_FILES = {
    "contract": "data/gate_sample.csv",
    "reality": "data/reality_gate_v1.csv",
    "empty": "data/empty_gate_v1.csv",
}

# Constants
BATCH_SIZE = 10
TRIALS_PER_GATE = 3
STRICT_PASS_REQUIRED = 3  # All 3 trials must pass

# Pass criteria per batch
BATCH_PASS_CRITERIA = {
    "json_valid": True,
    "n_to_n": True,
    "id_coverage": 1.0,
}


@dataclass
class TrialResult:
    """Result of a single trial."""
    trial_num: int
    batches_total: int
    batches_passed: int
    json_valid_count: int
    n_to_n_count: int
    ids_sent: int
    ids_received: int
    latency_ms: int
    errors: List[str] = field(default_factory=list)
    
    @property
    def passed(self) -> bool:
        """Trial passes only if ALL batches passed."""
        return self.batches_passed == self.batches_total and self.batches_total > 0


@dataclass
class GateResult:
    """Result for a single gate (e.g., Contract Gate)."""
    gate_name: str
    model: str
    csv_sha256: str
    trials: List[TrialResult] = field(default_factory=list)
    
    @property
    def trials_passed(self) -> int:
        return sum(1 for t in self.trials if t.passed)
    
    @property
    def passed(self) -> bool:
        """Gate passes only if 3/3 trials passed."""
        return self.trials_passed == STRICT_PASS_REQUIRED


@dataclass
class ModelResult:
    """Aggregated result for a model across all gates."""
    model: str
    gates: Dict[str, GateResult] = field(default_factory=dict)
    
    @property
    def pass_contract(self) -> bool:
        return self.gates.get("contract", GateResult("contract", self.model, "")).passed
    
    @property
    def pass_reality(self) -> bool:
        return self.gates.get("reality", GateResult("reality", self.model, "")).passed
    
    @property
    def pass_empty(self) -> bool:
        return self.gates.get("empty", GateResult("empty", self.model, "")).passed
    
    @property
    def pass_dual(self) -> bool:
        """PASS_DUAL = Contract AND Reality both pass."""
        return self.pass_contract and self.pass_reality


def calculate_sha256(path: str) -> str:
    """Calculate SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def load_gate_data(path: str) -> List[Dict[str, str]]:
    """Load gate CSV data."""
    with open(path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def resolve_api_credentials(args) -> None:
    """Resolve API credentials with priority: CLI > ENV > default path."""
    default_key_path = "data/attachment/api_key.txt"
    default_token_path = "data/attachment/api access token.txt"
    
    # API Key
    key_path = args.api_key_path or os.environ.get("LLM_API_KEY_FILE") or default_key_path
    if os.path.exists(key_path):
        os.environ["LLM_API_KEY_FILE"] = key_path
        print(f"Using API key from: {key_path}")
    elif not os.environ.get("LLM_API_KEY"):
        print(f"ERROR: API key file not found: {key_path}")
        print("Provide --api-key-path or set LLM_API_KEY/LLM_API_KEY_FILE")
        sys.exit(1)
    
    # API Token (optional)
    token_path = args.api_token_path or os.environ.get("LLM_ACCESS_TOKEN_FILE") or default_token_path
    if os.path.exists(token_path):
        os.environ["LLM_ACCESS_TOKEN_FILE"] = token_path


def build_prompt(batch: List[Dict[str, str]], is_empty_gate: bool = False) -> str:
    """Build batch prompt."""
    items = []
    for r in batch:
        source = r.get("source_zh", "") or r.get("tokenized_zh", "") or ""
        items.append({"string_id": r.get("string_id", ""), "tokenized_zh": source})
    return json.dumps(items, ensure_ascii=False)


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

Translate to Russian (mock or real)."""

EMPTY_GATE_PROMPT = """你是自动化测试助手。
Requirements:
1. Input is a JSON array of items with EMPTY source text.
2. Output MUST be a pure JSON array.
3. Each output item MUST have "string_id" and "target_ru".
4. For EMPTY source text, target_ru MUST be empty string "".
5. Count and IDs must match exactly.

Return array directly."""


def run_batch(
    client: LLMClient,
    batch: List[Dict[str, str]],
    model: str,
    is_empty_gate: bool = False
) -> Dict[str, Any]:
    """Run a single batch and validate response."""
    user_prompt = build_prompt(batch, is_empty_gate)
    input_ids = {r.get("string_id", "") for r in batch}
    system = EMPTY_GATE_PROMPT if is_empty_gate else SYSTEM_PROMPT
    
    start_time = time.time()
    try:
        result = client.chat(
            system=system,
            user=user_prompt,
            temperature=0.0,
            metadata={"step": "gate_test", "model_override": model, "is_batch": False}
        )
        latency_ms = result.latency_ms
        raw_text = result.text.strip()
        
        # Parse response
        parsed = []
        is_json_valid = False
        
        try:
            parsed = json.loads(raw_text)
            if isinstance(parsed, list):
                is_json_valid = True
            elif isinstance(parsed, dict):
                for key in ["results", "items", "data", "translations"]:
                    if key in parsed and isinstance(parsed[key], list):
                        parsed = parsed[key]
                        is_json_valid = True
                        break
        except json.JSONDecodeError:
            # Try to extract array
            match = re.search(r'\[.*\]', raw_text, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(0))
                    is_json_valid = isinstance(parsed, list)
                except:
                    pass
        
        # Validate
        output_ids = set()
        if is_json_valid:
            for item in parsed:
                if isinstance(item, dict) and "string_id" in item:
                    output_ids.add(item["string_id"])
        
        n_to_n = len(parsed) == len(batch) if is_json_valid else False
        id_coverage = len(output_ids & input_ids) / len(input_ids) if input_ids else 0
        
        # For empty gate, also verify empty targets
        empty_valid = True
        if is_empty_gate and is_json_valid:
            for item in parsed:
                if isinstance(item, dict):
                    target = item.get("target_ru", None)
                    if target is not None and target.strip() != "":
                        empty_valid = False
                        break
        
        batch_passed = is_json_valid and n_to_n and id_coverage >= 1.0
        if is_empty_gate:
            batch_passed = batch_passed and empty_valid
        
        return {
            "success": True,
            "passed": batch_passed,
            "json_valid": is_json_valid,
            "n_to_n": n_to_n,
            "id_coverage": id_coverage,
            "input_count": len(batch),
            "output_count": len(parsed) if is_json_valid else 0,
            "latency_ms": latency_ms,
            "error": None,
        }
        
    except Exception as e:
        return {
            "success": False,
            "passed": False,
            "json_valid": False,
            "n_to_n": False,
            "id_coverage": 0,
            "input_count": len(batch),
            "output_count": 0,
            "latency_ms": int((time.time() - start_time) * 1000),
            "error": str(e),
        }


def run_gate_trial(
    client: LLMClient,
    rows: List[Dict[str, str]],
    model: str,
    trial_num: int,
    is_empty_gate: bool = False
) -> TrialResult:
    """Run a single trial (all batches) for a gate."""
    batches = [rows[i:i + BATCH_SIZE] for i in range(0, len(rows), BATCH_SIZE)]
    
    result = TrialResult(
        trial_num=trial_num,
        batches_total=len(batches),
        batches_passed=0,
        json_valid_count=0,
        n_to_n_count=0,
        ids_sent=0,
        ids_received=0,
        latency_ms=0,
        errors=[],
    )
    
    for batch in batches:
        batch_result = run_batch(client, batch, model, is_empty_gate)
        
        result.ids_sent += batch_result["input_count"]
        result.latency_ms += batch_result["latency_ms"]
        
        if batch_result["success"]:
            if batch_result["json_valid"]:
                result.json_valid_count += 1
            if batch_result["n_to_n"]:
                result.n_to_n_count += 1
            result.ids_received += batch_result["output_count"]
            
            if batch_result["passed"]:
                result.batches_passed += 1
        else:
            result.errors.append(batch_result["error"] or "Unknown error")
    
    return result


def run_gate(
    client: LLMClient,
    gate_name: str,
    gate_path: str,
    model: str,
) -> GateResult:
    """Run all trials for a gate."""
    rows = load_gate_data(gate_path)
    csv_sha = calculate_sha256(gate_path)
    is_empty = gate_name == "empty"
    
    gate_result = GateResult(
        gate_name=gate_name,
        model=model,
        csv_sha256=csv_sha,
    )
    
    print(f"    Gate: {gate_name} ({len(rows)} rows, SHA: {csv_sha[:12]}...)")
    
    for trial_num in range(1, TRIALS_PER_GATE + 1):
        print(f"      Trial {trial_num}/{TRIALS_PER_GATE}...", end=" ", flush=True)
        trial = run_gate_trial(client, rows, model, trial_num, is_empty)
        gate_result.trials.append(trial)
        status = "✓ PASS" if trial.passed else "✗ FAIL"
        print(f"{status} ({trial.batches_passed}/{trial.batches_total} batches)")
    
    return gate_result


def run_model(client: LLMClient, model: str, gates: List[str]) -> ModelResult:
    """Run all requested gates for a model."""
    model_result = ModelResult(model=model)
    
    print(f"\n  Model: {model}")
    
    for gate_name in gates:
        gate_path = GATE_FILES.get(gate_name)
        if not gate_path or not os.path.exists(gate_path):
            print(f"    Gate: {gate_name} - SKIPPED (file not found: {gate_path})")
            continue
        
        gate_result = run_gate(client, gate_name, gate_path, model)
        model_result.gates[gate_name] = gate_result
    
    return model_result


def generate_summary_md(results: Dict[str, ModelResult], output_path: str) -> None:
    """Generate markdown summary report."""
    lines = [
        "# Gate Summary Report",
        f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        "## 结果摘要",
        "",
        "| Model | Contract | Reality | Empty | PASS_DUAL |",
        "|:------|:--------:|:-------:|:-----:|:---------:|",
    ]
    
    for model, result in results.items():
        contract = "✓" if result.pass_contract else "✗"
        reality = "✓" if result.pass_reality else "✗"
        empty = "✓" if result.pass_empty else "✗"
        dual = "**PASS**" if result.pass_dual else "FAIL"
        lines.append(f"| {model} | {contract} | {reality} | {empty} | {dual} |")
    
    lines.extend([
        "",
        "## 门禁语义",
        "- **严格 3/3**: 每个 Gate 必须 3 次 Trial 全部通过才算 PASS",
        "- **PASS_DUAL**: Contract Gate + Reality Gate 均通过",
        "",
        "## 详细数据",
        "",
    ])
    
    for model, result in results.items():
        lines.append(f"### {model}")
        for gate_name, gate in result.gates.items():
            lines.append(f"\n#### {gate_name.title()} Gate")
            lines.append(f"- CSV SHA256: `{gate.csv_sha256[:16]}...`")
            lines.append(f"- Trials Passed: {gate.trials_passed}/{STRICT_PASS_REQUIRED}")
            lines.append(f"- Status: {'PASS' if gate.passed else 'FAIL'}")
        lines.append("")
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description="Run Dual Gate tests")
    parser.add_argument("--models", nargs="+", required=True, help="Models to test")
    parser.add_argument("--gate", choices=["contract", "reality", "empty", "all"], 
                        default="all", help="Which gate(s) to run")
    parser.add_argument("--trials", type=int, default=3, help="Trials per gate")
    parser.add_argument("--batch-size", type=int, default=10, help="Batch size")
    parser.add_argument("--api-key-path", help="Path to API key file")
    parser.add_argument("--api-token-path", help="Path to API token file")
    parser.add_argument("--output-dir", default="reports", help="Output directory")
    args = parser.parse_args()
    
    global TRIALS_PER_GATE, BATCH_SIZE, STRICT_PASS_REQUIRED
    TRIALS_PER_GATE = args.trials
    BATCH_SIZE = args.batch_size
    STRICT_PASS_REQUIRED = args.trials
    
    # Resolve credentials
    resolve_api_credentials(args)
    
    # Determine gates to run
    if args.gate == "all":
        gates = ["contract", "reality", "empty"]
    else:
        gates = [args.gate]
    
    # Check gate files exist
    missing = [g for g in gates if not os.path.exists(GATE_FILES.get(g, ""))]
    if missing:
        print(f"Warning: Gate files not found for: {missing}")
        print("Run build_reality_gate.py first to generate Reality/Empty gates.")
    
    # Initialize client
    client = LLMClient()
    
    print("=" * 60)
    print("Dual Gate Runner")
    print(f"Models: {args.models}")
    print(f"Gates: {gates}")
    print(f"Trials: {args.trials} (strict {args.trials}/{args.trials} pass required)")
    print("=" * 60)
    
    # Run tests
    results: Dict[str, ModelResult] = {}
    for model in args.models:
        results[model] = run_model(client, model, gates)
    
    # Generate outputs
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(args.output_dir, f"gate_results_{date_str}.json")
    md_path = os.path.join(args.output_dir, f"gate_summary_{date_str}.md")
    
    # Save JSON
    os.makedirs(args.output_dir, exist_ok=True)
    json_data = {}
    for model, result in results.items():
        json_data[model] = {
            "pass_contract": result.pass_contract,
            "pass_reality": result.pass_reality,
            "pass_empty": result.pass_empty,
            "pass_dual": result.pass_dual,
            "gates": {
                name: {
                    "csv_sha256": gate.csv_sha256,
                    "trials_passed": gate.trials_passed,
                    "passed": gate.passed,
                    "trials": [asdict(t) for t in gate.trials],
                }
                for name, gate in result.gates.items()
            }
        }
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    print(f"\nResults saved to: {json_path}")
    
    # Generate markdown summary
    generate_summary_md(results, md_path)
    print(f"Summary saved to: {md_path}")
    
    # Print final summary
    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("-" * 60)
    for model, result in results.items():
        dual_status = "PASS" if result.pass_dual else "FAIL"
        print(f"{model}: PASS_DUAL={dual_status}")
    print("=" * 60)


if __name__ == "__main__":
    main()
