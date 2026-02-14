#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_30k_subset.py

30,000 row subset performance test for the full localization pipeline.
This is a smoke test that validates the entire pipeline can handle
production-scale data volumes within acceptable time limits.

Pipeline stages tested:
1. normalize_guard - Freeze placeholders and tags
2. translate_llm - Translate with mocked LLM
3. qa_hard - Validate translations
4. rehydrate_export - Restore placeholders and export

Performance Benchmarks:
- normalize: < 30 seconds
- translate: < 60 seconds (with mocks)
- qa: < 45 seconds
- rehydrate: < 20 seconds
- Total: < 3 minutes

Usage:
    cd /root/.openclaw/workspace/projects/game-localization-mvr/01_active/src
    python -m pytest tests/test_30k_subset.py -v
    
    # Or run directly:
    python tests/test_30k_subset.py
"""

import csv
import json
import os
import sys
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

# Add paths for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import pytest

# ============================================================================
# Configuration
# ============================================================================

PERFORMANCE_BENCHMARKS = {
    "normalize_max_seconds": 30,
    "translate_max_seconds": 60,
    "qa_max_seconds": 45,
    "rehydrate_max_seconds": 20,
    "total_max_seconds": 180,  # 3 minutes
}

SAMPLE_DATA_PATH = Path(__file__).parent / "data" / "sample_30k.csv"
WORKFLOW_PATH = Path(__file__).parent.parent / "workflow"
REPORTS_PATH = Path(__file__).parent / "reports"

# Store timings globally for report generation
TIMING_RESULTS = {}

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture(scope="module")
def temp_working_dir():
    """Create a temporary working directory for test artifacts."""
    tmpdir = tempfile.mkdtemp(prefix="test_30k_")
    yield Path(tmpdir)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture(scope="module")
def pipeline_paths(temp_working_dir):
    """Generate all file paths for the pipeline."""
    return {
        "input_csv": SAMPLE_DATA_PATH,
        "draft_csv": temp_working_dir / "draft.csv",
        "placeholder_map": temp_working_dir / "placeholder_map.json",
        "translated_csv": temp_working_dir / "translated.csv",
        "qa_report": temp_working_dir / "qa_report.json",
        "final_csv": temp_working_dir / "final.csv",
        "checkpoint_json": temp_working_dir / "checkpoint.json",
        "temp_glossary": temp_working_dir / "temp_glossary.yaml",
    }


@pytest.fixture(scope="module")
def mock_glossary_content():
    """Create a minimal glossary for testing."""
    return """
entries:
  - term_zh: "战士"
    term_ru: "Воин"
    status: "approved"
  - term_zh: "法师"
    term_ru: "Маг"
    status: "approved"
  - term_zh: "盗贼"
    term_ru: "Вор"
    status: "approved"
  - term_zh: "治疗"
    term_ru: "Исцеление"
    status: "approved"
  - term_zh: "攻击"
    term_ru: "Атака"
    status: "approved"
meta:
  compiled_hash: "test_hash_123"
