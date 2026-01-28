
import csv
import sys
from pathlib import Path

def main():
    root = Path("..")
    norm_csv = root / "data/Production Batch/01. Omni Production_go/Production_go_normalized.csv"
    trans_csv = root / "data/Production Batch/01. Omni Production_go/Production_go_translated.csv"
    
    # Read normalized
    with open(norm_csv, "r", encoding="utf-8-sig") as f:
        norm_rows = list(csv.DictReader(f))
    
    # Read translated
    if not trans_csv.exists():
        print("Translated CSV not found.")
        return

    with open(trans_csv, "r", encoding="utf-8-sig") as f:
        trans_rows = list(csv.DictReader(f))
        
    trans_ids = {r["string_id"] for r in trans_rows}
    
    missing = []
    for r in norm_rows:
        if r["string_id"] not in trans_ids:
            # Create a row with empty target
            new_r = r.copy()
            new_r["target_text"] = "" 
            missing.append(new_r)
            
    if missing:
        print(f"Found {len(missing)} missing rows. Appending...")
        headers = list(trans_rows[0].keys())
        
        with open(trans_csv, "a", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            for m in missing:
                # Ensure only relevant headers are written
                row_to_write = {k: m.get(k, "") for k in headers}
                writer.writerow(row_to_write)
        print("✅ Appended missing rows.")
    else:
        print("✅ No missing rows found.")

if __name__ == "__main__":
    main()
