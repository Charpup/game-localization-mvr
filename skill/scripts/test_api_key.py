#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试API密钥有效性"""

import os
import sys
import requests

def test_api_key():
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL", "https://api.apiyi.com/v1")
    
    if not api_key:
        print("❌ LLM_API_KEY 未设置")
        return False
    
    print(f"🔑 测试API密钥: {api_key[:20]}...")
    print(f"🌐 Base URL: {base_url}")
    
    # 测试 /models 端点
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        resp = requests.get(f"{base_url}/models", headers=headers, timeout=10)
        print(f"📡 状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            print("✅ API密钥有效")
            return True
        elif resp.status_code == 401:
            print(f"❌ 认证失败: {resp.text[:200]}")
            return False
        else:
            print(f"⚠️ 未知状态: {resp.text[:200]}")
            return False
            
    except Exception as e:
        print(f"❌ 请求失败: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_api_key()
    sys.exit(0 if success else 1)