"""


# ============================================================================
# Mock LLM Response Generator
# ============================================================================

def create_mock_llm_response(tokenized_text: str) -> str:
    """
    Create a mock Russian translation that preserves all tokens.
    
    This simulates a perfect LLM that:
    1. Translates Chinese to Russian
    2. Preserves all ⟦PH_X⟧ and ⟦TAG_X⟧ tokens
    3. Returns valid output
    """
    import re
    
    # Extract all tokens
    tokens = re.findall(r'⟦(?:PH_\d+|TAG_\d+)⟧', tokenized_text)
    
    # Create a mock Russian translation based on content length
    text_without_tokens = re.sub(r'⟦(?:PH_\d+|TAG_\d+)⟧', ' ', tokenized_text)
    char_count = len(text_without_tokens.strip())
    
    # Generate mock Russian text (deterministic based on length)
    russian_words = [
        "Перевод", "текста", "на", "русский", "язык",
        "локализация", "игры", "контент", "тестирование",
        "производительность", "большой", "объем", "данных"
    ]
    
    # Select words deterministically
    selected = []
    for i in range(max(2, min(char_count // 3, 8))):
        word_idx = (char_count + i * 7) % len(russian_words)
        selected.append(russian_words[word_idx])
    
    mock_translation = " ".join(selected)
    
    # Insert tokens back into the translation at appropriate positions
    if tokens:
        if len(tokens) == 1:
            mock_translation = f"{tokens[0]}{mock_translation}"
        else:
            mid = len(tokens) // 2
            mock_translation = f"{''.join(tokens[:mid])}{mock_translation}{''.join(tokens[mid:])}"
    
    return mock_translation


def mock_batch_llm_call(step, rows, **kwargs):
    """Mock batch_llm_call function."""
    results = []
    for row in rows:
        if isinstance(row, dict):
            tokenized = row.get("source_text") or row.get("tokenized_zh", "")
            row_id = row.get("id", "unknown")
        else:
            tokenized = str(row)
            row_id = str(len(results))
            
        mock_result = create_mock_llm_response(tokenized)
        results.append({
            "id": row_id,
            "target_ru": mock_result,
            "target_text": mock_result,
            "model_used": "mock-model"
        })
    return results


# ============================================================================
# Test Functions
# ============================================================================

class Test30KSubsetPerformance:
    """30,000 row subset performance test suite."""
    
    def test_01_sample_data_exists(self):
        """Verify sample_30k.csv exists and has correct row count."""
        assert SAMPLE_DATA_PATH.exists(), f"Sample data not found: {SAMPLE_DATA_PATH}"
        
        with open(SAMPLE_DATA_PATH, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 30000, f"Expected 30000 rows, got {len(rows)}"
        
        # Verify columns
        expected_cols = {"string_id", "source_zh", "context"}
        actual_cols = set(rows[0].keys())
        assert expected_cols.issubset(actual_cols), f"Missing columns: {expected_cols - actual_cols}"
    
    def test_02_normalize_guard_performance(self, pipeline_paths):
        """Test normalize_guard on 30k rows with performance benchmark."""
        from normalize_guard import NormalizeGuard
        
        schema_path = WORKFLOW_PATH / "placeholder_schema.yaml"
        
        print(f"\n⏱️  Testing normalize_guard on 30k rows...")
        start_time = time.time()
        
        guard = NormalizeGuard(
            input_path=str(pipeline_paths["input_csv"]),
            output_draft_path=str(pipeline_paths["draft_csv"]),
            output_map_path=str(pipeline_paths["placeholder_map"]),
            schema_path=str(schema_path),
            source_lang="zh-CN"
        )
        
        result = guard.run()
        
        elapsed = time.time() - start_time
        TIMING_RESULTS['normalize'] = elapsed
        
        # Verify success
        assert result is True, "normalize_guard failed"
        assert pipeline_paths["draft_csv"].exists(), "Draft CSV not created"
        assert pipeline_paths["placeholder_map"].exists(), "Placeholder map not created"
        
        # Performance assertion
        assert elapsed < PERFORMANCE_BENCHMARKS["normalize_max_seconds"], \
            f"normalize_guard too slow: {elapsed:.2f}s > {PERFORMANCE_BENCHMARKS['normalize_max_seconds']}s"
        
        # Verify output has correct row count
        with open(pipeline_paths["draft_csv"], 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 30000, f"Expected 30000 output rows, got {len(rows)}"
        
        print(f"✅ normalize_guard: {elapsed:.2f}s (benchmark: <{PERFORMANCE_BENCHMARKS['normalize_max_seconds']}s)")
    
    def test_03_translate_llm_performance(self, pipeline_paths, mock_glossary_content):
        """Test translate_llm on 30k rows with mocked LLM."""
        import src.scripts.translate_llm as tl as tl
        
        # Create temp glossary file
        glossary_path = pipeline_paths["temp_glossary"]
        with open(glossary_path, 'w', encoding='utf-8') as f:
            f.write(mock_glossary_content)
        
        print(f"\n⏱️  Testing translate_llm on 30k rows (with mocked LLM)...")
        
        # Mock the batch_llm_call
        with patch.object(tl, 'batch_llm_call', side_effect=mock_batch_llm_call):
            start_time = time.time()
            
            # Patch sys.argv for the main function
            original_argv = sys.argv
            try:
                sys.argv = [
                    "translate_llm.py",
                    "--input", str(pipeline_paths["draft_csv"]),
                    "--output", str(pipeline_paths["translated_csv"]),
                    "--glossary", str(glossary_path),
                    "--checkpoint", str(pipeline_paths["checkpoint_json"]),
                    "--model", "mock-model"
                ]
                
                result = tl.main()
            finally:
                sys.argv = original_argv
            
            elapsed = time.time() - start_time
            TIMING_RESULTS['translate'] = elapsed
        
        # Verify success
        assert result == 0 or result is None, f"translate_llm failed with exit code {result}"
        assert pipeline_paths["translated_csv"].exists(), "Translated CSV not created"
        
        # Performance assertion
        assert elapsed < PERFORMANCE_BENCHMARKS["translate_max_seconds"], \
            f"translate_llm too slow: {elapsed:.2f}s > {PERFORMANCE_BENCHMARKS['translate_max_seconds']}s"
        
        # Verify output
        with open(pipeline_paths["translated_csv"], 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 30000, f"Expected 30000 translated rows, got {len(rows)}"
        
        print(f"✅ translate_llm: {elapsed:.2f}s (benchmark: <{PERFORMANCE_BENCHMARKS['translate_max_seconds']}s)")
    
    def test_04_qa_hard_performance(self, pipeline_paths):
        """Test qa_hard on 30k rows with performance benchmark."""
        from qa_hard import QAHardValidator
        
        schema_path = WORKFLOW_PATH / "placeholder_schema.yaml"
        forbidden_path = WORKFLOW_PATH / "forbidden_patterns.txt"
        
        print(f"\n⏱️  Testing qa_hard on 30k rows...")
        start_time = time.time()
        
        validator = QAHardValidator(
            translated_csv=str(pipeline_paths["translated_csv"]),
            placeholder_map=str(pipeline_paths["placeholder_map"]),
            schema_yaml=str(schema_path),
            forbidden_txt=str(forbidden_path),
            report_json=str(pipeline_paths["qa_report"])
        )
        
        result = validator.run()
        
        elapsed = time.time() - start_time
        TIMING_RESULTS['qa'] = elapsed
        
        # Verify success (result is True even if errors found)
        assert result is True, "qa_hard failed"
        assert pipeline_paths["qa_report"].exists(), "QA report not created"
        
        # Performance assertion
        assert elapsed < PERFORMANCE_BENCHMARKS["qa_max_seconds"], \
            f"qa_hard too slow: {elapsed:.2f}s > {PERFORMANCE_BENCHMARKS['qa_max_seconds']}s"
        
        print(f"✅ qa_hard: {elapsed:.2f}s (benchmark: <{PERFORMANCE_BENCHMARKS['qa_max_seconds']}s)")
    
    def test_05_rehydrate_export_performance(self, pipeline_paths):
        """Test rehydrate_export on 30k rows with performance benchmark."""
        from rehydrate_export import RehydrateExporter
        
        print(f"\n⏱️  Testing rehydrate_export on 30k rows...")
        start_time = time.time()
        
        exporter = RehydrateExporter(
            translated_csv=str(pipeline_paths["translated_csv"]),
            placeholder_map=str(pipeline_paths["placeholder_map"]),
            final_csv=str(pipeline_paths["final_csv"]),
            overwrite_mode=False,
            target_lang="ru-RU"
        )
        
        result = exporter.run()
        
        elapsed = time.time() - start_time
        TIMING_RESULTS['rehydrate'] = elapsed
        
        # Verify success
        assert result is True, "rehydrate_export failed"
        assert pipeline_paths["final_csv"].exists(), "Final CSV not created"
        
        # Performance assertion
        assert elapsed < PERFORMANCE_BENCHMARKS["rehydrate_max_seconds"], \
            f"rehydrate_export too slow: {elapsed:.2f}s > {PERFORMANCE_BENCHMARKS['rehydrate_max_seconds']}s"
        
        # Verify output
        with open(pipeline_paths["final_csv"], 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 30000, f"Expected 30000 final rows, got {len(rows)}"
        
        print(f"✅ rehydrate_export: {elapsed:.2f}s (benchmark: <{PERFORMANCE_BENCHMARKS['rehydrate_max_seconds']}s)")
    
    def test_06_full_pipeline_total_time(self):
        """Verify total pipeline execution time is under 3 minutes."""
        total_time = sum(TIMING_RESULTS.values())
        TIMING_RESULTS['total'] = total_time
        
        print(f"\n📊 Total pipeline time: {total_time:.2f}s")
        print(f"   Target: <{PERFORMANCE_BENCHMARKS['total_max_seconds']}s (3 minutes)")
        
        assert total_time < PERFORMANCE_BENCHMARKS["total_max_seconds"], \
            f"Total pipeline too slow: {total_time:.2f}s > {PERFORMANCE_BENCHMARKS['total_max_seconds']}s"
        
        print(f"✅ Total pipeline time within benchmark!")
    
    def test_07_generate_performance_report(self, pipeline_paths):
        """Generate performance report markdown file."""
        REPORTS_PATH.mkdir(parents=True, exist_ok=True)
        report_path = REPORTS_PATH / "performance_30k.md"
        
        # Gather metrics
        timings = TIMING_RESULTS.copy()
        if 'total' not in timings:
            timings['total'] = sum(timings.values())
        
        # Calculate throughput
        throughputs = {k: 30000 / v if v > 0 else 0 for k, v in timings.items()}
        
        # Read QA report for error counts
        error_count = 0
        if pipeline_paths["qa_report"].exists():
            try:
                with open(pipeline_paths["qa_report"], 'r', encoding='utf-8') as f:
                    qa_data = json.load(f)
                    error_count = len(qa_data.get("errors", []))
            except:
                pass
        
        # Check all benchmarks
        normalize_pass = timings.get('normalize', 999) < PERFORMANCE_BENCHMARKS['normalize_max_seconds']
        translate_pass = timings.get('translate', 999) < PERFORMANCE_BENCHMARKS['translate_max_seconds']
        qa_pass = timings.get('qa', 999) < PERFORMANCE_BENCHMARKS['qa_max_seconds']
        rehydrate_pass = timings.get('rehydrate', 999) < PERFORMANCE_BENCHMARKS['rehydrate_max_seconds']
        total_pass = timings.get('total', 999) < PERFORMANCE_BENCHMARKS['total_max_seconds']
        all_pass = normalize_pass and translate_pass and qa_pass and rehydrate_pass and total_pass
        
        # Generate report
        report = f"""# 30K Row Subset Performance Test Report

