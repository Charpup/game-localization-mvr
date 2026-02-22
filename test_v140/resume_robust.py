#!/usr/bin/env python3
"""
健壮版翻译重启 - 带超时保护和错误处理
"""
import pandas as pd
import os
import json
import urllib.request
import time
import signal
from pathlib import Path

# Timeout handler
class TimeoutError(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutError("Request timeout")

signal.signal(signal.SIGALRM, timeout_handler)

# Setup
os.chdir('/root/.openclaw/workspace/projects/game-localization-mvr')

with open('.env') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            key, value = line.strip().split('=', 1)
            os.environ[key] = value

API_KEY = os.environ.get('OPENAI_API_KEY')
BASE_URL = os.environ.get('OPENAI_BASE_URL', 'https://api.apiyi.com/v1')

print("=" * 70)
print("Loc-MVR v1.4.0 健壮版翻译重启")
print("=" * 70)

# Load data
df = pd.read_csv('test_v140/output/translated_reliable.csv')
total = len(df)
start_idx = len(df[df['status'] == 'success'])

print(f"\n总数据: {total} 行")
print(f"已完成: {start_idx} 行")
print(f"待处理: {total - start_idx} 行")

if start_idx >= total:
    print("\n✅ 所有翻译已完成！")
    exit(0)

print(f"\n🚀 从第 {start_idx + 1} 行继续...")
print("=" * 70)

def translate_with_timeout(text, timeout_secs=30):
    """带超时的翻译"""
    prompt = f"Translate Chinese to English (game): {text[:100]}"
    
    req = urllib.request.Request(
        f'{BASE_URL}/chat/completions',
        headers={
            'Authorization': f'Bearer {API_KEY}',
            'Content-Type': 'application/json'
        },
        data=json.dumps({
            'model': 'kimi-k2.5',
            'messages': [
                {'role': 'system', 'content': 'Game translator zh→en'},
                {'role': 'user', 'content': prompt}
            ],
            'max_tokens': 150
        }).encode()
    )
    
    signal.alarm(timeout_secs)
    try:
        with urllib.request.urlopen(req, timeout=timeout_secs) as resp:
            result = json.loads(resp.read())
            signal.alarm(0)
            return result['choices'][0]['message']['content'].strip(), 'success'
    except TimeoutError:
        return "[TIMEOUT]", 'timeout'
    except Exception as e:
        signal.alarm(0)
        return f"[ERROR: {str(e)[:30]}]", 'error'

# Process remaining rows
batch_size = 5
save_interval = 10
processed = 0

for idx in range(start_idx, total):
    row = df.iloc[idx]
    text = row['source_zh']
    
    print(f"[{idx+1}/{total}] {text[:35]}...", end=' ', flush=True)
    
    start_time = time.time()
    trans, status = translate_with_timeout(text, timeout_secs=45)
    elapsed = time.time() - start_time
    
    df.at[idx, 'target_en'] = trans
    df.at[idx, 'status'] = status
    df.at[idx, 'latency'] = elapsed
    
    if status == 'success':
        print(f"✅ ({elapsed:.1f}s)")
    elif status == 'timeout':
        print(f"⏱️  TIMEOUT")
    else:
        print(f"❌ {trans[:20]}")
    
    processed += 1
    
    # Save periodically
    if processed % save_interval == 0:
        df.to_csv('test_v140/output/translated_reliable.csv', index=False)
        print(f"  💾 已保存 ({idx+1}/{total})")
    
    # Small delay
    time.sleep(0.5)

# Final save
df.to_csv('test_v140/output/translated_reliable.csv', index=False)

# Stats
success = len(df[df['status'] == 'success'])
print("\n" + "=" * 70)
print("✅ 完成!")
print(f"成功: {success}/{total} ({success/total*100:.1f}%)")
print("=" * 70)
