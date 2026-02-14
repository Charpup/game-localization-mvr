#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_batch_optimization.py

Comprehensive test suite for batch optimization module.
Tests dynamic batch sizing, parallel processing, token optimization, and metrics.

Run with: python -m pytest tests/test_batch_optimization.py -v
"""

import json
import os
import sys
import time
import threading
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import pytest

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "skill", "scripts"))

from batch_optimizer import (
    BatchConfig,
    BatchMetrics,
    BatchProcessor,
    estimate_tokens,
    estimate_batch_tokens,
    calculate_dynamic_batch_size,
    group_similar_length_texts,
    optimized_batch_call,
    CHARS_PER_TOKEN
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    tmp = tempfile.mkdtemp()
    yield tmp
    shutil.rmtree(tmp)


@pytest.fixture
def sample_rows():
    """Create sample rows for testing."""
    return [
        {"id": f"row_{i}", "source_text": f"测试文本{i}" * 10}
        for i in range(100)
    ]


@pytest.fixture
def mock_config():
    """Create a mock batch configuration."""
    return BatchConfig(
        dynamic_sizing=True,
        target_batch_time_ms=30000,
        max_workers=4,
        token_buffer=500,
        model_context_windows={
            "test-model": 128000,
            "small-model": 4000
        },
        latency_model={
            "test-model": 0.5,
            "fast-model": 0.2
        }
    )


@pytest.fixture
def mock_system_prompt():
    """Create a mock system prompt."""
    return "You are a helpful translator."


@pytest.fixture
def mock_user_prompt_template():
    """Create a mock user prompt template."""
    def template(items):
        return json.dumps({"items": items}, ensure_ascii=False)
    return template


# =============================================================================
# Test BatchConfig
# =============================================================================

class TestBatchConfig:
    """Tests for BatchConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = BatchConfig()
        assert config.dynamic_sizing is True
        assert config.target_batch_time_ms == 30000
        assert config.max_workers == 4
        assert config.token_buffer == 500
        assert config.preserve_order is True
        assert config.fail_fast is False
    
    def test_config_from_yaml_not_found(self):
        """Test loading config when YAML file doesn't exist."""
        config = BatchConfig.from_yaml("nonexistent.yaml")
        assert config.dynamic_sizing is True  # Should use defaults
    
    def test_config_custom_values(self):
        """Test custom configuration values."""
        config = BatchConfig(
            dynamic_sizing=False,
            max_workers=8,
            token_buffer=1000
        )
        assert config.dynamic_sizing is False
        assert config.max_workers == 8
        assert config.token_buffer == 1000


# =============================================================================
# Test BatchMetrics
# =============================================================================

class TestBatchMetrics:
    """Tests for BatchMetrics class."""
    
    def test_initial_state(self):
        """Test initial metrics state."""
        metrics = BatchMetrics()
        assert metrics.total_tokens == 0
        assert metrics.total_texts == 0
        assert metrics.processed_texts == 0
        assert metrics.tokens_per_sec == 0.0
        assert metrics.texts_per_sec == 0.0
    
    def test_update_throughput(self):
        """Test throughput calculation."""
        metrics = BatchMetrics()
        metrics.total_tokens = 1000
        metrics.processed_texts = 100
        time.sleep(0.1)  # Small delay
        metrics.update_throughput()
        
        assert metrics.tokens_per_sec > 0
        assert metrics.texts_per_sec > 0
    
    def test_calculate_eta(self):
        """Test ETA calculation."""
        metrics = BatchMetrics()
        metrics.texts_per_sec = 10.0
        eta = metrics.calculate_eta(remaining_texts=100)
        assert eta == 10.0  # 100 texts / 10 texts/sec
    
    def test_calculate_eta_zero_throughput(self):
        """Test ETA calculation with zero throughput."""
        metrics = BatchMetrics()
        metrics.texts_per_sec = 0.0
        eta = metrics.calculate_eta(remaining_texts=100)
        assert eta is None
    
    def test_to_dict(self):
        """Test metrics export to dictionary."""
        metrics = BatchMetrics()
        metrics.total_tokens = 1000
        metrics.total_texts = 100
        metrics.processed_texts = 50
        metrics.batch_count = 5
        
        data = metrics.to_dict()
        assert "timestamp" in data
        assert data["total_tokens"] == 1000
        assert data["total_texts"] == 100
        assert data["processed_texts"] == 50
        assert data["batch_count"] == 5
        assert "tokens_per_sec" in data
        assert "texts_per_sec" in data


