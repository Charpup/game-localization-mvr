#!/usr/bin/env python3
"""Prepare test input for pipeline (convert column names).

Input format has 2 header rows:
  Row 0: 语言id, 语言文本, 语言文本  (metadata)
  Row 1: id, zh, ru  (actual headers)
  Row 2+: data
"""
import csv
import sys

input_path = sys.argv[1]
output_path = sys.argv[2]

with open(input_path, 'r', encoding='utf-8-sig') as f:
    lines = f.readlines()

# Skip first metadata row, use second row as header
if len(lines) < 3:
    print("Error: Not enough lines")
    sys.exit(1)

# Parse with row 1 as header
import io
content = ''.join(lines[1:])  # Skip first row
reader = csv.DictReader(io.StringIO(content))
rows = list(reader)

# Map columns
fieldnames = ['string_id', 'source_zh', 'target_ru']
mapped_rows = []

for row in rows:
    string_id = row.get('id', '').strip()
    source_zh = row.get('zh', '').strip()
    
    # Skip empty source
    if not source_zh:
        continue
    
    mapped = {
        'string_id': string_id,
        'source_zh': source_zh,
        'target_ru': ''
    }
    mapped_rows.append(mapped)

with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(mapped_rows)

print(f"Converted {len(mapped_rows)} rows to {output_path}")
