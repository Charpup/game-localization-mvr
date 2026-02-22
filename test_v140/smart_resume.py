#!/usr/bin/env python3
"""
智能版翻译 - 自动跳过超时行，确保进度持续推进
"""
import pandas as pd
import os
import json
import urllib.request
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

os.chdir('/root/.openclaw/workspace/projects/game-localization-mvr')

with open('.env') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            key, value = line.strip().split('=', 1)
            os.environ[key] = value

API_KEY = os.environ.get('OPENAI_API_KEY')
BASE_URL = os.environ.get('OPENAI_BASE_URL', 'https://api.apiyi.com/v1')

print("=" * 70)
print("Loc-MVR v1.4.0 智能版翻译 - 自动跳过超时")
print("=" * 70)

df = pd.read_csv('test_v140/output/translated_reliable.csv')
total = len(df)
start_idx = len(df[df['status'] == 'success'])

print(f"\n总数据: {total} 行")
print(f"已完成: {start_idx} 行")
print(f"待处理: {total - start_idx} 行")

if start_idx >= total:
    print("\n✅ 已完成！")
    exit(0)

def translate_single(idx, text):
    """单条翻译，带错误处理"""
    try:
        # Truncate very long text
        text_short = text[:150] if len(text) > 150 else text
        
        prompt = f"Translate to English (concise): {text_short}"
        req = urllib.request.Request(
            f'{BASE_URL}/chat/completions',
            headers={
                'Authorization': f'Bearer {API_KEY}',
                'Content-Type': 'application/json'
            },
            data=json.dumps({
                'model': 'kimi-k2.5',
                'messages': [
                    {'role': 'system', 'content': 'Game translator'},
                    {'role': 'user', 'content': prompt}
                ],
                'max_tokens': 100
            }).encode()
        )
        
        start = time.time()
        with urllib.request.urlopen(req, timeout=20) as resp:  # Shorter timeout
            result = json.loads(resp.read())
            elapsed = time.time() - start
            trans = result['choices'][0]['message']['content'].strip()
            return idx, trans, 'success', elapsed
    except Exception as e:
        return idx, f"[SKIP: {str(e)[:20]}]", 'skipped', 0.0

print(f"\n🚀 处理剩余 {total - start_idx} 行...")
print("=" * 70)

# Process with shorter timeout per row
for idx in range(start_idx, total):
    row = df.iloc[idx]
    text = row['source_zh']
    
    print(f"[{idx+1}/{total}] {text[:30]}...", end=' ', flush=True)
    
    # Use ThreadPoolExecutor with timeout
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(translate_single, idx, text)
        try:
            i, trans, status, latency = future.result(timeout=25)  # Hard timeout
        except FutureTimeoutError:
            i, trans, status, latency = idx, "[TIMEOUT SKIP]", 'timeout', 0.0
            print("⏱️ SKIP", end='')
    
    df.at[idx, 'target_en'] = trans
    df.at[idx, 'status'] = status
    df.at[idx, 'latency'] = latency
    
    if status == 'success':
        print(f" ✅ ({latency:.1f}s)")
    else:
        print(f" ⚠️  {status}")
    
    # Save every 5 rows
    if (idx + 1) % 5 == 0:
        df.to_csv('test_v140/output/translated_reliable.csv', index=False)
        print(f"    💾 Saved ({idx+1}/{total})")

# Final save
df.to_csv('test_v140/output/translated_reliable.csv', index=False)

# Stats
success = len(df[df['status'] == 'success'])
skipped = len(df[df['status'].isin(['skipped', 'timeout'])])
print("\n" + "=" * 70)
print("✅ 完成!")
print(f"成功: {success} | 跳过: {skipped} | 总计: {total}")
print(f"完成率: {success/total*100:.1f}%")
print("=" * 70)
