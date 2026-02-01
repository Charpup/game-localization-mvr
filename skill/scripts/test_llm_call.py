#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试LLM API调用"""

import os
import sys
import json
import requests

def test_llm_call():
    api_key = "sk-2Ks9TvuDvfZzFkwID6Cb43EcEeCd40929e8eFe1dE5604080"
    base_url = "https://api.apiyi.com/v1"
    
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": "你是翻译助手"},
            {"role": "user", "content": "翻译：你好"}
        ]
    }
    
    print("🔍 测试LLM API调用...")
    print(f"URL: {url}")
    print(f"Model: {payload['model']}")
    
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        print(f"\n📡 状态码: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            print(f"✅ 调用成功")
            print(f"响应: {text}")
            return True
        else:
            print(f"❌ 调用失败")
            print(f"响应: {resp.text[:500]}")
            return False
            
    except Exception as e:
        print(f"❌ 异常: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_llm_call()
    sys.exit(0 if success else 1)
