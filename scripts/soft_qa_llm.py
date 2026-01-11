#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
soft_qa_llm.py
LLM-based soft quality assessment for translations.

Purpose:
  - Evaluate translation quality on multiple dimensions (fluency, accuracy, terminology, style)
  - Generate detailed quality report with scores and issues
  - Create repair tasks for items below threshold

Usage:
  python scripts/soft_qa_llm.py \
    data/translated.csv data/qa_soft_report.json \
    workflow/soft_qa_rubric.yaml data/glossary.yaml \
    --repair_tasks data/repair_tasks.jsonl

Environment:
  LLM_BASE_URL, LLM_API_KEY, LLM_MODEL (via runtime_adapter)
"""

import argparse
import csv
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

try:
    import yaml
except ImportError:
    yaml = None

from runtime_adapter import LLMClient, LLMError


def load_rubric(path: str) -> dict:
    """Load soft QA rubric configuration."""
    if yaml is None:
        raise RuntimeError("PyYAML required. Install with: pip install pyyaml")
    with open(path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_glossary_context(path: str, source_text: str) -> str:
    """Load glossary entries relevant to source text for context."""
    if not path or not Path(path).exists():
        return ""
    if yaml is None:
        return ""
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    
    entries = data.get("entries", [])
    relevant = []
    for e in entries:
        term_zh = e.get("term_zh", "")
        if term_zh and term_zh in source_text:
            term_ru = e.get("term_ru", "")
            status = e.get("status", "proposed")
            relevant.append(f"{term_zh} → {term_ru} ({status})")
    
    return "; ".join(relevant) if relevant else "无相关术语"


def read_csv_rows(path: str) -> List[Dict[str, str]]:
    """Read CSV file into list of dicts."""
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def extract_json_object(text: str) -> Optional[dict]:
    """Extract JSON object from LLM response."""
    text = (text or "").strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    
    # Find { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(text[start:end+1])
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
    return None


def evaluate_row(llm: LLMClient, rubric: dict, row: Dict[str, str], 
                 glossary_context: str) -> Dict[str, Any]:
    """
    Evaluate a single translation row with LLM.
    
    Returns dict with scores, issues, and suggestion.
    """
    source_text = row.get("source_zh") or row.get("tokenized_zh", "")
    target_text = row.get("target_text", "")
    string_id = row.get("string_id", "unknown")
    
    # Build prompt from rubric template
    prompt_template = rubric.get("prompt_template", "")
    target_lang = rubric.get("target_language", "ru-RU")
    
    user_prompt = prompt_template.format(
        source_text=source_text,
        target_text=target_text,
        target_lang=target_lang,
        glossary_context=glossary_context
    )
    
    system_prompt = "你是一位资深的游戏本地化质量审核专家。请按要求输出 JSON 评审结果。"
    
    try:
        result = llm.chat(system=system_prompt, user=user_prompt)
        response = extract_json_object(result.text)
        
        if response and "scores" in response:
            return {
                "string_id": string_id,
                "scores": response.get("scores", {}),
                "issues": response.get("issues", []),
                "suggestion": response.get("suggestion", ""),
                "status": "evaluated"
            }
        else:
            return {
                "string_id": string_id,
                "scores": {},
                "issues": ["LLM返回格式错误"],
                "suggestion": "",
                "status": "parse_error"
            }
    except LLMError as e:
        return {
            "string_id": string_id,
            "scores": {},
            "issues": [f"LLM调用失败: {e.kind}"],
            "suggestion": "",
            "status": "llm_error"
        }


def calculate_overall_score(scores: Dict[str, int], dimensions: dict) -> float:
    """Calculate weighted average score."""
    if not scores:
        return 0.0
    
    total_weight = 0.0
    weighted_sum = 0.0
    
    for dim, config in dimensions.items():
        weight = config.get("weight", 0.25)
        score = scores.get(dim, 0)
        if score:
            weighted_sum += weight * score
            total_weight += weight
    
    return weighted_sum / total_weight if total_weight > 0 else 0.0


def should_repair(scores: Dict[str, int], overall: float, rubric: dict) -> bool:
    """Determine if translation needs repair based on thresholds."""
    thresholds = rubric.get("thresholds", {})
    fail_threshold = thresholds.get("fail", 2.5)
    
    # Check overall score
    if overall < fail_threshold:
        return True
    
    # Check individual dimension triggers
    dimensions = rubric.get("dimensions", {})
    for dim, config in dimensions.items():
        warn_threshold = config.get("warn_threshold", 2)
        if scores.get(dim, 5) < warn_threshold:
            return True
    
    return False


def main():
    parser = argparse.ArgumentParser(description="LLM-based soft QA for translations")
    parser.add_argument("translated_csv", help="Input translated.csv")
    parser.add_argument("report_json", help="Output qa_soft_report.json")
    parser.add_argument("rubric_yaml", help="Soft QA rubric config")
    parser.add_argument("glossary_yaml", help="Glossary for context (optional)", nargs="?", default="")
    parser.add_argument("--repair_tasks", default="data/repair_tasks.jsonl", 
                        help="Output repair tasks file")
    parser.add_argument("--sample_rate", type=float, default=1.0,
                        help="Fraction of rows to evaluate (0.0-1.0)")
    parser.add_argument("--batch_size", type=int, default=1,
                        help="Rows per LLM call (default: 1 for detailed eval)")
    args = parser.parse_args()
    
    print(f"🔍 Starting Soft QA v1.0...")
    print(f"   Input: {args.translated_csv}")
    print(f"   Rubric: {args.rubric_yaml}")
    print(f"   Sample rate: {args.sample_rate}")
    print()
    
    # Load resources
    rubric = load_rubric(args.rubric_yaml)
    rows = read_csv_rows(args.translated_csv)
    
    if not rows:
        print("❌ No rows found in input.")
        sys.exit(1)
    
    # Initialize LLM
    try:
        llm = LLMClient()
        print(f"✅ Using LLM: {llm.model}")
    except LLMError as e:
        print(f"❌ LLM Error: {e}")
        sys.exit(2)
    
    # Sample rows if needed
    import random
    if args.sample_rate < 1.0:
        sample_size = max(1, int(len(rows) * args.sample_rate))
        rows = random.sample(rows, sample_size)
        print(f"✅ Sampled {sample_size} rows for evaluation")
    
    # Evaluate each row
    evaluations = []
    repair_tasks = []
    dimensions = rubric.get("dimensions", {})
    
    for idx, row in enumerate(rows, 1):
        string_id = row.get("string_id", "")
        source_text = row.get("source_zh") or row.get("tokenized_zh", "")
        
        # Get glossary context for this row
        glossary_context = load_glossary_context(args.glossary_yaml, source_text)
        
        # Evaluate
        eval_result = evaluate_row(llm, rubric, row, glossary_context)
        
        # Calculate overall score
        overall = calculate_overall_score(eval_result["scores"], dimensions)
        eval_result["overall_score"] = round(overall, 2)
        
        # Determine status
        thresholds = rubric.get("thresholds", {})
        if overall >= thresholds.get("pass", 3.5):
            eval_result["verdict"] = "pass"
        elif overall >= thresholds.get("warn", 2.5):
            eval_result["verdict"] = "warn"
        else:
            eval_result["verdict"] = "fail"
        
        evaluations.append(eval_result)
        
        # Create repair task if needed
        if should_repair(eval_result["scores"], overall, rubric):
            repair_tasks.append({
                "string_id": string_id,
                "source_zh": source_text,
                "target_text": row.get("target_text", ""),
                "issues": eval_result["issues"],
                "suggestion": eval_result["suggestion"],
                "scores": eval_result["scores"],
                "overall_score": overall
            })
        
        if idx % 10 == 0:
            print(f"  [PROGRESS] {idx}/{len(rows)}")
    
    # Calculate summary stats
    pass_count = sum(1 for e in evaluations if e.get("verdict") == "pass")
    warn_count = sum(1 for e in evaluations if e.get("verdict") == "warn")
    fail_count = sum(1 for e in evaluations if e.get("verdict") == "fail")
    avg_overall = sum(e.get("overall_score", 0) for e in evaluations) / len(evaluations) if evaluations else 0
    
    # Build report
    report = {
        "metadata": {
            "version": "1.0",
            "generated_at": datetime.now().isoformat(),
            "input_file": args.translated_csv,
            "rubric_file": args.rubric_yaml,
            "total_evaluated": len(evaluations),
            "sample_rate": args.sample_rate
        },
        "summary": {
            "pass": pass_count,
            "warn": warn_count,
            "fail": fail_count,
            "average_score": round(avg_overall, 2),
            "repair_needed": len(repair_tasks)
        },
        "evaluations": evaluations
    }
    
    # Write report
    Path(args.report_json).parent.mkdir(parents=True, exist_ok=True)
    with open(args.report_json, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"✅ Wrote report to {args.report_json}")
    
    # Write repair tasks
    if repair_tasks:
        Path(args.repair_tasks).parent.mkdir(parents=True, exist_ok=True)
        with open(args.repair_tasks, 'w', encoding='utf-8') as f:
            for task in repair_tasks:
                f.write(json.dumps(task, ensure_ascii=False) + "\n")
        print(f"✅ Wrote {len(repair_tasks)} repair tasks to {args.repair_tasks}")
    
    # Print summary
    print()
    print(f"📊 Soft QA Summary:")
    print(f"   Total evaluated: {len(evaluations)}")
    print(f"   Pass: {pass_count} ({100*pass_count/len(evaluations):.1f}%)")
    print(f"   Warn: {warn_count} ({100*warn_count/len(evaluations):.1f}%)")
    print(f"   Fail: {fail_count} ({100*fail_count/len(evaluations):.1f}%)")
    print(f"   Average score: {avg_overall:.2f}/5.0")
    print(f"   Repair needed: {len(repair_tasks)}")
    print()
    print("✅ Soft QA complete!")


if __name__ == "__main__":
    main()
