#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
repair_loop.py
Auto-repair loop for translations flagged by soft QA.

Purpose:
  - Read repair tasks from soft QA output
  - Attempt LLM-based repair with issue context
  - Validate repairs against hard QA rules
  - Checkpoint/resume support
  - Escalate unfixable items

Usage:
  python scripts/repair_loop.py \
    data/repair_tasks.jsonl data/translated.csv data/repaired.csv \
    workflow/style_guide.md data/glossary.yaml \
    --max_attempts 3

Environment:
  LLM_BASE_URL, LLM_API_KEY, LLM_MODEL (via runtime_adapter)
"""

import argparse
import csv
import json
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import yaml
except ImportError:
    yaml = None

from runtime_adapter import LLMClient, LLMError


# Token and CJK patterns for validation
TOKEN_RE = re.compile(r"⟦(PH_\d+|TAG_\d+)⟧")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def load_style_guide(path: str) -> str:
    """Load style guide content."""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def load_glossary(path: str) -> List[dict]:
    """Load glossary entries."""
    if not path or not Path(path).exists():
        return []
    if yaml is None:
        return []
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return data.get("entries", [])


def read_repair_tasks(path: str) -> Dict[str, List[dict]]:
    """
    Read repair tasks from JSONL file, grouped by string_id.
    Returns dict: string_id -> list of issues for that string.
    """
    grouped: Dict[str, List[dict]] = {}
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                task = json.loads(line)
                sid = task.get("string_id", "")
                if sid:  # Skip entries without string_id (e.g., soft_qa_failed markers)
                    if sid not in grouped:
                        grouped[sid] = []
                    grouped[sid].append(task)
    return grouped


def read_csv_rows(path: str) -> Dict[str, Dict[str, str]]:
    """Read translated CSV as dict keyed by string_id."""
    result = {}
    with open(path, 'r', encoding='utf-8-sig', newline='') as f:
        for row in csv.DictReader(f):
            sid = row.get("string_id", "").strip()
            if sid:
                result[sid] = row
    return result


def load_checkpoint(path: str) -> dict:
    """Load repair checkpoint."""
    if Path(path).exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"repaired_ids": {}, "stats": {"ok": 0, "fail": 0}}


def save_checkpoint(path: str, ckpt: dict) -> None:
    """Save repair checkpoint."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(ckpt, f, ensure_ascii=False, indent=2)


def tokens_signature(text: str) -> Dict[str, int]:
    """Count tokens in text."""
    counts: Dict[str, int] = {}
    for m in TOKEN_RE.finditer(text or ""):
        k = m.group(1)
        counts[k] = counts.get(k, 0) + 1
    return counts


def validate_translation(source_zh: str, target_text: str) -> Tuple[bool, str]:
    """
    Validate translation against hard rules.
    Returns (is_valid, reason).
    """
    if tokens_signature(source_zh) != tokens_signature(target_text):
        return False, "token_mismatch"
    if CJK_RE.search(target_text or ""):
        return False, "cjk_remaining"
    if not (target_text or "").strip():
        return False, "empty"
    return True, "ok"


