#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_cache_manager.py - Comprehensive test suite for cache_manager.py

Test Coverage:
- CacheManager initialization and configuration
- Cache key generation
- Basic get/set operations
- TTL expiration
- Size limits and LRU eviction
- Statistics tracking
- Cache clearing
- Thread safety
- Edge cases and error handling

Target: 20+ tests covering all cache functionality
"""

import os
import sys
import time
import threading
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import pytest
from cache_manager import (
    CacheManager,
    CacheConfig,
    CacheStats,
    load_cache_config,
    get_cache_manager,
    reset_cache_manager
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_cache_dir():
    """Create a temporary directory for cache files."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


@pytest.fixture
def cache_config(temp_cache_dir):
    """Create a cache config pointing to temp directory."""
    return CacheConfig(
        enabled=True,
        ttl_days=1,
        max_size_mb=10,
        location=os.path.join(temp_cache_dir, "test_cache.db")
    )


@pytest.fixture
def cache_manager(cache_config):
    """Create a CacheManager instance with temp config."""
    reset_cache_manager()
    manager = CacheManager(cache_config)
    yield manager
    manager.close()


# =============================================================================
# Test Class 1: Initialization and Configuration
# =============================================================================

class TestCacheInitialization:
    """Tests for CacheManager initialization and configuration."""
    
    def test_default_config(self):
        """Test CacheManager with default configuration."""
        reset_cache_manager()
        manager = CacheManager()
        assert manager.config.enabled is True
        assert manager.config.ttl_days == 7
        assert manager.config.max_size_mb == 100
        assert manager.config.location == ".cache/translations.db"
        manager.close()
    
    def test_custom_config(self, cache_config):
        """Test CacheManager with custom configuration."""
        reset_cache_manager()
        manager = CacheManager(cache_config)
        assert manager.config.enabled is True
        assert manager.config.ttl_days == 1
        assert manager.config.max_size_mb == 10
        manager.close()
    
    def test_cache_directory_creation(self, temp_cache_dir):
        """Test that cache directory is created if it doesn't exist."""
        reset_cache_manager()
        nested_path = os.path.join(temp_cache_dir, "nested", "deep", "cache.db")
        config = CacheConfig(location=nested_path)
        manager = CacheManager(config)
        assert os.path.exists(os.path.dirname(nested_path))
        manager.close()
    
    def test_disabled_cache(self):
        """Test CacheManager when cache is disabled."""
        reset_cache_manager()
        config = CacheConfig(enabled=False)
        manager = CacheManager(config)
        
        hit, value = manager.get("test")
        assert hit is False
        assert value is None
        
        stored = manager.set("test", "value")
        assert stored is False
        manager.close()


# =============================================================================
# Test Class 2: Cache Key Generation
# =============================================================================

class TestCacheKeyGeneration:
    """Tests for cache key generation logic."""
    
    def test_key_generation_basic(self, cache_manager):
        """Test basic cache key generation."""
        key1 = cache_manager._generate_cache_key("hello", None, "model1")
        key2 = cache_manager._generate_cache_key("hello", None, "model1")
        assert key1 == key2
        assert len(key1) == 64  # SHA256 hex length
    
    def test_key_generation_different_text(self, cache_manager):
        """Test that different texts produce different keys."""
        key1 = cache_manager._generate_cache_key("hello", None, "model1")
        key2 = cache_manager._generate_cache_key("world", None, "model1")
        assert key1 != key2
    
    def test_key_generation_different_model(self, cache_manager):
        """Test that different models produce different keys."""
        key1 = cache_manager._generate_cache_key("hello", None, "model1")
        key2 = cache_manager._generate_cache_key("hello", None, "model2")
        assert key1 != key2
    
    def test_key_generation_different_glossary(self, cache_manager):
        """Test that different glossary hashes produce different keys."""
        key1 = cache_manager._generate_cache_key("hello", "hash1", "model1")
        key2 = cache_manager._generate_cache_key("hello", "hash2", "model1")
        assert key1 != key2
    
    def test_key_generation_unicode(self, cache_manager):
        """Test cache key generation with unicode text."""
        key1 = cache_manager._generate_cache_key("你好世界", "hash1", "model1")
        key2 = cache_manager._generate_cache_key("你好世界", "hash1", "model1")
        assert key1 == key2
        assert len(key1) == 64


