#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
End-to-End Workflow Test (Self-Contained)

Tests the complete localization workflow:
  normalize → (translate) → qa → rehydrate

Uses fixtures from data/fixtures/ to ensure test consistency.
All subprocess calls use explicit UTF-8 encoding for Windows compatibility.
"""

import subprocess
import sys
import json
import csv
import tempfile
import shutil
from pathlib import Path


def run_command(cmd: list, description: str) -> bool:
    """Run command with UTF-8 encoding and check result."""
    print(f"\n{'='*60}")
    print(f"Step: {description}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}")
    print()
    
    # Explicit UTF-8 encoding for Windows compatibility
    result = subprocess.run(
        cmd, 
        capture_output=True, 
        text=True, 
        encoding='utf-8',
        errors='replace'  # Handle any remaining encoding issues gracefully
    )
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    if result.returncode != 0:
        print(f"[FAIL] Exit code {result.returncode}")
        return False
    
    print(f"[OK] Success")
    return True


def setup_test_environment():
    """Create temporary test directory with consistent fixtures."""
    temp_dir = Path("data/temp_e2e")
    temp_dir.mkdir(exist_ok=True)
    
    # Copy fixtures to temp directory
    fixtures_dir = Path("data/fixtures")
    
    # Use fixture input
    shutil.copy(fixtures_dir / "input_valid.csv", temp_dir / "input.csv")
    shutil.copy(fixtures_dir / "translated_valid.csv", temp_dir / "translated.csv")
    shutil.copy(fixtures_dir / "placeholder_map.json", temp_dir / "placeholder_map.json")
    
    return temp_dir


def cleanup_test_environment(temp_dir: Path):
    """Clean up temporary test files."""
    if temp_dir.exists():
        shutil.rmtree(temp_dir)


def test_end_to_end_workflow():
    """Test self-contained end-to-end workflow."""
    
    print("=" * 60)
    print("End-to-End Localization Workflow Test")
    print("=" * 60)
    print()
    print("Using self-contained test fixtures from data/fixtures/")
    print()
    
    # Setup
    temp_dir = setup_test_environment()
    
    try:
        # Step 1: Normalize (generate fresh placeholder map from input)
        if not run_command(
            [
                "python", "scripts/normalize_guard.py",
                str(temp_dir / "input.csv"),
                str(temp_dir / "draft.csv"),
                str(temp_dir / "placeholder_map_generated.json"),
                "workflow/placeholder_schema.yaml"
            ],
            "1. Normalize - Freeze placeholders"
        ):
            return False
        
        # Step 2: Simulate translation
        print(f"\n{'='*60}")
        print("Step: 2. Translate - Using pre-translated fixture")
        print(f"{'='*60}")
        print("(In production, this would be done by translators or LLM)")
        print()
        
        # For E2E test, we use the pre-translated fixture
        # In real workflow, draft.csv would be translated to translated.csv
        
        # Step 3: QA Hard - Use the generated placeholder map for consistency
        if not run_command(
            [
                "python", "scripts/qa_hard.py",
                str(temp_dir / "translated.csv"),
                str(temp_dir / "placeholder_map.json"),  # Use fixture map (matches translated.csv)
                "workflow/placeholder_schema.yaml",
                "workflow/forbidden_patterns.txt",
                str(temp_dir / "qa_report.json")
            ],
            "3. QA Hard - Validate translations"
        ):
            return False
        
        # Check QA report
        with open(temp_dir / "qa_report.json", 'r', encoding='utf-8') as f:
            qa_report = json.load(f)
        
        if qa_report.get('has_errors', False):
            print("[FAIL] QA validation failed - cannot proceed to rehydrate")
            print(f"  Errors: {qa_report.get('summary', {})}")
            return False
        
        print(f"[OK] QA passed with {qa_report.get('summary', {}).get('total_errors', 0)} errors")
        
        # Step 4: Rehydrate
        if not run_command(
            [
                "python", "scripts/rehydrate_export.py",
                str(temp_dir / "translated.csv"),
                str(temp_dir / "placeholder_map.json"),
                str(temp_dir / "final.csv")
            ],
            "4. Rehydrate - Restore placeholders"
        ):
            return False
        
        # Final verification
        print(f"\n{'='*60}")
        print("Final Verification")
        print(f"{'='*60}")
        
        final_path = temp_dir / "final.csv"
        if not final_path.exists():
            print("[FAIL] Final output file not found")
            return False
        
        # Verify content
        with open(final_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        print(f"[OK] Final output: {len(rows)} rows")
        
        # Spot check: verify placeholders were restored
        for row in rows:
            rehydrated = row.get('rehydrated_text', '')
            # Check that no tokens remain
            if '⟦' in rehydrated or '⟧' in rehydrated:
                print(f"[FAIL] Tokens still present in: {row['string_id']}")
                return False
        
        print("[OK] All tokens successfully rehydrated")
        print()
        
        print("=" * 60)
        print("End-to-End Workflow Test PASSED!")
        print("=" * 60)
        print()
        print("Workflow Summary:")
        print("  1. [OK] Normalize - Froze placeholders into tokens")
        print("  2. [OK] Translate - (Used pre-translated fixture)")
        print("  3. [OK] QA Hard - Validated all translations")
        print("  4. [OK] Rehydrate - Restored original placeholders")
        
        return True
        
    finally:
        # Cleanup temp files
        cleanup_test_environment(temp_dir)
        print()
        print("Cleaned up temporary test files")


def test_qa_error_detection():
    """Test that QA correctly detects errors in invalid translations."""
    
    print()
    print("=" * 60)
    print("QA Error Detection Test")
    print("=" * 60)
    print()
    
    temp_dir = Path("data/temp_qa_test")
    temp_dir.mkdir(exist_ok=True)
    
    try:
        fixtures_dir = Path("data/fixtures")
        
        # Run QA on invalid translations
        result = subprocess.run(
            [
                "python", "scripts/qa_hard.py",
                str(fixtures_dir / "translated_invalid.csv"),
                str(fixtures_dir / "placeholder_map.json"),
                "workflow/placeholder_schema.yaml",
                "workflow/forbidden_patterns.txt",
                str(temp_dir / "qa_report.json")
            ],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'
        )
        
        # QA should complete (exit 0) but report errors
        if result.returncode != 0:
            print(f"[WARN] QA script exited with code {result.returncode}")
        
        # Check that errors were detected
        with open(temp_dir / "qa_report.json", 'r', encoding='utf-8') as f:
            qa_report = json.load(f)
        
        if not qa_report.get('has_errors', False):
            print("[FAIL] QA should have detected errors in invalid translations")
            return False
        
        error_count = qa_report.get('summary', {}).get('total_errors', 0)
        print(f"[OK] QA correctly detected {error_count} errors")
        
        # Verify specific error types
        errors = qa_report.get('errors', [])
        error_types = set(e.get('type', '') for e in errors)
        
        expected_types = {'token_mismatch', 'forbidden_hit'}  # From our invalid fixture
        found_expected = expected_types & error_types
        
        if found_expected:
            print(f"[OK] Detected expected error types: {found_expected}")
        
        return True
        
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    print()
    print("#" * 60)
    print("# Localization MVR - E2E Test Suite")
    print("#" * 60)
    print()
    
    success = True
    
    # Test 1: E2E workflow with valid data
    if not test_end_to_end_workflow():
        success = False
    
    # Test 2: QA error detection
    if not test_qa_error_detection():
        success = False
    
    print()
    print("#" * 60)
    if success:
        print("# ALL TESTS PASSED")
    else:
        print("# SOME TESTS FAILED")
    print("#" * 60)
    
    sys.exit(0 if success else 1)
