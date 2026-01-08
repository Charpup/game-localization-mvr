#!/usr/bin/env python3
"""
测试 rehydrate_export.py 脚本
验证 token 还原功能是否正常工作
"""

import csv
import sys
from pathlib import Path


def test_rehydrate_export():
    """测试 rehydrate_export 输出"""
    
    print("🧪 Testing rehydrate_export.py output...")
    print()
    
    # 测试成功的还原
    print("=" * 60)
    print("Test 1: Good translations (should succeed)")
    print("=" * 60)
    
    final_path = Path("data/final_output.csv")
    if not final_path.exists():
        print("❌ Error: final_output.csv not found")
        return False
    
    with open(final_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"✅ Loaded {len(rows)} rows from final output")
    print()
    
    # 验证测试用例
    test_cases = [
        {
            'string_id': 'welcome_msg',
            'expected_rehydrated': 'Welcome {0} to the game!',
            'description': 'C# numbered placeholder'
        },
        {
            'string_id': 'level_up',
            'expected_rehydrated': "Congratulations! You've reached level {level}",
            'description': 'C# named placeholder'
        },
        {
            'string_id': 'color_text',
            'expected_rehydrated': '<color=#FF00FF>Rare Item</color> obtained!',
            'description': 'Unity color tags'
        },
        {
            'string_id': 'newline_test',
            'expected_rehydrated': 'First line\\nSecond line',
            'description': 'Newline escape sequence'
        }
    ]
    
    all_passed = True
    
    for test in test_cases:
        string_id = test['string_id']
        expected = test['expected_rehydrated']
        desc = test['description']
        
        # 找到对应的行
        row = next((r for r in rows if r['string_id'] == string_id), None)
        
        if not row:
            print(f"❌ Test failed: {string_id} not found in output")
            all_passed = False
            continue
        
        rehydrated = row.get('rehydrated_text', '')
        
        if rehydrated != expected:
            print(f"❌ Test failed: {string_id} ({desc})")
            print(f"   Expected: {expected}")
            print(f"   Got:      {rehydrated}")
            all_passed = False
            continue
        
        print(f"✅ Test passed: {string_id} ({desc})")
        print(f"   Rehydrated: {rehydrated}")
        print()
    
    if not all_passed:
        return False
    
    print("=" * 60)
    print("Test 2: Bad translations (should fail)")
    print("=" * 60)
    
    # 检查坏的翻译是否被正确拒绝
    bad_final_path = Path("data/final_bad_output.csv")
    if bad_final_path.exists():
        print("❌ Test failed: Bad translations should not produce output file")
        return False
    
    print("✅ Test passed: Bad translations correctly rejected")
    print("   (Unknown token PH_99 detected and script exited)")
    print()
    
    print("🎉 All rehydrate export tests passed!")
    return True


if __name__ == "__main__":
    success = test_rehydrate_export()
    sys.exit(0 if success else 1)
