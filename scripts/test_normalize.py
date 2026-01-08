#!/usr/bin/env python3
"""
测试 normalize_guard.py 脚本
验证占位符冻结功能是否正常工作
"""

import csv
import json
import sys
from pathlib import Path


def test_normalize_guard():
    """测试 normalize_guard 输出"""
    
    print("🧪 Testing normalize_guard.py output...")
    print()
    
    # 检查输出文件是否存在
    draft_path = Path("data/draft_output.csv")
    map_path = Path("data/placeholder_map_output.json")
    
    if not draft_path.exists():
        print("❌ Error: draft_output.csv not found")
        return False
    
    if not map_path.exists():
        print("❌ Error: placeholder_map_output.json not found")
        return False
    
    print("✅ Output files exist")
    
    # 读取 draft CSV
    with open(draft_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"✅ Loaded {len(rows)} rows from draft CSV")
    
    # 读取 placeholder map
    with open(map_path, 'r', encoding='utf-8') as f:
        map_data = json.load(f)
    
    mappings = map_data.get('mappings', {})
    print(f"✅ Loaded {len(mappings)} placeholder mappings")
    print()
    
    # 验证测试用例
    test_cases = [
        {
            'string_id': 'welcome_msg',
            'expected_tokens': ['⟦PH_1⟧'],
            'expected_mappings': {'PH_1': '{0}'}
        },
        {
            'string_id': 'color_text',
            'expected_tokens': ['⟦TAG_1⟧', '⟦TAG_2⟧'],
            'expected_mappings': {'TAG_1': '</color>', 'TAG_2': '<color=#FF00FF>'}
        },
        {
            'string_id': 'multi_placeholder',
            'expected_tokens': ['⟦PH_4⟧', '⟦PH_5⟧', '⟦PH_6⟧'],
            'expected_mappings': {
                'PH_4': '{itemName}',
                'PH_5': '{location}',
                'PH_6': '{playerName}'
            }
        }
    ]
    
    all_passed = True
    
    for test in test_cases:
        string_id = test['string_id']
        expected_tokens = test['expected_tokens']
        expected_mappings = test['expected_mappings']
        
        # 找到对应的行
        row = next((r for r in rows if r['string_id'] == string_id), None)
        
        if not row:
            print(f"❌ Test failed: {string_id} not found in output")
            all_passed = False
            continue
        
        tokenized = row.get('tokenized_zh', '')
        
        # 检查 token 是否存在
        tokens_found = all(token in tokenized for token in expected_tokens)
        
        if not tokens_found:
            print(f"❌ Test failed: {string_id}")
            print(f"   Expected tokens: {expected_tokens}")
            print(f"   Tokenized text: {tokenized}")
            all_passed = False
            continue
        
        # 检查映射是否正确
        mappings_correct = all(
            mappings.get(key) == value
            for key, value in expected_mappings.items()
        )
        
        if not mappings_correct:
            print(f"❌ Test failed: {string_id} - incorrect mappings")
            all_passed = False
            continue
        
        print(f"✅ Test passed: {string_id}")
        print(f"   Tokens: {expected_tokens}")
        print(f"   Tokenized: {tokenized}")
        print()
    
    # 验证总数
    metadata = map_data.get('metadata', {})
    total_placeholders = metadata.get('total_placeholders', 0)
    
    if total_placeholders != 11:
        print(f"❌ Expected 11 total placeholders, got {total_placeholders}")
        all_passed = False
    else:
        print(f"✅ Correct total placeholder count: {total_placeholders}")
    
    print()
    
    if all_passed:
        print("🎉 All tests passed!")
        return True
    else:
        print("❌ Some tests failed")
        return False


if __name__ == "__main__":
    success = test_normalize_guard()
    sys.exit(0 if success else 1)
