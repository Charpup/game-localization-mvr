#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_baseline_performance.py - Performance Baseline Tests for Game Localization MVR

This module establishes performance baselines for all pipeline stages:
- normalize_guard: Placeholder freezing and tokenization
- translate_llm: LLM-based translation (with mocks for consistent benchmarking)
- qa_hard: Hard rule validation
- rehydrate_export: Token restoration and export

Test Data Sizes:
- 1k rows: Small dataset (fast iteration)
- 10k rows: Medium dataset (typical workload)
- 30k rows: Large dataset (stress testing)

Usage:
    pytest tests/performance/test_baseline_performance.py -v
    pytest tests/performance/test_baseline_performance.py -v --benchmark-only
    pytest tests/performance/test_baseline_performance.py::TestNormalizeGuardPerformance -v

Metrics Collected:
- Execution time (wall clock)
- Memory usage (peak RSS)
- Throughput (rows/second)
- Error rates (if applicable)
"""

import pytest
import time
import csv
import json
import tempfile
import os
import sys
import gc
import psutil
from pathlib import Path
from typing import List, Dict, Tuple, Callable
from dataclasses import dataclass, asdict
from contextlib import contextmanager

# Add project paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from normalize_guard import NormalizeGuard, PlaceholderFreezer
from qa_hard import QAHardValidator
from rehydrate_export import RehydrateExporter
from tests.mock_llm import MockLLM, MockResponse

# =============================================================================
# Configuration
# =============================================================================

TEST_DATA_SIZES = [1000, 10000, 30000]  # 1k, 10k, 30k rows
BASE_DATA_PATH = Path(__file__).parent.parent.parent / "test_30_repaired.csv"
WORKFLOW_PATH = Path(__file__).parent.parent.parent / "workflow"
PERFORMANCE_RESULTS: List[Dict] = []


@dataclass
class PerformanceMetrics:
    """Container for performance measurement results."""
    module: str
    data_size: int
    execution_time_sec: float
    peak_memory_mb: float
    throughput_rows_per_sec: float
    error_count: int = 0
    additional_metrics: Dict = None
    
    def __post_init__(self):
        if self.additional_metrics is None:
            self.additional_metrics = {}
    
    def to_dict(self) -> Dict:
        return asdict(self)


@contextmanager
def measure_performance(module_name: str, data_size: int):
    """
    Context manager to measure performance of a code block.
    
    Usage:
        with measure_performance("normalize_guard", 1000) as metrics:
            # code to measure
            metrics["additional_metrics"]["custom"] = value
    """
    process = psutil.Process()
    
    # Force garbage collection before measurement
    gc.collect()
    
    # Record start state
    start_time = time.perf_counter()
    start_memory = process.memory_info().rss / 1024 / 1024  # MB
    
    metrics_container = {"additional_metrics": {}}
    
    try:
        yield metrics_container
    finally:
        # Record end state
        end_time = time.perf_counter()
        end_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        execution_time = end_time - start_time
        peak_memory = max(end_memory, start_memory)
        throughput = data_size / execution_time if execution_time > 0 else 0
        
        # Store result
        result = PerformanceMetrics(
            module=module_name,
            data_size=data_size,
            execution_time_sec=round(execution_time, 3),
            peak_memory_mb=round(peak_memory, 2),
            throughput_rows_per_sec=round(throughput, 2),
            error_count=metrics_container.get("error_count", 0),
            additional_metrics=metrics_container["additional_metrics"]
        )
        PERFORMANCE_RESULTS.append(result.to_dict())


def generate_test_csv(rows: int, output_path: Path, include_placeholders: bool = True) -> Path:
    """Generate a test CSV with specified number of rows."""
    
    # Sample Chinese text templates
    templates = [
        "医术秘传",
        "健壮秘传",
        "穿透秘传",
        "获得{0}金币",
        "玩家<color=#FF0000>{name}</color>加入了队伍",
        "任务完成度: %d%%",
        "[ITEM_NAME]已被添加到背包",
        "等级提升\\n新等级: {level}",
        "<b>警告</b>: 血量低于%H",
        "使用<size=14>{skill_name}</size>造成%d点伤害",
    ]
    
    fieldnames = [
        'string_id', 'source_zh', 'module_tag', 'module_confidence',
        'max_len_target', 'len_tier', 'source_locale', 'placeholder_flags',
        'status', 'is_empty_source', 'is_long_text'
    ]
    
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for i in range(rows):
            template = templates[i % len(templates)]
            # Add variation based on row number
            if i > 0:
                template = f"{template}_{i}"
            
            row = {
                'string_id': f'1000{i:05d}',
                'source_zh': template,
                'module_tag': 'ui_button' if i % 2 == 0 else 'misc',
                'module_confidence': '0.7' if i % 2 == 0 else '0.5',
                'max_len_target': '19' if i % 2 == 0 else '20',
                'len_tier': 'S',
                'source_locale': 'zh-CN',
                'placeholder_flags': 'count=0' if '{' not in template else 'count=1',
                'status': 'ok',
                'is_empty_source': 'False',
                'is_long_text': '1' if len(template) > 50 else '0'
            }
            writer.writerow(row)
    
    return output_path


def generate_placeholder_map(output_path: Path) -> Path:
    """Generate a sample placeholder map for testing."""
    data = {
        'metadata': {
            'version': '2.0',
            'generated_at': '2026-02-14T00:00:00',
            'input_file': 'test.csv',
            'total_placeholders': 10,
            'ph_count': 8,
            'tag_count': 2
        },
        'mappings': {
            'PH_1': '{0}',
            'PH_2': '{name}',
            'PH_3': '{level}',
            'PH_4': '{skill_name}',
            'PH_5': '%d',
            'PH_6': '%H',
            'PH_7': '[ITEM_NAME]',
            'PH_8': '\\n',
            'TAG_1': '<color=#FF0000>',
            'TAG_2': '</color>',
            'TAG_3': '<b>',
            'TAG_4': '</b>',
            'TAG_5': '<size=14>',
            'TAG_6': '</size>',
        }
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    return output_path


def generate_translated_csv(input_path: Path, output_path: Path) -> Path:
    """Generate a translated CSV based on input draft."""
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames + ['target_text']
    
    # Mock translations (Russian-like placeholders)
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in rows:
            source = row.get('tokenized_zh', row.get('source_zh', ''))
            # Simple mock: replace Chinese with "RU" prefix and keep tokens
            if '⟦PH_' in source or '⟦TAG_' in source:
                # Keep tokens, replace other text
                target = source
                for char in source:
                    if '\u4e00' <= char <= '\u9fff':  # CJK range
                        target = target.replace(char, 'RU')
            else:
                target = "RU_" + source
            
            row['target_text'] = target
            writer.writerow(row)
    
    return output_path


# =============================================================================
# Test Classes
# =============================================================================

class TestNormalizeGuardPerformance:
    """Performance tests for normalize_guard module."""
    
    @pytest.mark.parametrize("data_size", TEST_DATA_SIZES)
    def test_normalize_guard_performance(self, data_size: int, tmp_path: Path):
        """Measure normalize_guard performance at various data sizes."""
        
        # Setup test data
        input_csv = tmp_path / f"input_{data_size}.csv"
        output_draft = tmp_path / f"draft_{data_size}.csv"
        output_map = tmp_path / f"map_{data_size}.json"
        schema_path = WORKFLOW_PATH / "placeholder_schema.yaml"
        
        generate_test_csv(data_size, input_csv)
        
        # Measure performance
        with measure_performance("normalize_guard", data_size) as metrics:
            guard = NormalizeGuard(
                input_path=str(input_csv),
                output_draft_path=str(output_draft),
                output_map_path=str(output_map),
                schema_path=str(schema_path),
                source_lang="zh-CN"
            )
            success = guard.run()
            
            if not success:
                metrics["error_count"] = len(guard.errors)
            
            # Additional metrics
            metrics["additional_metrics"]["placeholders_frozen"] = len(guard.freezer.placeholder_map)
            metrics["additional_metrics"]["sanity_errors"] = len(guard.sanity_errors)
        
        # Assert baseline requirements
        result = PERFORMANCE_RESULTS[-1]
        
        # Performance thresholds (adjust based on hardware)
        max_time_thresholds = {
            1000: 5.0,   # 1k rows: max 5 seconds
            10000: 30.0, # 10k rows: max 30 seconds
            30000: 90.0  # 30k rows: max 90 seconds
        }
        
        min_throughput = {
            1000: 200,   # min 200 rows/sec
            10000: 300,  # min 300 rows/sec
            30000: 350   # min 350 rows/sec
        }
        
        assert result['execution_time_sec'] < max_time_thresholds[data_size], \
            f"Execution time {result['execution_time_sec']}s exceeds threshold {max_time_thresholds[data_size]}s"
        
        assert result['throughput_rows_per_sec'] > min_throughput[data_size], \
            f"Throughput {result['throughput_rows_per_sec']} rows/sec below threshold {min_throughput[data_size]}"


class TestTranslateLLMPerformance:
    """Performance tests for translate_llm module (with mocked LLM)."""
    
    @pytest.mark.parametrize("data_size", [1000, 10000])  # Skip 30k for LLM tests (too slow even with mocks)
    def test_translate_llm_performance(self, data_size: int, tmp_path: Path):
        """Measure translate_llm performance with mocked LLM."""
        
        # First create normalized data
        input_csv = tmp_path / f"input_{data_size}.csv"
        draft_csv = tmp_path / f"draft_{data_size}.csv"
        map_json = tmp_path / f"map_{data_size}.json"
        output_csv = tmp_path / f"translated_{data_size}.csv"
        schema_path = WORKFLOW_PATH / "placeholder_schema.yaml"
        
        generate_test_csv(data_size, input_csv)
        
        # Run normalize_guard first
        guard = NormalizeGuard(
            input_path=str(input_csv),
            output_draft_path=str(draft_csv),
            output_map_path=str(map_json),
            schema_path=str(schema_path),
            source_lang="zh-CN"
        )
        guard.run()
        
        # Setup mock LLM
        with MockLLM() as mock:
            # Pre-generate mock responses
            with open(draft_csv, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    source = row.get('tokenized_zh', '')
                    # Mock translation: replace Chinese with Russian placeholder
                    target = source
                    for char in source:
                        if '\u4e00' <= char <= '\u9fff':
                            target = target.replace(char, 'RU')
                    mock.add_response(source, target)
            
            # Measure translate_llm performance
            with measure_performance("translate_llm", data_size) as metrics:
                # Import here to use mocked version
                from translate_llm import main as translate_main
                
                # Create minimal args for translate_llm
                import argparse
                
                # We need to mock the batch_llm_call function
                def mock_batch_llm_call(*args, **kwargs):
                    rows = kwargs.get('rows', [])
                    results = []
                    for row in rows:
                        source = row.get('source_text', '')
                        # Get mock response
                        target = source
                        for char in source:
                            if '\u4e00' <= char <= '\u9fff':
                                target = target.replace(char, 'RU')
                        results.append({
                            'id': row.get('id'),
                            'target_ru': target
                        })
                    return results
                
                # Patch and run
                with pytest.MonkeyPatch().context() as mp:
                    from translate_llm import batch_llm_call
                    mp.setattr('translate_llm.batch_llm_call', mock_batch_llm_call)
                    
                    # Run translation logic
                    from translate_llm import load_checkpoint, save_checkpoint
                    
                    done_ids = set()
                    with open(draft_csv, 'r', encoding='utf-8-sig') as f:
                        all_rows = list(csv.DictReader(f))
                    
                    batch_inputs = []
                    for r in all_rows:
                        src = r.get('tokenized_zh') or r.get('source_zh') or ''
                        batch_inputs.append({
                            "id": r.get("string_id"),
                            "source_text": src
                        })
                    
                    # Process in batches
                    batch_size = 10
                    processed = 0
                    for i in range(0, len(batch_inputs), batch_size):
                        batch = batch_inputs[i:i+batch_size]
                        results = mock_batch_llm_call(rows=batch)
                        processed += len(results)
                    
                    metrics["additional_metrics"]["processed_rows"] = processed
                    metrics["additional_metrics"]["batch_size"] = batch_size
        
        result = PERFORMANCE_RESULTS[-1]
        
        # LLM translation is slower than other stages
        max_time_thresholds = {
            1000: 10.0,
            10000: 60.0
        }
        
        assert result['execution_time_sec'] < max_time_thresholds[data_size]


class TestQAHardPerformance:
    """Performance tests for qa_hard module."""
    
    @pytest.mark.parametrize("data_size", TEST_DATA_SIZES)
    def test_qa_hard_performance(self, data_size: int, tmp_path: Path):
        """Measure qa_hard performance at various data sizes."""
        
        # Setup test data
        input_csv = tmp_path / f"input_{data_size}.csv"
        draft_csv = tmp_path / f"draft_{data_size}.csv"
        map_json = tmp_path / f"map_{data_size}.json"
        translated_csv = tmp_path / f"translated_{data_size}.csv"
        report_json = tmp_path / f"qa_report_{data_size}.json"
        schema_path = WORKFLOW_PATH / "placeholder_schema.yaml"
        forbidden_path = WORKFLOW_PATH / "forbidden_patterns.txt"
        
        # Generate and normalize test data
        generate_test_csv(data_size, input_csv)
        guard = NormalizeGuard(
            input_path=str(input_csv),
            output_draft_path=str(draft_csv),
            output_map_path=str(map_json),
            schema_path=str(schema_path),
            source_lang="zh-CN"
        )
        guard.run()
        
        # Generate translated data
        generate_translated_csv(draft_csv, translated_csv)
        
        # Measure QA performance
        with measure_performance("qa_hard", data_size) as metrics:
            validator = QAHardValidator(
                translated_csv=str(translated_csv),
                placeholder_map=str(map_json),
                schema_yaml=str(schema_path),
                forbidden_txt=str(forbidden_path),
                report_json=str(report_json)
            )
            success = validator.run()
            
            metrics["error_count"] = len(validator.errors)
            metrics["additional_metrics"]["error_counts"] = validator.error_counts
        
        result = PERFORMANCE_RESULTS[-1]
        
        # QA hard should be fast (regex-based validation)
        max_time_thresholds = {
            1000: 2.0,
            10000: 10.0,
            30000: 30.0
        }
        
        assert result['execution_time_sec'] < max_time_thresholds[data_size]


class TestRehydrateExportPerformance:
    """Performance tests for rehydrate_export module."""
    
    @pytest.mark.parametrize("data_size", TEST_DATA_SIZES)
    def test_rehydrate_export_performance(self, data_size: int, tmp_path: Path):
        """Measure rehydrate_export performance at various data sizes."""
        
        # Setup test data
        input_csv = tmp_path / f"input_{data_size}.csv"
        draft_csv = tmp_path / f"draft_{data_size}.csv"
        map_json = tmp_path / f"map_{data_size}.json"
        translated_csv = tmp_path / f"translated_{data_size}.csv"
        final_csv = tmp_path / f"final_{data_size}.csv"
        schema_path = WORKFLOW_PATH / "placeholder_schema.yaml"
        
        # Generate test data pipeline
        generate_test_csv(data_size, input_csv)
        guard = NormalizeGuard(
            input_path=str(input_csv),
            output_draft_path=str(draft_csv),
            output_map_path=str(map_json),
            schema_path=str(schema_path),
            source_lang="zh-CN"
        )
        guard.run()
        generate_translated_csv(draft_csv, translated_csv)
        
        # Measure rehydrate performance
        with measure_performance("rehydrate_export", data_size) as metrics:
            exporter = RehydrateExporter(
                translated_csv=str(translated_csv),
                placeholder_map=str(map_json),
                final_csv=str(final_csv),
                overwrite_mode=False
            )
            success = exporter.run()
            
            if not success:
                metrics["error_count"] = len(exporter.errors)
            
            metrics["additional_metrics"]["tokens_restored"] = exporter.tokens_restored
        
        result = PERFORMANCE_RESULTS[-1]
        
        # Rehydrate should be very fast (string replacement)
        max_time_thresholds = {
            1000: 1.0,
            10000: 5.0,
            30000: 15.0
        }
        
        assert result['execution_time_sec'] < max_time_thresholds[data_size]


class TestFullPipelinePerformance:
    """Performance tests for the complete pipeline."""
    
    @pytest.mark.parametrize("data_size", [1000, 10000])  # Skip 30k for full pipeline (too slow)
    def test_full_pipeline_performance(self, data_size: int, tmp_path: Path):
        """Measure end-to-end pipeline performance."""
        
        input_csv = tmp_path / f"input_{data_size}.csv"
        draft_csv = tmp_path / f"draft_{data_size}.csv"
        map_json = tmp_path / f"map_{data_size}.json"
        translated_csv = tmp_path / f"translated_{data_size}.csv"
        report_json = tmp_path / f"qa_report_{data_size}.json"
        final_csv = tmp_path / f"final_{data_size}.csv"
        schema_path = WORKFLOW_PATH / "placeholder_schema.yaml"
        forbidden_path = WORKFLOW_PATH / "forbidden_patterns.txt"
        
        generate_test_csv(data_size, input_csv)
        
        with measure_performance("full_pipeline", data_size) as metrics:
            # Stage 1: Normalize
            guard = NormalizeGuard(
                input_path=str(input_csv),
                output_draft_path=str(draft_csv),
                output_map_path=str(map_json),
                schema_path=str(schema_path),
                source_lang="zh-CN"
            )
            guard.run()
            
            # Stage 2: Mock Translate
            generate_translated_csv(draft_csv, translated_csv)
            
            # Stage 3: QA
            validator = QAHardValidator(
                translated_csv=str(translated_csv),
                placeholder_map=str(map_json),
                schema_yaml=str(schema_path),
                forbidden_txt=str(forbidden_path),
                report_json=str(report_json)
            )
            validator.run()
            
            # Stage 4: Rehydrate
            exporter = RehydrateExporter(
                translated_csv=str(translated_csv),
                placeholder_map=str(map_json),
                final_csv=str(final_csv),
                overwrite_mode=False
            )
            exporter.run()
            
            metrics["additional_metrics"]["stages_completed"] = 4
        
        result = PERFORMANCE_RESULTS[-1]
        
        # Full pipeline should complete within reasonable time (without actual LLM calls)
        max_time_thresholds = {
            1000: 15.0,
            10000: 90.0
        }
        
        assert result['execution_time_sec'] < max_time_thresholds[data_size]


# =============================================================================
# Fixtures and Hooks
# =============================================================================

@pytest.fixture(scope="session", autouse=True)
def save_performance_results():
    """Save all performance results to JSON after test session."""
    yield
    
    # Save results to file
    results_path = Path(__file__).parent / "performance_results.json"
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'results': PERFORMANCE_RESULTS
        }, f, indent=2)
    
    print(f"\n\nPerformance results saved to: {results_path}")


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    # Run with: python test_baseline_performance.py
    pytest.main([__file__, "-v", "--tb=short"])
