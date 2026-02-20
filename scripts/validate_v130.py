#!/usr/bin/env python3
"""Validation pipeline for v1.3.0 multi-language support."""
import subprocess
import sys
from pathlib import Path

def check_file_exists(path, description):
    """Check if file exists."""
    if Path(path).exists():
        print(f"✅ {description}")
        return True
    else:
        print(f"❌ {description} - MISSING")
        return False

def validate_configuration():
    """Validate all configuration files."""
    print("\n=== Configuration Validation ===")
    checks = [
        ('src/config/language_pairs.yaml', 'Language pairs config'),
        ('src/config/prompts/en/batch_translate_system.txt', 'EN batch translate prompt'),
        ('src/config/prompts/en/glossary_translate_system.txt', 'EN glossary prompt'),
        ('src/config/prompts/en/soft_qa_system.txt', 'EN QA prompt'),
        ('src/config/qa_rules/en.yaml', 'EN QA rules'),
    ]
    return all(check_file_exists(f, desc) for f, desc in checks)

def validate_scripts():
    """Validate all core scripts support multi-language."""
    print("\n=== Script Validation ===")
    scripts = [
        'src/scripts/batch_runtime.py',
        'src/scripts/glossary_translate_llm.py',
        'src/scripts/soft_qa_llm.py',
    ]
    
    all_pass = True
    for script in scripts:
        result = subprocess.run(
            ['python', script, '--help'],
            capture_output=True,
            cwd=Path(__file__).parent.parent
        )
        if result.returncode == 0 and b'--target-lang' in result.stdout:
            print(f"✅ {script} - Multi-language support confirmed")
        else:
            print(f"❌ {script} - Missing --target-lang support")
            all_pass = False
    return all_pass

def validate_tests():
    """Validate test suite."""
    print("\n=== Test Suite Validation ===")
    result = subprocess.run(
        ['python', '-m', 'pytest', 'tests/unit/test_multi_language.py', '-v'],
        capture_output=True,
        cwd=Path(__file__).parent.parent
    )
    if result.returncode == 0:
        print("✅ Multi-language tests passing")
        return True
    else:
        print("❌ Some tests failing")
        print(result.stdout.decode())
        return False

def main():
    """Run full validation pipeline."""
    print("🔍 Loc-MVR v1.3.0 Validation Pipeline")
    
    results = [
        validate_configuration(),
        validate_scripts(),
        validate_tests(),
    ]
    
    if all(results):
        print("\n🎉 All validations passed! Ready for release.")
        return 0
    else:
        print("\n⚠️ Some validations failed. Please fix before release.")
        return 1

if __name__ == '__main__':
    sys.exit(main())
