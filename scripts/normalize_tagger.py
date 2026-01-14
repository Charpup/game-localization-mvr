#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
normalize_tagger.py

Classify source text entries with module_tag for weighted glossary extraction.
Uses heuristic rules first, LLM fallback only if confidence < threshold.

Module Tags:
    ui_button, ui_label, system_notice, skill_desc, item_desc, dialogue, misc

Usage:
    python scripts/normalize_tagger.py \
        --input "data/source.csv" \
        --output "data/normalized.csv" \
        --llm_threshold 0.7

Environment:
    LLM_BASE_URL, LLM_API_KEY (for LLM fallback)
"""

import argparse
import csv
import json
import os
import re
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Module tag enum
MODULE_TAGS = [
    "ui_button",      # Short action texts (≤6 chars)
    "ui_label",       # UI labels (≤15 chars)
    "system_notice",  # System messages
    "skill_desc",     # Skill descriptions
    "item_desc",      # Item descriptions
    "dialogue",       # NPC dialogue
    "misc"            # Everything else
]

# Keywords for heuristic classification
SKILL_KEYWORDS = ['技能', '攻击', '伤害', '效果', '持续', '回合', '暴击', '治疗', '概率', 
                  '提升', '降低', '释放', '触发', '目标', '敌方', '我方', '单位', '全体',
                  '护盾', '免伤', '驱散', '控制', '沉默', '眩晕', '冷却', '叠加']

ITEM_KEYWORDS = ['道具', '装备', '获得', '消耗', '碎片', '材料', '合成', '镶嵌', '宝石',
                 '戒指', '项链', '起爆符', '手里剑', '忍具', '礼包', '宝箱']

SYSTEM_KEYWORDS = ['已', '不可', '请', '警告', '提示', '确认', '取消', '是否', '正在',
                   '错误', '失败', '成功', '完成', '解锁', '开启', '关闭', '重置']

UI_BUTTON_KEYWORDS = ['确定', '取消', '返回', '领取', '购买', '前往', '开始', '继续',
                      '查看', '刷新', '使用', '选择', '分解', '升级', '兑换', '强化']

# Placeholder pattern for density calculation
PLACEHOLDER_PATTERN = re.compile(r'\{[\d\w]+\}|%[sd]|\u003c[^>]+\u003e|\[.+?\]|【.+?】')


@dataclass
class TagResult:
    string_id: str
    source_zh: str
    module_tag: str
    max_len_ru: int
    placeholder_flags: str
    confidence: float
    method: str  # "heuristic", "llm", or "skipped"
    status: str = "ok"  # "ok", "skipped_empty"
    is_empty_source: bool = False


def count_placeholders(text: str) -> int:
    """Count placeholders in text."""
    return len(PLACEHOLDER_PATTERN.findall(text))


def estimate_max_len_ru(text: str) -> int:
    """Estimate max Russian translation length (chars).
    
    Russian is typically 1.3-1.5x longer than Chinese.
    Add buffer for safety.
    """
    base_len = len(text)
    # Remove placeholders from base length
    clean_text = PLACEHOLDER_PATTERN.sub('', text)
    char_len = len(clean_text)
    
    # Expansion factor + original placeholder length
    ru_estimate = int(char_len * 1.5) + (base_len - char_len)
    
    # Add 20% buffer, min 10 chars
    return max(10, int(ru_estimate * 1.2))


def classify_heuristic(text: str) -> Tuple[str, float]:
    """Classify text using heuristic rules.
    
    Returns (module_tag, confidence).
    """
    text_len = len(text)
    placeholder_count = count_placeholders(text)
    placeholder_density = placeholder_count / max(1, text_len) * 100
    
    # Check for punctuation patterns
    has_question = '?' in text or '？' in text
    has_exclamation = '!' in text or '！' in text
    has_brackets = '【' in text or '】' in text or '「' in text or '」' in text
    has_ellipsis = '...' in text or '…' in text
    
    # Count keyword matches
    text_lower = text.lower()
    skill_score = sum(1 for kw in SKILL_KEYWORDS if kw in text)
    item_score = sum(1 for kw in ITEM_KEYWORDS if kw in text)
    system_score = sum(1 for kw in SYSTEM_KEYWORDS if kw in text)
    button_score = sum(1 for kw in UI_BUTTON_KEYWORDS if kw in text)
    
    # Classification logic
    
    # 1. Very short text (≤6 chars) → likely button
    if text_len <= 6 and not has_ellipsis:
        if button_score > 0:
            return "ui_button", 0.95
        return "ui_button", 0.75
    
    # 2. Short text (≤15 chars) with no dialogue markers → label
    if text_len <= 15 and not has_question and not has_exclamation and not has_ellipsis:
        if has_brackets:
            return "system_notice", 0.8
        return "ui_label", 0.7
    
    # 3. High placeholder density → system notice
    if placeholder_density > 5 or placeholder_count >= 3:
        return "system_notice", 0.8
    
    # 4. Skill description patterns
    if skill_score >= 3 or (skill_score >= 2 and '%' in text):
        return "skill_desc", 0.85
    
    # 5. Item description patterns
    if item_score >= 2 or (item_score >= 1 and '碎片' in text):
        return "item_desc", 0.8
    
    # 6. System notice patterns
    if system_score >= 2 or has_brackets:
        return "system_notice", 0.75
    
    # 7. Long text with dialogue markers → dialogue
    if text_len > 50 and (has_question or has_exclamation or has_ellipsis):
        return "dialogue", 0.75
    
    # 8. Very long text → likely dialogue or story
    if text_len > 100:
        return "dialogue", 0.6
    
    # 9. Medium-length skill-like text
    if skill_score >= 1 and text_len > 20:
        return "skill_desc", 0.65
    
    # 10. Default to misc with low confidence
    return "misc", 0.5


def classify_with_llm(entries: List[Dict], llm_client) -> Dict[str, Tuple[str, float]]:
    """Classify entries using LLM (batch).
    
    Returns dict of string_id -> (module_tag, confidence).
    """
    results = {}
    
    # Build prompt
    entries_text = ""
    for i, e in enumerate(entries[:20], 1):  # Max 20 per batch
        text = e['source_zh'][:100]  # Truncate long texts
        entries_text += f"{i}. [{e['string_id']}] {text}\n"
    
    prompt = f"""Classify each game text into one category:
