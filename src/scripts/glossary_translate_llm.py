#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
glossary_translate_llm.py

Dedicated script for glossary term translation (multi-language support).
Uses router-configured model for "glossary_translate" step.

Usage:
    python scripts/glossary_translate_llm.py \
        --proposals glossary/proposals.yaml \
        --output glossary/proposals_translated.yaml \
        --source-lang zh-CN --target-lang ru-RU \
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

try:
    from scripts.runtime_adapter import LLMClient, LLMError, BatchConfig, batch_llm_call, log_llm_progress
except ImportError:
    from runtime_adapter import LLMClient, LLMError, BatchConfig, batch_llm_call, log_llm_progress


# Language code mapping for short codes used in field names
LANG_CODE_MAP = {
    "zh-CN": "zh",
    "zh-TW": "zh_tw",
    "en-US": "en",
    "en-GB": "en",
    "ru-RU": "ru",
    "ja-JP": "ja",
    "ko-KR": "ko",
    "fr-FR": "fr",
    "de-DE": "de",
    "es-ES": "es",
    "pt-BR": "pt",
    "it-IT": "it",
    "ar-SA": "ar",
    "th-TH": "th",
    "vi-VN": "vi",
    "id-ID": "id",
}


@dataclass
class TranslatedTerm:
    term_source: str
    term_target: str
    confidence: float
    reason: str
    context: Optional[str] = None
    pos: Optional[str] = None


def get_short_lang_code(lang_code: str) -> str:
    """Get short language code for field naming (e.g., 'ru-RU' -> 'ru')."""
    return LANG_CODE_MAP.get(lang_code, lang_code.split('-')[0].lower())


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


def get_language_name(lang_code: str) -> str:
    """Get human-readable language name."""
    names = {
        "zh-CN": "简体中文",
        "zh-TW": "繁體中文",
        "en-US": "English",
        "en-GB": "English (UK)",
        "ru-RU": "Русский",
        "ja-JP": "日本語",
        "ko-KR": "한국어",
        "fr-FR": "Français",
        "de-DE": "Deutsch",
        "es-ES": "Español",
        "pt-BR": "Português (Brasil)",
        "it-IT": "Italiano",
        "ar-SA": "العربية",
        "th-TH": "ไทย",
        "vi-VN": "Tiếng Việt",
        "id-ID": "Bahasa Indonesia",
    }
    return names.get(lang_code, lang_code)


