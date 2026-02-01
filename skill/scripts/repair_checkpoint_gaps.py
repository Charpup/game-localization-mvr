"""
Repair Checkpoint Gaps
Purpose: 
  The translation process crashed/restarted, resulting in data loss in the CSV file 
  (~90% missing), while the checkpoint incorrectly reports completion.
  This script reconstructs a valid checkpoint based on:
  1. Part 1 Lock File (Trusted verification of Part 1)
  2. Actual CSV Output (Trusted verification of Part 3 partial progress)

Usage:
  python scripts/repair_checkpoint_gaps.py
"""
import json
import csv
import os
from pathlib import Path

# Config
PART1_LOCK = 'data/test06_outputs/checkpoint_part1.lock.json'
PART3_CSV = 'data/test06_outputs/translated_r1_part3.csv'
TARGET_CKPT = 'data/translate_checkpoint.json'
NORMALIZED_CSV = 'data/test06_outputs/normalized.csv'

def main():
    print(f"🚀 Repairing Checkpoint...")
    
    # 1. Load Part 1 Lock
    print(f"Reading Part 1 Lock: {PART1_LOCK}")
    with open(PART1_LOCK, 'r', encoding='utf-8') as f:
        part1 = json.load(f)
    part1_ids = set(part1.get('done_ids', {}).keys())
    print(f"  > Part 1 IDs: {len(part1_ids)}")

    # 2. Load Part 3 CSV
    print(f"Reading Part 3 CSV: {PART3_CSV}")
    part3_ids = set()
    if os.path.exists(PART3_CSV):
        with open(PART3_CSV, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if row:
                    part3_ids.add(str(row[0])) # string_id
    print(f"  > Part 3 IDs (Present in file): {len(part3_ids)}")

    # 3. Combine Valid IDs
    valid_ids = part1_ids.union(part3_ids)
    print(f"  > Total Valid Done IDs: {len(valid_ids)}")

    # 4. Load Normalized Total for Context
    total_rows = 0
    with open(NORMALIZED_CSV, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader) # header
        total_rows = sum(1 for _ in reader)
    print(f"  > Total Task Rows: {total_rows}")
    print(f"  > Missing/To-Do Rows: {total_rows - len(valid_ids)}")

    # 5. Reconstruct Checkpoint
    # We use Part 1 stats as baseline, ignore Part 3 stats (reset batch_idx to scan from start or keep safe)
    # The script scans sequentially, so batch_idx is optimization. Setting to 0 is safe.
    new_checkpoint = {
        "done_ids": {k: True for k in valid_ids},
        "stats": part1.get("stats", {"ok": 0, "escalated": 0}), # Keep Part 1 stats
        "batch_idx": 0
    }
    
    # Update stats based on count
    new_checkpoint["stats"]["ok"] = len(valid_ids)

    # 6. Save
    print(f"Writing corrected checkpoint to: {TARGET_CKPT}")
    with open(TARGET_CKPT, 'w', encoding='utf-8') as f:
        json.dump(new_checkpoint, f, ensure_ascii=False, indent=2)

    print("✅ Checkpoint repair complete. Resume translation now.")

if __name__ == "__main__":
    main()
