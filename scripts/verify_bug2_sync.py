#!/usr/bin/env python3
"""验证 Bug 2 补充修复: 规则同步到 Antigravity"""
import os

def verify_fix():
    # 检查 .agent/rules/localization-mvr-rules.md 是否包含 Rule 14
    antigravity_rules_path = '.agent/rules/localization-mvr-rules.md'
    if not os.path.exists(antigravity_rules_path):
        print(f"❌ 未找到 {antigravity_rules_path}")
        return False

    with open(antigravity_rules_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查关键字
    checks = [
        ('Parameter Locking' in content, "Parameter Locking 关键词"),
        ('batch_size' in content and '50' in content, "batch_size 参数"),
        ('立即停止执行' in content, "强制约束"),
        ('parameter_change_log.txt' in content, "变更日志引用"),
        ('Version: 2.3' in content, "版本号更新到 2.3"),
        ('2026-01-31' in content, "更新日期")
    ]

    failed_checks = [name for passed, name in checks if not passed]
    
    if not failed_checks:
        print("✅ Bug 2 补充修复验证通过: Rule 14 已同步到 Antigravity 规则文件")
        return True
    else:
        print(f"❌ Antigravity 规则文件内容不完整，缺失: {', '.join(failed_checks)}")
        return False

if __name__ == '__main__':
    import sys
    sys.exit(0 if verify_fix() else 1)
