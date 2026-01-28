
import csv
import json
import shutil
from pathlib import Path

def main():
    root = Path("..") # Assumes running from scripts/
    base_dir = root / "data/Production Batch/01. Omni Production_go"
    
    target_csv = base_dir / "Production_go_translated.csv"
    target_checkpoint = base_dir / "translate_checkpoint.json"
    
    # Load existing main files if present
    final_rows = []
    seen_ids = set()
    
    if target_csv.exists():
        with open(target_csv, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            for r in reader:
                final_rows.append(r)
                seen_ids.add(r["string_id"])
    else:
        headers = None # Will determine from shards
        
    final_done_ids = set()
    if target_checkpoint.exists():
        with open(target_checkpoint, "r", encoding="utf-8") as f:
            data = json.load(f)
            final_done_ids = set(data.get("done_ids", []))
            
    # Iterate shards 0-3
    shard_count = 4
    merged_count = 0
    
    for i in range(shard_count):
        shard_csv = base_dir / f"Production_go_translated_{i}.csv"
        shard_ckpt = base_dir / f"translate_checkpoint_{i}.json"
        
        if shard_csv.exists():
            print(f"Merging Shard {i} CSV...")
            with open(shard_csv, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                if not headers: headers = reader.fieldnames
                for r in reader:
                    sid = r["string_id"]
                    if sid not in seen_ids:
                        final_rows.append(r)
                        seen_ids.add(sid)
                        merged_count += 1
                        
        if shard_ckpt.exists():
            print(f"Merging Shard {i} Checkpoint...")
            with open(shard_ckpt, "r", encoding="utf-8") as f:
                data = json.load(f)
                final_done_ids.update(data.get("done_ids", []))

    # Write back
    print(f"Writing {len(final_rows)} rows to main CSV...")
    with open(target_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(final_rows)
        
    print(f"Writing {len(final_done_ids)} IDs to main Checkpoint...")
    with open(target_checkpoint, "w", encoding="utf-8") as f:
        json.dump({"done_ids": list(final_done_ids)}, f)

    print("✅ Merge Complete.")

if __name__ == "__main__":
    main()
