#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_benchmark.py

Benchmark script to compare throughput before/after optimization.
Generates synthetic workloads and measures performance characteristics.
"""

import json
import os
import sys
import time
import statistics
from pathlib import Path
from typing import Dict, List, Any
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skill", "scripts"))

from batch_optimizer import (
    BatchConfig,
    BatchProcessor,
    BatchMetrics,
    estimate_tokens,
    group_similar_length_texts,
    calculate_dynamic_batch_size
)


def generate_synthetic_rows(count: int, min_len: int = 10, max_len: int = 200) -> List[Dict[str, Any]]:
    """Generate synthetic rows with varying text lengths."""
    import random
    rows = []
    for i in range(count):
        length = random.randint(min_len, max_len)
        text = "测" * length  # CJK text
        rows.append({
            "id": f"row_{i:05d}",
            "source_text": text
        })
    return rows


def mock_llm_call(*args, **kwargs):
    """Mock LLM call with realistic latency simulation."""
    import random
    # Simulate 100-300ms latency
    time.sleep(random.uniform(0.1, 0.3))
    
    # Extract items from user prompt
    user_prompt = kwargs.get('user', '')
    try:
        data = json.loads(user_prompt)
        items = data.get('items', [])
        response_items = [{"id": item["id"], "target_ru": "Перевод"} for item in items]
        
        mock_response = Mock()
        mock_response.text = json.dumps({"items": response_items})
        mock_response.request_id = "mock-req"
        mock_response.usage = {
            "prompt_tokens": len(items) * 50,
            "completion_tokens": len(items) * 20,
            "total_tokens": len(items) * 70
        }
        return mock_response
    except:
        mock_response = Mock()
        mock_response.text = json.dumps({"items": []})
        mock_response.request_id = "mock-req"
        mock_response.usage = None
        return mock_response


def benchmark_standard_batching(rows: List[Dict], batch_size: int = 25) -> Dict[str, Any]:
    """Simulate standard batching (before optimization)."""
    print(f"  [Standard] Processing {len(rows)} rows with fixed batch_size={batch_size}")
    
    start_time = time.time()
    total_tokens = 0
    batch_count = 0
    
    # Simulate standard batch processing
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i+batch_size]
        batch_count += 1
        
        # Simulate token estimation
        for row in batch:
            total_tokens += estimate_tokens(row["source_text"]) * 2  # Input + output
        
        # Simulate LLM call
        time.sleep(0.2)  # Fixed 200ms per batch
    
    elapsed = time.time() - start_time
    
    return {
        "mode": "standard",
        "total_rows": len(rows),
        "batch_count": batch_count,
        "elapsed_seconds": elapsed,
        "tokens_per_sec": total_tokens / elapsed,
        "texts_per_sec": len(rows) / elapsed,
        "total_tokens": total_tokens
    }


def benchmark_optimized_batching(rows: List[Dict], config: BatchConfig) -> Dict[str, Any]:
    """Benchmark optimized batching (after optimization)."""
    print(f"  [Optimized] Processing {len(rows)} rows with dynamic sizing, workers={config.max_workers}")
    
    system_prompt = "You are a translator."
    user_template = lambda items: json.dumps({"items": items})
    
    with patch('batch_optimizer.LLMClient') as mock_client_class:
        mock_client = Mock()
        mock_client.chat = mock_llm_call
        mock_client_class.return_value = mock_client
        
        processor = BatchProcessor(
            model="test-model",
            system_prompt=system_prompt,
            user_prompt_template=user_template,
            config=config,
            _client=mock_client
        )
        
        start_time = time.time()
        results = processor.process(rows)
        elapsed = time.time() - start_time
        
        return {
            "mode": "optimized",
            "total_rows": len(rows),
            "batch_count": processor.metrics.batch_count,
            "elapsed_seconds": elapsed,
            "tokens_per_sec": processor.metrics.tokens_per_sec,
            "texts_per_sec": processor.metrics.texts_per_sec,
            "total_tokens": processor.metrics.total_tokens
        }


def run_benchmark_suite():
    """Run complete benchmark suite."""
    print("="*60)
    print("BATCH PROCESSING OPTIMIZATION BENCHMARK")
    print("="*60)
    
    results = []
    
    # Test configurations
    configs = [
        (100, 10, 50, "Small texts"),
        (100, 50, 200, "Medium texts"),
        (100, 100, 500, "Large texts"),
        (200, 10, 100, "High volume"),
    ]
    
    for count, min_len, max_len, description in configs:
        print(f"\n📊 Configuration: {description}")
        print(f"   Rows: {count}, Length range: {min_len}-{max_len}")
        
        rows = generate_synthetic_rows(count, min_len, max_len)
        
        # Standard batching (baseline)
        standard_result = benchmark_standard_batching(rows, batch_size=25)
        
        # Optimized batching
        config = BatchConfig(
            dynamic_sizing=True,
            max_workers=4,
            grouping_enabled=True
        )
        optimized_result = benchmark_optimized_batching(rows, config)
        
        # Calculate improvement
        throughput_improvement = (
            (optimized_result["texts_per_sec"] - standard_result["texts_per_sec"]) /
            standard_result["texts_per_sec"] * 100
        )
        
        time_improvement = (
            (standard_result["elapsed_seconds"] - optimized_result["elapsed_seconds"]) /
            standard_result["elapsed_seconds"] * 100
        )
        
        result = {
            "description": description,
            "row_count": count,
            "length_range": f"{min_len}-{max_len}",
            "standard": standard_result,
            "optimized": optimized_result,
            "improvement": {
                "throughput_pct": round(throughput_improvement, 1),
                "time_reduction_pct": round(time_improvement, 1)
            }
        }
        results.append(result)
        
        print(f"   Standard:  {standard_result['texts_per_sec']:.2f} texts/sec ({standard_result['elapsed_seconds']:.2f}s)")
        print(f"   Optimized: {optimized_result['texts_per_sec']:.2f} texts/sec ({optimized_result['elapsed_seconds']:.2f}s)")
        print(f"   Improvement: {throughput_improvement:+.1f}% throughput, {time_improvement:+.1f}% time reduction")
    
    # Calculate average improvement
    avg_throughput_improvement = statistics.mean([r["improvement"]["throughput_pct"] for r in results])
    avg_time_improvement = statistics.mean([r["improvement"]["time_reduction_pct"] for r in results])
    
    print("\n" + "="*60)
    print("BENCHMARK SUMMARY")
    print("="*60)
    print(f"Average throughput improvement: {avg_throughput_improvement:+.1f}%")
    print(f"Average time reduction: {avg_time_improvement:+.1f}%")
    
    # Save results
    report = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": {
            "avg_throughput_improvement_pct": round(avg_throughput_improvement, 1),
            "avg_time_reduction_pct": round(avg_time_improvement, 1),
            "target_achieved": avg_throughput_improvement >= 50
        },
        "results": results
    }
    
    os.makedirs("reports", exist_ok=True)
    with open("reports/batch_benchmark_results.json", "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed results saved to: reports/batch_benchmark_results.json")
    
    return report


if __name__ == "__main__":
    report = run_benchmark_suite()
    
    # Exit with appropriate code
    if report["summary"]["target_achieved"]:
        print("\n✅ Target achieved: 50%+ throughput improvement")
        sys.exit(0)
    else:
        print("\n⚠️  Target not fully achieved")
        sys.exit(1)
