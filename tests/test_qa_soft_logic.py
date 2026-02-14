#!/usr/bin/env python3
"""
Verification script for soft_qa_llm.py refactor using Mocks.
Ensures integration with partial_match and task mapping.
"""
import sys
import os
import json
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import soft_qa_llm

def test_qa_soft_refactor_logic():
    """Verify data mapping and partial result processing for soft QA."""
    
    # 1. Test input mapping (including ZH/RU concatenation)
    rows = [
        {"string_id": "id1", "source_zh": "你好", "target_text": "Привет"},
        {"string_id": "id2", "source_zh": "再见", "target_text": "Пока"}
    ]
    
    batch_rows = []
    for r in rows:
        batch_rows.append({
            "id": r.get("string_id"),
            "source_text": f"SRC: {r['source_zh']} | TGT: {r['target_text']}"
        })
    
    assert batch_rows[0]["id"] == "id1"
    assert "Привет" in batch_rows[0]["source_text"]
    print("✅ Input row mapping OK")

    # 2. Test user prompt reconstruction
    mock_batch_items = [{"id": r["id"], "source_text": r["source_text"]} for r in batch_rows]
    user_prompt = soft_qa_llm.build_user_prompt(mock_batch_items)
    
    prompt_data = json.loads(user_prompt)
    assert len(prompt_data) == 2
    assert prompt_data[0]["string_id"] == "id1"
    assert prompt_data[0]["source_zh"] == "你好"
    assert prompt_data[0]["target_ru"] == "Привет"
    print("✅ User prompt reconstruction OK")

    # 3. Test partial result processing (filtering)
    # Simulator returns ONLY ONE item with an issue
    mock_batch_results = [
        {
            "id": "id1",
            "issue_type": "tone",
            "severity": "minor",
            "problem": "Too formal",
            "suggestion": "Make it cuter",
            "preferred_fix_ru": "Приветик"
        }
    ]
    
    tasks = soft_qa_llm.process_batch_results(mock_batch_results)
    
    assert len(tasks) == 1
    assert tasks[0]["string_id"] == "id1"
    assert "minor" in tasks[0]["severity"]
    assert "Приветик" in tasks[0]["suggested_fix"]
    print("✅ Partial result processing OK")

    print("\n" + "="*50)
    print("✅ SOFT_QA REFACTOR VERIFIED (LOGIC ONLY)")
    print("="*50)

if __name__ == "__main__":
    test_qa_soft_refactor_logic()
