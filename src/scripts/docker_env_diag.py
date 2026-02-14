#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Docker环境诊断脚本"""

import os
import sys

def main():
    print("🔍 Docker环境诊断")
    print("=" * 60)
    
    # 检查环境变量
    api_key = os.getenv("LLM_API_KEY", "")
    base_url = os.getenv("LLM_BASE_URL", "")
    trace_path = os.getenv("LLM_TRACE_PATH", "")
    
    print(f"\n📋 环境变量:")
    print(f"  LLM_API_KEY: {'✅ 已设置' if api_key else '❌ 未设置'}")
    if api_key:
        print(f"    长度: {len(api_key)} 字符")
        print(f"    前缀: {api_key[:10]}...")
        print(f"    后缀: ...{api_key[-10:]}")
    
    print(f"\n  LLM_BASE_URL: {base_url if base_url else '❌ 未设置'}")
    print(f"  LLM_TRACE_PATH: {trace_path if trace_path else '(未设置)'}")
    
    print("\n📋 所有 LLM_ 开头的环境变量:")
    for key, val in os.environ.items():
        if key.startswith("LLM_"):
            if "API_KEY" in key and val:
                masked_val = f"{val[:5]}...{val[-5:]}" if len(val) > 10 else "***"
                print(f"  {key}: {masked_val}")
            else:
                print(f"  {key}: {val}")
    
    # Check if a file is causing interference
    key_file = os.getenv("LLM_API_KEY_FILE", "")
    if key_file:
        print(f"\n⚠️  发现 LLM_API_KEY_FILE 设置: {key_file}")
        if os.path.exists(key_file):
            print("  ✅ 文件存在")
            try:
                with open(key_file, 'r') as f:
                    content = f.read().strip()
                print(f"  📄 文件内容长度: {len(content)}")
                print(f"  📄 文件内容预览: {content[:10]}...{content[-10:]}")
            except Exception as e:
                print(f"  ❌ 读取失败: {e}")
        else:
            print("  ❌ 文件不存在")
    
    # 测试网络连接
    print(f"\n🌐 网络连接测试:")
    try:
        import requests
        resp = requests.get(f"{base_url}/models", headers={"Authorization": f"Bearer {api_key}"}, timeout=10)
        print(f"  状态码: {resp.status_code}")
        if resp.status_code == 200:
            print(f"  ✅ API连接成功")
        else:
            print(f"  ❌ API连接失败")
            print(f"  响应: {resp.text[:200]}")
    except Exception as e:
        print(f"  ❌ 网络错误: {str(e)}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
