#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
metrics_aggregator.py

Aggregates LLM usage metrics from trace logs and calculates costs.

Inputs:
  - LLM trace jsonl from runtime_adapter.py (data/llm_trace.jsonl)
  - Pricing config YAML (config/pricing.yaml) - PRIMARY SOURCE
  - Pricing tables (CSV) - optional supplement, Chinese and English
  - translated/repaired CSVs for line counts (optional)

Outputs:
  - data/metrics_summary.json
  - data/metrics_report.md

Usage:
  python scripts/metrics_aggregator.py \
    --trace data/llm_trace.jsonl \
    --pricing_yaml config/pricing.yaml \
    --translated data/translated.csv \
    --repaired data/repaired.csv

Cost Calculation:
  - Prefers usage tokens from LLM response if present
  - Falls back to estimation: tokens ~= ceil(chars / 4)
  - Separates prompt and completion costs
"""

import argparse
import csv
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None


# -------------------------
# Pricing CSV Parsing
# -------------------------

# Chinese pricing table patterns
RE_CN_PROMPT_PRICE = re.compile(r"提示价格[：:]\s*\$?\s*([0-9.]+)\s*/\s*1M", re.I)
RE_CN_COMP_PRICE = re.compile(r"补全价格[：:]\s*\$?\s*([0-9.]+)\s*/\s*1M", re.I)
RE_CN_PROMPT_MULT = re.compile(r"提示倍率[：:]\s*([0-9.]+)", re.I)
RE_CN_COMP_MULT = re.compile(r"补全倍率[：:]\s*([0-9.]+)", re.I)

# English pricing table patterns
RE_EN_PROMPT_PRICE = re.compile(r"(?:Prompt|Input)\s*(?:price)?[：:]?\s*\$?\s*([0-9.]+)\s*/\s*1M", re.I)
RE_EN_COMP_PRICE = re.compile(r"(?:Completion|Output)\s*(?:price)?[：:]?\s*\$?\s*([0-9.]+)\s*/\s*1M", re.I)
RE_EN_PROMPT_MULT = re.compile(r"(?:Prompt|Input)\s*(?:multiplier|ratio)[：:]?\s*([0-9.]+)", re.I)
RE_EN_COMP_MULT = re.compile(r"(?:Completion|Output)\s*(?:multiplier|ratio)[：:]?\s*([0-9.]+)", re.I)


def read_csv_rows(path: str) -> List[Dict[str, str]]:
    """Read CSV file as list of dicts."""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def parse_pricing_rows(rows: List[Dict[str, str]], source_name: str = "") -> Dict[str, dict]:
    """
    Parse pricing rows from CSV.
    Supports both Chinese and English column names.
    
    Returns: model -> {variants: [{prompt_per_1M, completion_per_1M, ...}]}
    """
    out: Dict[str, dict] = {}
    
    for r in rows:
        model = None
        price_text = ""
        mult_text = ""
        group = ""
        is_cn = False
        
        # Try Chinese columns
        if "模型名称" in r:
            model = (r.get("模型名称") or "").strip()
            price_text = r.get("价格") or ""
            mult_text = r.get("倍率") or ""
            group = (r.get("分组") or "").strip()
            is_cn = True
        # Try English columns
        elif "Model Name" in r:
            model = (r.get("Model Name") or "").strip()
            price_text = r.get("Price") or ""
            mult_text = r.get("Magnification") or r.get("Multiplier") or ""
            group = (r.get("Grouping") or r.get("Group") or "").strip()
            is_cn = False
        
        if not model:
            continue
        
        # Parse prices
        if is_cn:
            mp = RE_CN_PROMPT_PRICE.search(price_text)
            mc = RE_CN_COMP_PRICE.search(price_text)
            mmp = RE_CN_PROMPT_MULT.search(mult_text)
            mmc = RE_CN_COMP_MULT.search(mult_text)
        else:
            mp = RE_EN_PROMPT_PRICE.search(price_text)
            mc = RE_EN_COMP_PRICE.search(price_text)
            mmp = RE_EN_PROMPT_MULT.search(mult_text)
            mmc = RE_EN_COMP_MULT.search(mult_text)
        
        # Skip if no completion price found (required)
        if not mc:
            continue
        
        prompt_price = float(mp.group(1)) if mp else None
        comp_price = float(mc.group(1)) if mc else None
        prompt_mult = float(mmp.group(1)) if mmp else None
        comp_mult = float(mmc.group(1)) if mmc else None
        
        out.setdefault(model, {"variants": []})
        out[model]["variants"].append({
            "prompt_per_1M": prompt_price,
            "completion_per_1M": comp_price,
            "prompt_mult": prompt_mult,
            "completion_mult": comp_mult,
            "group": group or None,
            "source": source_name or ("cn" if is_cn else "en"),
        })
    
    return out


def normalize_pricing(pricing: Dict[str, dict]) -> Tuple[Dict[str, dict], List[str]]:
    """
    Cross-validate variants from multiple sources.
    Pick the best variant per model (prefer entries with both prompt and completion prices).
    Return normalized pricing + warnings.
    """
    norm: Dict[str, dict] = {}
    warnings: List[str] = []
    
    for model, blob in pricing.items():
        variants = blob.get("variants", [])
        if not variants:
            continue
        
        # Score variants by completeness
        def score(v):
            s = 0
            if v.get("prompt_per_1M") is not None:
                s += 1
            if v.get("completion_per_1M") is not None:
                s += 1
            if v.get("group"):
                s += 0.1
            return s
        
        variants_sorted = sorted(variants, key=score, reverse=True)
        best = variants_sorted[0]
        
        # Check for inconsistencies across variants
        for v in variants_sorted[1:]:
            for k in ("prompt_per_1M", "completion_per_1M"):
                a = best.get(k)
                b = v.get(k)
                if a is not None and b is not None and abs(float(a) - float(b)) > 1e-9:
                    warnings.append(
                        f"[pricing_mismatch] model={model} {k}: {a} != {b} (source={v.get('source')})"
                    )
        
        norm[model] = {
            "prompt_per_1M": best.get("prompt_per_1M"),
            "completion_per_1M": best.get("completion_per_1M"),
            "prompt_mult": best.get("prompt_mult"),
            "completion_mult": best.get("completion_mult"),
            "group": best.get("group"),
        }
        
        if norm[model]["prompt_per_1M"] is None:
            warnings.append(f"[pricing_missing_prompt] model={model}")
        if norm[model]["completion_per_1M"] is None:
            warnings.append(f"[pricing_missing_completion] model={model}")
    
    return norm, warnings


def load_pricing_yaml(path: str) -> Tuple[Dict[str, dict], List[str], dict, dict]:
    """
    Load pricing from YAML config file.
    Returns: (pricing_dict, warnings, surcharges, billing_config)
    """
    if yaml is None:
        return {}, ["[yaml_error] PyYAML not installed"], {}, {}
    
    if not Path(path).exists():
        return {}, [f"[yaml_error] File not found: {path}"], {}, {}
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except Exception as e:
        return {}, [f"[yaml_error] Failed to parse: {e}"], {}, {}
    
    pricing: Dict[str, dict] = {}
    warnings: List[str] = []
    
    models = data.get("models") or {}
    for model, prices in models.items():
        input_price = prices.get("input_per_1M")
        output_price = prices.get("output_per_1M")
        prompt_mult = prices.get("prompt_mult")
        completion_mult = prices.get("completion_mult")
        
        # Need at least one pricing method
        has_per_1m = input_price is not None or output_price is not None
        has_mult = prompt_mult is not None
        
        if not has_per_1m and not has_mult:
            warnings.append(f"[yaml_warning] model={model} has no prices")
            continue
        
        pricing[model] = {
            "prompt_per_1M": float(input_price) if input_price is not None else None,
            "completion_per_1M": float(output_price) if output_price is not None else None,
            "prompt_mult": float(prompt_mult) if prompt_mult is not None else None,
            "completion_mult": float(completion_mult) if completion_mult is not None else None,
            "group": None,
        }
    
    # Load surcharges
    surcharges = data.get("surcharges") or {}
    
    # Load billing config
    billing = data.get("billing") or {}
    
    return pricing, warnings, surcharges, billing


# -------------------------
# Trace Parsing & Cost
# -------------------------

def read_jsonl(path: str) -> List[dict]:
    """Read JSONL file as list of dicts."""
    if not Path(path).exists():
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def estimate_tokens(chars: int) -> int:
    """
    Estimate tokens from character count.
    Conservative heuristic for mixed zh/en text: ~4 chars per token.
    """
    return int(math.ceil(max(0, chars) / 4.0))


def count_csv_lines(path: Optional[str]) -> Optional[int]:
    """Count data lines in CSV (excluding header)."""
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        return max(0, sum(1 for _ in f) - 1)


def write_json(path: str, obj: Any) -> None:
    """Write JSON file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def write_text(path: str, s: str) -> None:
    """Write text file."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(s)


def main():
    ap = argparse.ArgumentParser(description="Metrics aggregator for LLM usage and costs")
    ap.add_argument("--trace", default="data/llm_trace.jsonl", help="LLM trace JSONL file")
    ap.add_argument("--pricing_yaml", default="config/pricing.yaml", help="Pricing YAML config (primary)")
    ap.add_argument("--pricing_csv", action="append", default=[], help="Additional pricing CSV file(s)")
    ap.add_argument("--translated", default=None, help="Translated CSV for line count")
    ap.add_argument("--repaired", default=None, help="Repaired CSV for line count")
    ap.add_argument("--out_json", default="data/metrics_summary.json", help="Output JSON")
    ap.add_argument("--out_md", default="data/metrics_report.md", help="Output markdown report")
    ap.add_argument("--currency", default="USD", help="Currency label")
    ap.add_argument("--surcharge_per_request", type=float, default=None, help="Fixed surcharge per request (overrides YAML)")
    ap.add_argument("--surcharge_percent", type=float, default=None, help="Percentage surcharge 0.0-1.0 (overrides YAML)")
    args = ap.parse_args()
    
    print(f"📊 Starting Metrics Aggregator...")
    print(f"   Trace: {args.trace}")
    print(f"   Pricing YAML: {args.pricing_yaml}")
    if args.pricing_csv:
        print(f"   Pricing CSVs: {len(args.pricing_csv)}")
    print()
    
    # Load pricing from YAML (primary)
    pricing: Dict[str, dict] = {}
    pricing_warnings: List[str] = []
    surcharge_per_req = 0.0
    surcharge_pct = 0.0
    billing_config: dict = {}
    
    if Path(args.pricing_yaml).exists():
        yaml_pricing, yaml_warnings, surcharges, billing_config = load_pricing_yaml(args.pricing_yaml)
        pricing.update(yaml_pricing)
        pricing_warnings.extend(yaml_warnings)
        surcharge_per_req = surcharges.get("per_request_usd", 0.0) or 0.0
        surcharge_pct = surcharges.get("percent_markup", 0.0) or 0.0
        print(f"✅ Loaded {len(yaml_pricing)} models from {args.pricing_yaml}")
        
        # Show billing mode
        billing_mode = billing_config.get("mode", "per_1m")
        print(f"   Billing mode: {billing_mode}")
    else:
        print(f"⚠️  Pricing YAML not found: {args.pricing_yaml}")
    
    # Load and merge pricing from CSVs (supplement)
    pricing_raw: Dict[str, dict] = {}
    for p in args.pricing_csv:
        if not Path(p).exists():
            print(f"⚠️  Pricing file not found: {p}")
            continue
        rows = read_csv_rows(p)
        parsed = parse_pricing_rows(rows, source_name=Path(p).stem)
        # Merge variants
        for k, v in parsed.items():
            pricing_raw.setdefault(k, {"variants": []})
            pricing_raw[k]["variants"].extend(v.get("variants", []))
        print(f"✅ Loaded {len(parsed)} models from {Path(p).name}")
    
    # Normalize CSV pricing and merge with YAML (YAML takes precedence)
    if pricing_raw:
        csv_pricing, csv_warnings = normalize_pricing(pricing_raw)
        pricing_warnings.extend(csv_warnings)
        for model, prices in csv_pricing.items():
            if model not in pricing:
                pricing[model] = prices
                
    print(f"✅ Total pricing: {len(pricing)} models")
    
    # Calculate conversion rate from billing config
    # conversion_rate = (new_recharge / old_recharge) × (new_group / old_group)
    recharge_rate = billing_config.get("recharge_rate", {})
    group_rate = billing_config.get("group_rate", {})
    conversion_rate = (
        (recharge_rate.get("new", 1.0) / max(recharge_rate.get("old", 1.0), 0.001)) *
        (group_rate.get("new", 1.0) / max(group_rate.get("old", 1.0), 0.001))
    )
    user_group_mult = billing_config.get("user_group_multiplier", 1.0)
    token_divisor = billing_config.get("token_divisor", 500000)
    billing_mode = billing_config.get("mode", "per_1m")  # "multiplier" or "per_1m"
    
    # Apply surcharge overrides from command line
    if args.surcharge_per_request is not None:
        surcharge_per_req = args.surcharge_per_request
    if args.surcharge_percent is not None:
        surcharge_pct = args.surcharge_percent
    
    # Load trace
    events = read_jsonl(args.trace)
    llm_calls = [e for e in events if e.get("type") == "llm_call"]
    print(f"✅ Loaded {len(llm_calls)} LLM calls from trace")
    print()
    
    # Aggregate metrics
    totals = {
        "calls": 0,
        "latency_ms_sum": 0,
        "usage_present_calls": 0,
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "estimated_calls": 0,
        "estimated_prompt_tokens": 0,
        "estimated_completion_tokens": 0,
        "cost": 0.0,
        "cost_estimated_portion": 0.0,
    }
    
    by_model_step: Dict[str, dict] = {}
    missing_pricing_models = set()
    unknown_step_count = 0  # Track calls without proper step metadata
    
    for e in llm_calls:
        model = (e.get("model") or "unknown").strip()
        step = (e.get("step") or "unknown").strip()
        latency_ms = int(e.get("latency_ms") or 0)
        
        # Track unknown steps
        if step == "unknown":
            unknown_step_count += 1
        
        # Get usage from trace
        usage = e.get("usage") or {}
        usage_present = bool(usage) and (
            usage.get("prompt_tokens") is not None or 
            usage.get("completion_tokens") is not None
        )
        
        req_chars = int(e.get("req_chars") or 0)
        resp_chars = int(e.get("resp_chars") or 0)
        
        if usage_present:
            pt = int(usage.get("prompt_tokens") or 0)
            ct = int(usage.get("completion_tokens") or 0)
            tt = int(usage.get("total_tokens") or (pt + ct))
        else:
            # Estimate tokens from character count
            pt = estimate_tokens(req_chars)
            ct = estimate_tokens(resp_chars)
            tt = pt + ct
        
        # Calculate cost based on billing mode
        price = pricing.get(model)
        if not price:
            missing_pricing_models.add(model)
        
        cost = 0.0
        
        if billing_mode == "multiplier" and price:
            # Multiplier formula:
            # cost = conversion_rate × group_rate × model_rate × 
            #        (prompt_tokens + completion_tokens × completion_ratio) / token_divisor
            prompt_mult = price.get("prompt_mult") or 0.0
            completion_mult = price.get("completion_mult") or 1.0
            
            effective_tokens = pt + ct * completion_mult
            cost = conversion_rate * user_group_mult * prompt_mult * effective_tokens / token_divisor
        else:
            # Per-1M token formula (default)
            prompt_per_1M = price.get("prompt_per_1M") if price else None
            comp_per_1M = price.get("completion_per_1M") if price else None
            
            if prompt_per_1M is not None:
                cost += (pt / 1_000_000.0) * float(prompt_per_1M)
            if comp_per_1M is not None:
                cost += (ct / 1_000_000.0) * float(comp_per_1M)
        
        # Apply surcharges
        cost += surcharge_per_req
        cost *= (1.0 + surcharge_pct)
        
        # Update totals
        totals["calls"] += 1
        totals["latency_ms_sum"] += latency_ms
        totals["prompt_tokens"] += pt
        totals["completion_tokens"] += ct
        totals["total_tokens"] += tt
        totals["cost"] += cost
        
        if usage_present:
            totals["usage_present_calls"] += 1
        else:
            totals["estimated_calls"] += 1
            totals["estimated_prompt_tokens"] += pt
            totals["estimated_completion_tokens"] += ct
            totals["cost_estimated_portion"] += cost
        
        # Update by model::step breakdown
        key = f"{model}::{step}"
        by_model_step.setdefault(key, {
            "model": model,
            "step": step,
            "calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
            "usage_present_calls": 0,
            "estimated_calls": 0,
            "latency_ms_sum": 0,
        })
        b = by_model_step[key]
        b["calls"] += 1
        b["prompt_tokens"] += pt
        b["completion_tokens"] += ct
        b["total_tokens"] += tt
        b["cost"] += cost
        b["latency_ms_sum"] += latency_ms
        b["usage_present_calls"] += 1 if usage_present else 0
        b["estimated_calls"] += 0 if usage_present else 1
    
    # Calculate averages for breakdown
    for b in by_model_step.values():
        b["avg_latency_ms"] = b["latency_ms_sum"] / b["calls"] if b["calls"] else 0
        del b["latency_ms_sum"]
    
    # Line counts
    translated_lines = count_csv_lines(args.translated)
    repaired_lines = count_csv_lines(args.repaired)
    denom_lines = repaired_lines or translated_lines
    
    cost_per_1k = None
    if denom_lines and denom_lines > 0:
        cost_per_1k = totals["cost"] / (denom_lines / 1000.0)
    
    usage_rate = None
    if totals["calls"] > 0:
        usage_rate = totals["usage_present_calls"] / totals["calls"]
    
    avg_latency = totals["latency_ms_sum"] / totals["calls"] if totals["calls"] else 0
    
    # Calculate unknown step ratio
    unknown_step_ratio = unknown_step_count / totals["calls"] if totals["calls"] > 0 else 0
    
    # Build summary
    summary = {
        "generated_at": datetime.now().isoformat(),
        "currency": args.currency,
        "trace_file": args.trace,
        "pricing": {
            "models_loaded": len(pricing),
            "warnings": pricing_warnings,
            "missing_models": list(missing_pricing_models),
        },
        "line_counts": {
            "translated_csv": args.translated,
            "translated_lines": translated_lines,
            "repaired_csv": args.repaired,
            "repaired_lines": repaired_lines,
            "denominator_for_per_1k": denom_lines,
        },
        "usage": {
            "total_calls": totals["calls"],
            "usage_present_calls": totals["usage_present_calls"],
            "usage_presence_rate": usage_rate,
            "estimated_calls": totals["estimated_calls"],
            "unknown_step_calls": unknown_step_count,
            "unknown_step_ratio": round(unknown_step_ratio, 4),
            "avg_latency_ms": round(avg_latency, 1),
        },
        "tokens": {
            "prompt_tokens": totals["prompt_tokens"],
            "completion_tokens": totals["completion_tokens"],
            "total_tokens": totals["total_tokens"],
            "estimated_prompt_tokens": totals["estimated_prompt_tokens"],
            "estimated_completion_tokens": totals["estimated_completion_tokens"],
        },
        "cost": {
            "total_cost": round(totals["cost"], 6),
            "cost_estimated_portion": round(totals["cost_estimated_portion"], 6),
            "cost_per_1k_lines": round(cost_per_1k, 6) if cost_per_1k else None,
        },
        "breakdown": sorted(by_model_step.values(), key=lambda x: x["cost"], reverse=True),
    }
    
    write_json(args.out_json, summary)
    print(f"✅ Wrote summary to {args.out_json}")
    
    # Generate Markdown report
    md = []
    md.append("# Localization Metrics Report\n\n")
    md.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
    
    md.append("## Summary\n\n")
    md.append(f"| Metric | Value |\n")
    md.append(f"|--------|-------|\n")
    md.append(f"| Total LLM Calls | {totals['calls']} |\n")
    md.append(f"| Avg Latency | {avg_latency:.1f} ms |\n")
    md.append(f"| Total Tokens | {totals['total_tokens']:,} |\n")
    md.append(f"| Prompt Tokens | {totals['prompt_tokens']:,} |\n")
    md.append(f"| Completion Tokens | {totals['completion_tokens']:,} |\n")
    md.append(f"| Total Cost | ${totals['cost']:.6f} {args.currency} |\n")
    if cost_per_1k:
        md.append(f"| Cost per 1k Lines | ${cost_per_1k:.6f} {args.currency} |\n")
    if usage_rate is not None:
        md.append(f"| Usage Data Present | {usage_rate:.1%} |\n")
    if totals["estimated_calls"] > 0:
        md.append(f"| Estimated Calls | {totals['estimated_calls']} |\n")
    md.append("\n")
    
    if missing_pricing_models:
        md.append("## ⚠️ Missing Pricing\n\n")
        md.append("The following models have no pricing data:\n\n")
        for m in sorted(missing_pricing_models):
            md.append(f"- `{m}`\n")
        md.append("\n")
    
    if pricing_warnings:
        md.append("## Pricing Warnings\n\n")
        for w in pricing_warnings[:20]:
            md.append(f"- {w}\n")
        if len(pricing_warnings) > 20:
            md.append(f"- ... ({len(pricing_warnings) - 20} more)\n")
        md.append("\n")
    
    md.append("## Cost by Model & Step\n\n")
    md.append("| Model | Step | Calls | Tokens | Cost |\n")
    md.append("|-------|------|-------|--------|------|\n")
    for b in summary["breakdown"][:30]:
        md.append(
            f"| {b['model']} | {b['step']} | {b['calls']} | "
            f"{b['total_tokens']:,} | ${b['cost']:.6f} |\n"
        )
    md.append("\n")
    
    # Unknown step warning
    if unknown_step_ratio > 0.01:  # More than 1%
        md.append("## ⚠️ Unknown Step Warning\n\n")
        md.append(f"> **{unknown_step_count}** LLM calls ({unknown_step_ratio:.1%}) have `step=unknown`.\n")
        md.append("> All `llm.chat()` calls should include `metadata={{\"step\": \"...\"}}`\n")
        md.append(">\n")
        md.append("> Valid steps: `translate`, `soft_qa`, `repair`, `glossary_autopromote`\n\n")
    
    write_text(args.out_md, "".join(md))
    print(f"✅ Wrote report to {args.out_md}")
    
    # Print summary
    print()
    print(f"📊 Metrics Summary:")
    print(f"   Calls: {totals['calls']}")
    print(f"   Tokens: {totals['total_tokens']:,}")
    print(f"   Cost: ${totals['cost']:.6f} {args.currency}")
    if cost_per_1k:
        print(f"   Per 1k lines: ${cost_per_1k:.6f}")
    print()
    print("✅ Metrics aggregation complete!")
    
    return 0


if __name__ == "__main__":
    exit(main())
