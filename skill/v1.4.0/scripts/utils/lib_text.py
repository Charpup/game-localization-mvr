#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import yaml
from typing import Dict, Optional, List

def load_punctuation_config(base_path: str, locale_path: Optional[str] = None) -> List[Dict[str, str]]:
    """
    Load and merge punctuation mappings.
    Returns list of dicts: [{'source': '...', 'target': '...'}, ...]
    Strategy: Base rules + Locale overrides (upsert by source key).
    """
    mappings = []
    
    # 1. Load Base
    try:
        with open(base_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            replace_map = data.get('replace', {})
            for k, v in replace_map.items():
                mappings.append({'source': k, 'target': v})
    except Exception:
        # It's acceptable if base doesn't exist or fails, we proceed
        pass
        
    # 2. Load Locale
    if locale_path:
        try:
            with open(locale_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                replace_map = data.get('replace', {})
                
                for k, v in replace_map.items():
                    # Upsert
                    found = False
                    for m in mappings:
                        if m['source'] == k:
                            m['target'] = v
                            found = True
                            break
                    if not found:
                        mappings.append({'source': k, 'target': v})
        except Exception:
            pass
            
    return mappings

def sanitize_punctuation(text: str, mappings: List[Dict[str, str]]) -> str:
    """
    Apply punctuation rules to text.
    """
    if not text or not mappings:
        return text
        
    result = text
    for rule in mappings:
        src = rule.get('source')
        tgt = rule.get('target')
        if src and src in result:
            result = result.replace(src, tgt)
            
    return result