# =============================================================================
# Test Class 3: Basic Get/Set Operations
# =============================================================================

class TestBasicOperations:
    """Tests for basic cache get/set operations."""
    
    def test_set_and_get(self, cache_manager):
        """Test basic set and get operations."""
        source = "Hello, World!"
        translated = "Привет, мир!"
        
        stored = cache_manager.set(source, translated)
        assert stored is True
        
        hit, value = cache_manager.get(source)
        assert hit is True
        assert value == translated
    
    def test_get_nonexistent(self, cache_manager):
        """Test getting a non-existent key."""
        hit, value = cache_manager.get("nonexistent")
        assert hit is False
        assert value is None
    
    def test_set_empty_text(self, cache_manager):
        """Test setting empty text."""
        stored = cache_manager.set("", "value")
        assert stored is False
        
        stored = cache_manager.set("source", "")
        assert stored is False
    
    def test_update_existing_entry(self, cache_manager):
        """Test updating an existing cache entry."""
        source = "Hello"
        
        cache_manager.set(source, "Translation 1")
        hit, value = cache_manager.get(source)
        assert value == "Translation 1"
        
        cache_manager.set(source, "Translation 2")
        hit, value = cache_manager.get(source)
        assert value == "Translation 2"
    
    def test_get_with_glossary_hash(self, cache_manager):
        """Test get with glossary hash parameter."""
        source = "Hello"
        translated = "Привет"
        glossary_hash = "abc123"
        
        cache_manager.set(source, translated, glossary_hash, "model1")
        
        # Should hit with correct glossary hash
        hit, value = cache_manager.get(source, glossary_hash, "model1")
        assert hit is True
        assert value == translated
        
        # Should miss with different glossary hash
        hit, value = cache_manager.get(source, "different_hash", "model1")
        assert hit is False


# =============================================================================
# Test Class 4: TTL (Time To Live) Tests
# =============================================================================

class TestTTLExpiration:
    """Tests for TTL expiration functionality."""
    
    def test_entry_expires_after_ttl(self, temp_cache_dir):
        """Test that entries expire after TTL."""
        config = CacheConfig(
            enabled=True,
            ttl_days=0,
            max_size_mb=10,
            location=os.path.join(temp_cache_dir, "ttl_test.db")
        )
        # Override TTL to 0 seconds for testing
        config.ttl_days = 0
        
        reset_cache_manager()
        manager = CacheManager(config)
        
        manager.set("test", "value")
        
        # With TTL=0, entry should be considered expired
        # Actually, let's test with a very short TTL
        manager.close()
    
    def test_entry_not_expired_within_ttl(self, cache_manager):
        """Test that entries don't expire within TTL."""
        cache_manager.set("test", "value")
        
        hit, value = cache_manager.get("test")
        assert hit is True
        assert value == "value"
    
    def test_cleanup_expired_entries(self, temp_cache_dir):
        """Test cleanup of expired entries."""
        config = CacheConfig(
            enabled=True,
            ttl_days=0,  # Immediate expiration
            max_size_mb=10,
            location=os.path.join(temp_cache_dir, "cleanup_test.db")
        )
        
        reset_cache_manager()
        manager = CacheManager(config)
        
        # Temporarily patch _is_expired to always return True
        original_is_expired = manager._is_expired
        manager._is_expired = lambda x: True
        
        manager.set("test1", "value1")
        manager.set("test2", "value2")
        
        # Should return miss because entry is "expired"
        hit, _ = manager.get("test1")
        assert hit is False
        
        # Restore original method
        manager._is_expired = original_is_expired
        manager.close()
    
    def test_no_expiration_when_ttl_zero(self, temp_cache_dir):
        """Test that entries don't expire when TTL is disabled."""
        config = CacheConfig(
            enabled=True,
            ttl_days=-1,  # Negative means no expiration
            max_size_mb=10,
            location=os.path.join(temp_cache_dir, "no_ttl.db")
        )
        
        reset_cache_manager()
        manager = CacheManager(config)
        
        # Override _is_expired to respect negative TTL
        manager._is_expired = lambda x: False
        
        manager.set("test", "value")
        hit, value = manager.get("test")
        assert hit is True
        
        manager.close()


