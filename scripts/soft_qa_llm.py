#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
soft_qa_llm.py (v2.0 - Batch Mode)
LLM-based soft quality review for translations.

Purpose:
  Soft QA 的价值不是"打分"，而是输出可执行的 repair tasks，让 repair loop 能自动修。
  评审维度：style_officialness, anime_tone, terminology_consistency, ui_brevity, ambiguity

  BATCH processing: multiple items per LLM call to reduce prompt token waste.

Usage:
  python scripts/soft_qa_llm.py \\
    data/translated.csv workflow/style_guide.md data/glossary.yaml workflow/soft_qa_rubric.yaml \\
    --batch_size 15 --out_report data/qa_soft_report.json --out_tasks data/repair_tasks.jsonl

Environment:
  LLM_BASE_URL, LLM_API_KEY, LLM_MODEL (via runtime_adapter)
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import yaml
except Exception:
    yaml = None

from runtime_adapter import LLMClient, LLMError

# Import batch utilities
try:
    from batch_utils import (
        BatchConfig, split_into_batches, parse_json_array, format_progress
    )
except ImportError:
    print("ERROR: batch_utils.py not found. Please ensure it exists in scripts/")
    sys.exit(1)

TOKEN_RE = re.compile(r"⟦(PH_\d+|TAG_\d+)⟧")


def load_text(p: str) -> str:
    """Load text file content."""
    with open(p, "r", encoding="utf-8") as f:
        return f.read().strip()


def load_yaml(p: str) -> dict:
    """Load YAML file."""
    if yaml is None:
        raise RuntimeError("PyYAML required: pip install pyyaml")
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def read_csv(p: str) -> List[Dict[str, str]]:
    """Read CSV file as list of dicts."""
    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_json(p: str, obj: Any) -> None:
    """Write JSON file."""
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def append_jsonl(p: str, items: List[dict]) -> None:
    """Append items to JSONL file."""
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


def token_counts(s: str) -> Dict[str, int]:
    """Count tokens in string."""
    d = {}
    for m in TOKEN_RE.finditer(s or ""):
        k = m.group(1)
        d[k] = d.get(k, 0) + 1
    return d


# Import glossary logic from translate_llm
from translate_llm import load_glossary, build_glossary_constraints, GlossaryEntry


def build_system_batch(style: str, glossary_summary: str) -> str:
    """Build system prompt for batch soft QA."""
    return (
        "你是手游本地化软质检（zh-CN → ru-RU）。\n\n"
        "输入：JSON 数组，每项包含 string_id、source_zh、target_ru。\n"
        "输出：JSON 对象，包含 tasks 数组，仅列出有问题的项。\n\n"
        "检查维度（只报问题，不要夸）：\n"
        "- 术语一致性（glossary）\n"
        "- 语气：官方为主，二次元口语为辅（避免过度口语或过度书面）\n"
        "- UI 简洁性（冗长/重复/不自然）\n"
        "- 歧义/误译/信息缺失\n"
        "- 标点与符号：禁止【】；占位符必须完整\n\n"
        "输出格式（硬性，仅输出 JSON）：\n"
        "{\n"
        '  "tasks": [\n'
        "    {\n"
        '      "string_id": "<id>",\n'
        '      "severity": "minor|major",\n'
        '      "issue_type": "terminology|tone|brevity|ambiguity|mistranslation|format|punctuation",\n'
        '      "problem": "<一句话描述问题>",\n'
        '      "suggestion": "<一句话给出修复方向>",\n'
        '      "preferred_fix_ru": "<可选：建议的修复后俄文>"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "规则：\n"
        '- 没问题则输出 { "tasks": [] }。\n'
        "- problem/suggestion 必须短句。\n"
        "- 每个有问题的 string_id 只输出一个最严重的 task。\n\n"
        f"术语表摘要（前 50 条）：\n{glossary_summary[:1500]}\n\n"
        f"style_guide（节选）：\n{style[:1000]}\n"
    )