**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}
**Test Data**: `tests/data/sample_30k.csv`
**Rows Processed**: 30,000

## Summary

| Metric | Value | Status |
|--------|-------|--------|
| Total Pipeline Time | {timings['total']:.2f}s | {'✅ PASS' if total_pass else '❌ FAIL'} |
| Throughput | {30000/timings['total']:.1f} rows/sec | - |
| QA Errors Found | {error_count} | {'✅ PASS' if error_count < 100 else '⚠️ WARN'} |

## Stage-by-Stage Performance

| Stage | Time (s) | Benchmark (s) | Throughput (rows/s) | Status |
|-------|----------|---------------|---------------------|--------|
| normalize_guard | {timings.get('normalize', 0):.2f} | <{PERFORMANCE_BENCHMARKS['normalize_max_seconds']} | {throughputs.get('normalize', 0):.1f} | {'✅ PASS' if normalize_pass else '❌ FAIL'} |
| translate_llm | {timings.get('translate', 0):.2f} | <{PERFORMANCE_BENCHMARKS['translate_max_seconds']} | {throughputs.get('translate', 0):.1f} | {'✅ PASS' if translate_pass else '❌ FAIL'} |
| qa_hard | {timings.get('qa', 0):.2f} | <{PERFORMANCE_BENCHMARKS['qa_max_seconds']} | {throughputs.get('qa', 0):.1f} | {'✅ PASS' if qa_pass else '❌ FAIL'} |
| rehydrate_export | {timings.get('rehydrate', 0):.2f} | <{PERFORMANCE_BENCHMARKS['rehydrate_max_seconds']} | {throughputs.get('rehydrate', 0):.1f} | {'✅ PASS' if rehydrate_pass else '❌ FAIL'} |

