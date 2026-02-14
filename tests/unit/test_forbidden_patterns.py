#!/usr/bin/env python3
"""
测试 forbidden_patterns.txt 规则
验证关键的禁用模式是否正常工作
"""

import re
import sys
from pathlib import Path


def test_forbidden_patterns():
    """测试禁用模式"""
    
    print("🧪 Testing forbidden_patterns.txt...")
    print()
    
    # 加载规则
    patterns_file = Path("workflow/forbidden_patterns.txt")
    if not patterns_file.exists():
        print("❌ Error: forbidden_patterns.txt not found")
        return False
    
    patterns = []
    with open(patterns_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                patterns.append(line)
    
    print(f"✅ Loaded {len(patterns)} forbidden patterns")
    print()
    
    # 测试用例
    test_cases = [
        # [文本, 应该匹配的模式, 描述]
        ("这是一些中文文本", r"[\u4e00-\u9fff]", "检测中文字符"),
        ("⟦PH_1⟧ some text ⟦PH_2", r"⟦PH_[0-9]+⟧.*⟦PH_[0-9]+(?!⟧)", "检测未闭合的PH token"),
        ("⟦TAG_1⟧ text ⟦TAG_2", r"⟦TAG_[0-9]+⟧.*⟦TAG_[0-9]+(?!⟧)", "检测未闭合的TAG token"),
        ("Text with  multiple  spaces", r"  {2,}", "检测连续空格"),
        ("TODO: finish this", r"TODO", "检测TODO标记"),
        ("[待翻译]的文本", r"\[待翻译\]", "检测待翻译标记"),
        ("Some � character", r"�", "检测乱码字符"),
    ]
    
    all_passed = True
    
    for text, expected_pattern, description in test_cases:
        # 找到匹配的模式
        matched = False
        for pattern in patterns:
            try:
                if re.search(pattern, text):
                    matched = True
                    if pattern == expected_pattern:
                        print(f"✅ {description}")
                        print(f"   匹配文本: '{text}'")
                        print(f"   使用模式: {pattern}")
                        print()
                        break
            except re.error as e:
                print(f"⚠️  警告: 模式 '{pattern}' 语法错误: {e}")
        
        if not matched:
            print(f"❌ 测试失败: {description}")
            print(f"   文本 '{text}' 应该匹配模式 {expected_pattern}，但未匹配")
            all_passed = False
            print()
    
    # 测试不应该匹配的情况
    negative_tests = [
        ("Normal English text", "正常英文文本不应触发禁用"),
        ("⟦PH_1⟧ ⟦PH_2⟧", "正确的token格式不应触发"),
        ("Single space text", "单个空格不应触发"),
    ]
    
    print("🔍 负面测试（不应该匹配）:")
    for text, description in negative_tests:
        matched_any = False
        for pattern in patterns:
            try:
                # 跳过某些通用模式
                if pattern in [r"  {2,}", r"[\u4e00-\u9fff]"]:
                    continue
                if re.search(pattern, text):
                    matched_any = True
                    break
            except re.error:
                pass
        
        if not matched_any:
            print(f"  ✅ {description}: '{text}'")
        else:
            print(f"  ⚠️  {description}: '{text}' 意外匹配了某个模式")
    
    print()
    
    if all_passed:
        print("🎉 All forbidden pattern tests passed!")
        return True
    else:
        print("❌ Some tests failed")
        return False


if __name__ == "__main__":
    success = test_forbidden_patterns()
    sys.exit(0 if success else 1)
