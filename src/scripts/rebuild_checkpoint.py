"""
Rebuild Correct Checkpoint
Purpose: Combine actual completed rows from:
  1. Part2 废弃文件 (contains Part1 data + Part2 partial)
  2. Part3 CSV (contains Part3 partial)
To create a correct checkpoint for resuming translation.
"""
import json
import csv
import os

PART2_BACKUP = 'data/test06_outputs/translated_r1.csv.part2_废弃'
PART3_CSV = 'data/test06_outputs/translated_r1_part3.csv'
OUTPUT_CKPT = 'data/translate_checkpoint.json'
NORMALIZED = 'data/test06_outputs/normalized.csv'

def main():
    print("🚀 Rebuilding Correct Checkpoint...")
    
    # 1. Read Part2 Backup (contains Part1 + Part2 partial)
    print(f"Reading Part2 backup: {PART2_BACKUP}")
    part2_ids = set()
    if os.path.exists(PART2_BACKUP):
        with open(PART2_BACKUP, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if row:
                    part2_ids.add(str(row[0]))  # string_id
    print(f"  > Part2 backup IDs: {len(part2_ids)}")

    # 2. Read Part3 CSV
    print(f"Reading Part3 CSV: {PART3_CSV}")
    part3_ids = set()
    if os.path.exists(PART3_CSV):
        with open(PART3_CSV, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            for row in reader:
                if row:
                    part3_ids.add(str(row[0]))
    print(f"  > Part3 CSV IDs: {len(part3_ids)}")

    # 3. Combine (union)
    all_done_ids = part2_ids.union(part3_ids)
    print(f"  > Combined Done IDs: {len(all_done_ids)}")

    # 4. Get total rows from normalized
    total_rows = 0
    with open(NORMALIZED, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)
        total_rows = sum(1 for _ in reader)
    print(f"  > Total Task Rows: {total_rows}")
    print(f"  > Remaining To-Do: {total_rows - len(all_done_ids)}")

    # 5. Create checkpoint
    checkpoint = {
        "done_ids": {k: True for k in all_done_ids},
        "stats": {"ok": len(all_done_ids), "escalated": 0},
        "batch_idx": 0
    }

    # 6. Save
    with open(OUTPUT_CKPT, 'w', encoding='utf-8') as f:
        json.dump(checkpoint, f, ensure_ascii=False, indent=2)
    print(f"✅ Checkpoint saved to: {OUTPUT_CKPT}")
    print(f"   Ready to resume translation for remaining {total_rows - len(all_done_ids)} rows")

if __name__ == "__main__":
    main()
