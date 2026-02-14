#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
glossary_translate_llm.py

Dedicated script for glossary term translation (zh→ru).
Uses router-configured model for "glossary_translate" step.

Usage:
    python scripts/glossary_translate_llm.py \
        --proposals glossary/proposals.yaml \
        --output glossary/proposals_translated.yaml \
        --batch_size 20 --max_terms 400

Environment:
    LLM_BASE_URL, LLM_API_KEY, (LLM_MODEL optional - uses router)
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass, asdict
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

from runtime_adapter import LLMClient, LLMError, BatchConfig, batch_llm_call, log_llm_progress


@dataclass
class TranslatedTerm:
    term_zh: str
    term_ru: str
    confidence: float
    reason: str
    context: Optional[str] = None


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
    """Build system prompt for glossary translation."""
    return (
        "你是术语表译者（zh-CN → ru-RU），为手游项目生成“可落地”的术语对。\n"
        "任务：把候选 id 翻译为 term_ru，并给出简短注释，避免把整句当术语。\n\n"
        "输出 JSON（仅输出 JSON）：\n"
        "{\n"
        "  \"items\": [\n"
        "    {\n"
        "      \"id\": \"<原样>\",\n"
        "      \"term_ru\": \"<俄文术语>\",\n"
        "      \"pos\": \"noun|verb|adj|phrase|name|system\",\n"
        "      \"notes\": \"<可选：一句话说明语境/是否可变格>\",\n"
        "      \"confidence\": 0.0\n"
        "    }\n"
        "  ]\n"
        "}\n\n"
        "规则（硬性）：\n"
        "- id 必须与输入一致（不要改写）。\n"
        "- term_ru 不得包含【】；如需要引号用 «».\n"
        "- 专有名词/技能名优先音译或官方惯用译法；系统词优先简洁一致。\n"
    )


def build_user_prompt(items: List[Dict]) -> str:
    """Build user prompt for glossary translation from batch items."""
    candidates = []
    for item in items:
        candidates.append({
            "term_zh": item.get('id', ''),
            "context": item.get('source_text', '') or ''
        })
    
    return (
        f"language_pair: zh-CN -> ru-RU\n"
        f"context_hint: Game Localization (Naruto-like)\n\n"
        "candidates:\n"
        f"{json.dumps(candidates, ensure_ascii=False, indent=2)}\n"
    )


def process_batch_results(batch_items: List[Dict], original_entries: List[Dict]) -> List[TranslatedTerm]:
    """Convert batch output items back to TranslatedTerm objects."""
    results = []
    entry_map = {e.get("term_zh"): e for e in original_entries}
    
    for item in batch_items:
        term_zh = item.get("id")
        entry = entry_map.get(term_zh)
        
        if not entry:
             continue

        term_ru = item.get("term_ru", "")
        if term_ru:
            results.append(TranslatedTerm(
                term_zh=term_zh,
                term_ru=term_ru,
                confidence=float(item.get("confidence", 0.0)),
                reason=item.get("notes", "") + " | " + item.get("pos", ""),
                context=entry.get("context")
            ))
    
    return results


def write_translated_yaml(path: str, results: List[TranslatedTerm], meta: Dict) -> None:
    """Write translated terms to YAML file."""
    if yaml is None:
        raise RuntimeError("PyYAML required")
    
    output = {
        "meta": {
            "generated_at": datetime.now().isoformat(),
            "step": "glossary_translate",
            "total_translated": len(results),
            **meta
        },
        "entries": [asdict(r) for r in results]
    }
    
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(output, f, allow_unicode=True, default_flow_style=False, sort_keys=False)


def main():
    ap = argparse.ArgumentParser(
        description="Glossary term translation (zh→ru) using LLM"
    )
    ap.add_argument("--proposals", "--input", required=True,
                    help="Input proposals YAML (from extract_terms)")
    ap.add_argument("--output", default="glossary/proposals_translated.yaml",
                    help="Output translated terms YAML")
    ap.add_argument("--style", default="workflow/style_guide.md",
                    help="Style guide for context")
    ap.add_argument("--batch_size", type=int, default=20,
                    help="Batch size for LLM translation")
    ap.add_argument("--max_terms", type=int, default=0,
                    help="Maximum terms to translate (0 = all)")
    ap.add_argument("--model", default="claude-haiku-4-5-20251001",
                    help="Model override (default: claude-haiku-4-5-20251001)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate without making LLM calls")
    args = ap.parse_args()
    
    print("🔤 Glossary Translate LLM")
    print(f"   Step: glossary_translate")
    print(f"   Proposals: {args.proposals}")
    print(f"   Output: {args.output}")
    print()
    
    # Load proposals
    if not Path(args.proposals).exists():
        print(f"❌ Proposals file not found: {args.proposals}")
        return 1
    
    entries = load_proposals(args.proposals)
    if not entries:
        print("ℹ️  No proposals to translate")
        return 0
    
    total_entries = len(entries)
    if args.max_terms > 0:
        entries = entries[:args.max_terms]
        print(f"✅ Loaded {len(entries)} / {total_entries} proposals (limited by --max_terms)")
    else:
        print(f"✅ Loaded {len(entries)} proposals")
    
    # Load style guide
    style_guide = load_style_guide(args.style)
    
    if args.dry_run:
        print()
        print("=" * 60)
        print("DRY-RUN MODE - Validation Summary")
        print("=" * 60)
        print(f"[OK] Would translate {len(entries)} terms")
        print(f"[OK] Step: glossary_translate (router-configured)")
        print(f"[OK] Would write to: {args.output}")
        print("[OK] Dry-run validation PASSED")
        print("=" * 60)
        return 0
    
    # Translate in batches using infrastructure
    # Map entries to rows expected by batch_llm_call
    rows = [
        {"id": e.get("term_zh"), "source_text": e.get("context", "")}
        for e in entries
    ]
    
    try:
        batch_results = batch_llm_call(
            step="glossary_translate",
            rows=rows,
            model=args.model,
            system_prompt=build_system_prompt(),
            user_prompt_template=build_user_prompt,
            content_type="normal",
            retry=1,
            allow_fallback=True
        )
        
        all_results = process_batch_results(batch_results, entries)
        
    except Exception as e:
        print(f"❌ Batch translation failed: {e}")
        return 1
    
    print()
    
    # Write output
    meta = {
        "source_proposals": args.proposals,
        "style_guide": args.style if style_guide else None,
        "batch_size": args.batch_size,
    }
    write_translated_yaml(args.output, all_results, meta)
    
    print(f"📋 Translated terms written to: {args.output}")
    print(f"   Total: {len(all_results)}")
    print()
    print("📝 Next steps:")
    print("   1. Run glossary_review_llm.py to review translations")
    print("   2. Or approve high-confidence translations directly")
    print()
    print("✅ Glossary translation complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
