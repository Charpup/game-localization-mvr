#!/usr/bin/env python3
"""
测试 extract_terms.py 脚本
验证术语提取功能是否正常工作
"""

import json
import sys
import yaml
from pathlib import Path


def test_extract_terms():
    """测试术语提取输出"""
    
    print("🧪 Testing extract_terms.py output...")
    print()
    
    # 测试文件路径
    candidates_path = Path("data/term_candidates_test.yaml")
    
    if not candidates_path.exists():
        print("❌ Error: term_candidates_test.yaml not found")
        print("   Please run: python scripts/extract_terms.py data/input.csv data/term_candidates_test.yaml data/glossary.yaml")
        return False
    
    # 加载候选列表
    with open(candidates_path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
    
    print(f"✅ Loaded term candidates file")
    print()
    
    # 验证基本结构
    required_keys = ['version', 'generated_at', 'statistics', 'candidates']
    for key in required_keys:
        if key not in data:
            print(f"❌ Test failed: Missing key '{key}' in output")
            return False
    
    print("✅ Test passed: File structure correct")
    print()
    
    # 验证统计信息
    stats = data['statistics']
    print(f"📊 Statistics:")
    print(f"   Total strings: {stats['total_strings']}")
    print(f"   Unique terms: {stats['unique_terms']}")
    print(f"   Total occurrences: {stats.get('total_occurrences', 'N/A')}")
    print()
    
    # 验证候选列表
    candidates = data['candidates']
    print(f"📋 Candidates ({len(candidates)} terms):")
    
    for i, cand in enumerate(candidates[:5], 1):  # 显示前 5 个
        term = cand.get('term', '')
        freq = cand.get('frequency', 0)
        string_ids = cand.get('string_ids', [])
        
        if not term or freq < 1:
            print(f"❌ Test failed: Invalid candidate #{i}")
            return False
        
        print(f"   {i}. {term} (频率: {freq}, 出现在 {len(string_ids)} 个字符串)")
    
    print()
    
    # 验证提取规则
    rules = data.get('extraction_rules', {})
    if rules:
        print(f"⚙️  Extraction rules:")
        print(f"   Min frequency: {rules.get('min_frequency')}")
        print(f"   Min length: {rules.get('min_length')}")
        print(f"   Max length: {rules.get('max_length')}")
        print(f"   Segmentation: {rules.get('segmentation')}")
    
    print()
    print("🎉 All extract_terms tests passed!")
    return True


if __name__ == "__main__":
    success = test_extract_terms()
    sys.exit(0 if success else 1)