def build_repair_prompt(string_id: str, translated_row: Dict[str, str], 
                        issues: List[dict], style_guide: str, 
                        glossary: List[dict]) -> Tuple[str, str]:
    """
    Build repair prompt with issue context.
    Handles new soft_qa format: type, note, suggested_fix
    Returns (system_prompt, user_prompt).
    """
    source_zh = translated_row.get("source_zh", "") or translated_row.get("tokenized_zh", "")
    current_text = translated_row.get("target_text", "")
    
    # Filter relevant glossary terms
    relevant_terms = []
    for e in glossary:
        term_zh = e.get("term_zh", "")
        if term_zh and term_zh in source_zh:
            term_ru = e.get("term_ru", "")
            status = e.get("status", "proposed")
            relevant_terms.append(f"{term_zh}→{term_ru}({status})")
    
    # Format issues from soft_qa output
    issue_descriptions = []
    suggested_fixes = []
    for iss in issues:
        dim = iss.get("type", "unknown")
        sev = iss.get("severity", "minor")
        note = iss.get("note", "")
        fix = iss.get("suggested_fix", "")
        issue_descriptions.append(f"[{dim}/{sev}] {note}")
        if fix:
            suggested_fixes.append(fix)
    
    system = (
        "你是一位资深的游戏本地化译者和修复专家。\n"
        "任务：根据给出的问题反馈，修复以下翻译。\n"
        "硬约束：\n"
        "1. 所有 token（⟦PH_x⟧ 或 ⟦TAG_x⟧）必须逐字保留，数量一致\n"
        "2. 输出不能包含任何中文字符\n"
        "3. 只输出修复后的译文，不要任何解释\n\n"
        f"风格规范：\n{style_guide[:2000]}\n"
    )
    
    user = (
        f"string_id: {string_id}\n"
        f"源文本: {source_zh}\n"
        f"当前译文: {current_text}\n"
        f"发现的问题:\n" + "\n".join(f"  - {d}" for d in issue_descriptions) + "\n"
        f"参考修复: {suggested_fixes[0] if suggested_fixes else '无'}\n"
        f"相关术语: {', '.join(relevant_terms) if relevant_terms else '无'}\n\n"
        "请输出修复后的译文（仅译文本身，不要JSON包装或解释）："
    )
    
    return system, user


def backoff_sleep(attempt: int) -> None:
    """Exponential backoff with jitter."""
    base = min(2 ** attempt, 30)
    jitter = random.uniform(0.2, 1.0)
    time.sleep(base * jitter)


def attempt_repair(llm: LLMClient, string_id: str, translated_row: Dict[str, str],
                   issues: List[dict], style_guide: str, 
                   glossary: List[dict], max_attempts: int) -> Tuple[Optional[str], str]:
    """
    Attempt to repair a translation.
    Returns (repaired_text or None, status_message).
    """
    source_zh = translated_row.get("source_zh", "") or translated_row.get("tokenized_zh", "")
    
    # Check if soft_qa already provided a suggested_fix that passes validation
    for iss in issues:
        suggested = iss.get("suggested_fix", "").strip()
        if suggested:
            is_valid, _ = validate_translation(source_zh, suggested)
            if is_valid:
                return suggested, "used_suggested_fix"
    
    # Otherwise, use LLM to repair
    working_issues = issues.copy()
    
    for attempt in range(max_attempts):
        try:
            system, user = build_repair_prompt(string_id, translated_row, working_issues, style_guide, glossary)
            result = llm.chat(system=system, user=user)
            repaired = result.text.strip()
            
            # Validate the repair
            is_valid, reason = validate_translation(source_zh, repaired)
            if is_valid:
                return repaired, "ok"
            
            # If validation failed, add feedback and retry
            working_issues = [{"type": "validation_failed", "severity": "major", 
                              "note": f"上次修复失败: {reason}", "suggested_fix": ""}] + issues[:2]
            
        except LLMError as e:
            if not e.retryable:
                return None, f"llm_error_non_retryable: {e.kind}"
            backoff_sleep(attempt)
        except Exception as e:
            backoff_sleep(attempt)
    
    return None, "max_attempts_exceeded"


