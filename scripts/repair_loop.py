#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
repair_loop.py
Auto-repair loop for translations with hard+soft QA issues.

Purpose:
  - Read qa_hard_report.json (blocking errors) + repair_tasks.jsonl (soft QA issues)
  - Hard fail priority: fix hard QA errors first (otherwise can't ship)
  - Soft major next: only fix major severity (minor can be left for human review)
  - Validate each repair with quick checks
  - Checkpoint/resume support
  - Escalate unfixable items

Usage:
  python scripts/repair_loop.py \
    data/translated.csv data/qa_hard_report.json data/repair_tasks.jsonl \
    workflow/style_guide.md data/glossary.yaml \
    --out_csv data/repaired.csv --max_retries 4

Environment:
  LLM_BASE_URL, LLM_API_KEY, LLM_MODEL (via runtime_adapter)
"""

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

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
CJK_RE = re.compile(r"[\u4e00-\u9fff]")


def read_csv(p: str) -> List[Dict[str, str]]:
    """Read CSV file as list of dicts."""
    with open(p, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(p: str, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    """Write CSV file."""
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def append_csv(p: str, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    """Append rows to CSV file."""
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    exists = Path(p).exists()
    with open(p, "a" if exists else "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            w.writeheader()
        w.writerows(rows)


def read_json(p: str) -> Any:
    """Read JSON file."""
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


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


def tokens_signature(text: str) -> Dict[str, int]:
    """Count tokens in text."""
    d = {}
    for m in TOKEN_RE.finditer(text or ""):
        k = m.group(1)
        d[k] = d.get(k, 0) + 1
    return d


def quick_validate(tokenized_zh: str, ru: str) -> Tuple[bool, str]:
    """
    Quick validation for repaired translation.
    Returns (is_valid, reason).
    """
    if tokens_signature(tokenized_zh) != tokens_signature(ru):
        return False, "token_mismatch"
    if CJK_RE.search(ru or ""):
        return False, "cjk_remaining"
    if not (ru or "").strip():
        return False, "empty"
    return True, "ok"


def iter_jsonl(p: str) -> List[dict]:
    """Read JSONL file as list of dicts."""
    if not p or not Path(p).exists():
        return []
    out = []
    with open(p, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def load_checkpoint(p: str) -> dict:
    """Load checkpoint file."""
    if Path(p).exists():
        return read_json(p)
    return {"done_ids": {}, "stats": {"ok": 0, "fail": 0}}


def save_checkpoint(p: str, obj: dict) -> None:
    """Save checkpoint file."""
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# Import glossary filters
from translate_llm import load_glossary, build_glossary_constraints, GlossaryEntry

def build_system(style: str) -> str:
    """Build system prompt for repair."""
    return (
        "你是手游本地化修复器（zh-CN → ru-RU）。你会根据给定的错误/建议，对 target_ru 进行修复。\n\n"
        "术语表规则（硬性）：\n"
        "- glossary 中出现的 term_zh → term_ru 必须严格使用 term_ru（大小写/词形按 glossary 指定；如需要变格请保持词根一致并优先保持 glossary 形式）。\n"
        "- 若源文包含 term_zh，但译文难以直接套用 term_ru，必须在不破坏占位符的前提下改写句子以容纳 term_ru。\n\n\n"
        "占位符规则（硬性）：\n"
        "- 任何形如 {TOKEN} / %s / %d / ${var} / <tag> / [xxx] 的占位符必须原样保留，不得翻译/改动/增删/移动。\n"
        "- 不得新增任何占位符；不得删除任何占位符。\n"
        "- 输出中禁止出现中文括号符号【】；如源文含【】用于分组/强调，俄语侧用 «» 或改写为“X: …”。\n\n\n"
        "输入包含：source_zh、current_ru、issues（可能来自 qa_hard 或 soft_qa）。\n"
        "输出格式（硬性）：\n"
        "- 只输出修复后的俄文纯文本，不解释，不要 JSON。\n"
        "修复优先级（从高到低）：\n"
        "1) 占位符/格式硬错误\n"
        "2) 术语一致性（按 glossary）\n"
        "3) 误译/漏译/歧义\n"
        "4) 语气与简洁性（在不引入新问题前提下）\n"
    )

def build_user(row: dict, issues: List[str], glossary_entries: List[GlossaryEntry], style_guide_excerpt: str) -> str:
    """Build user prompt for repair."""
    tokenized_zh = row.get("tokenized_zh") or row.get("source_zh") or ""
    current_ru = row.get("target_text") or ""
    sid =  row.get("string_id", "")
    
    # Build glossary excerpt
    approved, banned, proposed = build_glossary_constraints(glossary_entries, tokenized_zh)
    
    glossary_lines = []
    if approved:
        glossary_lines.append("【强制使用】")
        for k, v in approved.items():
            glossary_lines.append(f"- {k} → {v}")
    if banned:
        glossary_lines.append("【禁止自创】")
        for k in banned:
            glossary_lines.append(f"- {k}")
            
    glossary_text = "\n".join(glossary_lines) if glossary_lines else "(无)"

    # Format issues list
    issues_text = "\n".join([f"- {i}" for i in issues])

    return (
        f"string_id: {sid}\n"
        f"source_zh: {tokenized_zh}\n"
        f"current_ru: {current_ru}\n\n"
        "issues:\n"
        f"{issues_text}\n\n"
        "glossary_excerpt:\n"
        f"{glossary_text}\n\n"
        "style_guide_excerpt:\n"
        f"{style_guide_excerpt[:2000]}\n"
    )



def main():
    ap = argparse.ArgumentParser(description="Auto-repair loop for translations")
    ap.add_argument("translated_csv", help="Input translated.csv")
    ap.add_argument("qa_hard_report_json", help="Hard QA report (qa_hard_report.json)")
    ap.add_argument("repair_tasks_jsonl", help="Soft QA repair tasks (repair_tasks.jsonl)")
    ap.add_argument("style_guide_md", help="Style guide file")
    ap.add_argument("glossary_yaml", help="Glossary file", nargs="?", default="")
    ap.add_argument("--out_csv", default="data/repaired.csv", help="Output repaired CSV")
    ap.add_argument("--checkpoint", default="data/repair_checkpoint.json", help="Checkpoint file")
    ap.add_argument("--escalate_csv", default="data/escalate_list.csv", help="Escalation list")
    ap.add_argument("--max_retries", type=int, default=4, help="Max repair attempts per item")
    ap.add_argument("--only_soft_major", action="store_true", 
                    help="Only repair soft issues with major severity (skip minor)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate configuration and count issues without making LLM calls")
    args = ap.parse_args()

    print(f"🔧 Starting Repair Loop v2.0...")
    print(f"   Input: {args.translated_csv}")
    print(f"   Hard QA: {args.qa_hard_report_json}")
    print(f"   Soft tasks: {args.repair_tasks_jsonl}")
    print(f"   Max retries: {args.max_retries}")
    if args.only_soft_major:
        print(f"   Mode: Only soft major (skip minor)")
    print()

    # Load resources
    rows = read_csv(args.translated_csv)
    
    hard = {}
    if Path(args.qa_hard_report_json).exists():
        hard = read_json(args.qa_hard_report_json)
    
    soft_tasks = iter_jsonl(args.repair_tasks_jsonl)
    
    style = load_text(args.style_guide_md)
    glossary_text = ""
    if args.glossary_yaml and Path(args.glossary_yaml).exists():
        glossary_text = load_text(args.glossary_yaml)

    # Build issue map: string_id -> [issues...]
    # Priority: hard errors first, then soft major
    issue_map: Dict[str, List[str]] = {}
    hard_ids = set()
    soft_major_ids = set()

    # 1) Hard QA errors (blocking - must fix)
    for e in (hard.get("errors") or []):
        sid = e.get("string_id", "")
        if sid:
            issue_map.setdefault(sid, []).append(
                f"hard:{e.get('type','')}:{e.get('detail','')[:120]}"
            )
            hard_ids.add(sid)

    # 2) Soft QA tasks (major only if --only_soft_major)
    for t in soft_tasks:
        sid = t.get("string_id", "")
        if not sid:
            continue
        sev = (t.get("severity") or "minor").lower()
        if args.only_soft_major and sev != "major":
            continue
        issue_map.setdefault(sid, []).append(
            f"soft:{t.get('type','')}:{t.get('note','')[:120]}"
        )
        if sev == "major":
            soft_major_ids.add(sid)

    print(f"✅ Loaded {len(rows)} rows")
    print(f"✅ Hard errors: {len(hard_ids)} strings")
    print(f"✅ Soft major: {len(soft_major_ids)} strings")
    print(f"✅ Total to repair: {len(issue_map)} strings")

    # Dry-run mode
    if getattr(args, 'dry_run', False):
        print()
        print("=" * 60)
        print("DRY-RUN MODE - Validation Summary")
        print("=" * 60)
        print()
        print(f"[OK] Input CSV: {len(rows)} rows")
        print(f"[OK] Style guide: {len(style)} chars")
        print(f"[OK] Glossary: {len(glossary_text)} chars")
        print(f"[OK] Hard errors to fix: {len(hard_ids)}")
        print(f"[OK] Soft issues to fix: {len(soft_major_ids)}")
        print(f"[OK] Total repair items: {len(issue_map)}")
        
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
        if issue_map:
            print(f"     {len(issue_map)} items would be repaired in actual run")
        else:
            print(f"     No items need repair")
        print("=" * 60)
        return 0

    if not issue_map:
        print("\n✅ No issues found. Nothing to repair.")
        # Still write out_csv identical for pipeline convenience
        if rows:
            write_csv(args.out_csv, list(rows[0].keys()), rows)
        return 0

    # Load checkpoint
    ckpt = load_checkpoint(args.checkpoint)
    done_ids = ckpt.get("done_ids", {})

    # Initialize LLM
    try:
        llm = LLMClient()
        print(f"✅ Using LLM: {llm.default_model}")
    except LLMError as e:
        print(f"❌ LLM Error: {e}")
        return 2

    print()

    fieldnames = list(rows[0].keys())
    if "target_text" not in fieldnames:
        raise ValueError("translated.csv must include target_text column")

    esc_fields = ["string_id", "reason", "tokenized_zh", "last_output"]

    # Build rows by id for in-place editing
    rows_by_id = {(r.get("string_id") or "").strip(): r for r in rows}
    
    # Get targets: hard first, then soft (order matters for priority)
    targets_hard = [sid for sid in hard_ids if not done_ids.get(sid, False)]
    targets_soft = [sid for sid in issue_map.keys() 
                    if sid not in hard_ids and not done_ids.get(sid, False)]
    targets = targets_hard + targets_soft

    ok = ckpt["stats"].get("ok", 0)
    fail = ckpt["stats"].get("fail", 0)

    print(f"🚀 Processing {len(targets)} strings ({len(targets_hard)} hard, {len(targets_soft)} soft)...\n")

    for idx, sid in enumerate(targets, 1):
        row = rows_by_id.get(sid)
        if not row:
            print(f"  [{idx}/{len(targets)}] {sid}: ⚠️  not found in CSV, skipping")
            continue

        issues = issue_map.get(sid, [])
        is_hard = sid in hard_ids
        priority = "HARD" if is_hard else "soft"
        
        print(f"  [{idx}/{len(targets)}] {sid} [{priority}]: repairing ({len(issues)} issues)...")

        system = build_system(style)
        user = build_user(row, issues, glossary_text)

        tokenized_zh = row.get("tokenized_zh") or row.get("source_zh") or ""
        current = row.get("target_text") or ""

        last_err = ""
        repaired_text = ""
        
        # Select step based on repair type for model routing
        repair_step = "repair_hard" if is_hard else "repair_soft_major"
        
        for attempt in range(args.max_retries + 1):
            try:
                result = llm.chat(system=system, user=user, temperature=0.1, metadata={"step": repair_step, "string_id": sid})
                
                # Direct text usage (Pure Text Strict Mode)
                cand = result.text.strip()
                
                # Clean up if model still output JSON-like quotes around text
                if cand.startswith('"') and cand.endswith('"'):
                    cand = cand[1:-1]
                
                okv, why = quick_validate(tokenized_zh, cand)
                
                if not okv:
                    last_err = why
                    raise ValueError(f"validation_failed:{why}")
                
                repaired_text = cand
                break
                
            except LLMError as e:
                last_err = f"{last_err} | {e.kind}:{e}".strip(" |")
                if not e.retryable:
                    break
                time.sleep(min(2 ** attempt, 20) * (0.5 + 0.5 * (idx % 3)))
            except Exception as e:
                last_err = f"{last_err} | {type(e).__name__}:{e}".strip(" |")
                time.sleep(min(2 ** attempt, 20) * (0.5 + 0.5 * (idx % 3)))
                if attempt >= args.max_retries:
                    break

        if not repaired_text:
            append_csv(args.escalate_csv, esc_fields, [{
                "string_id": sid,
                "reason": f"repair_failed_after_retries:{last_err}",
                "tokenized_zh": tokenized_zh,
                "last_output": current[:300],
            }])
            fail += 1
            print(f"    ❌ escalated: {last_err[:60]}")
        else:
            rows_by_id[sid]["target_text"] = repaired_text
            ok += 1
            done_ids[sid] = True
            print(f"    ✅ repaired")

        # Save checkpoint periodically
        ckpt["done_ids"] = done_ids
        ckpt["stats"] = {"ok": ok, "fail": fail}
        save_checkpoint(args.checkpoint, ckpt)

        if idx % 50 == 0:
            print(f"\n  [PROGRESS] {idx}/{len(targets)} ok={ok} fail={fail}\n")

    # Write repaired file (full CSV with all rows, repaired in-place)
    repaired_rows = list(rows_by_id.values())
    write_csv(args.out_csv, fieldnames, repaired_rows)

    # Summary
    print()
    print(f"📊 Repair Loop Summary:")
    print(f"   Total targets: {len(targets)}")
    print(f"   Hard errors: {len(targets_hard)}")
    print(f"   Soft issues: {len(targets_soft)}")
    print(f"   Repaired: {ok}")
    print(f"   Failed: {fail}")

    print()
    print(f"✅ Output: {args.out_csv}")
    if fail > 0:
        print(f"⚠️  Escalated: {args.escalate_csv}")
    print()
    print("✅ Repair loop complete!")

    return 0


if __name__ == "__main__":
    exit(main())
