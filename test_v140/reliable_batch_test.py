#!/usr/bin/env python3
"""
Loc-MVR v1.4.0 实战测试 - 可靠版同步 Batch
特性：
- 同步处理避免线程问题
- 每 batch 保存进度（断点续传）
- 详细的日志和统计
"""

import pandas as pd
import os
import json
import urllib.request
import time
from pathlib import Path
from datetime import datetime

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
print("Loc-MVR v1.4.0 实战测试 - 同步 Batch 版")
print("=" * 70)

# Load data
print("\n📥 加载数据...")
df = pd.read_csv('test_v140/workflow/normalized_input.csv')
total_rows = len(df)
print(f"   总行数: {total_rows}")

# Check for existing progress
output_file = 'test_v140/output/translated_reliable.csv'
if Path(output_file).exists():
    existing = pd.read_csv(output_file)
    completed = len(existing[existing['target_en'].notna()])
    print(f"   发现已有进度: {completed} 行已完成")
    start_idx = completed
else:
    start_idx = 0
    # Initialize output file
    df['target_en'] = ''
    df['status'] = 'pending'
    df['latency'] = 0.0
    df.to_csv(output_file, index=False)
    print(f"   新建输出文件: {output_file}")

# Load glossary
print("\n📚 加载术语库...")
import yaml
with open('test_v140/glossary/proposals/terms_en.yaml') as f:
    data = yaml.safe_load(f)
    glossary = {item['term_zh']: item['term_en'] for item in data.get('proposals', [])}
print(f"   术语数: {len(glossary)}")

# Translation function
def translate_text(text, context='general', retries=2):
    """单条翻译，带重试"""
    
    glossary_str = ", ".join([f"{k}={v}" for k, v in list(glossary.items())[:5]])
    
    prompt = f"""Translate Chinese to English (Naruto game). Use: {glossary_str}

Text: {text}

Output ONLY the English translation:"""
    
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                f'{BASE_URL}/chat/completions',
                headers={
                    'Authorization': f'Bearer {API_KEY}',
                    'Content-Type': 'application/json'
                },
                data=json.dumps({
                    'model': 'kimi-k2.5',
                    'messages': [
                        {'role': 'system', 'content': 'Professional game translator (zh→en)'},
                        {'role': 'user', 'content': prompt}
                    ],
                    'temperature': 0.3,
                    'max_tokens': 200
                }).encode()
            )
            
            start = time.time()
            with urllib.request.urlopen(req, timeout=90) as resp:
                result = json.loads(resp.read())
                latency = time.time() - start
                trans = result['choices'][0]['message']['content'].strip()
                return trans, 'success', latency
                
        except Exception as e:
            if attempt < retries:
                print(f"      ⚠️  Retry {attempt+1}/{retries}")
                time.sleep(1)
            else:
                return f"[ERROR: {str(e)[:40]}]", 'error', 0.0

# Main translation loop
batch_size = 5  # Small batch for reliability
print(f"\n🚀 开始翻译")
print(f"   起始行: {start_idx}")
print(f"   Batch 大小: {batch_size}")
print(f"   预计批次: {(total_rows - start_idx + batch_size - 1) // batch_size}")
print("=" * 70)

overall_start = time.time()
success_count = 0
error_count = 0
total_latency = 0.0

for batch_start in range(start_idx, total_rows, batch_size):
    batch_end = min(batch_start + batch_size, total_rows)
    batch_num = (batch_start // batch_size) + 1
    total_batches = (total_rows + batch_size - 1) // batch_size
    
    print(f"\n[Batch {batch_num}/{total_batches}] 行 {batch_start+1}-{batch_end}")
    
    batch_results = []
    for idx in range(batch_start, batch_end):
        row = df.iloc[idx]
        text = row['source_zh']
        context = row.get('context', 'general')
        
        print(f"  {idx+1}. {text[:30]}...", end=' ', flush=True)
        
        trans, status, latency = translate_text(text, context)
        batch_results.append((idx, trans, status, latency))
        
        if status == 'success':
            success_count += 1
            total_latency += latency
            print(f"✅ ({latency:.1f}s)")
        else:
            error_count += 1
            print(f"❌ {trans[:30]}")
        
        # Small delay between requests
        time.sleep(0.3)
    
    # Save progress after each batch
    for idx, trans, status, latency in batch_results:
        df.at[idx, 'target_en'] = trans
        df.at[idx, 'status'] = status
        df.at[idx, 'latency'] = latency
    
    df.to_csv(output_file, index=False)
    print(f"  💾 已保存进度 ({batch_end}/{total_rows})")
    
    # Progress stats
    elapsed = time.time() - overall_start
    speed = (batch_end - start_idx) / elapsed if elapsed > 0 else 0
    eta = (total_rows - batch_end) / speed if speed > 0 else 0
    
    print(f"  📊 进度: {batch_end}/{total_rows} | 速度: {speed:.1f} 行/秒 | ETA: {eta/60:.1f} 分钟")

# Final stats
overall_elapsed = time.time() - overall_start
print("\n" + "=" * 70)
print("✅ 翻译完成!")
print("=" * 70)
print(f"总行数:     {total_rows}")
print(f"成功:       {success_count} ({success_count/total_rows*100:.1f}%)")
print(f"失败:       {error_count} ({error_count/total_rows*100:.1f}%)")
print(f"总耗时:     {overall_elapsed:.1f} 秒 ({overall_elapsed/60:.1f} 分钟)")
print(f"平均速度:   {total_rows/overall_elapsed:.1f} 行/秒")
if success_count > 0:
    print(f"平均延迟:   {total_latency/success_count:.1f} 秒/行")
print(f"输出文件:   {output_file}")
print("=" * 70)

# Show samples
print("\n📝 翻译样例:")
done_df = df[df['status'] == 'success']
for i in range(min(10, len(done_df))):
    row = done_df.iloc[i]
    print(f"  {row['source_zh'][:30]}... → {row['target_en'][:40]}...")
