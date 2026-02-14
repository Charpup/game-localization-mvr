#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Glossary Review Pipeline

Tests the full glossary review cycle:
    1. Make review queue (proposals → CSV)
    2. Apply review (CSV → approved/rejected)
    3. Compile (approved → compiled + lock)
"""

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import yaml
except ImportError:
    print("❌ PyYAML required")
    sys.exit(1)


def create_test_proposals(path: str) -> None:
    """Create test proposals YAML."""
    data = {
        "meta": {"test": True},
        "proposals": [
            {
                "term_zh": "忍术",
                "term_ru": "Ниндзюцу",
                "scope": "ip",
                "support": 10,
                "confidence": 0.9,
                "examples": ["忍者使用忍术", "高级忍术"]
            },
            {
                "term_zh": "查克拉",
                "term_ru": "Чакра",
                "scope": "base",
                "support": 8,
                "confidence": 0.85,
                "examples": ["查克拉不足"]
            },
            {
                "term_zh": "火影",
                "term_ru": "Хокаге",
                "scope": "ip",
                "support": 5,
                "confidence": 0.95,
                "examples": ["火影大人"]
            }
        ]
    }
    
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True)


def create_reviewed_csv(review_csv_in: str, review_csv_out: str) -> None:
    """Simulate user review decisions."""
    with open(review_csv_in, 'r', encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    
    # Simulate decisions
    for row in rows:
        if row["term_zh"] == "忍术":
            row["decision"] = "approve"
        elif row["term_zh"] == "查克拉":
            row["decision"] = "edit"
            row["term_ru_final"] = "чакра"  # lowercase
            row["note"] = "Prefer lowercase"
        elif row["term_zh"] == "火影":
            row["decision"] = "reject"
            row["note"] = "Keep as transliteration"
    
    with open(review_csv_out, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def run_script(cmd: list, name: str) -> bool:
    """Run script and check success."""
    print(f"\n{'='*60}")
    print(f"Running: {name}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}")
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    if result.returncode != 0:
        print(f"[FAIL] Exit code {result.returncode}")
        return False
    
    print(f"[OK] {name} passed")
    return True


def main():
    print()
    print("#" * 60)
    print("# Glossary Review Pipeline Test")
    print("#" * 60)
    
    # Setup temp directory
    temp_dir = Path("data/temp_glossary_test")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    glossary_dir = temp_dir / "glossary"
    glossary_dir.mkdir(exist_ok=True)
    
    proposals_path = str(temp_dir / "proposals.yaml")
    review_csv_path = str(temp_dir / "review_queue.csv")
    reviewed_csv_path = str(temp_dir / "reviewed.csv")
    approved_path = str(glossary_dir / "approved.yaml")
    rejected_path = str(glossary_dir / "rejected.yaml")
    compiled_path = str(glossary_dir / "compiled.yaml")
    
    all_passed = True
    
    try:
        # 1. Create test proposals
        print("\n[Step 1] Creating test proposals...")
        create_test_proposals(proposals_path)
        print(f"[OK] Created {proposals_path}")
        
        # 2. Make review queue
        ok = run_script([
            "python", "scripts/glossary_make_review_queue.py",
            "--proposals", proposals_path,
            "--out_csv", review_csv_path
        ], "glossary_make_review_queue.py")
        all_passed = all_passed and ok
        
        if not ok:
            return 1
        
        # Verify CSV created
        if not Path(review_csv_path).exists():
            print("[FAIL] Review CSV not created")
            return 1
        print(f"[OK] Review CSV created: {review_csv_path}")
        
        # 3. Simulate user review
        print("\n[Step 3] Simulating user review decisions...")
        create_reviewed_csv(review_csv_path, reviewed_csv_path)
        print(f"[OK] Created reviewed CSV with decisions")
        
        # 4. Apply review
        ok = run_script([
            "python", "scripts/glossary_apply_review.py",
            "--review_csv", reviewed_csv_path,
            "--approved", approved_path,
            "--rejected", rejected_path
        ], "glossary_apply_review.py")
        all_passed = all_passed and ok
        
        if not ok:
            return 1
        
        # Verify approved/rejected created
        if not Path(approved_path).exists():
            print("[FAIL] Approved YAML not created")
            return 1
        print(f"[OK] Approved YAML created: {approved_path}")
        
        # 5. Compile glossary
        ok = run_script([
            "python", "scripts/glossary_compile.py",
            "--approved", approved_path,
            "--out_compiled", compiled_path,
            "--language_pair", "zh-CN->ru-RU",
            "--genre", "anime",
            "--franchise", "naruto"
        ], "glossary_compile.py")
        all_passed = all_passed and ok
        
        if not ok:
            return 1
        
        # Verify compiled + lock
        if not Path(compiled_path).exists():
            print("[FAIL] Compiled YAML not created")
            return 1
        
        lock_path = compiled_path.replace(".yaml", ".lock.json")
        if not Path(lock_path).exists():
            print("[FAIL] Lock file not created")
            return 1
        
        print(f"[OK] Compiled YAML created: {compiled_path}")
        print(f"[OK] Lock file created: {lock_path}")
        
        # 6. Verify contents
        print("\n[Step 6] Verifying contents...")
        
        with open(compiled_path, 'r', encoding='utf-8') as f:
            compiled = yaml.safe_load(f)
        
        entries = compiled.get("entries", [])
        print(f"[OK] Compiled has {len(entries)} entries")
        
        # Check specific entries
        term_map = {e["term_zh"]: e["term_ru"] for e in entries}
        
        if "忍术" in term_map:
            print(f"[OK] 忍术 → {term_map['忍术']}")
        else:
            print("[FAIL] 忍术 not found in compiled")
            all_passed = False
        
        if "查克拉" in term_map and term_map["查克拉"] == "чакра":
            print(f"[OK] 查克拉 → {term_map['查克拉']} (edited)")
        else:
            print("[FAIL] 查克拉 edit not applied")
            all_passed = False
        
        if "火影" not in term_map:
            print("[OK] 火影 correctly rejected (not in compiled)")
        else:
            print("[FAIL] 火影 should have been rejected")
            all_passed = False
        
        # Check lock
        with open(lock_path, 'r', encoding='utf-8') as f:
            lock = json.load(f)
        
        print(f"[OK] Version: {lock.get('version')}")
        print(f"[OK] Hash: {lock.get('hash')}")
        print(f"[OK] Language pair: {lock.get('language_pair')}")
        
    finally:
        # Cleanup
        import shutil
        if temp_dir.exists():
            shutil.rmtree(temp_dir)
            print(f"\n[OK] Cleaned up {temp_dir}")
    
    print()
    if all_passed:
        print("#" * 60)
        print("# ALL GLOSSARY REVIEW TESTS PASSED")
        print("#" * 60)
        return 0
    else:
        print("#" * 60)
        print("# SOME TESTS FAILED")
        print("#" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
