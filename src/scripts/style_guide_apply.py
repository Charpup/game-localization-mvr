#!/usr/bin/env python3
import sys
import os
import json
import shutil
import time
import hashlib
import argparse

# ----------------------------------------------------------------------
# Deterministic Apply (FIX 3)
# ----------------------------------------------------------------------

def apply_style_guide(selected_path: str, target_path: str, meta_path: str, dry_run: bool):
    if not os.path.exists(selected_path):
        print(f"[Error] Selected file not found: {selected_path}")
        sys.exit(1)
        
    with open(selected_path, 'r', encoding='utf-8') as f:
        content = f.read()
        file_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
        
    meta = {
        "apply_timestamp": time.time(),
        "source_file": selected_path,
        "content_hash": file_hash,
        "method": "deterministic_copy"
    }
    
    if dry_run:
        print(f"[Dry-Run] Would copy {selected_path} -> {target_path}")
        print(f"[Dry-Run] Would write metadata to {meta_path}")
        return

    # Backup logic
    if os.path.exists(target_path):
        backup_path = f"{target_path}.bak.{int(time.time())}"
        shutil.copy2(target_path, backup_path)
        print(f"[Apply] Backed up existing guide to {backup_path}")
        
    # Copy file
    shutil.copy2(selected_path, target_path)
    print(f"[Apply] Applied style guide to {target_path}")
    
    # Write metadata
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2)
    print(f"[Apply] Written metadata to {meta_path}")

def main():
    parser = argparse.ArgumentParser(description="Deterministic Apply Style Guide")
    parser.add_argument("--selected", required=True, help="Path to selected best candidate")
    parser.add_argument("--target", default="workflow/style_guide.md", help="Target path for active style guide")
    parser.add_argument("--meta", default="workflow/style_guide_meta.json", help="Path for metadata")
    parser.add_argument("--dry-run", action="store_true", help="Simulate actions")
    
    args = parser.parse_args()
    
    apply_style_guide(args.selected, args.target, args.meta, args.dry_run)

if __name__ == "__main__":
    main()
