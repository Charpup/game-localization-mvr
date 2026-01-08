#!/usr/bin/env python3
"""
端到端 Workflow 测试
测试完整的本地化流程：normalize → translate → qa → rehydrate
"""

import subprocess
import sys
import json
from pathlib import Path


def run_command(cmd: list, description: str) -> bool:
    """运行命令并检查结果"""
    print(f"\n{'='*60}")
    print(f"Step: {description}")
    print(f"{'='*60}")
    print(f"Command: {' '.join(cmd)}")
    print()
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    if result.returncode != 0:
        print(f"❌ Failed with exit code {result.returncode}")
        return False
    
    print(f"✅ Success")
    return True


def test_end_to_end_workflow():
    """测试端到端工作流"""
    
    print("🚀 Testing End-to-End Localization Workflow")
    print("=" * 60)
    print()
    
    # Step 1: Normalize
    if not run_command(
        [
            "python", "scripts/normalize_guard.py",
            "data/input.csv",
            "data/draft_e2e.csv",
            "data/placeholder_map_e2e.json",
            "workflow/placeholder_schema.yaml"
        ],
        "1. Normalize - Freeze placeholders"
    ):
        return False
    
    # Step 2: Simulate translation (copy draft to translated with English)
    print(f"\n{'='*60}")
    print("Step: 2. Translate - Simulate translation")
    print(f"{'='*60}")
    print("(In real workflow, this would be done by translators or AI)")
    print("For testing, we'll use the pre-translated file")
    print()
    
    # Step 3: QA Hard
    if not run_command(
        [
            "python", "scripts/qa_hard.py",
            "data/translated_good.csv",
            "data/placeholder_map_e2e.json",
            "workflow/placeholder_schema.yaml",
            "workflow/forbidden_patterns.txt",
            "data/qa_report_e2e.json"
        ],
        "3. QA Hard - Validate translations"
    ):
        return False
    
    # Check QA report
    with open("data/qa_report_e2e.json", 'r', encoding='utf-8') as f:
        qa_report = json.load(f)
    
    if qa_report['has_errors']:
        print("❌ QA validation failed - cannot proceed to rehydrate")
        return False
    
    # Step 4: Rehydrate
    if not run_command(
        [
            "python", "scripts/rehydrate_export.py",
            "data/translated_good.csv",
            "data/placeholder_map_e2e.json",
            "data/final_e2e.csv"
        ],
        "4. Rehydrate - Restore placeholders"
    ):
        return False
    
    # Final verification
    print(f"\n{'='*60}")
    print("Final Verification")
    print(f"{'='*60}")
    
    final_path = Path("data/final_e2e.csv")
    if not final_path.exists():
        print("❌ Final output file not found")
        return False
    
    print(f"✅ Final output generated: {final_path}")
    print(f"   File size: {final_path.stat().st_size} bytes")
    print()
    
    print("=" * 60)
    print("🎉 End-to-End Workflow Test PASSED!")
    print("=" * 60)
    print()
    print("Workflow Summary:")
    print("  1. ✅ Normalize - Froze placeholders into tokens")
    print("  2. ✅ Translate - (Simulated with pre-translated data)")
    print("  3. ✅ QA Hard - Validated all translations")
    print("  4. ✅ Rehydrate - Restored original placeholders")
    print()
    print("Generated files:")
    print("  - data/draft_e2e.csv")
    print("  - data/placeholder_map_e2e.json")
    print("  - data/qa_report_e2e.json")
    print("  - data/final_e2e.csv")
    
    return True


if __name__ == "__main__":
    success = test_end_to_end_workflow()
    sys.exit(0 if success else 1)
