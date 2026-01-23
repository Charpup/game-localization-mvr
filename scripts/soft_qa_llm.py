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

# sys.stdout wrapping moved to __main__ block

try:
    import yaml
except Exception:
    yaml = None

from runtime_adapter import LLMClient, LLMError, BatchConfig, get_batch_config, batch_llm_call, log_llm_progress

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
        "任务：分析翻译质量，仅列出有问题的项。\n\n"
        "检查维度（只报问题，不要夸）：\n"
        "- 术语一致性（glossary）\n"
        "- 语气：官方为主，二次元口语为辅（避免过度口语或过度书面）\n"
        "- UI 简洁性（冗长/重复/不自然）\n"
        "- 歧义/误译/信息缺失\n"
        "- 标点与符号：禁止【】；占位符必须完整\n\n"
        "输出格式（硬性，仅输出 JSON）：\n"
        "{\n"
        '  "items": [\n'
        "    {\n"
        '      "id": "<id>",\n'
        '      "severity": "minor|major",\n'
        '      "issue_type": "terminology|tone|brevity|ambiguity|mistranslation|format|punctuation",\n'
        '      "problem": "<一句话描述问题>",\n'
        '      "suggestion": "<一句话给出修复方向>",\n'
        '      "preferred_fix_ru": "<可选：建议的修复后俄文>"\n'
        "    }\n"
        "  ]\n"
        "}\n"
        "规则：\n"
        '- 没问题则项目不出现在 items 中。\n'
        "- problem/suggestion 必须短句。\n"
        "- 每个有问题的 id 只输出一个最严重的 item。\n\n"
        f"术语表摘要（前 50 条）：\n{glossary_summary[:1500]}\n\n"
        f"style_guide（节选）：\n{style[:1000]}\n"
    )


def build_user_prompt(items: List[Dict]) -> str:
    """Build user prompt for soft QA from batch items."""
    # items comes from batch_llm_call where:
    # id = string_id
    # source_text = "SRC: {source_zh} | TGT: {target_ru}"
    # But for soft QA, we might want a cleaner format
    candidates = []
    for it in items:
        # Re-split source_text to get zh and ru
        parts = it.get("source_text", "").split(" | TGT: ")
        src_zh = parts[0].replace("SRC: ", "") if len(parts) > 0 else ""
        tgt_ru = parts[1] if len(parts) > 1 else ""
        
        candidates.append({
            "string_id": it["id"],
            "source_zh": src_zh,
            "target_ru": tgt_ru
        })
    
    return json.dumps(candidates, ensure_ascii=False, indent=2)


def build_glossary_summary(entries: List[GlossaryEntry], max_entries: int = 50) -> str:
    """Build compact glossary summary."""
    approved = [e for e in entries if e.status.lower() == "approved"][:max_entries]
    if not approved:
        return "(无)"
    lines = [f"- {e.term_zh} → {e.term_ru}" for e in approved]
    return "\n".join(lines)


def process_batch_results(batch_items: List[Dict]) -> List[dict]:
    """Normalize batch output items into task dicts."""
    valid_tasks = []
    for t in batch_items:
        # Note: items will only contain items with issues due to system prompt
        valid_tasks.append({
            "string_id": t.get("id", ""),
            "type": t.get("issue_type", "issue"),
            "severity": t.get("severity", "minor"),
            "note": f"{t.get('problem', '')} | Suggestion: {t.get('suggestion', '')}",
            "suggested_fix": t.get("preferred_fix_ru", ""),
        })
    return valid_tasks


def main():
    ap = argparse.ArgumentParser(description="LLM-based soft QA (Batch Mode v2.0)")
    ap.add_argument("translated_csv", nargs="?", help="Input translated.csv")
    ap.add_argument("--input", help="Alias for translated_csv")
    ap.add_argument("style_guide_md", nargs="?", default="workflow/style_guide.md", help="Style guide file")
    ap.add_argument("glossary_yaml", nargs="?", default="data/glossary.yaml", help="Glossary file")
    ap.add_argument("rubric_yaml", nargs="?", default="workflow/soft_qa_rubric.yaml", help="Soft QA rubric config (legacy, ignored)")
    ap.add_argument("--batch_size", type=int, default=15, help="Items per batch")
    ap.add_argument("--model", default="claude-haiku-4-5-20251001", help="Model override")
    ap.add_argument("--max_batch_tokens", type=int, default=4000, help="Max tokens per batch")
    ap.add_argument("--out_report", default="data/qa_soft_report.json", help="Output report JSON")
    ap.add_argument("--out_tasks", default="data/repair_tasks.jsonl", help="Output repair tasks JSONL")
    ap.add_argument("--dry-run", action="store_true", 
                    help="Validate configuration without making LLM calls")
    args = ap.parse_args()

    # Resolve input path
    input_path = args.input or args.translated_csv
    if not input_path:
        ap.print_help()
        return 1

    print(f"🔍 Soft QA v2.0 (Batch Mode)")
    # Load resources
    rows = read_csv(input_path)
    style = load_text(args.style_guide_md)

    glossary_path = args.glossary_yaml
    glossary_entries = []
    if glossary_path and Path(glossary_path).exists():
        glossary_entries, _ = load_glossary(glossary_path)
    
    glossary_summary = build_glossary_summary(glossary_entries)
    
    print(f"✅ Loaded {len(rows)} rows from {input_path}")
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

    # Split into batches (logic handled by batch_llm_call internally)
    start_time = time.time()
    major = 0
    minor = 0
    all_tasks = 0
    batch_errors = 0

    # Prepare rows for batch_llm_call
    # Source text for soft QA needs both ZH and RU
    batch_rows = []
    for r in rows_with_target:
        src = r.get("source_zh") or r.get("tokenized_zh") or ""
        tgt = r.get("target_text") or ""
        batch_rows.append({
            "id": r.get("string_id"),
            "source_text": f"SRC: {src} | TGT: {tgt}"
        })

    # Execute batch call
    try:
        batch_results = batch_llm_call(
            step="soft_qa",
            rows=batch_rows,
            model=args.model,
            system_prompt=build_system_batch(style, glossary_summary),
            user_prompt_template=build_user_prompt,
            content_type="normal",
            retry=1,
            allow_fallback=True,
            partial_match=True
        )
        
        print("   Batch results received, processing tasks...")
        tasks = process_batch_results(batch_results)
        
        if tasks:
            append_jsonl(args.out_tasks, tasks)
            all_tasks = len(tasks)
            for t in tasks:
                if t.get("severity") == "major":
                    major += 1
                else:
                    minor += 1
                    
    except Exception as e:
        print(f"❌ Soft QA failed: {e}")
        return 1

    # Calculate batches for report
    config_inst = get_batch_config()
    b_size = config_inst.get_batch_size(args.model, "normal")
    total_batches = (len(batch_rows) + b_size - 1) // b_size if b_size > 0 else 1

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
            "batches_processed": total_batches,
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
    # Ensure UTF-8 output on Windows
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    exit(main())
