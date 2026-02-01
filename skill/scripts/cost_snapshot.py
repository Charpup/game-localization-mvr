#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cost_snapshot.py

Aggregate LLM trace into cost snapshots.
- Read trace JSONL
- Filter by run_id and time window
- Aggregate by step/model
- Detect anomalies (completion hits max_tokens)
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


def load_trace(trace_path: str) -> List[Dict[str, Any]]:
    """Load all trace entries from JSONL file."""
    entries = []
    if not Path(trace_path).exists():
        return entries
    
    with open(trace_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("type") == "llm_call":
                    entries.append(entry)
            except json.JSONDecodeError:
                continue
    return entries


def filter_entries(
    entries: List[Dict[str, Any]],
    run_id: Optional[str] = None,
    start_ts: Optional[str] = None,
    end_ts: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Filter trace entries by run_id and time window."""
    filtered = []
    for entry in entries:
        # Filter by run_id
        if run_id and entry.get("run_id") != run_id:
            continue
        
        # Filter by time window
        entry_ts = entry.get("ts") or entry.get("timestamp")
        if entry_ts:
            if start_ts and entry_ts < start_ts:
                continue
            if end_ts and entry_ts > end_ts:
                continue
        
        filtered.append(entry)
    return filtered


def detect_completion_anomalies(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Detect entries where completion_tokens >= 98% of max_tokens."""
    anomaly_entries = []
    step_counts = {}
    model_counts = {}
    
    for entry in entries:
        max_tokens = entry.get("max_tokens")
        completion = entry.get("completion_tokens", 0)
        
        if max_tokens and max_tokens > 0:
            if completion >= 0.98 * max_tokens:
                anomaly_entries.append(entry)
                step = entry.get("step", "unknown")
                model = entry.get("selected_model", "unknown")
                step_counts[step] = step_counts.get(step, 0) + 1
                model_counts[model] = model_counts.get(model, 0) + 1
    
    total = len(entries)
    count = len(anomaly_entries)
    ratio = count / total if total > 0 else 0
    
    # Top steps and models
    top_steps = sorted(step_counts.keys(), key=lambda k: step_counts[k], reverse=True)[:5]
    top_models = sorted(model_counts.keys(), key=lambda k: model_counts[k], reverse=True)[:5]
    
    return {
        "count": count,
        "ratio": round(ratio, 4),
        "top_steps": top_steps,
        "top_models": top_models
    }


def aggregate_trace(
    trace_path: str,
    run_id: Optional[str] = None,
    start_ts: Optional[str] = None,
    end_ts: Optional[str] = None
) -> Dict[str, Any]:
    """
    Aggregate trace into cost summary.
    
    Returns snapshot dict with local costs, by_step breakdown, and anomalies.
    """
    entries = load_trace(trace_path)
    entries = filter_entries(entries, run_id, start_ts, end_ts)
    
    if not entries:
        return {
            "run_id": run_id or "unknown",
            "window": {"start_ts": start_ts, "end_ts": end_ts},
            "local": {
                "total_calls": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "total_cost_usd_est": 0,
                "by_step": {}
            },
            "anomalies": {"completion_hits_max_tokens": {"count": 0, "ratio": 0}}
        }
    
    # Aggregate totals
    total_prompt = 0
    total_completion = 0
    total_cost = 0
    by_step: Dict[str, Dict[str, Any]] = {}
    by_model: Dict[str, Dict[str, Any]] = {}
    
    for entry in entries:
        prompt = entry.get("prompt_tokens", 0)
        completion = entry.get("completion_tokens", 0)
        cost = entry.get("cost_usd_est", 0)
        step = entry.get("step", "unknown")
        model = entry.get("selected_model", "unknown")
        
        total_prompt += prompt
        total_completion += completion
        total_cost += cost
        
        # By step
        if step not in by_step:
            by_step[step] = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd_est": 0}
        by_step[step]["calls"] += 1
        by_step[step]["prompt_tokens"] += prompt
        by_step[step]["completion_tokens"] += completion
        by_step[step]["cost_usd_est"] += cost
        
        # By model
        if model not in by_model:
            by_model[model] = {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd_est": 0}
        by_model[model]["calls"] += 1
        by_model[model]["prompt_tokens"] += prompt
        by_model[model]["completion_tokens"] += completion
        by_model[model]["cost_usd_est"] += cost
    
    # Round costs
    for step_data in by_step.values():
        step_data["cost_usd_est"] = round(step_data["cost_usd_est"], 4)
    for model_data in by_model.values():
        model_data["cost_usd_est"] = round(model_data["cost_usd_est"], 4)
    
    # Detect anomalies
    anomalies = {
        "completion_hits_max_tokens": detect_completion_anomalies(entries)
    }
    
    # Determine actual time window from entries
    timestamps = [e.get("ts") or e.get("timestamp") for e in entries if e.get("ts") or e.get("timestamp")]
    actual_start = min(timestamps) if timestamps else start_ts
    actual_end = max(timestamps) if timestamps else end_ts
    
    return {
        "run_id": run_id or entries[0].get("run_id", "unknown"),
        "window": {
            "start_ts": actual_start,
            "end_ts": actual_end
        },
        "local": {
            "total_calls": len(entries),
            "total_prompt_tokens": total_prompt,
            "total_completion_tokens": total_completion,
            "total_cost_usd_est": round(total_cost, 4),
            "by_step": by_step,
            "by_model": by_model
        },
        "anomalies": anomalies
    }


def save_snapshot(
    snapshot: Dict[str, Any],
    output_dir: str = "reports/cost"
) -> str:
    """Save snapshot to JSON file."""
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    run_id = snapshot.get("run_id", "unknown")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"snapshot_{run_id}_{ts}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)
    
    return filepath


def generate_report_md(snapshot: Dict[str, Any]) -> str:
    """Generate markdown reconcile report."""
    lines = ["# Cost Reconciliation Report", ""]
    
    run_id = snapshot.get("run_id", "unknown")
    window = snapshot.get("window", {})
    local = snapshot.get("local", {})
    anomalies = snapshot.get("anomalies", {})
    
    # Summary
    lines.append("## Summary")
    lines.append(f"- **Run ID**: `{run_id}`")
    lines.append(f"- **Window**: {window.get('start_ts', 'N/A')} → {window.get('end_ts', 'N/A')}")
    lines.append(f"- **Total Calls**: {local.get('total_calls', 0)}")
    lines.append(f"- **Total Prompt Tokens**: {local.get('total_prompt_tokens', 0):,}")
    lines.append(f"- **Total Completion Tokens**: {local.get('total_completion_tokens', 0):,}")
    lines.append(f"- **Estimated Cost (USD)**: ${local.get('total_cost_usd_est', 0):.4f}")
    lines.append("")
    
    # By Step
    lines.append("## Cost by Step")
    lines.append("| Step | Calls | Prompt Tokens | Completion Tokens | Cost (USD) |")
    lines.append("|------|-------|---------------|-------------------|------------|")
    by_step = local.get("by_step", {})
    for step, data in sorted(by_step.items(), key=lambda x: x[1].get("cost_usd_est", 0), reverse=True):
        lines.append(f"| {step} | {data.get('calls', 0)} | {data.get('prompt_tokens', 0):,} | {data.get('completion_tokens', 0):,} | ${data.get('cost_usd_est', 0):.4f} |")
    lines.append("")
    
    # By Model
    lines.append("## Cost by Model")
    lines.append("| Model | Calls | Prompt Tokens | Completion Tokens | Cost (USD) |")
    lines.append("|-------|-------|---------------|-------------------|------------|")
    by_model = local.get("by_model", {})
    for model, data in sorted(by_model.items(), key=lambda x: x[1].get("cost_usd_est", 0), reverse=True):
        lines.append(f"| {model} | {data.get('calls', 0)} | {data.get('prompt_tokens', 0):,} | {data.get('completion_tokens', 0):,} | ${data.get('cost_usd_est', 0):.4f} |")
    lines.append("")
    
    # Anomalies
    lines.append("## Anomalies")
    completion_hits = anomalies.get("completion_hits_max_tokens", {})
    count = completion_hits.get("count", 0)
    ratio = completion_hits.get("ratio", 0)
    
    if ratio > 0.01:
        lines.append(f"> [!WARNING]")
        lines.append(f"> **Completion hits max_tokens**: {count} calls ({ratio*100:.2f}%)")
    elif count > 0:
        lines.append(f"> [!NOTE]")
        lines.append(f"> Completion hits max_tokens: {count} calls ({ratio*100:.2f}%)")
    else:
        lines.append("No anomalies detected.")
    
    if completion_hits.get("top_steps"):
        lines.append(f"- Top steps: {', '.join(completion_hits['top_steps'])}")
    if completion_hits.get("top_models"):
        lines.append(f"- Top models: {', '.join(completion_hits['top_models'])}")
    lines.append("")
    
    return "\n".join(lines)


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Generate cost snapshot from LLM trace")
    parser.add_argument("--trace", default="data/llm_trace.jsonl", help="Trace JSONL path")
    parser.add_argument("--run_id", help="Filter by run_id")
    parser.add_argument("--start", help="Start timestamp (ISO format)")
    parser.add_argument("--end", help="End timestamp (ISO format)")
    parser.add_argument("--output_dir", default="reports/cost", help="Output directory")
    
    args = parser.parse_args()
    
    print(f"📊 Generating cost snapshot...")
    print(f"   Trace: {args.trace}")
    
    snapshot = aggregate_trace(args.trace, args.run_id, args.start, args.end)
    
    # Save JSON
    json_path = save_snapshot(snapshot, args.output_dir)
    print(f"   Snapshot: {json_path}")
    
    # Save MD report
    md_content = generate_report_md(snapshot)
    md_path = os.path.join(args.output_dir, "reconcile_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"   Report: {md_path}")
    
    # Print summary
    local = snapshot.get("local", {})
    print()
    print(f"✅ Summary:")
    print(f"   Calls: {local.get('total_calls', 0)}")
    print(f"   Cost: ${local.get('total_cost_usd_est', 0):.4f}")


if __name__ == "__main__":
    main()