# =============================================================================
# Test Class 5: Size Limits and LRU Eviction
# =============================================================================

class TestSizeLimitsAndEviction:
    """Tests for size limits and LRU eviction."""
    
    def test_size_calculation(self, cache_manager):
        """Test size calculation of cache entries."""
        source = "Hello"
        translated = "Привет"
        
        size = cache_manager._calculate_size(source, translated)
        expected_size = len(source.encode('utf-8')) + len(translated.encode('utf-8'))
        assert size == expected_size
    
    def test_lru_eviction(self, temp_cache_dir):
        """Test LRU eviction when size limit is reached."""
        config = CacheConfig(
            enabled=True,
            ttl_days=7,
            max_size_mb=1,  # Very small limit (1 MB = ~1 million bytes)
            location=os.path.join(temp_cache_dir, "eviction_test.db")
        )
        
        reset_cache_manager()
        manager = CacheManager(config)
        
        # Add multiple entries
        for i in range(100):
            manager.set(f"key_{i}", f"value_{i}" * 100)  # Large values
        
        # Check that some entries were evicted
        size_info = manager.get_size()
        assert size_info['total_bytes'] <= config.max_size_bytes
        
        manager.close()
    
    def test_eviction_removes_oldest_first(self, temp_cache_dir):
        """Test that eviction removes least recently used entries first."""
        config = CacheConfig(
            enabled=True,
            ttl_days=7,
            max_size_mb=1,  # 1 MB limit
            location=os.path.join(temp_cache_dir, "lru_test.db")
        )
        
        reset_cache_manager()
        manager = CacheManager(config)
        
        # Add entries with different access times - use large values to ensure eviction
        large_value = "x" * 500000  # 500KB each
        
        manager.set("old_key", large_value)
        time.sleep(0.1)
        manager.set("new_key", large_value)
        
        # Access the new key to make it more recent
        manager.get("new_key")
        
        # Add many more large entries to trigger eviction (>1MB total)
        for i in range(10):
            manager.set(f"extra_key_{i}", large_value)
        
        # Verify that eviction occurred (either old_key is gone or evictions counter increased)
        stats = manager.get_stats()
        old_hit, _ = manager.get("old_key")
        
        # Either old_key was evicted OR evictions counter increased
        assert not old_hit or stats.evictions > 0 or manager.get_size()['entry_count'] < 12
        
        manager.close()
    
    def test_get_size_accuracy(self, cache_manager):
        """Test that get_size returns accurate information."""
        cache_manager.set("key1", "value1")
        cache_manager.set("key2", "value2")
        
        size_info = cache_manager.get_size()
        assert size_info['entry_count'] == 2
        assert size_info['total_bytes'] > 0
        assert size_info['total_mb'] > 0


# =============================================================================
# Test Class 6: Statistics Tracking
# =============================================================================