def build_system_prompt(source_lang: str, target_lang: str) -> str:
    """
    Build system prompt for glossary translation based on language pair.
    
    Args:
        source_lang: Source language code (e.g., 'zh-CN', 'en-US')
        target_lang: Target language code (e.g., 'ru-RU', 'en-US')
    
    Returns:
        System prompt string tailored for the language pair
    """
    source_name = get_language_name(source_lang)
    target_name = get_language_name(target_lang)
    target_short = get_short_lang_code(target_lang)
    
    # Base prompt template with language placeholders
    base_prompt = (
        f"你是术语表译者（{source_name} → {target_name}），为手游项目生成"可落地"的术语对。\n"
        f"任务：把候选 id 翻译为 term_{target_short}，并给出简短注释，避免把整句当术语。\n\n"
    )
    
    # Language-specific rules
    lang_rules = {
        "ru": [
            "term_ru 不得包含【】；如需要引号用 «»。",
            "专有名词/技能名优先音译或官方惯用译法；系统词优先简洁一致。",
        ],
        "en": [
            "Use natural, game-appropriate English terminology.",
            "Prioritize official translations for proper nouns/skill names.",
            "Keep system terms concise and consistent.",
        ],
        "ja": [
            "カタカナ表記はゲーム業界標準に従う。",
            "固有名詞は公式訳を優先する。",
        ],
        "ko": [
            "게임 업계 표준 용어를 사용하세요.",
            "고유명사는 공식 번역을 우선시하세요.",
        ],
        "fr": [
            "Utilisez la terminologie naturelle et appropriée pour les jeux.",
            "Priorisez les traductions officielles pour les noms propres.",
        ],
        "de": [
            "Verwenden Sie natürliche, spielgerechte deutsche Terminologie.",
            "Priorisieren Sie offizielle Übersetzungen für Eigennamen.",
        ],
        "es": [
            "Utilice terminología natural y apropiada para videojuegos.",
            "Priorice las traducciones oficiales para nombres propios.",
        ],
    }
    
    # Get rules for target language (default to generic)
    target_rules = lang_rules.get(target_short, [
        f"Use natural, game-appropriate {target_name} terminology.",
        "Prioritize official translations for proper nouns/skill names.",
    ])
    
    # Build rules section
    rules_section = "规则（硬性）：\n" if target_short in ["zh", "ru", "ja", "ko"] else "Rules (Mandatory):\n"
    rules_section += "- id 必须与输入一致（不要改写）。\n" if target_short in ["zh", "ru", "ja", "ko"] else "- id must match input exactly (do not rewrite).\n"
    
    for rule in target_rules:
        rules_section += f"- {rule}\n"
    
    # Output format section
    output_section = (
        "\n输出 JSON（仅输出 JSON）：\n"
        "{\n"
        '  "items": [\n'
        "    {\n"
        '      "id": "<原样>",\n'
        f'      "term_{target_short}": "<{target_name}术语>",\n'
        '      "pos": "noun|verb|adj|phrase|name|system",\n'
        '      "notes": "<可选：一句话说明语境/是否可变格>",\n'
        '      "confidence": 0.0\n'
        "    }\n"
        "  ]\n"
        "}\n"
    ) if target_short in ["zh", "ru", "ja", "ko"] else (
        "\nOutput JSON (output JSON only):\n"
        "{\n"
        '  "items": [\n'
        "    {\n"
        '      "id": "<original>",\n'
        f'      "term_{target_short}": "<{target_name} Term>",\n'
        '      "pos": "noun|verb|adj|phrase|name|system",\n'
        '      "notes": "<optional: context notes>",\n'
        '      "confidence": 0.0\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )
    
    return base_prompt + output_section + "\n" + rules_section


def build_user_prompt(items: List[Dict], source_lang: str, target_lang: str) -> str:
    """Build user prompt for glossary translation from batch items."""
    source_name = get_language_name(source_lang)
    target_name = get_language_name(target_lang)
    
    candidates = []
    for item in items:
        candidates.append({
            "term_source": item.get('id', ''),
            "context": item.get('source_text', '') or ''
        })
    
    return (
        f"language_pair: {source_lang} -> {target_lang}\n"
        f"context_hint: Game Localization (Naruto-like)\n\n"
        "candidates:\n"
        f"{json.dumps(candidates, ensure_ascii=False, indent=2)}\n"
    )


def process_batch_results(
    batch_items: List[Dict], 
    original_entries: List[Dict],
    target_lang: str
) -> List[TranslatedTerm]:
    """
    Convert batch output items back to TranslatedTerm objects.
    
    Args:
        batch_items: Items returned from LLM batch processing
        original_entries: Original input entries
        target_lang: Target language code for field name resolution
    """
    results = []
    entry_map = {e.get("term_zh"): e for e in original_entries}
    
    # Get dynamic field name for target language
    target_short = get_short_lang_code(target_lang)
    term_field = f"term_{target_short}"
    
    for item in batch_items:
        term_source = item.get("id")
        entry = entry_map.get(term_source)
        
        if not entry:
            continue

        term_target = item.get(term_field, "")
        if term_target:
            results.append(TranslatedTerm(
                term_source=term_source,
                term_target=term_target,
                confidence=float(item.get("confidence", 0.0)),
                reason=item.get("notes", "") + " | " + item.get("pos", ""),
                context=entry.get("context"),
                pos=item.get("pos")
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
        description="Glossary term translation (multi-language) using LLM"
    )
    ap.add_argument("--proposals", "--input", required=True,
                    help="Input proposals YAML (from extract_terms)")
    ap.add_argument("--output", default="glossary/proposals_translated.yaml",
                    help="Output translated terms YAML")
    ap.add_argument("--source-lang", default="zh-CN",
                    help="Source language code (default: zh-CN)")
    ap.add_argument("--target-lang", default="ru-RU",
                    help="Target language code (default: ru-RU)")
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
    
    source_name = get_language_name(args.source_lang)
    target_name = get_language_name(args.target_lang)
    
    print("🔤 Glossary Translate LLM")
    print(f"   Step: glossary_translate")
    print(f"   Language Pair: {source_name} ({args.source_lang}) → {target_name} ({args.target_lang})")
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
        print(f"[OK] From {source_name} ({args.source_lang}) to {target_name} ({args.target_lang})")
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
            system_prompt=build_system_prompt(args.source_lang, args.target_lang),
            user_prompt_template=lambda items: build_user_prompt(items, args.source_lang, args.target_lang),
            content_type="normal",
            retry=1,
            allow_fallback=True
        )
        
        all_results = process_batch_results(batch_results, entries, args.target_lang)
        
    except Exception as e:
        print(f"❌ Batch translation failed: {e}")
        return 1
    
    print()
    
    # Write output
    meta = {
        "source_proposals": args.proposals,
        "source_lang": args.source_lang,
        "target_lang": args.target_lang,
        "style_guide": args.style if style_guide else None,
        "batch_size": args.batch_size,
    }
    write_translated_yaml(args.output, all_results, meta)
    
    print(f"📋 Translated terms written to: {args.output}")
    print(f"   Total: {len(all_results)}")
    print(f"   Language: {source_name} → {target_name}")
    print()
    print("📝 Next steps:")
    print("   1. Run glossary_review_llm.py to review translations")
    print("   2. Or approve high-confidence translations directly")
    print()
    print("✅ Glossary translation complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
