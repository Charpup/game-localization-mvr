#!/usr/bin/env python3
import csv
import argparse
import os
from typing import Dict, Any, List

def load_csv(path: str) -> Dict[str, Dict[str, Any]]:
    data = {}
    with open(path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid = row.get('string_id')
            if sid:
                data[sid] = row
    return data

def compare(file_a: str, file_b: str, output_dir: str):
    data_a = load_csv(file_a)
    data_b = load_csv(file_b)
    
    diffs = []
    
    all_keys = set(data_a.keys()) | set(data_b.keys())
    
    for sid in all_keys:
        row_a = data_a.get(sid, {})
        row_b = data_b.get(sid, {})
        
        target_a = row_a.get('target_text') or row_a.get('target_ru') or ''
        target_b = row_b.get('target_text') or row_b.get('target_ru') or ''
        
        if target_a != target_b:
            diffs.append({
                'string_id': sid,
                'a_target': target_a,
                'b_target': target_b,
                'status': 'modified' if (sid in data_a and sid in data_b) else ('added' if sid in data_b else 'deleted')
            })

    os.makedirs(output_dir, exist_ok=True)
    
    # Write diff CSV
    diff_csv = os.path.join(output_dir, 'diff_rows.csv')
    with open(diff_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['string_id', 'status', 'a_target', 'b_target'])
        writer.writeheader()
        writer.writerows(diffs)
        
    # Write summary Report
    report_md = os.path.join(output_dir, 'diff_report.md')
    with open(report_md, 'w', encoding='utf-8') as f:
        f.write(f"# Translation Diff Report\n\n")
        f.write(f"- File A: {file_a}\n")
        f.write(f"- File B: {file_b}\n")
        f.write(f"- Total Differences: {len(diffs)}\n\n")
        f.write("| String ID | Status | A (Old) | B (New) |\n")
        f.write("|---|---|---|---|\n")
        for d in diffs[:50]: # Top 50
            f.write(f"| {d['string_id']} | {d['status']} | {d['a_target'][:30]} | {d['b_target'][:30]} |\n")
        if len(diffs) > 50:
            f.write(f"\n... and {len(diffs)-50} more. See diff_rows.csv for full list.\n")

    print(f"Diff complete. Found {len(diffs)} differences.")
    print(f"  CSV: {diff_csv}")
    print(f"  Report: {report_md}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("file_a", help="Base file (Old)")
    parser.add_argument("file_b", help="New file (New)")
    parser.add_argument("--output", default="data/diff_output")
    args = parser.parse_args()
    
    compare(args.file_a, args.file_b, args.output)

if __name__ == "__main__":
    main()
