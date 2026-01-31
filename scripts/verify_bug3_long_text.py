#!/usr/bin/env python3
"""验证 Bug 3 修复: 长文本隔离机制"""
import csv
import tempfile
import subprocess
import os
import json

def verify_fix():
    print("=== Bug 3 验证: 长文本隔离机制 ===\n")
    
    # 创建测试 CSV (包含长文本和短文本)
    test_input = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8', newline='')
    test_input.write('string_id,source_zh\n')
    test_input.write('short_001,短文本测试\n')
    # 生成超过 500 字符的长文本
    long_text = "这是一个超长文本" * 70  # 70 * 8 = 560 字符
    test_input.write(f'long_002,{long_text}\n')
    test_input.write('short_003,另一个短文本\n')
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

    # 检查输出是否包含 is_long_text 列
    print(f"2. 检查输出 CSV 是否包含 is_long_text 列...")
    with open(output_csv, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

        if 'is_long_text' not in reader.fieldnames:
            print("❌ 输出 CSV 缺少 is_long_text 列")
            cleanup_files(test_input.name, output_csv, map_json)
            return False

        # 检查标签正确性
        print(f"3. 检查长文本标签正确性...")
        short_rows = [r for r in rows if 'short' in r['string_id']]
        long_rows = [r for r in rows if 'long' in r['string_id']]

        if not short_rows or not long_rows:
            print("❌ 测试数据不完整")
            cleanup_files(test_input.name, output_csv, map_json)
            return False

        # 验证短文本标记为 0
        for row in short_rows:
            if row['is_long_text'] != '0':
                print(f"❌ 短文本 {row['string_id']} 标记错误: {row['is_long_text']}")
                cleanup_files(test_input.name, output_csv, map_json)
                return False

        # 验证长文本标记为 1
        for row in long_rows:
            if row['is_long_text'] != '1':
                print(f"❌ 长文本 {row['string_id']} 标记错误: {row['is_long_text']}")
                cleanup_files(test_input.name, output_csv, map_json)
                return False

        print(f"   ✓ 短文本标记: {len(short_rows)} 行 (is_long_text=0)")
        print(f"   ✓ 长文本标记: {len(long_rows)} 行 (is_long_text=1)")

    # 检查 translate_llm.py 中的长文本检测逻辑
    print(f"4. 检查 translate_llm.py 中的长文本检测逻辑...")
    with open('scripts/translate_llm.py', 'r', encoding='utf-8') as f:
        content = f.read()
        
        # 检查是否包含正确的检测逻辑
        if 'is_long_text' not in content:
            print("❌ translate_llm.py 缺少 is_long_text 检测")
            cleanup_files(test_input.name, output_csv, map_json)
            return False
        
        if 'content_type = "long_text"' not in content:
            print("❌ translate_llm.py 缺少 content_type 设置")
            cleanup_files(test_input.name, output_csv, map_json)
            return False

        print(f"   ✓ translate_llm.py 包含长文本检测逻辑")

    cleanup_files(test_input.name, output_csv, map_json)
    print("\n✅ Bug 3 修复验证通过: 长文本隔离机制正常工作")
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