# =============================================================================
# Test Token Estimation
# =============================================================================

class TestTokenEstimation:
    """Tests for token estimation functions."""
    
    def test_estimate_tokens_empty(self):
        """Test token estimation for empty string."""
        assert estimate_tokens("") == 1  # Minimum 1 token
    
    def test_estimate_tokens_cjk(self):
        """Test token estimation for CJK text."""
        text = "测试文本" * 10  # 40 chars
        expected = max(1, 40 // CHARS_PER_TOKEN)
        assert estimate_tokens(text) == expected
    
    def test_estimate_tokens_mixed(self):
        """Test token estimation for mixed text."""
        text = "Hello 世界" * 10  # 80 chars (40 latin + 40 CJK)
        expected = max(1, 80 // CHARS_PER_TOKEN)
        assert estimate_tokens(text) == expected
    
    def test_estimate_batch_tokens(self):
        """Test batch token estimation."""
        rows = [
            {"id": "1", "source_text": "测试" * 20},  # 40 chars
            {"id": "2", "source_text": "文本" * 20},  # 40 chars
        ]
        system_prompt = "Translate" * 10  # 90 chars
        
        tokens = estimate_batch_tokens(rows, system_prompt)
        assert tokens > 0
        # Should include system prompt + text content + JSON overhead
        assert tokens >= estimate_tokens(system_prompt)


# =============================================================================
# Test Dynamic Batch Sizing
# =============================================================================

class TestDynamicBatchSizing:
    """Tests for dynamic batch sizing functionality."""
    
    def test_calculate_dynamic_batch_size_basic(self, mock_config):
        """Test basic dynamic batch size calculation."""
        size = calculate_dynamic_batch_size(
            model="test-model",
            avg_text_length=100,
            config=mock_config,
            historical_latency_ms=None
        )
        assert size >= 1
        assert size <= 100
    
    def test_calculate_dynamic_batch_size_with_latency(self, mock_config):
        """Test dynamic batch size with historical latency."""
        size = calculate_dynamic_batch_size(
            model="test-model",
            avg_text_length=100,
            config=mock_config,
            historical_latency_ms=0.5
        )
        assert size >= 1
    
    def test_calculate_dynamic_batch_size_small_context(self, mock_config):
        """Test batch size with small context window."""
        size = calculate_dynamic_batch_size(
            model="small-model",
            avg_text_length=1000,
            config=mock_config,
            historical_latency_ms=None
        )
        # Should be limited by context window
        assert size >= 1
    
    def test_calculate_dynamic_batch_size_fast_latency(self, mock_config):
        """Test batch size with fast latency model."""
        size_fast = calculate_dynamic_batch_size(
            model="fast-model",
            avg_text_length=100,
            config=mock_config,
            historical_latency_ms=0.2
        )
        size_slow = calculate_dynamic_batch_size(
            model="test-model",
            avg_text_length=100,
            config=mock_config,
            historical_latency_ms=1.0
        )
        # Fast latency should allow larger batches
        assert size_fast >= size_slow


# =============================================================================
# Test Text Grouping
# =============================================================================

class TestTextGrouping:
    """Tests for text grouping optimization."""
    
    def test_group_similar_length_empty(self):
        """Test grouping with empty list."""
        groups = group_similar_length_texts([], max_variance=100)
        assert groups == []
    
    def test_group_similar_length_single(self):
        """Test grouping with single item."""
        rows = [{"id": "1", "source_text": "short"}]
        groups = group_similar_length_texts(rows, max_variance=100)
        assert len(groups) == 1
        assert len(groups[0]) == 1
    
    def test_group_similar_length_similar(self):
        """Test grouping similar length texts."""
        rows = [
            {"id": "1", "source_text": "a" * 50},
            {"id": "2", "source_text": "b" * 55},  # Similar length
            {"id": "3", "source_text": "c" * 60},  # Similar length
        ]
        groups = group_similar_length_texts(rows, max_variance=100)
        # All should be in one group
        assert len(groups) == 1
        assert len(groups[0]) == 3
    
    def test_group_similar_length_different(self):
        """Test grouping different length texts."""
        rows = [
            {"id": "1", "source_text": "a" * 50},
            {"id": "2", "source_text": "b" * 200},  # Different length
            {"id": "3", "source_text": "c" * 300},  # Different length
        ]
        groups = group_similar_length_texts(rows, max_variance=50)
        # Should be split into groups
        assert len(groups) >= 2
    
    def test_group_preserves_order_within_group(self):
        """Test that order is preserved within groups."""
        rows = [
            {"id": "1", "source_text": "a" * 50},
            {"id": "2", "source_text": "b" * 55},
            {"id": "3", "source_text": "c" * 60},
        ]
        groups = group_similar_length_texts(rows, max_variance=100)
        # Order within group should be preserved
        assert groups[0][0]["id"] == "1"
        assert groups[0][1]["id"] == "2"
        assert groups[0][2]["id"] == "3"


# =============================================================================
# Test BatchProcessor
# =============================================================================

class TestBatchProcessor:
    """Tests for BatchProcessor class."""
    
    def test_processor_initialization(self, mock_config, mock_system_prompt, mock_user_prompt_template):
        """Test processor initialization."""
        processor = BatchProcessor(
            model="test-model",
            system_prompt=mock_system_prompt,
            user_prompt_template=mock_user_prompt_template,
            config=mock_config
        )
        assert processor.model == "test-model"
        assert processor.config == mock_config
        assert processor.metrics.total_texts == 0
    
    def test_calculate_batch_size_with_dynamic_sizing(self, mock_config, mock_system_prompt, mock_user_prompt_template):
        """Test batch size calculation with dynamic sizing enabled."""
        processor = BatchProcessor(
            model="test-model",
            system_prompt=mock_system_prompt,
            user_prompt_template=mock_user_prompt_template,
            config=mock_config
        )
        
        rows = [{"id": f"{i}", "source_text": "测试" * 50} for i in range(10)]
        size = processor._calculate_batch_size(rows)
        assert size >= 1
    
    def test_calculate_batch_size_without_dynamic_sizing(self, mock_config, mock_system_prompt, mock_user_prompt_template):
        """Test batch size calculation with dynamic sizing disabled."""
        mock_config.dynamic_sizing = False
        processor = BatchProcessor(
            model="test-model",
            system_prompt=mock_system_prompt,
            user_prompt_template=mock_user_prompt_template,
            config=mock_config
        )
        
        rows = [{"id": f"{i}", "source_text": "测试" * 50} for i in range(10)]
        size = processor._calculate_batch_size(rows)
        assert size >= 1
    
    def test_update_latency_history(self, mock_config, mock_system_prompt, mock_user_prompt_template):
        """Test latency history updates."""
        processor = BatchProcessor(
            model="test-model",
            system_prompt=mock_system_prompt,
            user_prompt_template=mock_user_prompt_template,
            config=mock_config
        )
        
        processor._update_latency_history(1000, 100)  # 1000ms for 100 tokens
        assert len(processor.latency_history["test-model"]) == 1
        
        # Add more measurements
        for _ in range(105):
            processor._update_latency_history(1000, 100)
        
        # Should keep only last 100
        assert len(processor.latency_history["test-model"]) == 100
    
    def test_get_historical_latency(self, mock_config, mock_system_prompt, mock_user_prompt_template):
        """Test historical latency retrieval."""
        processor = BatchProcessor(
            model="test-model",
            system_prompt=mock_system_prompt,
            user_prompt_template=mock_user_prompt_template,
            config=mock_config
        )
        
        # No history yet
        assert processor._get_historical_latency() is None
        
        # Add some history
        processor._update_latency_history(1000, 100)
        processor._update_latency_history(2000, 100)
        
        latency = processor._get_historical_latency()
        assert latency is not None
        assert latency > 0
    
    @patch('batch_optimizer.LLMClient')
    def test_process_single_batch_success(self, mock_client_class, mock_config, mock_system_prompt, mock_user_prompt_template):
        """Test successful single batch processing."""
        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps({"items": [{"id": "1", "target_ru": "翻译"}]})
        mock_response.request_id = "test-req-1"
        mock_response.usage = None
        mock_client.chat.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        processor = BatchProcessor(
            model="test-model",
            system_prompt=mock_system_prompt,
            user_prompt_template=mock_user_prompt_template,
            config=mock_config
        )
        
        batch_rows = [{"id": "1", "source_text": "测试"}]
        idx, items, error = processor._process_single_batch(batch_rows, 0)
        
        assert error is None
        assert len(items) == 1
        assert items[0]["id"] == "1"
    
    @patch('batch_optimizer.LLMClient')
    def test_process_single_batch_failure(self, mock_client_class, mock_config, mock_system_prompt, mock_user_prompt_template):
        """Test failed single batch processing."""
        # Setup mock to raise exception
        mock_client = MagicMock()
        mock_client.chat.side_effect = Exception("API Error")
        mock_client_class.return_value = mock_client
        
        processor = BatchProcessor(
            model="test-model",
            system_prompt=mock_system_prompt,
            user_prompt_template=mock_user_prompt_template,
            config=mock_config,
            retry=0  # No retry for faster test
        )
        
        batch_rows = [{"id": "1", "source_text": "测试"}]
        idx, items, error = processor._process_single_batch(batch_rows, 0)
        
        assert error is not None
        assert len(items) == 0


# =============================================================================
# Test Integration
# =============================================================================

class TestIntegration:
    """Integration tests for the full optimization pipeline."""
    
    @patch('batch_optimizer.BatchProcessor._process_single_batch')
    def test_process_empty_rows(self, mock_process, mock_config, mock_system_prompt, mock_user_prompt_template):
        """Test processing empty row list."""
        processor = BatchProcessor(
            model="test-model",
            system_prompt=mock_system_prompt,
            user_prompt_template=mock_user_prompt_template,
            config=mock_config
        )
        
        results = processor.process([])
        assert results == []
        mock_process.assert_not_called()
    
    @patch('batch_optimizer.LLMClient')
    def test_metrics_export(self, mock_client_class, temp_dir, mock_system_prompt, mock_user_prompt_template):
        """Test metrics export functionality."""
        # Setup mock
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "items": [{"id": f"{i}", "target_ru": f"翻译{i}"} for i in range(5)]
        })
        mock_response.request_id = "test-req"
        mock_response.usage = None
        mock_client.chat.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        config = BatchConfig(
            dynamic_sizing=False,
            max_workers=1,
            metrics_enabled=True,
            metrics_export_path=os.path.join(temp_dir, "metrics.jsonl")
        )
        
        processor = BatchProcessor(
            model="test-model",
            system_prompt=mock_system_prompt,
            user_prompt_template=mock_user_prompt_template,
            config=config
        )
        
        rows = [{"id": f"{i}", "source_text": f"测试{i}"} for i in range(5)]
        results = processor.process(rows)
        
        # Check metrics file was created
        assert os.path.exists(config.metrics_export_path)
        with open(config.metrics_export_path, 'r') as f:
            metrics_data = json.loads(f.readline())
            assert "total_texts" in metrics_data
            assert "tokens_per_sec" in metrics_data
    
    def test_parallel_processing_configuration(self, mock_system_prompt, mock_user_prompt_template):
        """Test parallel processing with multiple workers."""
        config = BatchConfig(
            dynamic_sizing=False,
            max_workers=4,
            preserve_order=True
        )
        
        processor = BatchProcessor(
            model="test-model",
            system_prompt=mock_system_prompt,
            user_prompt_template=mock_user_prompt_template,
            config=config
        )
        
        assert processor.config.max_workers == 4
        assert processor.config.preserve_order is True
    
    def test_glossary_precomputation(self, mock_config, mock_system_prompt, mock_user_prompt_template):
        """Test pre-computed glossary context."""
        processor = BatchProcessor(
            model="test-model",
            system_prompt=mock_system_prompt,
            user_prompt_template=mock_user_prompt_template,
            config=mock_config
        )
        
        glossary = "- 测试 → тест\n- 文本 → текст"
        processor.glossary_context = glossary
        
        assert processor.glossary_context == glossary


