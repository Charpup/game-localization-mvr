#!/usr/bin/env python3
import csv
import sys
from pathlib import Path

def prepare_csv(input_path, output_path):
    input_path = Path(input_path)
    output_path = Path(output_path)
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(input_path, 'r', encoding='utf-8-sig', newline='') as f_in:
        reader = csv.DictReader(f_in)
        # Check if headers are as expected
        if 'id' not in reader.fieldnames or 'zh' not in reader.fieldnames:
            print(f"❌ Error: Unexpected headers {reader.fieldnames}")
            sys.exit(1)
            
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f_out:
            fieldnames = ['string_id', 'source_zh']
            # Also keep 'ru' if it exists, though it might be empty
            if 'ru' in reader.fieldnames:
                fieldnames.append('source_ru')
            
            writer = csv.DictWriter(f_out, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            
            seen_ids = {}
            count = 0
            for row in reader:
                string_id = row['id']
                if string_id in seen_ids:
                    seen_ids[string_id] += 1
                    string_id = f"{string_id}_dup{seen_ids[string_id]}"
                else:
                    seen_ids[string_id] = 0
                
                out_row = {
                    'string_id': string_id,
                    'source_zh': row['zh']
                }
                if 'ru' in row:
                    out_row['source_ru'] = row['ru']
                writer.writerow(out_row)
                count += 1
                
    print(f"✅ Prepared {count} rows. Output: {output_path}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: prepare_production_csv.py <input> <output>")
        sys.exit(1)
    prepare_csv(sys.argv[1], sys.argv[2])