- ui_button: Short action button text (确定, 取消, 领取)
- ui_label: UI labels and headers
- system_notice: System messages, errors, notifications
- skill_desc: Skill/ability descriptions with damage/effects
- item_desc: Item/equipment descriptions
- dialogue: NPC dialogue, story text
- misc: Other

Texts:
{entries_text}

Output JSON array:
[{{"id": 1, "string_id": "...", "tag": "skill_desc", "confidence": 0.9}}]

Only output JSON, no explanation."""

    try:
        result = llm_client.chat(
            system="You are a game text classifier.",
            user=prompt,
            metadata={"step": "normalize_tagging", "batch_size": len(entries)}
        )
        
        # Parse response
        try:
            data = json.loads(result.text.strip())
        except:
            start = result.text.find('[')
            end = result.text.rfind(']')
            if start != -1 and end > start:
                data = json.loads(result.text[start:end+1])
            else:
                return results
        
        for item in data:
            sid = str(item.get("string_id", ""))
            tag = item.get("tag", "misc")
            conf = float(item.get("confidence", 0.7))
            if tag in MODULE_TAGS and sid:
                results[sid] = (tag, conf)
                
    except Exception as e:
        print(f"    ⚠️ LLM classification error: {e}")
    
    return results


def process_entries(input_csv: str, llm_threshold: float, use_llm: bool = True) -> List[TagResult]:
    """Process all entries with heuristic + optional LLM fallback."""
    results = []
    low_confidence_entries = []
    
    # Read input
    with open(input_csv, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        
        # Flexible column mapping
        id_col = None
        zh_col = None
        for name in ['string_id', 'id', 'ID', 'StringId']:
            if name in fields:
                id_col = name
                break
        for name in ['source_zh', 'zh', 'ZH', 'text', 'Text']:
            if name in fields:
                zh_col = name
                break
        
        if not id_col or not zh_col:
            raise ValueError(f"CSV must have ID and source columns. Found: {fields}")
        
        rows = list(reader)
    
    print(f"  Processing {len(rows)} entries with heuristic classification...")
    
    # First pass: heuristic classification - PRESERVE ALL ROWS
    for row in rows:
        string_id = str(row.get(id_col, ''))
        source_zh = row.get(zh_col, '') or ''
        
        # Handle empty source - PRESERVE ROW with status=skipped_empty
        if not source_zh.strip():
            result = TagResult(
                string_id=string_id,
                source_zh=source_zh,
                module_tag="empty",
                max_len_ru=0,
                placeholder_flags="",
                confidence=1.0,
                method="skipped",
                status="skipped_empty",
                is_empty_source=True
            )
            results.append(result)
            continue
        
        tag, confidence = classify_heuristic(source_zh)
        placeholder_count = count_placeholders(source_zh)
        max_len_ru = estimate_max_len_ru(source_zh)
        
        result = TagResult(
            string_id=string_id,
            source_zh=source_zh,
            module_tag=tag,
            max_len_ru=max_len_ru,
            placeholder_flags=f"count={placeholder_count}" if placeholder_count else "",
            confidence=confidence,
            method="heuristic",
            status="ok",
            is_empty_source=False
        )
        results.append(result)
        
        if confidence < llm_threshold:
            low_confidence_entries.append({
                'string_id': string_id,
                'source_zh': source_zh,
                'result_idx': len(results) - 1
            })
    
    # Second pass: LLM for low-confidence entries
    if use_llm and low_confidence_entries:
        print(f"  Found {len(low_confidence_entries)} low-confidence entries (< {llm_threshold})")
        
        try:
            from runtime_adapter import LLMClient
            llm = LLMClient()
            
            # Process in batches
            for i in range(0, len(low_confidence_entries), 20):
                batch = low_confidence_entries[i:i+20]
                print(f"    LLM batch {i//20 + 1}/{(len(low_confidence_entries)+19)//20}...")
                
                llm_results = classify_with_llm(batch, llm)
                
                for entry in batch:
                    sid = entry['string_id']
                    if sid in llm_results:
                        tag, conf = llm_results[sid]
                        idx = entry['result_idx']
                        results[idx].module_tag = tag
                        results[idx].confidence = conf
                        results[idx].method = "llm"
                        
        except Exception as e:
            print(f"  ⚠️ LLM fallback unavailable: {e}")
            print("  Continuing with heuristic-only results.")
    
    return results


def write_normalized_csv(path: str, results: List[TagResult]) -> None:
    """Write normalized CSV output."""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'string_id', 'source_zh', 'module_tag', 'max_len_ru', 
            'placeholder_flags', 'confidence', 'status', 'is_empty_source'
        ])
        writer.writeheader()
        for r in results:
            writer.writerow({
                'string_id': r.string_id,
                'source_zh': r.source_zh,
                'module_tag': r.module_tag,
                'max_len_ru': r.max_len_ru,
                'placeholder_flags': r.placeholder_flags,
                'confidence': round(r.confidence, 2),
                'status': r.status,
                'is_empty_source': r.is_empty_source
            })


def main():
    ap = argparse.ArgumentParser(
        description="Classify source texts with module tags for weighted extraction"
    )
    ap.add_argument("--input", required=True,
                    help="Input CSV file")
    ap.add_argument("--output", default="data/normalized.csv",
                    help="Output normalized CSV")
    ap.add_argument("--llm_threshold", type=float, default=0.7,
                    help="Confidence threshold for LLM fallback")
    ap.add_argument("--no-llm", action="store_true",
                    help="Disable LLM fallback, use heuristic only")
    ap.add_argument("--dry-run", action="store_true",
                    help="Validate without writing output")
    args = ap.parse_args()
    
    print("🏷️  Normalize Tagger")
    print(f"   Input: {args.input}")
    print(f"   Output: {args.output}")
    print(f"   LLM threshold: {args.llm_threshold}")
    print()
    
    if not Path(args.input).exists():
        print(f"❌ Input file not found: {args.input}")
        return 1
    
    # Process entries
    results = process_entries(
        args.input, 
        args.llm_threshold,
        use_llm=not args.no_llm
    )
    
    if not results:
        print("❌ No entries processed")
        return 1
    
    # Stats
    tag_counts = {}
    method_counts = {"heuristic": 0, "llm": 0}
    for r in results:
        tag_counts[r.module_tag] = tag_counts.get(r.module_tag, 0) + 1
        method_counts[r.method] = method_counts.get(r.method, 0) + 1
    
    print()
    print("📊 Classification Stats:")
    for tag in MODULE_TAGS:
        count = tag_counts.get(tag, 0)
        pct = count / len(results) * 100 if results else 0
        print(f"   {tag:15} {count:5} ({pct:5.1f}%)")
    print()
    print(f"   Heuristic: {method_counts['heuristic']}, LLM: {method_counts['llm']}")
    
    if args.dry_run:
        print()
        print("DRY-RUN: Would write to", args.output)
        return 0
    
    # Write output
    write_normalized_csv(args.output, results)
    print()
    print(f"✅ Wrote {len(results)} entries to: {args.output}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
