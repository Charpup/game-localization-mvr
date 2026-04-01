#!/usr/bin/env python3
"""Test qa_hard.py using reproducible fixtures."""

import io
import json
import shutil
import subprocess
import sys
from pathlib import Path

PYTHON = sys.executable


def configure_standard_streams() -> None:
    """Best-effort UTF-8 console setup for Windows CLI execution."""
    if sys.platform != 'win32':
        return

    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None:
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding='utf-8', errors='replace')
                continue
            buffer = getattr(stream, "buffer", None)
            if buffer is not None:
                wrapped = io.TextIOWrapper(buffer, encoding='utf-8', errors='replace')
                setattr(sys, stream_name, wrapped)
        except Exception:
            continue


def run_qa(translated_csv: Path, report_path: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            PYTHON,
            "scripts/qa_hard.py",
            str(translated_csv),
            "data/fixtures/placeholder_map.json",
            "workflow/placeholder_schema.yaml",
            "workflow/forbidden_patterns.txt",
            str(report_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_qa_hard() -> bool:
    """Test qa_hard output against stable fixtures."""
    print("[TEST] Testing qa_hard.py output...")
    print()

    temp_dir = Path("data/temp_qa_hard_test")
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        good_report_path = temp_dir / "qa_report_good.json"
        bad_report_path = temp_dir / "qa_report_bad.json"

        good_result = run_qa(Path("data/fixtures/translated_valid.csv"), good_report_path)
        bad_result = run_qa(Path("data/fixtures/translated_bad.csv"), bad_report_path)

        if good_result.returncode != 0:
            print("[FAIL] Good fixture unexpectedly failed")
            print(good_result.stdout)
            print(good_result.stderr)
            return False

        if not good_report_path.exists():
            print("[FAIL] Error: generated good QA report not found")
            return False

        if not bad_report_path.exists():
            print("[FAIL] Error: generated bad QA report not found")
            return False

        print("=" * 60)
        print("Test 1: Good translations (should pass)")
        print("=" * 60)

        with open(good_report_path, "r", encoding="utf-8") as f:
            good_report = json.load(f)

        print(f"Total rows: {good_report['total_rows']}")
        print(f"Has errors: {good_report['has_errors']}")
        print(f"Total errors: {good_report['metadata']['total_errors']}")

        if good_report["has_errors"]:
            print("[FAIL] Test failed: Good translations should not have errors")
            return False

        print("[OK] Test passed: No errors in good translations")
        print()

        print("=" * 60)
        print("Test 2: Bad translations (should fail)")
        print("=" * 60)

        with open(bad_report_path, "r", encoding="utf-8") as f:
            bad_report = json.load(f)

        print(f"Total rows: {bad_report['total_rows']}")
        print(f"Has errors: {bad_report['has_errors']}")
        print(f"Total errors: {bad_report['metadata']['total_errors']}")
        print()

        print("Error counts:")
        for error_type, count in bad_report["error_counts"].items():
            if count > 0:
                print(f"  - {error_type}: {count}")

        if bad_result.returncode == 0:
            print("[FAIL] Test failed: Bad translations should have non-zero exit code")
            return False

        if not bad_report["has_errors"]:
            print("[FAIL] Test failed: Bad translations should have errors")
            return False

        expected_errors = {
            "token_mismatch": True,
            "tag_unbalanced": True,
            "forbidden_hit": True,
        }

        for error_type, should_exist in expected_errors.items():
            count = bad_report["error_counts"].get(error_type, 0)
            if should_exist and count == 0:
                print(f"[FAIL] Test failed: Expected {error_type} errors but found none")
                return False

        print()
        print("[OK] Test passed: All expected error types detected")
        print()

        print("Sample errors from bad translations:")
        for i, error in enumerate(bad_report["errors"][:5], 1):
            print(f"{i}. [{error['type']}] {error['string_id']}")
            detail = str(error["detail"]).encode("ascii", "backslashreplace").decode("ascii")
            print(f"   {detail}")

        print()
        print("[PASS] All QA Hard tests passed!")
        return True
    finally:
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    configure_standard_streams()
    success = test_qa_hard()
    sys.exit(0 if success else 1)