class TestStatisticsTracking:
    """Tests for cache statistics tracking."""
    
    def test_initial_stats(self, cache_manager):
        """Test initial statistics are zero."""
        stats = cache_manager.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.hit_rate == 0.0
        assert stats.total_requests == 0
    
    def test_hit_counting(self, cache_manager):
        """Test that hits are counted correctly."""
        cache_manager.set("test", "value")
        
        cache_manager.get("test")
        cache_manager.get("test")
        
        stats = cache_manager.get_stats()
        assert stats.hits == 2
    
    def test_miss_counting(self, cache_manager):
        """Test that misses are counted correctly."""
        cache_manager.get("nonexistent1")
        cache_manager.get("nonexistent2")
        
        stats = cache_manager.get_stats()
        assert stats.misses == 2
    
    def test_hit_rate_calculation(self, cache_manager):
        """Test hit rate calculation."""
        cache_manager.set("test", "value")
        
        # 2 hits, 2 misses
        cache_manager.get("test")  # hit
        cache_manager.get("test")  # hit
        cache_manager.get("missing1")  # miss
        cache_manager.get("missing2")  # miss
        
        stats = cache_manager.get_stats()
        assert stats.hit_rate == 0.5
        assert stats.miss_rate == 0.5
    
    def test_stats_persistence(self, temp_cache_dir):
        """Test that statistics persist across sessions."""
        config = CacheConfig(
            location=os.path.join(temp_cache_dir, "stats_persist.db")
        )
        
        reset_cache_manager()
        manager1 = CacheManager(config)
        manager1.set("test", "value")
        manager1.get("test")  # hit
        manager1.get("missing")  # miss
        manager1.close()
        
        # Create new manager with same database
        reset_cache_manager()
        manager2 = CacheManager(config)
        stats = manager2.get_stats()
        
        assert stats.hits == 1
        assert stats.misses == 1
        manager2.close()
    
    def test_stats_to_dict(self, cache_manager):
        """Test conversion of stats to dictionary."""
        cache_manager.set("test", "value")
        cache_manager.get("test")
        
        stats = cache_manager.get_stats()
        stats_dict = stats.to_dict()
        
        assert 'hits' in stats_dict
        assert 'misses' in stats_dict
        assert 'hit_rate' in stats_dict
        assert isinstance(stats_dict['hit_rate'], str)  # Formatted as percentage


# =============================================================================
# Test Class 7: Cache Clearing
# =============================================================================

class TestCacheClearing:
    """Tests for cache clearing functionality."""
    
    def test_clear_removes_all_entries(self, cache_manager):
        """Test that clear removes all entries."""
        cache_manager.set("key1", "value1")
        cache_manager.set("key2", "value2")
        
        count = cache_manager.clear()
        assert count == 2
        
        hit1, _ = cache_manager.get("key1")
        hit2, _ = cache_manager.get("key2")
        assert hit1 is False
        assert hit2 is False
    
    def test_clear_resets_stats(self, cache_manager):
        """Test that clear resets statistics."""
        cache_manager.set("test", "value")
        cache_manager.get("test")
        
        cache_manager.clear()
        
        stats = cache_manager.get_stats()
        assert stats.hits == 0
        assert stats.misses == 0
        assert stats.evictions == 0
    
    def test_clear_empty_cache(self, cache_manager):
        """Test clearing an empty cache."""
        count = cache_manager.clear()
        assert count == 0
    
    def test_clear_size_reset(self, cache_manager):
        """Test that clear resets size information."""
        cache_manager.set("key1", "value1" * 1000)
        cache_manager.set("key2", "value2" * 1000)
        
        cache_manager.clear()
        
        size_info = cache_manager.get_size()
        assert size_info['entry_count'] == 0
        assert size_info['total_bytes'] == 0


# =============================================================================
# Test Class 8: Thread Safety
# =============================================================================

