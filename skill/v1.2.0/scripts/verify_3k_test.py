#!/usr/bin/env python3
import pandas as pd
import json
import os
import sys

def check_file(path, desc):
    if not os.path.exists(path):
        print(f"❌ {desc} NOT FOUND: {path}")
        return False
    return True

def verify_results():
    base_dir = "data/Test_Batch/10._full-pipeline_press_test_3k-row"
    trans_csv = os.path.join(base_dir, "3k_translated.csv")
    qa_report = os.path.join(base_dir, "3k_qa_hard_report.json")
    repaired_csv = os.path.join(base_dir, "3k_repaired_hard.csv")
    
    # 1. Check Translation
    if check_file(trans_csv, "Translated CSV"):
        try:
            df = pd.read_csv(trans_csv)
            print(f"✅ Translated CSV: {len(df)} rows")
            if len(df) != 3000:
                print(f"   ⚠️ Warning: Expected 3000 rows, found {len(df)}")
            
            # Check for mock
            mock_count = df['target_text'].str.contains('Mock Ru', na=False).sum()
            if mock_count > 0:
                print(f"   ❌ Found {mock_count} MOCK rows! Data contamination detected.")
            else:
                print("   ✅ No mock data detected.")
                
        except Exception as e:
            print(f"   ❌ Error reading CSV: {e}")

    # 2. Check QA Report
    if check_file(qa_report, "QA Report"):
        try:
            with open(qa_report, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            errors = report.get('errors', [])
            print(f"✅ QA Report: {len(errors)} errors found")
            
            # Breakdown
            types = {}
            for e in errors:
                types[e['type']] = types.get(e['type'], 0) + 1
            print(f"   Errors by type: {types}")
            
        except Exception as e:
            print(f"   ❌ Error reading Report: {e}")

    # 3. Check Repaired CSV
    if check_file(repaired_csv, "Repaired CSV"):
        try:
            df_rep = pd.read_csv(repaired_csv)
            print(f"✅ Repaired CSV: {len(df_rep)} rows")
        except Exception as e:
            print(f"   ❌ Error reading Repaired CSV: {e}")

if __name__ == "__main__":
    verify_results()
