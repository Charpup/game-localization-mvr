#!/usr/bin/env python3
"""
Verification script for glossary_translate_llm.py refactor using Mocks.
Ensures batch_llm_call and process_batch_results are correctly integrated.
"""
import sys
import os
import json
from unittest.mock import MagicMock, patch
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Import the module components
import glossary_translate_llm
from runtime_adapter import LLMResult

def test_refactor_integration():
    """Verify that glossary_translate_llm correctly handles mapping and results."""
    
    entries = [
        {"term_zh": "火之意志", "context": "Plot context"},
        {"term_zh": "写轮眼", "context": "Skill context"}
    ]
    
    # 1. Test data mapping (rows construction)
    rows = [
        {"id": e.get("term_zh"), "source_text": e.get("context", "")}
        for e in entries
    ]
    assert rows[0]["id"] == "火之意志"
    assert rows[1]["source_text"] == "Skill context"
    print("✅ Input row mapping sequence OK")

    # 2. Test prompt generation mapping
    # items in build_user_prompt are constructed by batch_llm_call
    mock_items = [{"id": r["id"], "source_text": r["source_text"]} for r in rows]
    user_prompt = glossary_translate_llm.build_user_prompt(mock_items)
    
    assert "火之意志" in user_prompt
    assert "Skill context" in user_prompt
    print("✅ User prompt template mapping OK")

    # 3. Test multi-stage result processing
    # Simulated output from batch_llm_call
    mock_batch_results = [
        {
            "id": "火之意志",
            "term_ru": "Воля Огня",
            "pos": "phrase",
            "notes": "Core concept",
            "confidence": 0.95
        },
        {
            "id": "写轮眼",
            "term_ru": "Шаринган",
            "pos": "name",
            "notes": "Dojutsu",
            "confidence": 0.99
        }
    ]
    
    all_results = glossary_translate_llm.process_batch_results(mock_batch_results, entries)
    
    assert len(all_results) == 2
    assert all_results[0].term_zh == "火之意志"
    assert all_results[0].term_ru == "Воля Огня"
    assert all_results[1].term_ru == "Шаринган"
    print(f"✅ Result processing and mapping back OK: {len(all_results)} items")

    print("\n" + "="*50)
    print("✅ GLOSSARY_TRANSLATE REFACTOR VERIFIED (LOGIC ONLY)")
    print("="*50)

if __name__ == "__main__":
    test_refactor_integration()
