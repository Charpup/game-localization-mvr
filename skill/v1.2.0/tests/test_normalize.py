#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test normalize_guard.py

Uses fixtures from data/fixtures/ for consistent testing.
All file operations use explicit UTF-8 encoding for Windows compatibility.
"""

import csv
import json
import subprocess
import sys
import tempfile
import shutil
from pathlib import Path


def test_normalize_with_fixtures():
    """Test normalize_guard using stable fixtures."""
    
    print("=" * 60)
    print("Test: normalize_guard.py with fixtures")
    print("=" * 60)
    print()
    
    fixtures_dir = Path("data/fixtures")
    temp_dir = Path("data/temp_normalize_test")
    temp_dir.mkdir(exist_ok=True)
    
    try:
        # Run normalize on fixture input
        result = subprocess.run(
            [
                "python", "scripts/normalize_guard.py",
                str(fixtures_dir / "input_valid.csv"),
                str(temp_dir / "draft.csv"),
                str(temp_dir / "placeholder_map.json"),
                "workflow/placeholder_schema.yaml"
            ],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        if result.returncode != 0:
            print(f"[FAIL] normalize_guard exited with code {result.returncode}")
            print(result.stderr)
            return False
        
        print("[OK] normalize_guard completed successfully")
        
        # Load outputs using utf-8-sig for BOM handling
        with open(temp_dir / "draft.csv", 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        with open(temp_dir / "placeholder_map.json", 'r', encoding='utf-8') as f:
            map_data = json.load(f)
        
        print(f"[OK] Generated {len(rows)} rows")
        
        mappings = map_data.get('mappings', {})
        print(f"[OK] Generated {len(mappings)} placeholder mappings")
        print()
        
        # Test cases based on fixture data
        test_cases = [
            {
                'string_id': 'welcome_msg',
                'expected_pattern': '⟦PH_',  # Should contain PH token
                'expected_original': '{0}'
            },
            {
                'string_id': 'color_text',
                'expected_pattern': '⟦TAG_',  # Should contain TAG token
                'expected_original': '<color=#FF00FF>'
            },
            {
                'string_id': 'printf_test',
                'expected_pattern': '⟦PH_',  # Should contain PH token
                'expected_original': '%d'
            }
        ]
        
        all_passed = True
        
        for test in test_cases:
            string_id = test['string_id']
            expected_pattern = test['expected_pattern']
            
            # Find row
            row = next((r for r in rows if r.get('string_id') == string_id), None)
            
            if not row:
                print(f"[FAIL] {string_id}: not found in output")
                all_passed = False
                continue
            
            tokenized = row.get('tokenized_zh', '')
            
            if expected_pattern not in tokenized:
                print(f"[FAIL] {string_id}: expected pattern '{expected_pattern}' not found")
                print(f"       Got: {tokenized}")
                all_passed = False
                continue
            
            print(f"[OK] {string_id}: tokens present")
            print(f"     Tokenized: {tokenized[:60]}...")
        
        print()
        
        # Verify mappings contain expected originals
        mapping_values = list(mappings.values())
        
        for test in test_cases:
            expected = test['expected_original']
            if expected in mapping_values:
                print(f"[OK] Mapping found for: {expected}")
            else:
                print(f"[WARN] Mapping not found for: {expected}")
        
        # Verify placeholder count is reasonable (not hardcoded)
        metadata = map_data.get('metadata', {})
        total = metadata.get('total_placeholders', len(mappings))
        
        if total >= 7 and total <= 15:  # Reasonable range for our fixtures
            print(f"[OK] Placeholder count in expected range: {total}")
        else:
            print(f"[WARN] Unexpected placeholder count: {total}")
        
        print()
        
        if all_passed:
            print("[PASS] All normalize tests passed")
            return True
        else:
            print("[FAIL] Some normalize tests failed")
            return False
            
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


def test_normalize_roundtrip():
    """Test that normalized text can be processed and rehydrated."""
    
    print()
    print("=" * 60)
    print("Test: Normalize Roundtrip")
    print("=" * 60)
    print()
    
    fixtures_dir = Path("data/fixtures")
    temp_dir = Path("data/temp_roundtrip_test")
    temp_dir.mkdir(exist_ok=True)
    
    try:
        # Step 1: Normalize
        subprocess.run(
            [
                "python", "scripts/normalize_guard.py",
                str(fixtures_dir / "input_valid.csv"),
                str(temp_dir / "draft.csv"),
                str(temp_dir / "placeholder_map.json"),
                "workflow/placeholder_schema.yaml"
            ],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        # Step 2: Create a "translated" version (just copy tokenized to target)
        with open(temp_dir / "draft.csv", 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # Add target_text column (copy tokenized_zh for test purposes)
        for row in rows:
            row['target_text'] = row.get('tokenized_zh', '')
        
        with open(temp_dir / "translated.csv", 'w', encoding='utf-8', newline='') as f:
            if rows:
                fieldnames = list(rows[0].keys())
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(rows)
        
        # Step 3: Rehydrate
        result = subprocess.run(
            [
                "python", "scripts/rehydrate_export.py",
                str(temp_dir / "translated.csv"),
                str(temp_dir / "placeholder_map.json"),
                str(temp_dir / "final.csv")
            ],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        if result.returncode != 0:
            print(f"[FAIL] Rehydrate failed: {result.stderr}")
            return False
        
        # Verify no tokens remain
        with open(temp_dir / "final.csv", 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            final_rows = list(reader)
        
        for row in final_rows:
            rehydrated = row.get('rehydrated_text', '')
            if '⟦' in rehydrated or '⟧' in rehydrated:
                print(f"[FAIL] Token still present in {row.get('string_id')}")
                return False
        
        print(f"[OK] Roundtrip successful: {len(final_rows)} rows processed")
        print("[PASS] Normalize roundtrip test passed")
        return True
        
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    print()
    print("#" * 60)
    print("# normalize_guard.py Test Suite")
    print("#" * 60)
    print()
    
    success = True
    
    if not test_normalize_with_fixtures():
        success = False
    
    if not test_normalize_roundtrip():
        success = False
    
    print()
    print("#" * 60)
    if success:
        print("# ALL TESTS PASSED")
    else:
        print("# SOME TESTS FAILED")
    print("#" * 60)
    
    sys.exit(0 if success else 1)