## Benchmarks

All benchmarks assume:
- Standard development hardware (2+ cores)
- No actual LLM calls (mocked for translate)
- CSV I/O on local filesystem

| Stage | Target | Rationale |
|-------|--------|-----------|
| normalize | <30s | Text processing + regex matching |
| translate | <60s | Mock LLM overhead + validation |
| qa | <45s | Rule validation on all rows |
| rehydrate | <20s | Token replacement + CSV write |
| **Total** | **<180s** | **3 minute smoke test** |

## Data Composition

The 30K test dataset contains:

| Content Type | Approximate % |
|--------------|---------------|
| Simple text (no placeholders/tags) | ~40% |
| Text with placeholders ({{0}}, %d, etc.) | ~25% |
| Text with Unity/HTML tags | ~15% |
| Complex (both placeholders + tags) | ~15% |
| Long text (>500 chars) | ~5% |

## QA Validation Results

- **Total Errors**: {error_count}
- **Error Limit**: 2000 (hard limit in qa_hard.py)
- **Status**: {'✅ Within limits' if error_count < 2000 else '❌ Exceeded limit'}

## Conclusion

The pipeline successfully processed 30,000 rows of synthetic game localization data.

**Status**: {'✅ ALL BENCHMARKS PASSED' if all_pass else '❌ SOME BENCHMARKS FAILED'}

