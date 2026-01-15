#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
glossary_review_llm.py

LLM-assisted glossary review fallback for users who don't speak target language.

Usage:
    python scripts/glossary_review_llm.py \
        --proposals glossary/proposals_translated.yaml \
        --output glossary/review_recommendations.yaml \
        --mode recommend

Environment:
    LLM_BASE_URL, LLM_API_KEY, (LLM_MODEL optional - uses router)
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import yaml
except ImportError:
    yaml = None

from runtime_adapter import LLMClient, LLMError


@dataclass
class ReviewResult:
    term_zh: str
    term_ru: str
    recommendation: str  # "approve", "reject", "revise"
    confidence: float
    reason: str
    suggested_term: Optional[str] = None


def load_proposals(path: str) -> List[Dict[str, Any]]:
    """Load proposed glossary entries from YAML."""
    if not Path(path).exists():
        return []
    if yaml is None:
        raise RuntimeError("PyYAML required. Install with: pip install pyyaml")
    
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    
    # Support multiple key names
    return data.get("candidates", data.get("entries", data.get("proposals", [])))


def load_style_guide(path: str) -> str:
    """Load style guide for context."""
    if not Path(path).exists():
        return ""
    with open(path, 'r', encoding='utf-8') as f:
        return f.read().strip()


def build_system_prompt() -> str:
    """Build system prompt for glossary review."""
    return (
        "你是术语表审校（zh-CN → ru-RU）。\n"
        "任务：审核候选术语对的准确性、风格一致性。\n\n"
        "输出 JSON（仅输出 JSON）：\n"
        "{\n"
        "  \"reviews\": [\n"
        "    {\n"
        "      \"term_zh\": \"<原样>\",\n"
        "      \"term_ru\": \"<原样>\",\n"
        "      \"status\": \"approved|rejected\",\n"
        "      \"comment\": \"<简短理由>\"\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "判定标准：\n"
        "- approved: 准确、地道、符合游戏风格。\n"
        "- rejected: 错译、过于口语/书面、含义错误。\n"
    )


def build_user_prompt(entries: List[Dict]) -> str:
    """Build user prompt for glossary review."""
    candidates = []
    for e in entries:
        candidates.append({
            "term_zh": e.get('term_zh', ''),
            "term_ru": e.get('term_ru', ''),
            "context": e.get('context', '') or ''
        })
        
    return (
        "language_pair: zh-CN -> ru-RU\n\n"
        "review_candidates:\n"
        f"{json.dumps(candidates, ensure_ascii=False, indent=2)}\n"
    )


def parse_review_response(text: str, entries: List[Dict]) -> List[ReviewResult]:
    """Parse LLM review response."""
    results = []
    text = (text or "").strip()
    
    data = {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fallback
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end+1])
            except:
                pass
            
    reviews = data.get("reviews", [])
    if not isinstance(reviews, list):
        if isinstance(data, list):
            reviews = data
        else:
            return []

    # Map inputs
    entry_map = {e.get('term_zh'): e for e in entries}

    for item in reviews:
        term_zh = item.get("term_zh")
        entry = entry_map.get(term_zh)
        if not entry:
            continue
            
        status = item.get("status", "rejected").lower()
        if status not in ["approved", "rejected", "revise"]:
            status = "rejected"
            
        # If status is approved, confident = 1.0, otherwise 0.0 or heuristic
        conf = 1.0 if status == "approved" else 0.0
        
        results.append(ReviewResult(
            term_zh=term_zh,
            term_ru=entry.get("term_ru", ""),
            recommendation=status,
            confidence=conf,
            reason=item.get("comment", ""),
            suggested_term=None # Prompt v2 doesn't explicitly ask for suggestion in this schema, keeping it simple
        ))
    
    return results


def write_recommendations_yaml(path: str, results: List[ReviewResult], mode: str) -> None:
    """Write review recommendations to YAML file."""
    if yaml is None:
        raise RuntimeError("PyYAML required")
    
    output = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "mode": mode,
            "total_reviewed": len(results),
            "approved": sum(1 for r in results if r.recommendation == "approved"),
            "rejected": sum(1 for r in results if r.recommendation == "rejected"),
        },
        "reviews": []
    }
    
    for r in results:
        review_entry = {
            "term_zh": r.term_zh,
            "term_ru": r.term_ru,
            "recommendation": r.recommendation,
            "reason": r.reason,
        }
        output["reviews"].append(review_entry)
        
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(output, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def main():
    ap = argparse.ArgumentParser(
        description="LLM-assisted glossary review for users who don't speak target language"
    )
    ap.add_argument("--proposals", required=True,
                    help="Input proposals YAML (from glossary_translate)")
    ap.add_argument("--output", required=True,
                    help="Output review file (YAML)")
    ap.add_argument("--style", default="workflow/style_guide.md",
                    help="Style guide for context")
    ap.add_argument("--mode", default="recommend", 
                    help="For compatibility, currently only supports recommendations output")
    ap.add_argument("--batch_size", type=int, default=10,
                    help="Batch size for LLM review")
    ap.add_argument("--max_terms", type=int, default=0,
                    help="Maximum terms to process (0 = all)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate without making LLM calls")
    args = ap.parse_args()
    
    print("🔍 Glossary Review LLM")
    print(f"   Proposals: {args.proposals}")
    print(f"   Output: {args.output}")
    print()
    
    # Load proposals
    if not Path(args.proposals).exists():
        print(f"❌ Proposals file not found: {args.proposals}")
        return 1
    
    entries = load_proposals(args.proposals)
    if not entries:
        print("ℹ️  No proposals to review")
        return 0
    
    # Filter entries that have term_ru
    entries_with_ru = [e for e in entries if e.get("term_ru")]
    if len(entries_with_ru) < len(entries):
        print(f"⚠️  Skipping {len(entries) - len(entries_with_ru)} entries missing 'term_ru'")
    entries = entries_with_ru
    
    if args.max_terms > 0:
        entries = entries[:args.max_terms]
    
    print(f"✅ Loaded {len(entries)} entries to review")
    
    # Load style guide
    # style_guide = load_style_guide(args.style) # Not used in v2 prompt currently but good to keep if needed
    
    if args.dry_run:
        print("[OK] Dry-run passed")
        return 0
    
    # Initialize LLM
    try:
        llm = LLMClient()
        print(f"✅ LLM client initialized")
    except LLMError as e:
        print(f"❌ LLM initialization failed: {e}")
        return 1
    
    all_results = []
    
    for i in range(0, len(entries), args.batch_size):
        batch = entries[i:i + args.batch_size]
        batch_num = i // args.batch_size + 1
        
        print(f"  Batch {batch_num}: Reviewing {len(batch)} entries...")
        
        system = build_system_prompt()
        user = build_user_prompt(batch)
        
        try:
            result = llm.chat(
                system=system,
                user=user,
                metadata={"step": "glossary_review", "batch": batch_num},
                response_format={"type": "json_object"}
            )
            
            reviews = parse_review_response(result.text, batch)
            all_results.extend(reviews)
            print(f"    ✅ Reviewed: {len(reviews)}")
            
        except LLMError as e:
            print(f"    ⚠️  LLM error: {e}")
            
    write_recommendations_yaml(args.output, all_results, args.mode)
    print(f"\n✅ Output written to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
