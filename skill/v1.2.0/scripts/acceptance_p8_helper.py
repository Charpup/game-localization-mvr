import yaml
import json
import pandas as pd
from pathlib import Path

def merge_glossary():
    print("--- Step 1: Merging Glossary Proposals ---")
    old_path = Path("workflow/p3_glossary_compiled.yaml")
    prop_path = Path("workflow/p3_glossary_proposals.yaml")
    new_path = Path("workflow/p3_glossary_new_test.yaml")
    
    if not prop_path.exists():
        print("❌ Proposals file missing")
        return False
        
    with open(old_path, 'r', encoding='utf-8') as f:
        old_data = yaml.safe_load(f) or {}
    
    with open(prop_path, 'r', encoding='utf-8') as f:
        prop_data = yaml.safe_load(f) or {}
        
    new_entries = prop_data.get('proposals', [])
    for entry in new_entries:
        entry['status'] = 'approved' # Force approve for test
        
    old_data['entries'] = old_data.get('entries', []) + new_entries
    
    with open(new_path, 'w', encoding='utf-8') as f:
        yaml.dump(old_data, f, allow_unicode=True)
    
    print(f"✅ Created {new_path} with {len(new_entries)} new entries.")
    return True

def prepare_data():
    print("--- Step 2: Preparing 100-row Test Data ---")
    input_csv = Path("data/p3_translated.csv")
    output_csv = Path("data/p3_refresh_test_100.csv")
    
    df = pd.read_csv(input_csv)
    df_small = df.head(100)
    df_small.to_csv(output_csv, index=False, encoding='utf-8-sig')
    print(f"✅ Created {output_csv} (100 rows).")

if __name__ == "__main__":
    if merge_glossary():
        prepare_data()
