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
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional

# Ensure UTF-8 output on Windows
# if sys.platform == 'win32':
#     import io
#     sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
#     sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

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


# Import glossary logic from translate_llm
from translate_llm import load_glossary, build_glossary_constraints, GlossaryEntry

def build_system(style: str) -> str:
    """Build system prompt for soft QA."""
    return (
        "你是手游本地化软质检（zh-CN → ru-RU）。\n\n"
        "输入：source_zh + target_ru。输出：需要修复的任务列表（JSON），用于后续 repair_loop。\n\n"
        "检查维度（只报问题，不要夸）：\n"
        "- 术语一致性（glossary）\n"
        "- 语气：官方为主，二次元口语为辅（避免过度口语或过度书面）\n"
        "- UI 简洁性（冗长/重复/不自然）\n"
        "- 歧义/误译/信息缺失\n"
        "- 标点与符号：禁止【】；占位符必须完整\n\n"
        "输出 JSON（硬性，且仅输出 JSON）：\n"
        "{\n"
        "  \"tasks\": [\n"
        "    {\n"
        "      \"string_id\": \"<id>\",\n"
        "      \"severity\": \"minor|major\",\n"
        "      \"issue_type\": \"terminology|tone|brevity|ambiguity|mistranslation|format|punctuation\",\n"
        "      \"problem\": \"<一句话描述问题>\",\n"
        "      \"suggestion\": \"<一句话给出修复方向>\",\n"
        "      \"preferred_fix_ru\": \"<可选：给出你建议的修复后俄文；若不确定留空字符串>\"\n"
        "    }\n"
        "  ]\n"
        "}\n"
        "规则：\n"
        "- 没问题则输出 { \"tasks\": [] }。\n"
        "- problem/suggestion 必须短句，避免长段解释。\n"
    )


def build_user(row: Dict[str, str], glossary_entries: List[GlossaryEntry], style_guide_excerpt: str) -> str:
    """Build user prompt for soft QA (single item)."""
    sid = row.get("string_id", "").strip()
    source_zh = row.get("source_zh", "").strip() or row.get("tokenized_zh", "").strip()
    target_ru = row.get("target_text", "").strip()
    
    # Build glossary excerpt (similar to translate_llm)
    # We check against source_zh for relevant terms
    approved, banned, proposed = build_glossary_constraints(glossary_entries, source_zh)
    
    glossary_lines = []
    if approved:
        glossary_lines.append("【强制使用】")
        for k, v in approved.items():
            glossary_lines.append(f"- {k} → {v}")
    if banned:
        glossary_lines.append("【禁止自创】")
        for k in banned:
            glossary_lines.append(f"- {k}")
    if proposed:
        glossary_lines.append("【参考建议】")
        for k, vals in proposed.items():
            glossary_lines.append(f"- {k} → {', '.join(vals)}")
            
    glossary_text = "\n".join(glossary_lines) if glossary_lines else "(无)"

    return (
        f"string_id: {sid}\n"
        f"source_zh: {source_zh}\n"
        f"target_ru: {target_ru}\n\n"
        "glossary_excerpt:\n"
        f"{glossary_text}\n\n"
        "style_guide_excerpt:\n"
        f"{style_guide_excerpt[:2000]}\n"
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
    ap.add_argument("--batch_size", type=int, default=40, help="Ignored in single-mode v2")
    ap.add_argument("--out_report", default="data/qa_soft_report.json", help="Output report JSON")
    ap.add_argument("--out_tasks", default="data/repair_tasks.jsonl", help="Output repair tasks JSONL")
    ap.add_argument("--dry-run", action="store_true", 
                    help="Validate configuration without making LLM calls")
    args = ap.parse_args()

    print(f"🔍 Starting Soft QA v2.0 (Single-Item Strict JSON)...")
    print(f"   Input: {args.translated_csv}")
    print()

    # Load resources
    rows = read_csv(args.translated_csv)
    style = load_text(args.style_guide_md)
    # rubric = load_yaml(args.rubric_yaml) # Not used in new prompt structure directly but kept for comp

    glossary_path = args.glossary_yaml
    glossary_entries = []
    if glossary_path and Path(glossary_path).exists():
        glossary_entries, _ = load_glossary(glossary_path)
    
    # Dry-run mode
    if getattr(args, 'dry_run', False):
        print()
        print("=" * 60)
        print("DRY-RUN MODE - Validating configuration")
        print("=" * 60)
        print()
        print(f"[OK] Input loaded: {len(rows)} rows")
        print(f"[OK] Style guide: {len(style)} chars")
        print(f"[OK] Glossary loaded: {len(glossary_entries)} entries")
        
        # Check LLM env
        import os
        llm_model = os.getenv("LLM_MODEL", "")
        if llm_model:
            print(f"[OK] LLM model: {llm_model}")
        else:
            print(f"[WARN] LLM_MODEL not set")
        
        print()
        print("=" * 60)
        print("[OK] Dry-run validation PASSED")
        print("=" * 60)
        return 0

    # Initialize LLM
    try:
        llm = LLMClient()
        print(f"✅ Using LLM: {llm.default_model}")
    except LLMError as e:
        print(f"❌ LLM Error: {e}")
        return 1

    print(f"✅ Loaded {len(rows)} rows")
    print()

    # Clean output files (fresh start)
    if Path(args.out_tasks).exists():
        Path(args.out_tasks).unlink()

    # Process single items
    major = 0
    minor = 0
    all_tasks = 0
    batch_errors = 0

    i = 0
    while i < len(rows):
        row = rows[i]
        
        # Skip if no target text
        if not row.get("target_text"):
            i += 1
            continue

        if (i+1) % 10 == 0:
            print(f"  [{i+1}/{len(rows)}] Processing...")

        try:
            system = build_system(style)
            user = build_user(row, glossary_entries, style)
            
            result = llm.chat(
                system=system, 
                user=user, 
                temperature=0.1, 
                metadata={"step": "soft_qa", "string_id": row.get("string_id")},
                response_format={"type": "json_object"}
            )
            obj = extract_json(result.text)
            
            if not obj or "tasks" not in obj:
                # Retry logic could be added here, but for now we log and move on
                print(f"    ⚠️  Invalid JSON response for {row.get('string_id')}")
                batch_errors += 1
                i += 1
                continue

            # Extract issues as tasks
            tasks_found = obj.get("tasks", [])
            
            valid_tasks = []
            for t in tasks_found:
                # Normalize task object to expected output format
                # Prompt output: string_id, severity, issue_type, problem, suggestion, preferred_fix_ru
                # Output expectation: string_id, type, severity, note, suggested_fix
                
                sev = t.get("severity", "minor")
                if sev == "major":
                    major += 1
                else:
                    minor += 1
                
                valid_tasks.append({
                    "string_id": t.get("string_id") or row.get("string_id"),
                    "type": t.get("issue_type", "issue"),
                    "severity": sev,
                    "note": f"{t.get('problem', '')} | Suggestion: {t.get('suggestion', '')}",
                    "suggested_fix": t.get("preferred_fix_ru", ""),
                })

            if valid_tasks:
                append_jsonl(args.out_tasks, valid_tasks)
                all_tasks += len(valid_tasks)
            
        except LLMError as e:
            print(f"    ❌ LLM Error: {e.kind} - {e}")
            batch_errors += 1
        except Exception as e:
            print(f"    ❌ Error: {e}")
            batch_errors += 1

        i += 1

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