def build_batch_input(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Build batch input for soft QA."""
    batch_items = []
    for row in rows:
        batch_items.append({
            "string_id": row.get("string_id", ""),
            "source_zh": row.get("source_zh", "") or row.get("tokenized_zh", ""),
            "target_ru": row.get("target_text", "")
        })
    return batch_items


def build_glossary_summary(entries: List[GlossaryEntry], max_entries: int = 50) -> str:
    """Build compact glossary summary."""
    approved = [e for e in entries if e.status.lower() == "approved"][:max_entries]
    if not approved:
        return "(无)"
    lines = [f"- {e.term_zh} → {e.term_ru}" for e in approved]
    return "\n".join(lines)


def extract_tasks_from_response(text: str) -> List[dict]:
    """Extract tasks array from LLM response."""
    text = (text or "").strip()
    
    # Try direct parse
    try:
        obj = json.loads(text)
        if isinstance(obj, dict) and "tasks" in obj:
            return obj["tasks"]
    except json.JSONDecodeError:
        pass
    
    # Find { ... } block
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            obj = json.loads(text[start:end + 1])
            if isinstance(obj, dict) and "tasks" in obj:
                return obj["tasks"]
        except json.JSONDecodeError:
            pass
    
    return []


def process_batch(
    batch: List[Dict[str, str]],
    llm: LLMClient,
    style: str,
    glossary_summary: str,
    batch_idx: int,
    max_retries: int = 2
) -> List[dict]:
    """
    Process a batch of rows through soft QA.
    
    Returns:
        List of task dicts (only problem items)
    """
    if not batch:
        return []
    
    system = build_system_batch(style, glossary_summary)
    batch_input = build_batch_input(batch)
    user_prompt = json.dumps(batch_input, ensure_ascii=False, indent=None)
    
    for attempt in range(max_retries + 1):
        try:
            result = llm.chat(
                system=system,
                user=user_prompt,
                temperature=0.1,
                metadata={
                    "step": "soft_qa",
                    "batch_idx": batch_idx,
                    "batch_size": len(batch),
                    "attempt": attempt
                },
                response_format={"type": "json_object"}
            )
            
            tasks = extract_tasks_from_response(result.text)
            
            # Normalize tasks
            valid_tasks = []
            for t in tasks:
                valid_tasks.append({
                    "string_id": t.get("string_id", ""),
                    "type": t.get("issue_type", "issue"),
                    "severity": t.get("severity", "minor"),
                    "note": f"{t.get('problem', '')} | Suggestion: {t.get('suggestion', '')}",
                    "suggested_fix": t.get("preferred_fix_ru", ""),
                })
            
            return valid_tasks
            
        except Exception as e:
            if attempt >= max_retries:
                print(f"    ⚠️ Batch {batch_idx} error: {e}")
                return []
            time.sleep(1)
    
    return []


def main():
    ap = argparse.ArgumentParser(description="LLM-based soft QA (Batch Mode v2.0)")
    ap.add_argument("translated_csv", help="Input translated.csv")
    ap.add_argument("style_guide_md", help="Style guide file")
    ap.add_argument("glossary_yaml", help="Glossary file")
    ap.add_argument("rubric_yaml", help="Soft QA rubric config (legacy, ignored)")
    ap.add_argument("--batch_size", type=int, default=15, help="Items per batch")
    ap.add_argument("--max_batch_tokens", type=int, default=4000, help="Max tokens per batch")
    ap.add_argument("--out_report", default="data/qa_soft_report.json", help="Output report JSON")
    ap.add_argument("--out_tasks", default="data/repair_tasks.jsonl", help="Output repair tasks JSONL")
    ap.add_argument("--dry-run", action="store_true", 
                    help="Validate configuration without making LLM calls")
    args = ap.parse_args()

    print(f"🔍 Soft QA v2.0 (Batch Mode)")
    print(f"   Input: {args.translated_csv}")
    print(f"   Batch size: {args.batch_size}")
    print()

    # Load resources
    rows = read_csv(args.translated_csv)
    style = load_text(args.style_guide_md)

    glossary_path = args.glossary_yaml
    glossary_entries = []
    if glossary_path and Path(glossary_path).exists():
        glossary_entries, _ = load_glossary(glossary_path)
    
    glossary_summary = build_glossary_summary(glossary_entries)
    
    print(f"✅ Loaded {len(rows)} rows")
    print(f"   Glossary: {len(glossary_entries)} entries")
    
    # Filter rows with target_text
    rows_with_target = [r for r in rows if r.get("target_text")]
    print(f"   Rows with translations: {len(rows_with_target)}")
    
    # Dry-run mode
    if getattr(args, 'dry_run', False):
        print()
        print("=" * 60)
        print("DRY-RUN MODE - Validation Summary")
        print("=" * 60)
        
        config = BatchConfig(max_items=args.batch_size, max_tokens=args.max_batch_tokens)
        config.text_fields = ["source_zh", "tokenized_zh", "target_text"]
        batches = split_into_batches(rows_with_target, config)
        
        print(f"[OK] Would create {len(batches)} batches")
        print(f"[OK] Average batch size: {len(rows_with_target) / max(1, len(batches)):.1f}")
        print()
        print("[OK] Dry-run validation PASSED")
        print("=" * 60)
        return 0

    # Initialize LLM
    try:
        llm = LLMClient()
        print(f"✅ LLM: {llm.default_model}")
    except LLMError as e:
        print(f"❌ LLM Error: {e}")
        return 1

    print()

    # Clean output file (fresh start)
    if Path(args.out_tasks).exists():
        Path(args.out_tasks).unlink()

    # Split into batches
    config = BatchConfig(max_items=args.batch_size, max_tokens=args.max_batch_tokens)
    config.text_fields = ["source_zh", "tokenized_zh", "target_text"]
    batches = split_into_batches(rows_with_target, config)
    print(f"   Batches: {len(batches)}")
    print()

    # Process batches
    start_time = time.time()
    major = 0
    minor = 0
    all_tasks = 0
    batch_errors = 0

    for batch_idx, batch in enumerate(batches):
        batch_start = time.time()
        
        tasks = process_batch(
            batch, llm, style, glossary_summary, batch_idx
        )
        
        if tasks:
            append_jsonl(args.out_tasks, tasks)
            all_tasks += len(tasks)
            for t in tasks:
                if t.get("severity") == "major":
                    major += 1
                else:
                    minor += 1
        
        # Progress
        batch_time = time.time() - batch_start
        elapsed = time.time() - start_time
        
        if (batch_idx + 1) % 5 == 0 or batch_idx == len(batches) - 1:
            print(format_progress(
                batch_idx + 1, len(batches), batch_idx + 1, len(batches),
                elapsed, batch_time
            ))

    # Write report
    report = {
        "version": "2.0",
        "mode": "batch",
        "has_findings": (major + minor) > 0,
        "summary": {
            "major": major,
            "minor": minor,
            "total_tasks": all_tasks,
            "batch_errors": batch_errors,
            "rows_processed": len(rows_with_target),
            "batches_processed": len(batches),
        },
        "outputs": {
            "repair_tasks_jsonl": args.out_tasks,
        },
    }
    write_json(args.out_report, report)

    # Print summary
    total_elapsed = time.time() - start_time
    print()
    print(f"📊 Soft QA Summary:")
    print(f"   Rows processed: {len(rows_with_target)}")
    print(f"   Major issues: {major}")
    print(f"   Minor issues: {minor}")
    print(f"   Total tasks: {all_tasks}")
    print(f"   Total time: {int(total_elapsed)}s")
    print()
    print(f"✅ Report: {args.out_report}")
    if all_tasks > 0:
        print(f"✅ Repair tasks: {args.out_tasks}")

    return 0


if __name__ == "__main__":
    exit(main())
