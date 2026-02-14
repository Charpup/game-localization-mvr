#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
normalize_tagger.py (v2.0)

Classify source text entries with module_tag and length constraints.
Features:
- New Fields: module_tag, module_confidence, max_len_target, len_tier (S/M/L), source_locale
- Logic: Heuristic first, LLM fallback if confidence < threshold.
- Invariant: ALL input rows preserved.

Usage:
    python scripts/normalize_tagger.py \
        --input "data/source_raw.csv" \
        --output "data/normalized.csv" \
        --source-locale "zh-CN"
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import yaml
from dataclasses import dataclass, asdict
from typing import Dict, List, Any, Optional, Tuple

# Unified batch infrastructure
try:
    from runtime_adapter import BatchConfig, batch_llm_call, log_llm_progress
except ImportError:
    batch_llm_call = None

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Module tags
MODULE_TAGS = [
    "ui_button",      # Short action texts (≤6 chars)
    "ui_label",       # UI labels (≤15 chars)
    "system_notice",  # System messages
    "skill_desc",     # Skill descriptions
    "item_desc",      # Item descriptions
    "dialogue",       # NPC dialogue
    "misc"            # Everything else
]

# Keywords (ZH-CN)
KEYWORDS = {
    'skill_desc': ['技能', '攻击', '伤害', '效果', '持续', '回合', '暴击', '治疗', '概率'],
    'item_desc': ['道具', '装备', '获得', '消耗', '碎片', '材料', '合成'],
    'system_notice': ['已', '不可', '请', '警告', '提示', '确认', '错误', '失败', '成功'],
    'ui_button': ['确定', '取消', '返回', '领取', '购买', '前往', '开始']
}

# ID Prefix rules (High confidence classification)
ID_PREFIX_RULES = {
    'ui_button': ['BTN_', 'BUTTON_', 'UI_BTN'],
    'ui_label': ['UI_', 'LABEL_', 'TXT_'],
    'skill_desc': ['SKILL_', 'ABILITY_', 'SPELL_'],
    'item_desc': ['ITEM_', 'EQUIP_', 'MATERIAL_'],
    'dialogue': ['DIALOG_', 'NPC_', 'STORY_', 'QUEST_'],
    'system_notice': ['SYS_', 'MSG_', 'NOTICE_', 'ERROR_'],
}

# Thresholds
LONG_TEXT_THRESHOLD = 200  # Character count
PLACEHOLDER_PATTERN = re.compile(r'\{[\d\w]+\}|%[sd]|\u003c[^>]+\u003e|\[.+?\]|【.+?】')

TAGGER_SYSTEM_PROMPT = """You are a game localization text classifier.
Classify each text entry into exactly ONE category:
- ui_button: Short action buttons (≤6 chars), e.g., "确定", "取消"
- ui_label: UI labels (≤15 chars), e.g., "等级", "金币"
- skill_desc: Skill/ability descriptions with damage/effect terms
- item_desc: Item/equipment descriptions
- dialogue: NPC dialogue, story text, quest descriptions
- system_notice: System messages, warnings, errors
- misc: Everything else

Return JSON format:
{"items": [{"id": "<string_id>", "tag": "<category>", "confidence": <0.0-1.0>}]}
"""

@dataclass
class TagResult:
    string_id: str
    source_zh: str
    module_tag: str
    module_confidence: float
    max_len_target: int
    len_tier: str  # S, M, L
    source_locale: str
    placeholder_flags: str
    status: str = "ok"
    is_empty_source: bool = False
    is_long_text: bool = False

def count_placeholders(text: str) -> int:
    return len(PLACEHOLDER_PATTERN.findall(text))

def get_len_tier(length: int) -> str:
    if length <= 10: return "S"
    if length <= 50: return "M"
    return "L"

# Load length rules
def load_length_rules(path: str = "config/length_rules.yaml") -> dict:
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    return {"default": {"multiplier": 3.0, "min_buffer": 5, "max_absolute": 500}}

def calculate_max_len_target(text: str, content_type: str, rules: dict) -> int:
    """Calculate max target length based on rules."""
    zh_len = len(text)
    
    # Get rules
    type_rules = rules.get("by_content_type", {}).get(content_type, rules.get("default", {}))
    
    multiplier = type_rules.get("multiplier", 3.0)
    min_buffer = type_rules.get("min_buffer", 5)
    max_absolute = type_rules.get("max_absolute", 500)
    
    calculated = int(zh_len * multiplier) + min_buffer
    return min(calculated, max_absolute)

def heuristic_tag(text: str, string_id: str = "") -> Tuple[str, float]:
    """Heuristic tagging with ID prefix support."""
    if not text:
        return "misc", 0.0

    # 1. ID Prefix Priority (High confidence)
    if string_id:
        sid_upper = string_id.upper()
        for tag, prefixes in ID_PREFIX_RULES.items():
            if any(sid_upper.startswith(p) for p in prefixes):
                return tag, 0.95

    length = len(text)
    
    # 2. Length-based high confidence
    if length <= 4:
        # Check if button keyword
        if any(k in text for k in KEYWORDS['ui_button']):
            return "ui_button", 0.95
        return "ui_button", 0.7  # Short text default
        
    # 3. Keywords
    scores = {}
    for tag, kws in KEYWORDS.items():
        score = sum(1 for kw in kws if kw in text)
        if score > 0:
            scores[tag] = score
            
    if scores:
        best_tag = max(scores, key=scores.get)
        return best_tag, 0.8
        
    # 4. Structure
    if '...' in text or len(text) > 60:
        return "dialogue", 0.6
        
    return "misc", 0.5