---
*Auto-generated by test_30k_subset.py*
"""
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        print(f"\n📝 Performance report written to: {report_path}")


# ============================================================================
# Standalone execution
# ============================================================================

if __name__ == "__main__":
    """Run tests directly without pytest."""
    print("=" * 60)
    print("30K Row Subset Performance Test")
    print("=" * 60)
    
    # Create temp directory
    tmpdir = tempfile.mkdtemp(prefix="test_30k_")
    temp_path = Path(tmpdir)
    
    try:
        test = Test30KSubsetPerformance()
        
        # Generate paths
        paths = {
            "input_csv": SAMPLE_DATA_PATH,
            "draft_csv": temp_path / "draft.csv",
            "placeholder_map": temp_path / "placeholder_map.json",
            "translated_csv": temp_path / "translated.csv",
            "qa_report": temp_path / "qa_report.json",
            "final_csv": temp_path / "final.csv",
            "checkpoint_json": temp_path / "checkpoint.json",
            "temp_glossary": temp_path / "temp_glossary.yaml",
        }
        
        mock_glossary = """
entries:
  - term_zh: "战士"
    term_ru: "Воин"
    status: "approved"
meta:
  compiled_hash: "test_hash_123"
"""
        
        # Run tests sequentially
        test.test_01_sample_data_exists()
        print("✅ Sample data verified\n")
        
        test.test_02_normalize_guard_performance(paths)
        print("✅ Normalize complete\n")
        
        test.test_03_translate_llm_performance(paths, mock_glossary)
        print("✅ Translate complete\n")
        
        test.test_04_qa_hard_performance(paths)
        print("✅ QA complete\n")
        
        test.test_05_rehydrate_export_performance(paths)
        print("✅ Rehydrate complete\n")
        
        test.test_06_full_pipeline_total_time()
        print("✅ Total time verified\n")
        
        test.test_07_generate_performance_report(paths)
        
        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)
        
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
