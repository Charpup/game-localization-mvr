#!/usr/bin/env python3
"""
Loc-MVR v1.4.0 分批异步实战测试
利用现有 batch_utils 和 batch_runtime 实现
"""

import sys
sys.path.insert(0, '/root/.openclaw/workspace/projects/game-localization-mvr/skill/v1.4.0/scripts/core')
sys.path.insert(0, '/root/.openclaw/workspace/projects/game-localization-mvr/skill/v1.4.0/scripts/utils')

import pandas as pd
import os
import json
import urllib.request
import time
import yaml
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime

# Load env
with open('/root/.openclaw/workspace/projects/game-localization-mvr/.env') as f:
    for line in f:
        if '=' in line and not line.startswith('#'):
            key, value = line.strip().split('=', 1)
            os.environ[key] = value

API_KEY = os.environ.get('OPENAI_API_KEY')
BASE_URL = os.environ.get('OPENAI_BASE_URL', 'https://api.apiyi.com/v1')
MODEL = 'kimi-k2.5'

@dataclass
class BatchResult:
    """Result of a batch translation."""
    batch_idx: int
    rows: List[Dict]
    success: bool
    error: str = ""
    latency: float = 0.0

class AsyncBatchTranslator:
    """异步分批翻译器 - 实战测试版"""
    
    def __init__(self, max_workers=3, batch_size=10):
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.results = []
        self.errors = []
        
    def translate_single(self, text: str, context: str = "general", glossary: Dict = None) -> str:
        """单条翻译 - 直接 API 调用"""
        
        glossary_str = ""
        if glossary:
            glossary_str = "Use these terms: " + ", ".join([f"{k}={v}" for k, v in list(glossary.items())[:8]])
        
        prompt = f"""Translate this Chinese game text to English (Naruto theme).
{glossary_str}
Context: {context}

Text: {text}

Output only the English translation, nothing else."""

        req = urllib.request.Request(
            f'{BASE_URL}/chat/completions',
            headers={
                'Authorization': f'Bearer {API_KEY}',
                'Content-Type': 'application/json'
            },
            data=json.dumps({
                'model': MODEL,
                'messages': [
                    {'role': 'system', 'content': 'You are a professional game localization translator (zh-CN → en-US).'},
                    {'role': 'user', 'content': prompt}
                ],
                'temperature': 0.3,
                'max_tokens': 300
            }).encode()
        )
        
        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                result = json.loads(response.read())
                return result['choices'][0]['message']['content'].strip()
        except Exception as e:
            return f"[ERROR: {str(e)[:30]}]"
    
    def translate_batch(self, batch_rows: List[Dict], batch_idx: int, glossary: Dict) -> BatchResult:
        """翻译一个 batch"""
        start_time = time.time()
        
        print(f"  [Batch {batch_idx}] Starting ({len(batch_rows)} rows)...")
        
        translated = []
        for row in batch_rows:
            text = row.get('source_zh', '')
            context = row.get('context', 'general')
            
            try:
                result = self.translate_single(text, context, glossary)
                translated.append({
                    **row,
                    'target_en': result,
                    'status': 'success'
                })
            except Exception as e:
                translated.append({
                    **row,
                    'target_en': f"[ERROR: {e}]",
                    'status': 'error',
                    'error_msg': str(e)
                })
        
        latency = time.time() - start_time
        print(f"  [Batch {batch_idx}] ✅ Done ({latency:.1f}s)")
        
        return BatchResult(
            batch_idx=batch_idx,
            rows=translated,
            success=True,
            latency=latency
        )
    
    def run_parallel(self, df: pd.DataFrame, glossary: Dict) -> pd.DataFrame:
        """并行执行所有 batches"""
        
        # Split into batches
        total = len(df)
        batches = []
        for i in range(0, total, self.batch_size):
            batch = df.iloc[i:i+self.batch_size].to_dict('records')
            batches.append((batch, i // self.batch_size))
        
        print(f"\n🔥 开始并行翻译")
        print(f"   总行数: {total}")
        print(f"   Batch 大小: {self.batch_size}")
        print(f"   Batch 数量: {len(batches)}")
        print(f"   并行度: {self.max_workers}")
        print("=" * 60)
        
        all_results = []
        completed = 0
        
        # Use ThreadPoolExecutor for async processing
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_batch = {
                executor.submit(self.translate_batch, batch, idx, glossary): idx 
                for batch, idx in batches
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_batch):
                batch_idx = future_to_batch[future]
                try:
                    result = future.result()
                    all_results.extend(result.rows)
                    completed += len(result.rows)
                    print(f"💾 进度: {completed}/{total} ({completed/total*100:.1f}%)")
                except Exception as e:
                    print(f"❌ Batch {batch_idx} failed: {e}")
        
        print("=" * 60)
        print(f"✅ 完成: {len(all_results)} 行")
        
        return pd.DataFrame(all_results)


def main():
    """实战测试主函数"""
    print("=" * 70)
    print("Loc-MVR v1.4.0 分批异步实战测试")
    print("=" * 70)
    
    # 1. Load data
    print("\n📥 加载数据...")
    df = pd.read_csv('/root/.openclaw/workspace/projects/game-localization-mvr/test_v140/workflow/normalized_input.csv')
    
    # For this test, use all 500 rows
    total_rows = len(df)
    print(f"   总数据: {total_rows} 行")
    
    # 2. Load glossary
    print("\n📚 加载术语库...")
    with open('/root/.openclaw/workspace/projects/game-localization-mvr/test_v140/glossary/proposals/terms_en.yaml') as f:
        data = yaml.safe_load(f)
        glossary = {item['term_zh']: item['term_en'] for item in data.get('proposals', [])}
    print(f"   术语数: {len(glossary)}")
    
    # 3. Run async translation
    print("\n🚀 启动异步翻译...")
    translator = AsyncBatchTranslator(max_workers=3, batch_size=10)
    
    start_time = time.time()
    result_df = translator.run_parallel(df, glossary)
    total_time = time.time() - start_time
    
    # 4. Save results
    print("\n💾 保存结果...")
    result_df.to_csv('/root/.openclaw/workspace/projects/game-localization-mvr/test_v140/output/translated_en_async.csv', index=False)
    
    # 5. Stats
    success_count = len(result_df[result_df['status'] == 'success'])
    error_count = len(result_df[result_df['status'] == 'error'])
    
    print("\n" + "=" * 70)
    print("📊 测试结果统计")
    print("=" * 70)
    print(f"总数据:      {total_rows} 行")
    print(f"成功:        {success_count} 行 ({success_count/total_rows*100:.1f}%)")
    print(f"失败:        {error_count} 行 ({error_count/total_rows*100:.1f}%)")
    print(f"总耗时:      {total_time:.1f} 秒")
    print(f"平均速度:    {total_rows/total_time:.1f} 行/秒")
    print(f"输出文件:    test_v140/output/translated_en_async.csv")
    print("=" * 70)
    
    # Show samples
    print("\n📝 翻译样例:")
    for i in range(min(5, len(result_df))):
        row = result_df.iloc[i]
        print(f"  {row['source_zh'][:30]}... → {row['target_en'][:40]}...")
    
    return result_df


if __name__ == '__main__':
    main()
