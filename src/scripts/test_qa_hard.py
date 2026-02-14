#!/usr/bin/env python3
"""
测试 qa_hard.py 脚本
验证 QA 检查功能是否正常工作
"""

import json
import sys
from pathlib import Path


def test_qa_hard():
    """测试 qa_hard 输出"""
    
    print("🧪 Testing qa_hard.py output...")
    print()
    
    # 测试好的翻译
    print("=" * 60)
    print("Test 1: Good translations (should pass)")
    print("=" * 60)
    
    good_report_path = Path("data/qa_report_good.json")
    if not good_report_path.exists():
        print("❌ Error: qa_report_good.json not found")
        return False
    
    with open(good_report_path, 'r', encoding='utf-8') as f:
        good_report = json.load(f)
    
    print(f"Total rows: {good_report['total_rows']}")
    print(f"Has errors: {good_report['has_errors']}")
    print(f"Total errors: {good_report['metadata']['total_errors']}")
    
    if good_report['has_errors']:
        print("❌ Test failed: Good translations should not have errors")
        return False
    
    print("✅ Test passed: No errors in good translations")
    print()
    
    # 测试坏的翻译
    print("=" * 60)
    print("Test 2: Bad translations (should fail)")
    print("=" * 60)
    
    bad_report_path = Path("data/qa_report_bad.json")
    if not bad_report_path.exists():
        print("❌ Error: qa_report_bad.json not found")
        return False
    
    with open(bad_report_path, 'r', encoding='utf-8') as f:
        bad_report = json.load(f)
    
    print(f"Total rows: {bad_report['total_rows']}")
    print(f"Has errors: {bad_report['has_errors']}")
    print(f"Total errors: {bad_report['metadata']['total_errors']}")
    print()
    
    print("Error counts:")
    for error_type, count in bad_report['error_counts'].items():
        if count > 0:
            print(f"  - {error_type}: {count}")
    
    if not bad_report['has_errors']:
        print("❌ Test failed: Bad translations should have errors")
        return False
    
    # 验证预期的错误类型
    expected_errors = {
        'token_mismatch': True,
        'tag_unbalanced': True,
        'forbidden_hit': True,
        'new_placeholder_found': True
    }
    
    for error_type, should_exist in expected_errors.items():
        count = bad_report['error_counts'].get(error_type, 0)
        if should_exist and count == 0:
            print(f"❌ Test failed: Expected {error_type} errors but found none")
            return False
    
    print()
    print("✅ Test passed: All expected error types detected")
    print()
    
    # 显示示例错误
    print("Sample errors from bad translations:")
    for i, error in enumerate(bad_report['errors'][:5], 1):
        print(f"{i}. [{error['type']}] {error['string_id']}")
        print(f"   {error['detail']}")
    
    print()
    print("🎉 All QA Hard tests passed!")
    return True


if __name__ == "__main__":
    success = test_qa_hard()
    sys.exit(0 if success else 1)
