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

from runtime_adapter import LLMClient, LLMError


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


def build_translate_prompt(entries: List[Dict], style_guide: str, batch_size: int = 20) -> str:
    """Build prompt for translating glossary terms zh→ru."""
    entries_text = ""
    for i, e in enumerate(entries[:batch_size], 1):
        term_zh = e.get('term_zh', '')
        context = e.get('context', '') or ''
        if not context and e.get('examples'):
            examples = e.get('examples', [])
            if examples and isinstance(examples[0], dict):
                context = examples[0].get('source_zh', '')[:80]
        
        entries_text += f"{i}. {term_zh}\n"
        if context:
            entries_text += f"   Context: {context[:80]}\n"
    
    prompt = f"""You are a professional game localization translator for zh-CN → ru-RU.

Translate the following Chinese game terms to Russian.

For each term, provide:
1. term_ru: Russian translation
2. confidence: 0.0 to 1.0 (how certain you are)
3. reason: brief explanation of translation choice

Translation Guidelines:
- Proper nouns (names, places): transliterate, do not translate
- Game mechanics terms: use established Russian gaming terminology
- Keep translations concise and natural for game UI

Style Guide Context:
{style_guide[:500] if style_guide else "(No style guide provided)"}

Chinese Terms:
{entries_text}

Output JSON array:
[
  {{"id": 1, "term_ru": "Ниндзя", "confidence": 0.95, "reason": "Standard transliteration"}},
  {{"id": 2, "term_ru": "Урон", "confidence": 0.9, "reason": "Common RPG term"}}
]

Only output the JSON array, no explanation."""
    
    return prompt


def parse_translate_response(text: str, entries: List[Dict]) -> List[TranslatedTerm]:
    """Parse LLM translation response."""
    results = []
    
    # Extract JSON from response
    try:
        data = json.loads(text.strip())
    except json.JSONDecodeError:
        start = text.find('[')
        end = text.rfind(']')
        if start != -1 and end > start:
            try:
                data = json.loads(text[start:end+1])
            except:
                return []
        else:
            return []
    
    if not isinstance(data, list):
        return []
    
    for item in data:
        idx = item.get("id", 0) - 1
        if 0 <= idx < len(entries):
            entry = entries[idx]
            term_ru = item.get("term_ru", "")
            if term_ru:
                results.append(TranslatedTerm(
                    term_zh=entry.get("term_zh", ""),
                    term_ru=term_ru,
                    confidence=float(item.get("confidence", 0.0)),
                    reason=item.get("reason", ""),
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
    ap.add_argument("--proposals", required=True,
                    help="Input proposals YAML (from extract_terms)")
    ap.add_argument("--output", default="glossary/proposals_translated.yaml",
                    help="Output translated terms YAML")
    ap.add_argument("--style", default="workflow/style_guide.md",
                    help="Style guide for context")
    ap.add_argument("--batch_size", type=int, default=20,
                    help="Batch size for LLM translation")
    ap.add_argument("--max_terms", type=int, default=0,
                    help="Maximum terms to translate (0 = all)")
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
    
    # Initialize LLM with explicit step
    try:
        llm = LLMClient()
        print(f"✅ LLM client initialized")
    except LLMError as e:
        print(f"❌ LLM initialization failed: {e}")
        return 1
    
    # Translate in batches
    all_results: List[TranslatedTerm] = []
    
    for i in range(0, len(entries), args.batch_size):
        batch = entries[i:i + args.batch_size]
        batch_num = i // args.batch_size + 1
        total_batches = (len(entries) + args.batch_size - 1) // args.batch_size
        
        print(f"  [{batch_num}/{total_batches}] Translating {len(batch)} terms...")
        
        prompt = build_translate_prompt(batch, style_guide, args.batch_size)
        
        try:
            # CRITICAL: metadata.step MUST be exactly "glossary_translate"
            result = llm.chat(
                system="You are a professional game localization translator for zh-CN → ru-RU.",
                user=prompt,
                metadata={
                    "step": "glossary_translate",  # REQUIRED for routing
                    "batch": batch_num,
                    "scope": "zh-CN->ru-RU"
                }
            )
            
            translations = parse_translate_response(result.text, batch)
            all_results.extend(translations)
            
            print(f"    ✅ Translated: {len(translations)}")
            
        except LLMError as e:
            print(f"    ⚠️  LLM error: {e}")
    
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
