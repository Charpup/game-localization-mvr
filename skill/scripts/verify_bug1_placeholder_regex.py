#!/usr/bin/env python3
"""验证 Bug 1 修复: 占位符 Regex 扩展"""
import yaml
import re

def verify_fix():
    with open('workflow/placeholder_schema.yaml', 'r', encoding='utf-8') as f:
        schema = yaml.safe_load(f)

    # 检查是否存在 percent_space_letter pattern
    patterns = schema.get('patterns', [])
    found = False
    for p in patterns:
        if p.get('name') == 'percent_space_letter':
            found = True
            pattern = p.get('regex')
            # 测试能否匹配 "% H"
            if re.search(pattern, "获得 % H 点数"):
                print("✅ Bug 1 修复验证通过: pattern 已添加且能匹配 '% H'")
                return True
            else:
                print("❌ Pattern 已添加但无法匹配测试样例")
                return False

    if not found:
        print("❌ 未找到 percent_space_letter pattern")
        return False

if __name__ == '__main__':
    import sys
    sys.exit(0 if verify_fix() else 1)
