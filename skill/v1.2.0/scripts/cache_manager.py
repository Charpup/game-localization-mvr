#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cache_manager.py - Response Caching Layer for Localization Pipeline
Purpose:
  SQLite-based persistent cache for LLM translation responses.
  Provides TTL support, LRU eviction, and hit/miss statistics.
  
Features:
  - Persistent SQLite storage
  - Cache key: hash(source_text + glossary_hash + model_name)
  - Configurable TTL (default 7 days)
  - Size limits with LRU eviction
  - Cache hit/miss statistics tracking
  - Thread-safe operations

Version: 1.0.0
"""

import hashlib
import json
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import os


@dataclass
class CacheStats:
    """Cache performance statistics."""
    hits: int = 0
    misses: int = 0
    evictions: int = 0
    total_size_bytes: int = 0
    
    @property
    def total_requests(self) -> int:
        return self.hits + self.misses
    
    @property
    def hit_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.hits / self.total_requests
    
    @property
    def miss_rate(self) -> float:
        if self.total_requests == 0:
            return 0.0
        return self.misses / self.total_requests
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "total_requests": self.total_requests,
            "hit_rate": f"{self.hit_rate:.2%}",
            "miss_rate": f"{self.miss_rate:.2%}",
            "total_size_mb": f"{self.total_size_bytes / (1024 * 1024):.2f}"
        }


@dataclass
class CacheConfig:
    """Cache configuration settings."""
    enabled: bool = True
    ttl_days: int = 7
    max_size_mb: int = 100
    location: str = ".cache/translations.db"
    
    @property
    def ttl_seconds(self) -> int:
        return self.ttl_days * 24 * 60 * 60
    
    @property
    def max_size_bytes(self) -> int:
        return self.max_size_mb * 1024 * 1024


class CacheManager:
    """
    SQLite-based persistent cache manager for translation responses.
    
    Cache key format: SHA256(source_text + glossary_hash + model_name)
    """
    
    def __init__(self, config: Optional[CacheConfig] = None):
        """
        Initialize the cache manager.
        
        Args:
            config: Cache configuration. Uses defaults if not provided.
        """
        self.config = config or CacheConfig()
        self.stats = CacheStats()
        self._local = threading.local()
        self._lock = threading.RLock()
        
        # Ensure cache directory exists
        self._ensure_cache_dir()
        
        # Initialize database
        self._init_db()
    
    def _ensure_cache_dir(self) -> None:
        """Create cache directory if it doesn't exist."""
        cache_path = Path(self.config.location)
        cache_dir = cache_path.parent
        if cache_dir and not cache_dir.exists():
            cache_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get thread-local database connection."""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.config.location,
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def _init_db(self) -> None:
        """Initialize SQLite database schema."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Main cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS translations (
                    cache_key TEXT PRIMARY KEY,
                    source_text TEXT NOT NULL,
                    translated_text TEXT NOT NULL,
                    model_name TEXT NOT NULL,
                    glossary_hash TEXT,
                    created_at INTEGER NOT NULL,
                    accessed_at INTEGER NOT NULL,
                    access_count INTEGER DEFAULT 1,
                    size_bytes INTEGER NOT NULL
                )
            """)
            
            # Statistics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_stats (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    hits INTEGER DEFAULT 0,
                    misses INTEGER DEFAULT 0,
                    evictions INTEGER DEFAULT 0,
                    total_size_bytes INTEGER DEFAULT 0
                )
            """)
            
            # Initialize stats row if not exists
            cursor.execute("""
                INSERT OR IGNORE INTO cache_stats (id, hits, misses, evictions, total_size_bytes)
                VALUES (1, 0, 0, 0, 0)
            """)
            
            # Create indexes for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_accessed_at ON translations(accessed_at)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at ON translations(created_at)
            """)
            
            conn.commit()
    
    def _generate_cache_key(
        self,
        source_text: str,
        glossary_hash: Optional[str],
        model_name: str
    ) -> str:
        """
        Generate cache key from source text, glossary hash, and model name.
        
        Args:
            source_text: The source text to translate
            glossary_hash: Hash of the glossary used
            model_name: Name of the LLM model
            
        Returns:
            SHA256 hash as hex string
        """
        key_string = f"{source_text}|{glossary_hash or ''}|{model_name}"
        return hashlib.sha256(key_string.encode('utf-8')).hexdigest()
    
    def _calculate_size(self, source_text: str, translated_text: str) -> int:
        """Calculate the size in bytes of a cache entry."""
        return len(source_text.encode('utf-8')) + len(translated_text.encode('utf-8'))
    
    def _is_expired(self, created_at: int) -> bool:
        """Check if a cache entry has expired based on TTL."""
        if self.config.ttl_seconds <= 0:
            return False  # No expiration
        return (int(time.time()) - created_at) > self.config.ttl_seconds
    
    def _evict_if_needed(self, new_entry_size: int) -> None:
        """
        Evict old entries if adding new entry would exceed size limit.
        Uses LRU (Least Recently Used) eviction policy.
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Get current total size
            cursor.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM translations")
            current_size = cursor.fetchone()[0]
            
            # Calculate projected size
            projected_size = current_size + new_entry_size
            max_size = self.config.max_size_bytes
            
            if max_size > 0 and projected_size > max_size:
                # Need to evict entries (LRU: least recently accessed first)
                excess = projected_size - max_size
                evicted_count = 0
                
                cursor.execute("""
                    SELECT cache_key, size_bytes FROM translations
                    ORDER BY accessed_at ASC, access_count ASC
                """)
                
                for row in cursor.fetchall():
                    if excess <= 0:
                        break
                    
                    cursor.execute(
                        "DELETE FROM translations WHERE cache_key = ?",
                        (row['cache_key'],)
                    )
                    excess -= row['size_bytes']
                    evicted_count += 1
                
                # Update eviction stats
                cursor.execute(
                    "UPDATE cache_stats SET evictions = evictions + ? WHERE id = 1",
                    (evicted_count,)
                )
                self.stats.evictions += evicted_count
                
                conn.commit()
    
    def _cleanup_expired(self) -> int:
        """
        Remove expired entries from cache.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if self.config.ttl_seconds <= 0:
                return 0
            
            cutoff_time = int(time.time()) - self.config.ttl_seconds
            
            cursor.execute(
                "DELETE FROM translations WHERE created_at < ?",
                (cutoff_time,)
            )
            removed = cursor.rowcount
            
            if removed > 0:
                conn.commit()
            
            return removed
    
    def get(
        self,
        source_text: str,
        glossary_hash: Optional[str] = None,
        model_name: str = "default"
    ) -> Tuple[bool, Optional[str]]:
        """
        Retrieve a translation from cache.
        
        Args:
            source_text: The source text
            glossary_hash: Hash of the glossary (optional)
            model_name: Name of the model used
            
        Returns:
            Tuple of (cache_hit, translated_text or None)
        """
        if not self.config.enabled:
            self.stats.misses += 1
            self._update_stats_db(miss=True)
            return False, None
        
        cache_key = self._generate_cache_key(source_text, glossary_hash, model_name)
        
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM translations WHERE cache_key = ?",
                (cache_key,)
            )
            row = cursor.fetchone()
            
            if row is None:
                self.stats.misses += 1
                self._update_stats_db(miss=True)
                return False, None
            
            # Check if expired
            if self._is_expired(row['created_at']):
                cursor.execute(
                    "DELETE FROM translations WHERE cache_key = ?",
                    (cache_key,)
                )
                conn.commit()
                self.stats.misses += 1
                self._update_stats_db(miss=True)
                return False, None
            
            # Update access metadata (LRU tracking)
            current_time = int(time.time())
            cursor.execute("""
                UPDATE translations 
                SET accessed_at = ?, access_count = access_count + 1
                WHERE cache_key = ?
            """, (current_time, cache_key))
            
            # Update hit stats
            cursor.execute(
                "UPDATE cache_stats SET hits = hits + 1 WHERE id = 1"
            )
            
            conn.commit()
            
            self.stats.hits += 1
            return True, row['translated_text']
    
    def set(
        self,
        source_text: str,
        translated_text: str,
        glossary_hash: Optional[str] = None,
        model_name: str = "default"
    ) -> bool:
        """
        Store a translation in cache.
        
        Args:
            source_text: The source text
            translated_text: The translated result
            glossary_hash: Hash of the glossary (optional)
            model_name: Name of the model used
            
        Returns:
            True if stored successfully
        """
        if not self.config.enabled:
            return False
        
        if not source_text or not translated_text:
            return False
        
        cache_key = self._generate_cache_key(source_text, glossary_hash, model_name)
        current_time = int(time.time())
        size_bytes = self._calculate_size(source_text, translated_text)
        
        # Check if we need to evict entries
        self._evict_if_needed(size_bytes)
        
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO translations 
                (cache_key, source_text, translated_text, model_name, glossary_hash,
                 created_at, accessed_at, access_count, size_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (
                cache_key, source_text, translated_text, model_name, glossary_hash,
                current_time, current_time, size_bytes
            ))
            
            conn.commit()
            
            # Update total size stats
            cursor.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM translations")
            total_size = cursor.fetchone()[0]
            cursor.execute(
                "UPDATE cache_stats SET total_size_bytes = ? WHERE id = 1",
                (total_size,)
            )
            conn.commit()
            
            self.stats.total_size_bytes = total_size
            
        return True
    
    def _update_stats_db(self, miss: bool = False) -> None:
        """Update statistics in database."""
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if miss:
                cursor.execute(
                    "UPDATE cache_stats SET misses = misses + 1 WHERE id = 1"
                )
            
            conn.commit()
    
    def get_stats(self) -> CacheStats:
        """
        Get current cache statistics.
        
        Returns:
            CacheStats object with current statistics
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT hits, misses, evictions, total_size_bytes FROM cache_stats WHERE id = 1"
            )
            row = cursor.fetchone()
            
            if row:
                self.stats.hits = row['hits']
                self.stats.misses = row['misses']
                self.stats.evictions = row['evictions']
                self.stats.total_size_bytes = row['total_size_bytes']
            
            return self.stats
    
    def clear(self) -> int:
        """
        Clear all cache entries.
        
        Returns:
            Number of entries removed
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM translations")
            count = cursor.fetchone()[0]
            
            cursor.execute("DELETE FROM translations")
            cursor.execute("""
                UPDATE cache_stats 
                SET hits = 0, misses = 0, evictions = 0, total_size_bytes = 0 
                WHERE id = 1
            """)
            
            conn.commit()
            
            # Reset in-memory stats
            self.stats = CacheStats()
            
            return count
    
    def get_size(self) -> Dict[str, Any]:
        """
        Get current cache size information.
        
        Returns:
            Dictionary with size metrics
        """
        with self._lock:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("SELECT COUNT(*) FROM translations")
            entry_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COALESCE(SUM(size_bytes), 0) FROM translations")
            total_bytes = cursor.fetchone()[0]
            
            cursor.execute("SELECT MIN(created_at), MAX(created_at) FROM translations")
            row = cursor.fetchone()
            oldest = row[0] if row else None
            newest = row[1] if row else None
            
            return {
                "entry_count": entry_count,
                "total_bytes": total_bytes,
                "total_mb": total_bytes / (1024 * 1024),
                "max_mb": self.config.max_size_mb,
                "usage_percent": (total_bytes / self.config.max_size_bytes * 100) 
                    if self.config.max_size_bytes > 0 else 0,
                "oldest_entry": oldest,
                "newest_entry": newest
            }
    
    def close(self) -> None:
        """Close database connections."""
        with self._lock:
            if hasattr(self._local, 'connection') and self._local.connection:
                self._local.connection.close()
                self._local.connection = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


def load_cache_config(config_path: str = "config/pipeline.yaml") -> CacheConfig:
    """
    Load cache configuration from YAML file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        CacheConfig object
    """
    config = CacheConfig()
    
    try:
        import yaml
        if Path(config_path).exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            cache_config = data.get('cache', {})
            
            if 'enabled' in cache_config:
                config.enabled = cache_config['enabled']
            if 'ttl_days' in cache_config:
                config.ttl_days = cache_config['ttl_days']
            if 'max_size_mb' in cache_config:
                config.max_size_mb = cache_config['max_size_mb']
            if 'location' in cache_config:
                config.location = cache_config['location']
    except ImportError:
        pass  # Use defaults if yaml not available
    except Exception as e:
        print(f"Warning: Failed to load cache config: {e}")
    
    return config


# Global cache manager instance (lazy initialization)
_cache_manager: Optional[CacheManager] = None


def get_cache_manager(config_path: str = "config/pipeline.yaml") -> CacheManager:
    """
    Get or create global cache manager instance.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        CacheManager instance
    """
    global _cache_manager
    if _cache_manager is None:
        config = load_cache_config(config_path)
        _cache_manager = CacheManager(config)
    return _cache_manager


def reset_cache_manager() -> None:
    """Reset global cache manager (useful for testing)."""
    global _cache_manager
    _cache_manager = None


if __name__ == "__main__":
    # Simple CLI for cache management
    import argparse
    
    parser = argparse.ArgumentParser(description="Cache Manager CLI")
    parser.add_argument("--stats", action="store_true", help="Show cache statistics")
    parser.add_argument("--clear", action="store_true", help="Clear all cache entries")
    parser.add_argument("--size", action="store_true", help="Show cache size")
    parser.add_argument("--config", default="config/pipeline.yaml", help="Config path")
    
    args = parser.parse_args()
    
    config = load_cache_config(args.config)
    
    if not args.stats and not args.clear and not args.size:
        parser.print_help()
        exit(0)
    
    with CacheManager(config) as cache:
        if args.stats:
            stats = cache.get_stats()
            print("Cache Statistics:")
            print(f"  Hits: {stats.hits}")
            print(f"  Misses: {stats.misses}")
            print(f"  Hit Rate: {stats.hit_rate:.2%}")
            print(f"  Evictions: {stats.evictions}")
        
        if args.size:
            size_info = cache.get_size()
            print("Cache Size:")
            print(f"  Entries: {size_info['entry_count']}")
            print(f"  Size: {size_info['total_mb']:.2f} MB / {size_info['max_mb']} MB")
            print(f"  Usage: {size_info['usage_percent']:.1f}%")
        
        if args.clear:
            count = cache.clear()
            print(f"Cleared {count} cache entries")
