#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
build_gate_v4_data.py

Generates fixed assets for Empty Gate V4:
- data/empty_gate_v4_batch.csv
- data/empty_gate_v4_batch.meta.json
"""

import csv
import hashlib
import json
import os
import sys

OUTPUT_CSV = "data/empty_gate_v4_batch.csv"
OUTPUT_META = "data/empty_gate_v4_batch.meta.json"

# Fixed Data Definition (5 Non-Empty + 5 Empty)
FIXED_DATA = [
    # Non-Empty (Mixed types)
    {"string_id": "UI_BUTTON_OK", "source_zh": "确定", "type": "UI"},
    {"string_id": "DIA_TUTORIAL_01", "source_zh": "欢迎来到新世界！", "type": "Dialogue"},
    {"string_id": "SYS_ERR_NET", "source_zh": "网络连接失败，请重试。", "type": "System"},
    {"string_id": "ITEM_DESC_POTION", "source_zh": "恢复 50 点生命值。", "type": "Item"},
    {"string_id": "UI_LABEL_cancel", "source_zh": "取消", "type": "UI"},
    
    # Empty (Empty Source or Whitespace)
    {"string_id": "UI_SPACER_01", "source_zh": "", "type": "UI"},
    {"string_id": "DIA_SILENCE_01", "source_zh": "   ", "type": "Dialogue"},
    {"string_id": "SYS_EMPTY_LOG", "source_zh": "", "type": "System"},
    {"string_id": "PHO_001", "source_zh": "", "type": "Placeholder"},
    {"string_id": "UI_HIDDEN_LABEL", "source_zh": " ", "type": "UI"},
]

def calculate_sha256(filepath):
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        # Read and update hash string value in blocks of 4K
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def main():
    os.makedirs("data", exist_ok=True)
    
    # Write CSV
    with open(OUTPUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["string_id", "source_zh", "type"])
        writer.writeheader()
        writer.writerows(FIXED_DATA)
        
    print(f"Wrote {len(FIXED_DATA)} rows to {OUTPUT_CSV}")
    
    # Calculate Hash
    file_hash = calculate_sha256(OUTPUT_CSV)
    
    # Write Meta
    meta = {
        "gate": "empty_gate_v4_thorough",
        "batch_size": 10,
        "empty_rows": 5,
        "non_empty_rows": 5,
        "source_dataset_id": "fixed_v4_assets",
        "sha256": file_hash,
        "rules_version": "v4.0"
    }
    
    with open(OUTPUT_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
        
    print(f"Wrote metadata to {OUTPUT_META}")
    print(f"SHA256: {file_hash}")

if __name__ == "__main__":
    main()