# =============================================================================
# Test Performance Characteristics
# =============================================================================

class TestPerformance:
    """Tests for performance characteristics."""
    
    def test_token_estimation_performance(self):
        """Test token estimation performance with large texts."""
        large_text = "测试文本" * 10000  # 40000 chars
        
        start = time.time()
        for _ in range(1000):
            estimate_tokens(large_text)
        elapsed = time.time() - start
        
        # Should be very fast (less than 1 second for 1000 iterations)
        assert elapsed < 1.0
    
    def test_grouping_performance(self):
        """Test text grouping performance with many rows."""
        rows = [
            {"id": f"{i}", "source_text": f"文本{i}" * (i % 10 + 1)}
            for i in range(1000)
        ]
        
        start = time.time()
        groups = group_similar_length_texts(rows, max_variance=100)
        elapsed = time.time() - start
        
        # Should be fast (less than 1 second for 1000 rows)
        assert elapsed < 1.0
        assert len(groups) > 0
    
    def test_metrics_thread_safety(self):
        """Test metrics thread safety."""
        metrics = BatchMetrics()
        errors = []
        
        def update_metrics():
            try:
                for _ in range(100):
                    with metrics.metrics_lock:
                        metrics.total_tokens += 10
                        metrics.processed_texts += 1
            except Exception as e:
                errors.append(e)
        
        # Start multiple threads
        threads = [threading.Thread(target=update_metrics) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        assert metrics.total_tokens == 10000  # 10 threads * 100 updates * 10 tokens
        assert metrics.processed_texts == 1000  # 10 threads * 100 updates


# =============================================================================
# Test Backward Compatibility
# =============================================================================

class TestBackwardCompatibility:
    """Tests for backward compatibility with existing code."""
    
    def test_batch_config_has_required_attributes(self):
        """Test that BatchConfig has all required attributes."""
        config = BatchConfig()
        
        # Required attributes
        assert hasattr(config, 'dynamic_sizing')
        assert hasattr(config, 'target_batch_time_ms')
        assert hasattr(config, 'max_workers')
        assert hasattr(config, 'token_buffer')
        assert hasattr(config, 'preserve_order')
        assert hasattr(config, 'fail_fast')
    
    def test_batch_metrics_has_required_methods(self):
        """Test that BatchMetrics has all required methods."""
        metrics = BatchMetrics()
        
        # Required methods
        assert hasattr(metrics, 'update_throughput')
        assert hasattr(metrics, 'calculate_eta')
        assert hasattr(metrics, 'to_dict')


# =============================================================================
# Benchmark Tests
# =============================================================================

class TestBenchmark:
    """Benchmark tests to verify throughput improvements."""
    
    @pytest.mark.slow
    def test_benchmark_grouping_overhead(self):
        """Benchmark the overhead of text grouping."""
        rows = [{"id": f"{i}", "source_text": f"测试文本{i}" * 10} for i in range(100)]
        
        # Without grouping
        start = time.time()
        for _ in range(100):
            _ = rows[:]
        baseline_time = time.time() - start
        
        # With grouping
        start = time.time()
        for _ in range(100):
            group_similar_length_texts(rows, max_variance=100)
        grouping_time = time.time() - start
        
        # Grouping overhead should be minimal (less than 10x baseline)
        overhead = grouping_time / max(baseline_time, 0.001)
        assert overhead < 10
    
    def test_dynamic_vs_static_batch_size(self, mock_config):
        """Compare dynamic vs static batch sizing."""
        # Static sizing (typical fixed batch size)
        static_size = 25
        
        # Dynamic sizing for different text lengths
        sizes = []
        for text_len in [50, 100, 200, 500, 1000]:
            size = calculate_dynamic_batch_size(
                model="test-model",
                avg_text_length=text_len,
                config=mock_config
            )
            sizes.append(size)
        
        # All sizes should be valid (>= 1)
        assert all(s >= 1 for s in sizes), "All batch sizes should be >= 1"
        # Maximum should be reasonable (<= 100)
        assert all(s <= 100 for s in sizes), "All batch sizes should be <= 100"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