def build_tagger_prompt(items: List[Dict]) -> str:
    """Build user prompt for LLM classification."""
    # items from batch_llm_call: list of {'id', 'source_text'}
    clean_items = []
    for it in items:
        clean_items.append({
            "id": it["id"],
            "text": it["source_text"][:500] # Truncate for efficiency
        })
    return f"Classify these texts:\n{json.dumps(clean_items, ensure_ascii=False, indent=2)}"

def llm_tag_fallback(low_conf_entries: List[Dict], model: str) -> Dict[str, Tuple[str, float]]:
    """Call LLM to classify low-confidence entries."""
    if not low_conf_entries or not batch_llm_call:
        return {}
    
    # Row format for batch_llm_call
    batch_rows = [{"id": e["string_id"], "source_text": e["source_zh"]} for e in low_conf_entries]
    
    print(f"  [Tagger] {len(batch_rows)} entries below threshold, invoking LLM...")
    
    try:
        results = batch_llm_call(
            step="normalize_tag",
            rows=batch_rows,
            model=model,
            system_prompt=TAGGER_SYSTEM_PROMPT,
            user_prompt_template=build_tagger_prompt,
            content_type="normal",
            retry=1,
            allow_fallback=True
        )
        
        tag_map = {}
        for it in results:
            sid = str(it.get("id", ""))
            tag = it.get("tag", "misc")
            conf = it.get("confidence", 0.85)
            if sid and tag in MODULE_TAGS:
                tag_map[sid] = (tag, conf)
        
        return tag_map
    except Exception as e:
        print(f"⚠️  LLM Tag Fallback failed: {e}")
        return {}

def process_entries(input_csv: str, source_locale: str, llm_threshold: float, 
                    use_llm: bool, length_rules_path: str = "config/length_rules.yaml",
                    model: str = "claude-haiku-4-5-20251001") -> List[TagResult]:
    
    rules = load_length_rules(length_rules_path)

    results = []
    low_conf_buffer = []  # Store metadata for fallback
    
    try:
        with open(input_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
    except Exception as e:
        print(f"[Error] Failed to read CSV: {e}")
        return []
        
    print(f"Processing {len(rows)} rows...")
    
    # Pass 1: Heuristic & Long Text detection
    for i, row in enumerate(rows):
        sid = row.get('string_id') or row.get('id') or row.get('ID')
        src = row.get('source_zh') or row.get('source') or row.get('zh') or ''
        
        if not sid:
            continue
            
        is_empty = not bool(src.strip())
        tag, conf = heuristic_tag(src, string_id=sid) if not is_empty else ("empty", 1.0)
        
        is_long = len(src) > LONG_TEXT_THRESHOLD
        max_len = calculate_max_len_target(src, tag, rules)
        len_tier = get_len_tier(len(src))
        
        res = TagResult(
            string_id=str(sid),
            source_zh=src,
            module_tag=tag,
            module_confidence=conf,
            max_len_target=max_len,
            len_tier=len_tier,
            source_locale=source_locale,
            placeholder_flags=f"count={count_placeholders(src)}",
            status="skipped_empty" if is_empty else "ok",
            is_empty_source=is_empty,
            is_long_text=is_long
        )
        
        if not is_empty and conf < llm_threshold and use_llm:
            low_conf_buffer.append({
                "index": i,
                "string_id": str(sid),
                "source_zh": src
            })
            
        results.append(res)
        
    # Pass 2: LLM Fallback
    if low_conf_buffer and use_llm:
        tag_map = llm_tag_fallback(low_conf_buffer, model)
        
        # Apply updates
        update_count = 0
        for entry in low_conf_buffer:
            idx = entry["index"]
            sid = entry["string_id"]
            if sid in tag_map:
                new_tag, new_conf = tag_map[sid]
                results[idx].module_tag = new_tag
                results[idx].module_confidence = new_conf
                results[idx].status = "llm_tagged"
                update_count += 1
        
        print(f"  [Tagger] LLM updated {update_count} entries")
        
    return results

def write_csv(path: str, results: List[TagResult]):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8', newline='') as f:
        # Explicit column order
        fieldnames = [
            'string_id', 'source_zh', 'module_tag', 'module_confidence',
            'max_len_target', 'len_tier', 'source_locale', 
            'placeholder_flags', 'status', 'is_empty_source', 'is_long_text'
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="data/normalized.csv")
    parser.add_argument("--source-locale", default="zh-CN")
    parser.add_argument("--llm-threshold", type=float, default=0.7)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--length-rules", default="config/length_rules.yaml")
    
    args = parser.parse_args()
    
    results = process_entries(
        args.input, 
        args.source_locale, 
        args.llm_threshold, 
        not args.no_llm,
        args.length_rules,
        args.model
    )
    
    if results:
        write_csv(args.output, results)
        print(f"✅ Normalized {len(results)} rows to {args.output}")
    else:
        print("❌ No rows processed")
        sys.exit(1)

if __name__ == "__main__":
    main()