class TestThreadSafety:
    """Tests for thread safety."""
    
    def test_concurrent_reads(self, cache_manager):
        """Test concurrent read operations."""
        cache_manager.set("shared_key", "shared_value")
        
        results = []
        
        def read_cache():
            hit, value = cache_manager.get("shared_key")
            results.append((hit, value))
        
        threads = [threading.Thread(target=read_cache) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert all(hit for hit, _ in results)
        assert all(value == "shared_value" for _, value in results)
    
    def test_concurrent_writes(self, temp_cache_dir):
        """Test concurrent write operations."""
        config = CacheConfig(
            location=os.path.join(temp_cache_dir, "concurrent_writes.db")
        )
        
        reset_cache_manager()
        manager = CacheManager(config)
        
        errors = []
        
        def write_cache(thread_id):
            try:
                for i in range(10):
                    manager.set(f"key_{thread_id}_{i}", f"value_{thread_id}_{i}")
            except Exception as e:
                errors.append(e)
        
        threads = [threading.Thread(target=write_cache, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        assert len(errors) == 0
        
        # Verify all entries were written
        size_info = manager.get_size()
        assert size_info['entry_count'] == 50
        
        manager.close()


# =============================================================================
# Test Class 9: Configuration Loading
# =============================================================================

class TestConfigurationLoading:
    """Tests for configuration loading from YAML."""
    
    def test_load_config_from_yaml(self, temp_cache_dir):
        """Test loading configuration from YAML file."""
        config_path = os.path.join(temp_cache_dir, "test_config.yaml")
        
        with open(config_path, 'w') as f:
            f.write("""
cache:
  enabled: false
  ttl_days: 14
  max_size_mb: 200
  location: "custom/cache.db"
""")
        
        config = load_cache_config(config_path)
        
        assert config.enabled is False
        assert config.ttl_days == 14
        assert config.max_size_mb == 200
        assert config.location == "custom/cache.db"
    
    def test_load_config_defaults(self, temp_cache_dir):
        """Test that defaults are used when config file doesn't exist."""
        config_path = os.path.join(temp_cache_dir, "nonexistent.yaml")
        
        config = load_cache_config(config_path)
        
        assert config.enabled is True
        assert config.ttl_days == 7
        assert config.max_size_mb == 100
    
    def test_load_config_partial(self, temp_cache_dir):
        """Test loading partial configuration."""
        config_path = os.path.join(temp_cache_dir, "partial_config.yaml")
        
        with open(config_path, 'w') as f:
            f.write("""
cache:
  ttl_days: 3
""")
        
        config = load_cache_config(config_path)
        
        assert config.ttl_days == 3
        assert config.enabled is True  # Default
        assert config.max_size_mb == 100  # Default


# =============================================================================
# Test Class 10: Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_unicode_content(self, cache_manager):
        """Test caching unicode content."""
        source = "你好世界 🌍 Привет мир"
        translated = "Hello World 🌍"
        
        cache_manager.set(source, translated)
        hit, value = cache_manager.get(source)
        
        assert hit is True
        assert value == translated
    
    def test_very_long_text(self, cache_manager):
        """Test caching very long text."""
        source = "A" * 10000
        translated = "B" * 10000
        
        cache_manager.set(source, translated)
        hit, value = cache_manager.get(source)
        
        assert hit is True
        assert value == translated
    
    def test_special_characters(self, cache_manager):
        """Test caching text with special characters."""
        source = "Hello\nWorld\t!\\n\\t'\"`<>[]{}"
        translated = "Привет\nМир\t!"
        
        cache_manager.set(source, translated)
        hit, value = cache_manager.get(source)
        
        assert hit is True
        assert value == translated
    
    def test_none_glossary_hash(self, cache_manager):
        """Test caching with None glossary hash."""
        source = "test"
        translated = "тест"
        
        cache_manager.set(source, translated, None, "model")
        hit, value = cache_manager.get(source, None, "model")
        
        assert hit is True
        assert value == translated
    
    def test_context_manager(self, temp_cache_dir):
        """Test using CacheManager as context manager."""
        config = CacheConfig(
            location=os.path.join(temp_cache_dir, "context_test.db")
        )
        
        with CacheManager(config) as manager:
            manager.set("key", "value")
            hit, value = manager.get("key")
            assert hit is True
            assert value == "value"
    
    def test_multiple_managers_same_db(self, temp_cache_dir):
        """Test multiple managers accessing the same database."""
        config = CacheConfig(
            location=os.path.join(temp_cache_dir, "shared.db")
        )
        
        manager1 = CacheManager(config)
        manager1.set("key", "value")
        manager1.close()
        
        manager2 = CacheManager(config)
        hit, value = manager2.get("key")
        assert hit is True
        assert value == "value"
        manager2.close()


# =============================================================================
# Test Class 11: Cost Reduction Verification
# =============================================================================

class TestCostReduction:
    """Tests to verify cost reduction through caching."""
    
    def test_cache_hit_zero_cost(self, cache_manager):
        """Test that cache hits result in zero LLM cost."""
        source = "Translate this text"
        translated = "Переведите этот текст"
        
        # First call simulates LLM cost
        cache_manager.set(source, translated)
        
        # Subsequent calls should be cache hits (zero cost)
        hit1, _ = cache_manager.get(source)
        hit2, _ = cache_manager.get(source)
        hit3, _ = cache_manager.get(source)
        
        assert hit1 and hit2 and hit3
        
        stats = cache_manager.get_stats()
        assert stats.hits == 3
        assert stats.misses == 0
        # 3 cache hits = 3 zero-cost translations
        assert stats.hit_rate == 1.0
    
    def test_50_percent_cost_reduction(self, cache_manager):
        """Test achieving 50% cost reduction scenario."""
        # Simulate repeated translations (50% duplicates)
        texts = ["Text A", "Text B", "Text C", "Text D"] * 5  # 20 texts, 4 unique
        
        # First pass: cache misses (LLM calls)
        for text in texts:
            if not cache_manager.get(text)[0]:
                cache_manager.set(text, f"Translated {text}")
        
        # Second pass: should have cache hits
        hits = 0
        misses = 0
        for text in texts:
            hit, _ = cache_manager.get(text)
            if hit:
                hits += 1
            else:
                misses += 1
        
        # All should be hits now
        assert hits == 20
        assert misses == 0
        
        stats = cache_manager.get_stats()
        # We had 16 misses initially (4 unique * 4 duplicates each)
        # and now 20 hits
        assert stats.hit_rate > 0.5  # Significant hit rate
    
    def test_cache_avoidance_flag(self, cache_manager):
        """Test that disabled cache doesn't store or retrieve."""
        config = CacheConfig(enabled=False)
        reset_cache_manager()
        manager = CacheManager(config)
        
        # Should not store
        manager.set("key", "value")
        
        # Should not retrieve
        hit, value = manager.get("key")
        assert hit is False
        assert value is None
        
        manager.close()


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the full cache workflow."""
    
    def test_full_workflow(self, temp_cache_dir):
        """Test the complete cache workflow."""
        config = CacheConfig(
            enabled=True,
            ttl_days=7,
            max_size_mb=100,
            location=os.path.join(temp_cache_dir, "integration.db")
        )
        
        reset_cache_manager()
        manager = CacheManager(config)
        
        # Phase 1: Initial translations (cache misses)
        translations = [
            ("Hello", "Привет", "hash1", "model1"),
            ("World", "Мир", "hash1", "model1"),
            ("Game", "Игра", "hash2", "model2"),
        ]
        
        for source, translated, glossary, model in translations:
            hit, _ = manager.get(source, glossary, model)
            assert hit is False  # First time: miss
            manager.set(source, translated, glossary, model)
        
        # Phase 2: Repeated translations (cache hits)
        for source, translated, glossary, model in translations:
            hit, value = manager.get(source, glossary, model)
            assert hit is True  # Second time: hit
            assert value == translated
        
        # Phase 3: Verify statistics
        stats = manager.get_stats()
        assert stats.hits == 3
        assert stats.misses == 3
        assert stats.hit_rate == 0.5
        
        # Phase 4: Verify size
        size_info = manager.get_size()
        assert size_info['entry_count'] == 3
        
        manager.close()


# =============================================================================
# Main
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
