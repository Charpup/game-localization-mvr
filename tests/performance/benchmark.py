#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark.py - Performance Benchmark Automation Script

This script provides standalone benchmarking for all pipeline modules:
- normalize_guard: Placeholder freezing and tokenization
- translate_llm: LLM-based translation (with mock)
- qa_hard: Hard rule validation
- rehydrate_export: Token restoration and export

Usage:
    # Run all benchmarks
    python benchmark.py --all
    
    # Run specific module benchmarks
    python benchmark.py --module normalize_guard
    python benchmark.py --module translate_llm
    python benchmark.py --module qa_hard
    python benchmark.py --module rehydrate_export
    
    # Specify data sizes
    python benchmark.py --all --sizes 1000,10000,30000
    
    # Save results to file
    python benchmark.py --all --output benchmark_results.json
    
    # Compare with previous results
    python benchmark.py --all --compare previous_results.json

Output Format:
    JSON with metrics: time, memory, throughput, error rates
"""

import argparse
import csv
import json
import time
import gc
import sys
import os
from pathlib import Path
from typing import List, Dict, Optional, Callable, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
import psutil

# Add project paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent))

from normalize_guard import NormalizeGuard
from qa_hard import QAHardValidator
from rehydrate_export import RehydrateExporter

# =============================================================================
# Configuration
# =============================================================================

DEFAULT_SIZES = [1000, 10000, 30000]
WORKFLOW_PATH = Path(__file__).parent.parent.parent / "workflow"

BENCHMARK_TEMPLATES = [
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


@dataclass
class BenchmarkResult:
    """Container for benchmark results."""
    module: str
    data_size: int
    execution_time_sec: float
    peak_memory_mb: float
    throughput_rows_per_sec: float
    error_count: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    additional_metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return asdict(self)


class PerformanceTimer:
    """Context manager for timing code execution."""
    
    def __init__(self):
        self.start_time = None
        self.end_time = None
        self.peak_memory = 0
        self.process = psutil.Process()
    
    def __enter__(self):
        gc.collect()
        self.start_memory = self.process.memory_info().rss / 1024 / 1024
        self.start_time = time.perf_counter()
        return self
    
    def __exit__(self, *args):
        self.end_time = time.perf_counter()
        end_memory = self.process.memory_info().rss / 1024 / 1024
        self.peak_memory = max(end_memory, self.start_memory)
    
    @property
    def elapsed(self) -> float:
        return self.end_time - self.start_time if self.end_time else 0


# =============================================================================
# Data Generation
# =============================================================================

def generate_test_csv(rows: int, output_path: Path, seed: int = 42) -> Path:
    """Generate a test CSV with specified number of rows."""
    
    fieldnames = [
        'string_id', 'source_zh', 'module_tag', 'module_confidence',
        'max_len_target', 'len_tier', 'source_locale', 'placeholder_flags',
        'status', 'is_empty_source', 'is_long_text'
    ]
    
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for i in range(rows):
            template = BENCHMARK_TEMPLATES[i % len(BENCHMARK_TEMPLATES)]
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


def generate_translated_csv(input_path: Path, output_path: Path) -> Path:
    """Generate a translated CSV based on input draft."""
    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames + ['target_text']
    
    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in rows:
            source = row.get('tokenized_zh', row.get('source_zh', ''))
            target = source
            for char in source:
                if '\u4e00' <= char <= '\u9fff':
                    target = target.replace(char, 'RU')
            
            row['target_text'] = target
            writer.writerow(row)
    
    return output_path


# =============================================================================
# Benchmark Functions
# =============================================================================

def benchmark_normalize_guard(data_size: int, tmp_dir: Path) -> BenchmarkResult:
    """Benchmark normalize_guard module."""
    
    print(f"  [normalize_guard] Testing with {data_size} rows...")
    
    input_csv = tmp_dir / f"input_{data_size}.csv"
    output_draft = tmp_dir / f"draft_{data_size}.csv"
    output_map = tmp_dir / f"map_{data_size}.json"
    schema_path = WORKFLOW_PATH / "placeholder_schema.yaml"
    
    generate_test_csv(data_size, input_csv)
    
    timer = PerformanceTimer()
    with timer:
        guard = NormalizeGuard(
            input_path=str(input_csv),
            output_draft_path=str(output_draft),
            output_map_path=str(output_map),
            schema_path=str(schema_path),
            source_lang="zh-CN"
        )
        success = guard.run()
    
    return BenchmarkResult(
        module="normalize_guard",
        data_size=data_size,
        execution_time_sec=round(timer.elapsed, 3),
        peak_memory_mb=round(timer.peak_memory, 2),
        throughput_rows_per_sec=round(data_size / timer.elapsed, 2) if timer.elapsed > 0 else 0,
        error_count=len(guard.errors),
        additional_metrics={
            "placeholders_frozen": len(guard.freezer.placeholder_map),
            "sanity_errors": len(guard.sanity_errors),
            "success": success
        }
    )


def benchmark_translate_llm(data_size: int, tmp_dir: Path) -> BenchmarkResult:
    """Benchmark translate_llm module (with mock LLM)."""
    
    print(f"  [translate_llm] Testing with {data_size} rows (mock LLM)...")
    
    # Setup prerequisites
    input_csv = tmp_dir / f"input_{data_size}.csv"
    draft_csv = tmp_dir / f"draft_{data_size}.csv"
    map_json = tmp_dir / f"map_{data_size}.json"
    output_csv = tmp_dir / f"translated_{data_size}.csv"
    schema_path = WORKFLOW_PATH / "placeholder_schema.yaml"
    
    generate_test_csv(data_size, input_csv)
    
    # Run normalize first
    guard = NormalizeGuard(
        input_path=str(input_csv),
        output_draft_path=str(draft_csv),
        output_map_path=str(map_json),
        schema_path=str(schema_path),
        source_lang="zh-CN"
    )
    guard.run()
    
    # Mock translation (simulating batch processing)
    timer = PerformanceTimer()
    with timer:
        with open(draft_csv, 'r', encoding='utf-8-sig') as f:
            rows = list(csv.DictReader(f))
        
        # Simulate batch processing
        batch_size = 10
        processed = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i+batch_size]
            # Simulate processing time per batch
            time.sleep(0.001)  # 1ms per batch
            processed += len(batch)
        
        # Generate output
        generate_translated_csv(draft_csv, output_csv)
    
    return BenchmarkResult(
        module="translate_llm",
        data_size=data_size,
        execution_time_sec=round(timer.elapsed, 3),
        peak_memory_mb=round(timer.peak_memory, 2),
        throughput_rows_per_sec=round(data_size / timer.elapsed, 2) if timer.elapsed > 0 else 0,
        additional_metrics={
            "batch_size": batch_size,
            "note": "Mock LLM - actual LLM would be 100-1000x slower"
        }
    )


def benchmark_qa_hard(data_size: int, tmp_dir: Path) -> BenchmarkResult:
    """Benchmark qa_hard module."""
    
    print(f"  [qa_hard] Testing with {data_size} rows...")
    
    # Setup prerequisites
    input_csv = tmp_dir / f"input_{data_size}.csv"
    draft_csv = tmp_dir / f"draft_{data_size}.csv"
    map_json = tmp_dir / f"map_{data_size}.json"
    translated_csv = tmp_dir / f"translated_{data_size}.csv"
    report_json = tmp_dir / f"qa_report_{data_size}.json"
    schema_path = WORKFLOW_PATH / "placeholder_schema.yaml"
    forbidden_path = WORKFLOW_PATH / "forbidden_patterns.txt"
    
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
    
    # Benchmark QA
    timer = PerformanceTimer()
    with timer:
        validator = QAHardValidator(
            translated_csv=str(translated_csv),
            placeholder_map=str(map_json),
            schema_yaml=str(schema_path),
            forbidden_txt=str(forbidden_path),
            report_json=str(report_json)
        )
        success = validator.run()
    
    return BenchmarkResult(
        module="qa_hard",
        data_size=data_size,
        execution_time_sec=round(timer.elapsed, 3),
        peak_memory_mb=round(timer.peak_memory, 2),
        throughput_rows_per_sec=round(data_size / timer.elapsed, 2) if timer.elapsed > 0 else 0,
        error_count=len(validator.errors),
        additional_metrics={
            "error_counts": validator.error_counts
        }
    )


def benchmark_rehydrate_export(data_size: int, tmp_dir: Path) -> BenchmarkResult:
    """Benchmark rehydrate_export module."""
    
    print(f"  [rehydrate_export] Testing with {data_size} rows...")
    
    # Setup prerequisites
    input_csv = tmp_dir / f"input_{data_size}.csv"
    draft_csv = tmp_dir / f"draft_{data_size}.csv"
    map_json = tmp_dir / f"map_{data_size}.json"
    translated_csv = tmp_dir / f"translated_{data_size}.csv"
    final_csv = tmp_dir / f"final_{data_size}.csv"
    schema_path = WORKFLOW_PATH / "placeholder_schema.yaml"
    
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
    
    # Benchmark rehydrate
    timer = PerformanceTimer()
    with timer:
        exporter = RehydrateExporter(
            translated_csv=str(translated_csv),
            placeholder_map=str(map_json),
            final_csv=str(final_csv),
            overwrite_mode=False
        )
        success = exporter.run()
    
    return BenchmarkResult(
        module="rehydrate_export",
        data_size=data_size,
        execution_time_sec=round(timer.elapsed, 3),
        peak_memory_mb=round(timer.peak_memory, 2),
        throughput_rows_per_sec=round(data_size / timer.elapsed, 2) if timer.elapsed > 0 else 0,
        error_count=len(exporter.errors),
        additional_metrics={
            "tokens_restored": exporter.tokens_restored,
            "punctuation_converted": exporter.punctuation_converted
        }
    )


# =============================================================================
# Reporting
# =============================================================================

def print_results(results: List[BenchmarkResult]):
    """Print benchmark results in a formatted table."""
    
    print("\n" + "="*100)
    print("BENCHMARK RESULTS")
    print("="*100)
    
    # Group by module
    modules = {}
    for r in results:
        if r.module not in modules:
            modules[r.module] = []
        modules[r.module].append(r)
    
    for module, module_results in sorted(modules.items()):
        print(f"\n{module.upper()}:")
        print("-" * 100)
        print(f"{'Size':>10} {'Time (s)':>12} {'Memory (MB)':>14} {'Throughput':>14} {'Errors':>10}")
        print("-" * 100)
        
        for r in sorted(module_results, key=lambda x: x.data_size):
            print(f"{r.data_size:>10,} {r.execution_time_sec:>12.3f} {r.peak_memory_mb:>14.2f} "
                  f"{r.throughput_rows_per_sec:>13.2f}x {r.error_count:>10}")
    
    print("\n" + "="*100)


def save_results(results: List[BenchmarkResult], output_path: Path):
    """Save results to JSON file."""
    
    data = {
        "timestamp": datetime.now().isoformat(),
        "system_info": {
            "python_version": sys.version,
            "platform": sys.platform,
            "cpu_count": psutil.cpu_count(),
            "memory_total_gb": round(psutil.virtual_memory().total / 1024**3, 2)
        },
        "results": [r.to_dict() for r in results]
    }
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    
    print(f"\nResults saved to: {output_path}")


def compare_results(current: List[BenchmarkResult], previous_path: Path):
    """Compare current results with previous benchmark."""
    
    with open(previous_path, 'r', encoding='utf-8') as f:
        previous_data = json.load(f)
    
    previous_results = {f"{r['module']}_{r['data_size']}": r for r in previous_data['results']}
    
    print("\n" + "="*100)
    print("COMPARISON WITH PREVIOUS RUN")
    print("="*100)
    print(f"{'Module':<20} {'Size':>10} {'Time Δ':>12} {'Throughput Δ':>14} {'Status':>10}")
    print("-" * 100)
    
    for r in current:
        key = f"{r.module}_{r.data_size}"
        if key in previous_results:
            prev = previous_results[key]
            time_delta = r.execution_time_sec - prev['execution_time_sec']
            throughput_delta = r.throughput_rows_per_sec - prev['throughput_rows_per_sec']
            
            # Determine status
            time_pct = (time_delta / prev['execution_time_sec']) * 100 if prev['execution_time_sec'] > 0 else 0
            if time_pct > 10:
                status = "⚠️ REGRESSION"
            elif time_pct < -10:
                status = "✅ IMPROVED"
            else:
                status = "✓ STABLE"
            
            print(f"{r.module:<20} {r.data_size:>10,} {time_delta:>+11.3f}s "
                  f"{throughput_delta:>+13.2f}x {status:>10}")
        else:
            print(f"{r.module:<20} {r.data_size:>10,} {'N/A':>12} {'N/A':>14} {'NEW':>10}")
    
    print("="*100)


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Performance Benchmark for Game Localization MVR",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python benchmark.py --all
    python benchmark.py --module normalize_guard --sizes 1000,10000
    python benchmark.py --all --output results.json
    python benchmark.py --all --compare previous_results.json
        """
    )
    
    parser.add_argument('--all', action='store_true',
                        help='Run all module benchmarks')
    parser.add_argument('--module', choices=['normalize_guard', 'translate_llm', 'qa_hard', 'rehydrate_export'],
                        help='Run specific module benchmark')
    parser.add_argument('--sizes', type=str, default=','.join(map(str, DEFAULT_SIZES)),
                        help=f'Comma-separated data sizes (default: {",".join(map(str, DEFAULT_SIZES))})')
    parser.add_argument('--output', type=str,
                        help='Save results to JSON file')
    parser.add_argument('--compare', type=str,
                        help='Compare with previous results file')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Verbose output')
    
    args = parser.parse_args()
    
    if not args.all and not args.module:
        parser.error("Must specify --all or --module")
    
    # Parse sizes
    sizes = [int(s.strip()) for s in args.sizes.split(',')]
    
    # Create temp directory
    import tempfile
    tmp_dir = Path(tempfile.mkdtemp(prefix="benchmark_"))
    
    try:
        print(f"Benchmark started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Temp directory: {tmp_dir}")
        print(f"Data sizes: {sizes}")
        print()
        
        results = []
        
        # Determine modules to benchmark
        modules_to_run = []
        if args.all:
            modules_to_run = ['normalize_guard', 'translate_llm', 'qa_hard', 'rehydrate_export']
        else:
            modules_to_run = [args.module]
        
        # Run benchmarks
        for module in modules_to_run:
            print(f"\nBenchmarking {module}...")
            for size in sizes:
                if module == 'translate_llm' and size > 10000:
                    print(f"  Skipping {size} rows for translate_llm (too slow even with mocks)")
                    continue
                
                try:
                    if module == 'normalize_guard':
                        result = benchmark_normalize_guard(size, tmp_dir)
                    elif module == 'translate_llm':
                        result = benchmark_translate_llm(size, tmp_dir)
                    elif module == 'qa_hard':
                        result = benchmark_qa_hard(size, tmp_dir)
                    elif module == 'rehydrate_export':
                        result = benchmark_rehydrate_export(size, tmp_dir)
                    
                    results.append(result)
                    
                    if args.verbose:
                        print(f"    Time: {result.execution_time_sec:.3f}s, "
                              f"Throughput: {result.throughput_rows_per_sec:.2f} rows/sec")
                
                except Exception as e:
                    print(f"  ERROR: {e}")
                    import traceback
                    traceback.print_exc()
        
        # Print results
        print_results(results)
        
        # Save results
        if args.output:
            save_results(results, Path(args.output))
        
        # Compare with previous
        if args.compare:
            compare_results(results, Path(args.compare))
        
        print(f"\nBenchmark completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
        if args.verbose:
            print(f"Cleaned up temp directory: {tmp_dir}")


if __name__ == "__main__":
    main()
