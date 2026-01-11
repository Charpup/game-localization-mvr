#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
soft_qa_llm.py
LLM-based soft quality review for translations.

Purpose:
  Soft QA 的价值不是"打分"，而是输出可执行的 repair tasks，让 repair loop 能自动修。
  评审维度：style_officialness, anime_tone, terminology_consistency, ui_brevity, ambiguity

Usage:
  python scripts/soft_qa_llm.py \
    data/translated.csv workflow/style_guide.md data/glossary.yaml workflow/soft_qa_rubric.yaml \
    --batch_size 40 --out_report data/qa_soft_report.json --out_tasks data/repair_tasks.jsonl

Environment:
  LLM_BASE_URL, LLM_API_KEY, LLM_MODEL (via runtime_adapter)
"""

import argparse
import csv
import json
import os
import re
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import yaml
except Exception:
    yaml = None

from runtime_adapter import LLMClient, LLMError

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


def build_system(style: str) -> str:
    """Build system prompt for soft QA."""
    return (
        "你是资深游戏本地化语言 QA（ru-RU）。\n"
        "你只做'软质量评审'：风格、术语一致性、UI可读性、歧义风险。\n"
        "注意：不可变 token（⟦PH_x⟧/⟦TAG_x⟧）必须保留；你不能要求删除 token。\n"
        "输出必须是 JSON，不要解释文本。\n\n"
        "风格规范：\n" + style
    )


def build_user(batch: List[Dict[str, str]], glossary_text: str, rubric: dict) -> str:
    """Build user prompt for soft QA batch."""
    # Extract dimension keys and descriptions for stable prompting
    dims = rubric.get("dimensions", [])
    dim_desc = [{"key": d["key"], "description": d["description"]} for d in dims]

    payload = []
    for r in batch:
        payload.append({
            "string_id": r.get("string_id", ""),
            "source_zh": r.get("source_zh", ""),
            "tokenized_zh": r.get("tokenized_zh", ""),
            "target_text": r.get("target_text", ""),
        })

    return (
        "请对以下条目做软质量评审，输出 JSON：\n"
        "{\n"
        "  \"items\": [\n"
        "    {\"string_id\": \"...\", \"issues\": [\n"
        "        {\"dimension\": \"...\", \"severity\": \"minor|major\", \"note\": \"...\", \"suggested_fix\": \"...\"}\n"
        "    ]}\n"
        "  ],\n"
        "  \"summary\": {\"major\": 0, \"minor\": 0}\n"
        "}\n\n"
        "规则：\n"
        "- 如果条目没有问题，issues 数组为空 []\n"
        "- dimension 只能是以下之一：style_officialness, anime_tone, terminology_consistency, ui_brevity, ambiguity\n"
        "- severity 只能是 minor 或 major\n"
        "- suggested_fix 应该是修复后的完整译文（保留所有 token）\n\n"
        f"评审维度：{json.dumps(dim_desc, ensure_ascii=False)}\n\n"
        "术语表（参考；approved 必须遵守）：\n"
        f"{glossary_text[:4000]}\n\n"
        "条目：\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def extract_json(text: str) -> Optional[dict]:
    """Extract JSON object from LLM response."""
    text = (text or "").strip()
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    
    # Fallback: find { ... } block
    s = text.find("{")
    e = text.rfind("}")
    if s != -1 and e != -1 and e > s:
        try:
            obj = json.loads(text[s:e+1])
            if isinstance(obj, dict):
                return obj
        except Exception:
            return None
    return None


def main():
    ap = argparse.ArgumentParser(description="LLM-based soft QA for translations")
    ap.add_argument("translated_csv", help="Input translated.csv")
    ap.add_argument("style_guide_md", help="Style guide file")
    ap.add_argument("glossary_yaml", help="Glossary file")
    ap.add_argument("rubric_yaml", help="Soft QA rubric config")
    ap.add_argument("--batch_size", type=int, default=40, help="Rows per LLM call")
    ap.add_argument("--out_report", default="data/qa_soft_report.json", help="Output report JSON")
    ap.add_argument("--out_tasks", default="data/repair_tasks.jsonl", help="Output repair tasks JSONL")
    args = ap.parse_args()

    print(f"🔍 Starting Soft QA v1.0...")
    print(f"   Input: {args.translated_csv}")
    print(f"   Batch size: {args.batch_size}")
    print()

    # Load resources
    rows = read_csv(args.translated_csv)
    style = load_text(args.style_guide_md)
    rubric = load_yaml(args.rubric_yaml)

    glossary_text = ""
    if args.glossary_yaml and Path(args.glossary_yaml).exists():
        glossary_text = load_text(args.glossary_yaml)

    # Initialize LLM
    try:
        llm = LLMClient()
        print(f"✅ Using LLM: {llm.model}")
    except LLMError as e:
        print(f"❌ LLM Error: {e}")
        return 1

    print(f"✅ Loaded {len(rows)} rows")
    print()

    # Clean output files (fresh start)
    if Path(args.out_tasks).exists():
        Path(args.out_tasks).unlink()

    # Process batches
    major = 0
    minor = 0
    all_tasks = 0
    batch_errors = 0

    i = 0
    while i < len(rows):
        batch = rows[i:i+args.batch_size]
        batch_start = i + 1
        batch_end = min(i + args.batch_size, len(rows))
        
        print(f"  [{batch_start}-{batch_end}/{len(rows)}] Processing...")

        try:
            system = build_system(style)
            user = build_user(batch, glossary_text, rubric)
            
            result = llm.chat(system=system, user=user, temperature=0.1, metadata={"step": "soft_qa"})
            obj = extract_json(result.text)
            
            if not obj or "items" not in obj:
                # Soft QA failure should not break pipeline
                print(f"    ⚠️  Invalid JSON response, skipping batch")
                append_jsonl(args.out_tasks, [{
                    "string_id": "",
                    "type": "soft_qa_failed",
                    "severity": "major",
                    "note": "soft QA model output invalid JSON",
                    "suggested_fix": "run soft QA again with smaller batch_size",
                }])
                major += 1
                batch_errors += 1
                i += args.batch_size
                continue

            # Extract issues as tasks
            tasks = []
            batch_major = 0
            batch_minor = 0
            
            for it in obj.get("items", []):
                sid = it.get("string_id", "")
                issues = it.get("issues", []) or []
                
                for iss in issues:
                    sev = iss.get("severity", "minor")
                    if sev == "major":
                        major += 1
                        batch_major += 1
                    else:
                        minor += 1
                        batch_minor += 1
                    
                    tasks.append({
                        "string_id": sid,
                        "type": iss.get("dimension", ""),
                        "severity": sev,
                        "note": iss.get("note", ""),
                        "suggested_fix": iss.get("suggested_fix", ""),
                    })

            if tasks:
                append_jsonl(args.out_tasks, tasks)
                all_tasks += len(tasks)
            
            print(f"    ✅ Found {batch_major} major, {batch_minor} minor issues")

        except LLMError as e:
            print(f"    ❌ LLM Error: {e.kind} - {e}")
            batch_errors += 1
        except Exception as e:
            print(f"    ❌ Error: {e}")
            batch_errors += 1

        i += args.batch_size

    # Write report
    report = {
        "version": "1.0",
        "has_findings": (major + minor) > 0,
        "summary": {
            "major": major,
            "minor": minor,
            "total_tasks": all_tasks,
            "batch_errors": batch_errors,
            "rows_processed": len(rows),
        },
        "outputs": {
            "repair_tasks_jsonl": args.out_tasks,
        },
    }
    write_json(args.out_report, report)

    # Print summary
    print()
    print(f"📊 Soft QA Summary:")
    print(f"   Rows processed: {len(rows)}")
    print(f"   Major issues: {major}")
    print(f"   Minor issues: {minor}")
    print(f"   Total tasks: {all_tasks}")
    print(f"   Batch errors: {batch_errors}")
    print()
    print(f"✅ Report: {args.out_report}")
    if all_tasks > 0:
        print(f"✅ Repair tasks: {args.out_tasks}")
    print()
    print("✅ Soft QA complete!")

    return 0


if __name__ == "__main__":
    exit(main())
