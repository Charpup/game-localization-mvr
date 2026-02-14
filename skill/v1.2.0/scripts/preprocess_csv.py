#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
预处理测试 CSV，转换列名格式并抽取样本

输入格式：语言id,语言文本,语言文本 (id,zh,ru)
输出格式：string_id,source_zh
"""

import csv
import sys
from pathlib import Path

def preprocess_csv(input_path: str, output_path: str, max_rows: int = 500):
    """转换 CSV 格式并抽取样本"""
    
    rows = []
    
    with open(input_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        
        # 跳过前两行（标题行）
        next(reader)  # 语言id,语言文本,语言文本
        next(reader)  # id,zh,ru
        
        for row in reader:
            if len(row) >= 2:
                string_id = row[0].strip()
                source_zh = row[1].strip() if len(row) > 1 else ''
                
                # 跳过空行
                if not string_id or not source_zh:
                    continue
                
                rows.append({
                    'string_id': string_id,
                    'source_zh': source_zh
                })
                
                # 限制行数
                if len(rows) >= max_rows:
                    break
    
    # 写入输出文件
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['string_id', 'source_zh'])
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"✅ 已转换并提取 {len(rows)} 行到 {output_path}")
    return len(rows)


if __name__ == "__main__":
    input_file = "data/testInput_001.csv"
    output_file = "data/input.csv"
    max_rows = 500
    
    count = preprocess_csv(input_file, output_file, max_rows)
    print(f"总计处理: {count} 行")
