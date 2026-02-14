#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coverage measurement script for translate_llm.py
"""

import sys
import os

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

# Mock runtime_adapter before importing translate_llm
from unittest.mock import Mock, MagicMock

# Create comprehensive mock
mock_runtime = Mock()
mock_runtime.LLMClient = Mock
mock_runtime.LLMError = Exception
mock_runtime.batch_llm_call = Mock()
mock_runtime.log_llm_progress = Mock()

sys.modules['runtime_adapter'] = mock_runtime

# Now import and run coverage
import coverage
cov = coverage.Coverage(
    source=['scripts.translate_llm'],
    omit=['*/tests/*', '*/test_*']
)
cov.start()

# Import the module to measure
import importlib
import scripts.translate_llm as tl

# Run a comprehensive set of operations
from dataclasses import dataclass
from pathlib import Path
import tempfile
import shutil
import json
import csv

# Create temp directory
tmpdir = tempfile.mkdtemp()

try:
    # Test GlossaryEntry
    entry = tl.GlossaryEntry(term_zh="测试", term_ru="Тест", status="approved")
    
    # Test glossary constraints
    entries = [
        tl.GlossaryEntry(term_zh="战士", term_ru="Воин", status="approved"),
        tl.GlossaryEntry(term_zh="法师", term_ru="Маг", status="approved"),
    ]
    constraints = tl.build_glossary_constraints(entries, "战士和法师")
    
    # Test token signature
    sig = tl.tokens_signature("⟦PH_1⟧战士⟦PH_2⟧")
    
    # Test validation
    ok, err = tl.validate_translation("⟦PH_1⟧战士", "⟦PH_1⟧Воин")
    ok2, err2 = tl.validate_translation("⟦PH_1⟧战士", "Воин")  # Should fail
    ok3, err3 = tl.validate_translation("战士", "战士")  # Should fail CJK
    
    # Test prompt builders
    factory = tl.build_system_prompt_factory("style", "glossary")
    prompt = factory([{"string_id": "1", "max_length_target": 50}])
    user_prompt = tl.build_user_prompt([{"id": "1", "source_text": "test"}])
    
    # Test checkpoint
    ckpt_path = os.path.join(tmpdir, "ckpt.json")
    tl.save_checkpoint(ckpt_path, {"1", "2"})
    loaded = tl.load_checkpoint(ckpt_path)
    
    # Test text loading
    text_path = os.path.join(tmpdir, "test.txt")
    with open(text_path, 'w') as f:
        f.write("content")
    text = tl.load_text(text_path)
    
    # Test glossary loading
    glossary_path = os.path.join(tmpdir, "glossary.yaml")
    with open(glossary_path, 'w') as f:
        f.write("entries:\n  - term_zh: 战士\n    term_ru: Воин\n    status: approved\n")
    glossary, hash_val = tl.load_glossary(glossary_path)
    
    # Test glossary summary
    summary = tl.build_glossary_summary(entries)
    
    # Test main() with mocked args
    csv_path = os.path.join(tmpdir, "input.csv")
    with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=["string_id", "source_zh", "tokenized_zh"])
        writer.writeheader()
        writer.writerow({"string_id": "1", "source_zh": "战士", "tokenized_zh": "战士"})
    
    output_path = os.path.join(tmpdir, "output.csv")
    ckpt2 = os.path.join(tmpdir, "checkpoint.json")
    
    mock_runtime.batch_llm_call.return_value = [{"id": "1", "target_ru": "Воин"}]
    
    with open(os.path.join(tmpdir, "style.md"), 'w') as f:
        f.write("style")
    with open(os.path.join(tmpdir, "glossary.yaml"), 'w') as f:
        f.write("entries: []")
    
    import sys
    from unittest.mock import patch
    with patch.object(sys, 'argv', [
        'translate_llm.py',
        '--input', csv_path,
        '--output', output_path,
        '--style', os.path.join(tmpdir, "style.md"),
        '--glossary', os.path.join(tmpdir, "glossary.yaml"),
        '--checkpoint', ckpt2,
        '--model', 'test-model'
    ]):
        tl.main()

finally:
    shutil.rmtree(tmpdir)

cov.stop()
cov.save()

# Generate reports
print("\n" + "="*60)
print("COVERAGE REPORT FOR translate_llm.py")
print("="*60)
cov.report()

# Write HTML report
html_dir = os.path.join(os.path.dirname(__file__), 'coverage_translate_llm')
cov.html_report(directory=html_dir)
print(f"\nHTML report generated at: {html_dir}")

# Get coverage percentage
total = cov.get_data()
files = list(total.measured_files())
if files:
    analysis = cov.analysis(files[0])
    covered = len(analysis[1])  # executed lines
    missing = len(analysis[2])  # missing lines
    total_lines = covered + missing
    percentage = (covered / total_lines * 100) if total_lines > 0 else 0
    print(f"\nTotal Coverage: {percentage:.1f}% ({covered}/{total_lines} lines)")
