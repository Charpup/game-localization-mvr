
import csv
import sys
from pathlib import Path

def main():
    root = Path("..")
    base_file = root / "data/Production Batch/01. Omni Production_go/Production_go_translated.csv"
    repaired_1 = root / "data/Production Batch/01. Omni Production_go/Production_go_repaired.csv"
    repaired_2 = root / "data/Production Batch/01. Omni Production_go/Production_go_repaired_final.csv"
    output_file = root / "data/Production Batch/01. Omni Production_go/Production_go_completed.csv"
    
    print(f"Loading base: {base_file}")
    with open(base_file, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
        
    id_map = {r["string_id"]: r for r in rows}
    
    # Load Repair 1 (Hard QA fixes)
    count1 = 0
    if repaired_1.exists():
        print(f"Loading repairs from: {repaired_1}")
        with open(repaired_1, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                sid = r["string_id"]
                # If target text is different from base (and not empty), update
                # Actually, simpler: if this row was in the task list for Loop 1, we accept it.
                # But we don't have the task list easily handy. 
                # Heuristic: If repaired_1 has a valid translation and base didn't (or had error), use it.
                # Since Loop 1 writes the WHOLE file, we can iterate and check differences.
                if sid in id_map:
                    # Update if changed
                    if r.get("target_text") != id_map[sid].get("target_text"):
                        id_map[sid]["target_text"] = r.get("target_text")
                        count1 += 1
    
    # Load Repair 2 (Missing Rows)
    count2 = 0
    if repaired_2.exists():
        print(f"Loading repairs from: {repaired_2}")
        with open(repaired_2, "r", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                sid = r["string_id"]
                if sid in id_map:
                     # Since Loop 2 worked on empty rows, any non-empty content is an update
                    if r.get("target_text") and not id_map[sid].get("target_text"):
                        id_map[sid]["target_text"] = r.get("target_text")
                        count2 += 1
                    # Or if it just differs (maybe Loop 2 modified something else? Unlikely)
                    elif r.get("target_text") != id_map[sid].get("target_text") and r.get("target_text"):
                        id_map[sid]["target_text"] = r.get("target_text")
                        count2 += 1

    print(f"Applied {count1} fixes from Loop 1 and {count2} fixes from Loop 2.")
    
    # Write output
    headers = list(rows[0].keys())
    with open(output_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(id_map.values())
        
    print(f"✅ Saved merged output to: {output_file} ({len(id_map)} rows)")

if __name__ == "__main__":
    main()
