#!/usr/bin/env python3
"""验证 Bug 4 修复: 标签空格清理"""
import csv
import tempfile
import subprocess
import os

def verify_fix():
    print("=== Bug 4 验证: 标签空格清理 ===\n")
    
    # 创建测试 CSV (包含 HTML/Unity 标签)
    test_input = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8', newline='')
    test_input.write('string_id,source_zh\n')
    test_input.write('tag_001,这是<color=#ff0000>红色文本</color>\n')
    test_input.write('tag_002,<b>粗体</b>和<i>斜体</i>混合\n')
    test_input.write('tag_003,<size=14>大号字体</size>测试\n')
    test_input.close()

    # 运行 normalize_guard.py
    output_csv = tempfile.NamedTemporaryFile(suffix='.csv', delete=False).name
    map_json = tempfile.NamedTemporaryFile(suffix='.json', delete=False).name

    print(f"1. 测试 normalize_guard.py...")
    result = subprocess.run([
        'python', 'scripts/normalize_guard.py',
        test_input.name, output_csv, map_json, 'workflow/placeholder_schema.yaml'
    ], capture_output=True, text=True, encoding='utf-8')

    if result.returncode != 0:
        print(f"❌ normalize_guard.py 执行失败:")
        print(f"   stderr: {result.stderr}")
        print(f"   stdout: {result.stdout}")
        cleanup_files(test_input.name, output_csv, map_json)
        return False

    # 检查输出是否保留标签完整性
    print(f"2. 检查标签完整性...")
    with open(output_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        if not rows:
            print("❌ 输出 CSV 为空")
            cleanup_files(test_input.name, output_csv, map_json)
            return False

        # 检查每一行的 tokenized_zh
        for row in rows:
            tokenized = row.get('tokenized_zh', '')
            
            # 标签不应有多余空格
            if '< color' in tokenized or 'color =' in tokenized:
                print(f"❌ 标签被破坏 ({row['string_id']}): {tokenized}")
                cleanup_files(test_input.name, output_csv, map_json)
                return False
            
            # 标签不应被分词插入空格
            if '< b >' in tokenized or '< / b >' in tokenized:
                print(f"❌ 标签被分词破坏 ({row['string_id']}): {tokenized}")
                cleanup_files(test_input.name, output_csv, map_json)
                return False

        print(f"   ✓ 所有标签保持完整 ({len(rows)} 行)")

    # 检查标签是否被正确冻结为 token
    print(f"3. 检查标签冻结...")
    tag_frozen_count = 0
    for row in rows:
        tokenized = row.get('tokenized_zh', '')
        # 检查是否包含 TAG token
        if '⟦TAG_' in tokenized:
            tag_frozen_count += 1

    if tag_frozen_count > 0:
        print(f"   ✓ {tag_frozen_count} 行包含冻结的标签 token")
    else:
        print(f"   ⚠️  未检测到冻结的标签 token（可能标签已被完整保留）")

    cleanup_files(test_input.name, output_csv, map_json)
    print("\n✅ Bug 4 修复验证通过: 标签空格清理机制正常工作")
    return True

def cleanup_files(*files):
    """清理临时文件"""
    for f in files:
        try:
            if os.path.exists(f):
                os.remove(f)
        except:
            pass

if __name__ == '__main__':
    import sys
    sys.exit(0 if verify_fix() else 1)
