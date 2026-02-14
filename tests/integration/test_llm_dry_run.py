#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test LLM Scripts Dry-Run Mode

Validates that all LLM-dependent scripts can run in dry-run mode
without requiring actual API access.

This test ensures:
1. Scripts can parse arguments correctly
2. Input files can be loaded and validated
3. Configuration is correct
4. Scripts exit cleanly without LLM calls
"""

import subprocess
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def run_dry_run(cmd: list, name: str) -> bool:
    """Run a script in dry-run mode and check success."""
    print(f"\n{'='*60}")
    print(f"Testing: {name}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}")
    print()
    
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
    
    # Check for dry-run success message
    if "PASSED" in result.stdout or "Dry-run" in result.stdout:
        print("[OK] Dry-run validation successful")
        return True
    
    print("[WARN] Completed but no explicit PASSED message")
    return True


def test_translate_dry_run():
    """Test translate_llm.py --dry-run"""
    fixtures = Path("data/fixtures")
    
    return run_dry_run([
        "python", "scripts/translate_llm.py",
        "--input", str(fixtures / "input_valid.csv"),
        "--output", "data/temp_test_translated.csv",
        "--style", "workflow/style_guide.md",
        "--glossary", str(fixtures / "placeholder_map.json"),
        "--dry-run"
    ], "translate_llm.py --dry-run")


def test_soft_qa_dry_run():
    """Test soft_qa_llm.py --dry-run"""
    fixtures = Path("data/fixtures")
    
    return run_dry_run([
        "python", "scripts/soft_qa_llm.py",
        str(fixtures / "translated_valid.csv"),
        "workflow/style_guide.md",
        "data/glossary.yaml",
        "workflow/soft_qa_rubric.yaml",
        "--dry-run"
    ], "soft_qa_llm.py --dry-run")


def test_repair_loop_dry_run():
    """Test repair_loop.py --dry-run"""
    fixtures = Path("data/fixtures")
    
    # Create empty repair tasks for test
    temp_tasks = Path("data/temp_repair_tasks.jsonl")
    temp_tasks.write_text("", encoding="utf-8")
    
    # Create empty hard report
    temp_report = Path("data/temp_qa_report.json")
    temp_report.write_text('{"has_errors": false, "errors": []}', encoding="utf-8")
    
    try:
        result = run_dry_run([
            "python", "scripts/repair_loop.py",
            str(fixtures / "translated_valid.csv"),
            str(temp_report),
            str(temp_tasks),
            "workflow/style_guide.md",
            "data/glossary.yaml",
            "--dry-run"
        ], "repair_loop.py --dry-run")
        return result
    finally:
        # Cleanup
        if temp_tasks.exists():
            temp_tasks.unlink()
        if temp_report.exists():
            temp_report.unlink()


def test_glossary_autopromote_dry_run():
    """Test glossary_autopromote.py --dry-run"""
    fixtures = Path("data/fixtures")
    
    return run_dry_run([
        "python", "scripts/glossary_autopromote.py",
        "--before", str(fixtures / "translated_valid.csv"),
        "--after", str(fixtures / "translated_valid.csv"),
        "--style", "workflow/style_guide.md",
        "--glossary", "data/glossary.yaml",
        "--dry-run"
    ], "glossary_autopromote.py --dry-run")


if __name__ == "__main__":
    print()
    print("#" * 60)
    print("# LLM Scripts Dry-Run Test Suite")
    print("#" * 60)
    print()
    print("Testing that LLM scripts can validate configuration")
    print("without making actual API calls.")
    print()
    
    results = []
    
    # Test each LLM script
    results.append(("translate_llm.py", test_translate_dry_run()))
    results.append(("soft_qa_llm.py", test_soft_qa_dry_run()))
    results.append(("repair_loop.py", test_repair_loop_dry_run()))
    results.append(("glossary_autopromote.py", test_glossary_autopromote_dry_run()))
    
    # Summary
    print()
    print("#" * 60)
    print("# Summary")
    print("#" * 60)
    print()
    
    all_passed = True
    for name, passed in results:
        status = "[OK]" if passed else "[FAIL]"
        print(f"  {status} {name}")
        if not passed:
            all_passed = False
    
    print()
    
    if all_passed:
        print("#" * 60)
        print("# ALL DRY-RUN TESTS PASSED")
        print("#" * 60)
        print()
        print("All LLM scripts can be validated without API access.")
        print("Configuration is correct and ready for actual use.")
    else:
        print("#" * 60)
        print("# SOME TESTS FAILED")
        print("#" * 60)
    
    sys.exit(0 if all_passed else 1)
