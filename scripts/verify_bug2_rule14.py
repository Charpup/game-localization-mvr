#!/usr/bin/env python3
"""验证 Bug 2 修复: Rule 14 参数锁定"""
import os

def verify_fix():
    # 检查 WORKSPACE_RULES.md 是否包含 Rule 14
    rules_path = 'docs/WORKSPACE_RULES.md'
    if not os.path.exists(rules_path):
        print(f"❌ 未找到 {rules_path}")
        return False

    with open(rules_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 检查关键字
    checks = [
        ('Rule 14' in content or '## 14.' in content, "Rule 14 标题"),
        ('Parameter Locking' in content, "Parameter Locking 关键词"),
        ('batch_size' in content and '50' in content, "batch_size 参数"),
        ('立即停止执行' in content or 'STOP execution' in content or '禁止' in content, "强制约束"),
        ('parameter_change_log.txt' in content, "变更日志引用")
    ]

    failed_checks = [name for passed, name in checks if not passed]
    
    if not failed_checks:
        # 检查参数变更日志是否存在
        log_path = 'data/parameter_change_log.txt'
        if os.path.exists(log_path):
            print("✅ Bug 2 修复验证通过: Rule 14 已添加且包含强制约束，参数变更日志已创建")
            return True
        else:
            print(f"❌ 参数变更日志不存在: {log_path}")
            return False
    else:
        print(f"❌ Rule 14 内容不完整，缺失: {', '.join(failed_checks)}")
        return False

if __name__ == '__main__':
    import sys
    sys.exit(0 if verify_fix() else 1)