def main():
    parser = argparse.ArgumentParser(description="Auto-repair loop for translations")
    parser.add_argument("repair_tasks", help="Input repair_tasks.jsonl")
    parser.add_argument("translated_csv", help="Original translated.csv")
    parser.add_argument("repaired_csv", help="Output repaired.csv")
    parser.add_argument("style_guide", help="Style guide path")
    parser.add_argument("glossary", help="Glossary path", nargs="?", default="")
    parser.add_argument("--max_attempts", type=int, default=3,
                        help="Max repair attempts per item")
    parser.add_argument("--checkpoint", default="data/repair_checkpoint.json",
                        help="Checkpoint file path")
    parser.add_argument("--escalate_csv", default="data/escalate_list.csv",
                        help="Escalation list for unfixable items")
    args = parser.parse_args()
    
    print(f"🔧 Starting Repair Loop v1.0...")
    print(f"   Tasks: {args.repair_tasks}")
    print(f"   Max attempts: {args.max_attempts}")
    print()
    
    # Load resources
    style_guide = load_style_guide(args.style_guide)
    glossary = load_glossary(args.glossary)
    tasks_by_id = read_repair_tasks(args.repair_tasks)
    translated = read_csv_rows(args.translated_csv)
    
    if not tasks_by_id:
        print("✅ No repair tasks. Nothing to do.")
        sys.exit(0)
    
    print(f"✅ Loaded {len(tasks_by_id)} strings with repair tasks")
    
    # Initialize LLM
    try:
        llm = LLMClient()
        print(f"✅ Using LLM: {llm.model}")
    except LLMError as e:
        print(f"❌ LLM Error: {e}")
        sys.exit(2)
    
    # Load checkpoint
    ckpt = load_checkpoint(args.checkpoint)
    repaired_ids = ckpt.get("repaired_ids", {})
    
    # Process tasks grouped by string_id
    repaired_rows = []
    escalated = []
    
    string_ids = list(tasks_by_id.keys())
    for idx, string_id in enumerate(string_ids, 1):
        issues = tasks_by_id[string_id]
        
        # Skip if already repaired
        if string_id in repaired_ids:
            print(f"  [{idx}/{len(string_ids)}] {string_id}: skipped (already repaired)")
            continue
        
        # Get original translated row
        if string_id not in translated:
            print(f"  [{idx}/{len(string_ids)}] {string_id}: ⚠️  not found in translated.csv, skipping")
            continue
        
        translated_row = translated[string_id]
        print(f"  [{idx}/{len(string_ids)}] {string_id}: repairing ({len(issues)} issues)...")
        
        # Attempt repair
        repaired_text, status = attempt_repair(
            llm, string_id, translated_row, issues, 
            style_guide, glossary, args.max_attempts
        )
        
        if repaired_text:
            # Success - update row
            repaired_row = dict(translated_row)
            repaired_row["target_text"] = repaired_text
            repaired_row["repair_status"] = "repaired"
            repaired_rows.append(repaired_row)
            
            repaired_ids[string_id] = True
            ckpt["stats"]["ok"] = ckpt["stats"].get("ok", 0) + 1
            print(f"    ✅ repaired ({status})")
        else:
            # Failed - escalate
            source_zh = translated_row.get("source_zh", "") or translated_row.get("tokenized_zh", "")
            escalated.append({
                "string_id": string_id,
                "reason": f"repair_failed: {status}",
                "tokenized_zh": source_zh,
                "last_output": translated_row.get("target_text", "")[:300]
            })
            ckpt["stats"]["fail"] = ckpt["stats"].get("fail", 0) + 1
            print(f"    ❌ escalated: {status}")
        
        # Save checkpoint periodically
        if idx % 10 == 0:
            ckpt["repaired_ids"] = repaired_ids
            save_checkpoint(args.checkpoint, ckpt)
    
    # Final checkpoint save
    ckpt["repaired_ids"] = repaired_ids
    save_checkpoint(args.checkpoint, ckpt)
    
    # Write repaired.csv
    if repaired_rows:
        Path(args.repaired_csv).parent.mkdir(parents=True, exist_ok=True)
        
        # Get fieldnames from first row
        fieldnames = list(repaired_rows[0].keys())
        if "repair_status" not in fieldnames:
            fieldnames.append("repair_status")
        
        with open(args.repaired_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(repaired_rows)
        print(f"✅ Wrote {len(repaired_rows)} repaired rows to {args.repaired_csv}")
    
    # Append to escalate list
    if escalated:
        Path(args.escalate_csv).parent.mkdir(parents=True, exist_ok=True)
        esc_fields = ["string_id", "reason", "tokenized_zh", "last_output"]
        
        exists = Path(args.escalate_csv).exists()
        mode = 'a' if exists else 'w'
        with open(args.escalate_csv, mode, encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=esc_fields)
            if not exists:
                writer.writeheader()
            writer.writerows(escalated)
        print(f"⚠️  Escalated {len(escalated)} items to {args.escalate_csv}")
    
    # Summary
    print()
    print(f"📊 Repair Loop Summary:")
    print(f"   Total strings: {len(string_ids)}")
    print(f"   Repaired: {ckpt['stats']['ok']}")
    print(f"   Failed: {ckpt['stats']['fail']}")
    print()
    print("✅ Repair loop complete!")


if __name__ == "__main__":
    main()
