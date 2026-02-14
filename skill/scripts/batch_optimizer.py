#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_optimizer.py (v1.0 - High Throughput Batch Processing)

Purpose:
  Optimized batch processing infrastructure with:
  - Dynamic batch sizing based on token counts and model context
  - Parallel batch processing with worker pool
  - Token optimization (grouping similar-length texts)
  - Real-time progress & metrics tracking

Features:
  1. Dynamic Batch Sizing: Adaptive batch sizes based on input tokens, context window, latency
  2. Parallel Processing: Configurable worker pool with result ordering preservation
  3. Token Optimization: Group similar-length texts, pre-compute glossary context
  4. Progress & Metrics: Real-time throughput metrics, ETA calculation
"""

import json
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable, Union
from collections import defaultdict
import statistics

try:
    import yaml
except ImportError:
    yaml = None

# Import from runtime_adapter
from runtime_adapter import LLMClient, LLMError, LLMResult, get_batch_config, parse_llm_response

# Token estimation constants
CHARS_PER_TOKEN = 4  # Conservative for CJK/Cyrillic mix


@dataclass
class BatchMetrics:
    """Metrics for batch processing performance tracking."""
    start_time: float = field(default_factory=time.time)
    total_tokens: int = 0
    total_texts: int = 0
    processed_texts: int = 0
    failed_texts: int = 0
    total_latency_ms: int = 0
    batch_count: int = 0
    failed_batch_count: int = 0
    
    # Token throughput tracking
    tokens_per_sec: float = 0.0
    texts_per_sec: float = 0.0
    
    # ETA tracking
    estimated_completion_time: Optional[float] = None
    
    # Thread safety (not part of dataclass fields)
    def __post_init__(self):
        self.metrics_lock = threading.Lock()
    
    def update_throughput(self):
        """Update throughput metrics."""
        elapsed = time.time() - self.start_time
        if elapsed > 0:
            self.tokens_per_sec = self.total_tokens / elapsed
            self.texts_per_sec = self.processed_texts / elapsed
    
    def calculate_eta(self, remaining_texts: int) -> Optional[float]:
        """Calculate estimated time of arrival for completion."""
        if self.texts_per_sec > 0:
            return remaining_texts / self.texts_per_sec
        return None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary for export."""
        self.update_throughput()
        return {
            "timestamp": datetime.now().isoformat(),
            "elapsed_seconds": time.time() - self.start_time,
            "total_tokens": self.total_tokens,
            "total_texts": self.total_texts,
            "processed_texts": self.processed_texts,
            "failed_texts": self.failed_texts,
            "batch_count": self.batch_count,
            "failed_batch_count": self.failed_batch_count,
            "tokens_per_sec": round(self.tokens_per_sec, 2),
            "texts_per_sec": round(self.texts_per_sec, 2),
            "avg_latency_ms": round(self.total_latency_ms / max(self.batch_count, 1), 2),
            "estimated_completion_time": self.estimated_completion_time
        }


@dataclass
class BatchConfig:
    """Configuration for batch processing optimization."""
    dynamic_sizing: bool = True
    target_batch_time_ms: int = 30000
    max_workers: int = 4
    token_buffer: int = 500
    preserve_order: bool = True
    fail_fast: bool = False
    
    # Model-specific settings
    model_context_windows: Dict[str, int] = field(default_factory=dict)
    latency_model: Dict[str, float] = field(default_factory=dict)
    
    # Grouping settings
    grouping_enabled: bool = True
    similarity_threshold: float = 0.8
    max_length_variance: int = 100
    
    # Metrics settings
    metrics_enabled: bool = True
    metrics_export_path: str = "reports/batch_metrics.jsonl"
    realtime_interval_ms: int = 1000
    
    @classmethod
    def from_yaml(cls, path: str = "config/pipeline.yaml") -> "BatchConfig":
        """Load configuration from YAML file."""
        if yaml is None:
            return cls()  # Return defaults
        
        # Try relative to script directory first
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        full_path = os.path.join(script_dir, path)
        if not os.path.exists(full_path):
            full_path = path
        
        if not os.path.exists(full_path):
            return cls()  # Return defaults
        
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            
            batch_config = config.get("batch_processing", {})
            
            return cls(
                dynamic_sizing=batch_config.get("dynamic_sizing", True),
                target_batch_time_ms=batch_config.get("target_batch_time_ms", 30000),
                max_workers=batch_config.get("max_workers", 4),
                token_buffer=batch_config.get("token_buffer", 500),
                preserve_order=batch_config.get("parallel", {}).get("preserve_order", True),
                fail_fast=batch_config.get("parallel", {}).get("fail_fast", False),
                model_context_windows=batch_config.get("model_context_windows", {}),
                latency_model=batch_config.get("latency_model", {}),
                grouping_enabled=batch_config.get("grouping", {}).get("enabled", True),
                similarity_threshold=batch_config.get("grouping", {}).get("similarity_threshold", 0.8),
                max_length_variance=batch_config.get("grouping", {}).get("max_length_variance", 100),
                metrics_enabled=batch_config.get("metrics", {}).get("enabled", True),
                metrics_export_path=batch_config.get("metrics", {}).get("export_path", "reports/batch_metrics.jsonl"),
                realtime_interval_ms=batch_config.get("metrics", {}).get("realtime_interval_ms", 1000)
            )
        except Exception as e:
            print(f"Warning: Failed to load config from {full_path}: {e}")
            return cls()


def estimate_tokens(text: str) -> int:
    """Estimate token count from text using chars/4 heuristic."""
    return max(1, len(text or "") // CHARS_PER_TOKEN)


def estimate_batch_tokens(rows: List[Dict[str, Any]], system_prompt: str) -> int:
    """Estimate total tokens for a batch."""
    total = estimate_tokens(system_prompt)
    for row in rows:
        total += estimate_tokens(row.get("source_text", ""))
        total += estimate_tokens(json.dumps({"id": row.get("id")}, ensure_ascii=False))
    return total


def calculate_dynamic_batch_size(
    model: str,
    avg_text_length: int,
    config: BatchConfig,
    historical_latency_ms: Optional[float] = None
) -> int:
    """
    Calculate optimal batch size based on:
    - Model context window
    - Target processing time
    - Historical latency per model
    """
    # Get model context window
    context_window = config.model_context_windows.get(model, 128000)
    
    # Get latency model (ms per token)
    latency_per_token = historical_latency_ms or config.latency_model.get(model, 0.5)
    
    # Estimate tokens per text (prompt + response)
    estimated_tokens_per_text = (avg_text_length // CHARS_PER_TOKEN) * 2 + 50  # 2x for I/O + overhead
    
    # Calculate max batch size based on target time
    # batch_size * tokens_per_text * latency_per_token <= target_time_ms
    target_tokens = config.target_batch_time_ms / max(latency_per_token, 0.1)
    time_based_size = int(target_tokens / max(estimated_tokens_per_text, 1))
    
    # Calculate max batch size based on context window (with buffer)
    available_context = context_window - config.token_buffer
    context_based_size = available_context // max(estimated_tokens_per_text, 1)
    
    # Take the minimum of time-based and context-based limits
    optimal_size = min(time_based_size, context_based_size)
    
    # Apply reasonable bounds
    optimal_size = max(1, min(optimal_size, 100))
    
    return optimal_size


def group_similar_length_texts(
    rows: List[Dict[str, Any]],
    max_variance: int = 100
) -> List[List[Dict[str, Any]]]:
    """
    Group texts by similar length for better batch efficiency.
    
    This helps because:
    1. Similar-length texts have similar token counts
    2. Reduces padding waste in batch processing
    3. More predictable processing time per batch
    """
    if not rows:
        return []
    
    # Sort by text length
    sorted_rows = sorted(rows, key=lambda r: len(r.get("source_text", "")))
    
    groups = []
    current_group = [sorted_rows[0]]
    current_length = len(sorted_rows[0].get("source_text", ""))
    
    for row in sorted_rows[1:]:
        text_length = len(row.get("source_text", ""))
        
        # Check if within variance threshold
        if abs(text_length - current_length) <= max_variance:
            current_group.append(row)
        else:
            groups.append(current_group)
            current_group = [row]
            current_length = text_length
    
    if current_group:
        groups.append(current_group)
    
    return groups


class BatchProcessor:
    """
    High-throughput batch processor with dynamic sizing and parallel execution.
    """
    
    def __init__(
        self,
        model: str,
        system_prompt: Union[str, Callable[[List[Dict]], str]],
        user_prompt_template: Callable[[List[Dict]], str],
        config: Optional[BatchConfig] = None,
        content_type: str = "normal",
        retry: int = 1,
        _client: Optional[LLMClient] = None  # For testing
    ):
        self.model = model
        self.system_prompt = system_prompt
        self.user_prompt_template = user_prompt_template
        self.config = config or BatchConfig.from_yaml()
        self.content_type = content_type
        self.retry = retry
        
        # Initialize metrics
        self.metrics = BatchMetrics()
        self.metrics_lock = threading.Lock()
        
        # Initialize client (lazy if not provided)
        self._client = _client
        self._client_initialized = _client is not None
        
        # Load batch runtime config for fallback
        self.batch_config = get_batch_config()
        
        # Historical latency tracking (model -> list of latencies)
        self.latency_history: Dict[str, List[float]] = defaultdict(list)
        
        # Pre-computed glossary context (computed once per batch)
        self.glossary_context: Optional[str] = None
    
    @property
    def client(self) -> LLMClient:
        """Lazy initialization of LLMClient."""
        if not self._client_initialized:
            self._client = LLMClient()
            self._client_initialized = True
        return self._client
    
    def _get_historical_latency(self) -> Optional[float]:
        """Get average historical latency for the model."""
        if self.model in self.latency_history and len(self.latency_history[self.model]) > 0:
            return statistics.median(self.latency_history[self.model])
        return None
    
    def _update_latency_history(self, latency_ms: float, tokens: int):
        """Update latency history with new measurement."""
        if tokens > 0:
            latency_per_token = latency_ms / tokens
            self.latency_history[self.model].append(latency_per_token)
            # Keep only last 100 measurements
            self.latency_history[self.model] = self.latency_history[self.model][-100:]
    
    def _calculate_batch_size(self, rows: List[Dict[str, Any]]) -> int:
        """Calculate optimal batch size for given rows."""
        if not self.config.dynamic_sizing:
            # Fall back to runtime config
            return self.batch_config.get_batch_size(self.model, self.content_type)
        
        # Calculate average text length
        avg_length = sum(len(r.get("source_text", "")) for r in rows) / max(len(rows), 1)
        
        # Get historical latency
        historical_latency = self._get_historical_latency()
        
        # Calculate dynamic size
        dynamic_size = calculate_dynamic_batch_size(
            self.model,
            int(avg_length),
            self.config,
            historical_latency
        )
        
        # Get max from runtime config as upper bound
        max_size = self.batch_config.get_batch_size(self.model, self.content_type)
        
        return min(dynamic_size, max_size)
    
    def _process_single_batch(
        self,
        batch_rows: List[Dict[str, Any]],
        batch_index: int
    ) -> Tuple[int, List[Dict[str, Any]], Optional[str]]:
        """
        Process a single batch.
        
        Returns:
            (batch_index, results, error_message)
        """
        # Prepare items
        items = [{"id": r["id"], "source_text": r.get("source_text", "")} for r in batch_rows]
        user_prompt = self.user_prompt_template(items)
        
        # Determine system prompt (static or dynamic)
        if callable(self.system_prompt):
            final_system_prompt = self.system_prompt(batch_rows)
        else:
            final_system_prompt = self.system_prompt
        
        # Add pre-computed glossary context if available
        if self.glossary_context and "术语表摘要：" not in final_system_prompt:
            final_system_prompt += f"\n\n术语表摘要：\n{self.glossary_context}"
        
        # Get timeout from runtime config
        timeout = self.batch_config.get_timeout(self.model, self.content_type)
        
        # Estimate tokens for metrics
        estimated_tokens = estimate_batch_tokens(batch_rows, final_system_prompt)
        
        batch_error = None
        batch_items = []
        
        for attempt in range(self.retry + 1):
            try:
                t0 = time.time()
                response = self.client.chat(
                    system=final_system_prompt,
                    user=user_prompt,
                    temperature=0,
                    metadata={
                        "step": "batch_optimize",
                        "model_override": self.model,
                        "batch_idx": batch_index,
                        "batch_size": len(batch_rows),
                        "is_batch": True
                    },
                    timeout=timeout
                )
                
                latency_ms = int((time.time() - t0) * 1000)
                batch_items = parse_llm_response(response.text, batch_rows)
                
                # Update metrics
                with self.metrics_lock:
                    self.metrics.total_tokens += estimated_tokens
                    self.metrics.processed_texts += len(batch_items)
                    self.metrics.total_latency_ms += latency_ms
                    self.metrics.batch_count += 1
                
                # Update latency history
                self._update_latency_history(latency_ms, estimated_tokens)
                
                return (batch_index, batch_items, None)
                
            except (ValueError, LLMError) as e:
                batch_error = str(e)
                if attempt < self.retry:
                    time.sleep(2 ** attempt)  # Exponential backoff
                    continue
            except Exception as e:
                batch_error = str(e)
                if attempt < self.retry:
                    time.sleep(2 ** attempt)
                    continue
        
        # Batch failed after all retries
        with self.metrics_lock:
            self.metrics.failed_texts += len(batch_rows)
            self.metrics.failed_batch_count += 1
        
        return (batch_index, [], batch_error)
    
    def _export_metrics(self):
        """Export metrics to file."""
        if not self.config.metrics_enabled:
            return
        
        try:
            os.makedirs(os.path.dirname(self.config.metrics_export_path) or ".", exist_ok=True)
            with open(self.config.metrics_export_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(self.metrics.to_dict(), ensure_ascii=False) + "\n")
        except Exception:
            pass  # Metrics export should not break processing
    
    def _print_progress(self, total_batches: int, remaining: int):
        """Print real-time progress."""
        with self.metrics_lock:
            self.metrics.update_throughput()
            processed = self.metrics.processed_texts
            total = self.metrics.total_texts
            eta = self.metrics.calculate_eta(remaining)
            
            progress_pct = (processed / total * 100) if total > 0 else 0
            
            print(f"\n📊 Batch Progress: {processed}/{total} texts ({progress_pct:.1f}%)")
            print(f"   Throughput: {self.metrics.texts_per_sec:.2f} texts/sec | "
                  f"{self.metrics.tokens_per_sec:.2f} tokens/sec")
            print(f"   Batches: {self.metrics.batch_count} completed, "
                  f"{self.metrics.failed_batch_count} failed")
            if eta:
                print(f"   ETA: {eta:.1f}s remaining")
            sys.stdout.flush()
    
    def process(
        self,
        rows: List[Dict[str, Any]],
        pre_computed_glossary: Optional[str] = None,
        progress_callback: Optional[Callable[[BatchMetrics], None]] = None
    ) -> List[Dict[str, Any]]:
        """
        Process rows with optimized batching.
        
        Args:
            rows: List of rows to process, each with 'id' and 'source_text'
            pre_computed_glossary: Optional pre-computed glossary context
            progress_callback: Optional callback for progress updates
        
        Returns:
            List of processed results
        """
        if not rows:
            return []
        
        # Initialize metrics
        self.metrics.total_texts = len(rows)
        self.glossary_context = pre_computed_glossary
        
        # Group similar-length texts if enabled
        if self.config.grouping_enabled:
            groups = group_similar_length_texts(rows, self.config.max_length_variance)
            # Flatten groups back to rows (preserving group ordering)
            rows = [row for group in groups for row in group]
        
        # Create batches with dynamic sizing
        batches = []
        remaining_rows = rows[:]
        
        while remaining_rows:
            # Calculate optimal batch size for remaining rows
            batch_size = self._calculate_batch_size(remaining_rows)
            
            # Take batch
            batch = remaining_rows[:batch_size]
            remaining_rows = remaining_rows[batch_size:]
            
            batches.append(batch)
        
        total_batches = len(batches)
        print(f"📦 Created {total_batches} batches for {len(rows)} texts "
              f"(dynamic sizing: {self.config.dynamic_sizing})")
        
        # Process batches
        results = []
        failed_batches = []
        
        if self.config.max_workers > 1:
            # Parallel processing
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                # Submit all batches
                future_to_index = {
                    executor.submit(self._process_single_batch, batch, i): i 
                    for i, batch in enumerate(batches)
                }
                
                # Collect results
                batch_results = [None] * total_batches
                completed = 0
                
                for future in as_completed(future_to_index):
                    batch_index = future_to_index[future]
                    try:
                        idx, items, error = future.result()
                        batch_results[idx] = (idx, items, error)
                        completed += 1
                        
                        if error:
                            failed_batches.append({"index": idx, "error": error})
                        
                        # Progress update every 5% or on error
                        if completed % max(1, total_batches // 20) == 0 or error:
                            self._print_progress(total_batches, len(rows) - self.metrics.processed_texts)
                            if progress_callback:
                                with self.metrics_lock:
                                    progress_callback(self.metrics)
                            
                    except Exception as e:
                        batch_results[batch_index] = (batch_index, [], str(e))
                        failed_batches.append({"index": batch_index, "error": str(e)})
                        
                        if self.config.fail_fast:
                            executor.shutdown(wait=False)
                            raise
                
                # Reorder results if needed
                if self.config.preserve_order:
                    batch_results.sort(key=lambda x: x[0])
                
                # Collect all results
                for idx, items, error in batch_results:
                    results.extend(items)
        else:
            # Sequential processing
            for i, batch in enumerate(batches):
                idx, items, error = self._process_single_batch(batch, i)
                
                if error:
                    failed_batches.append({"index": i, "error": error})
                
                results.extend(items)
                
                # Progress update
                if (i + 1) % max(1, total_batches // 10) == 0:
                    self._print_progress(total_batches, len(rows) - self.metrics.processed_texts)
                    if progress_callback:
                        with self.metrics_lock:
                            progress_callback(self.metrics)
        
        # Final metrics
        self._print_progress(total_batches, 0)
        self._export_metrics()
        
        # Summary
        print(f"\n{'='*60}")
        print(f"✅ Batch Processing Complete")
        print(f"   Processed: {self.metrics.processed_texts}/{self.metrics.total_texts} texts")
        print(f"   Failed: {self.metrics.failed_texts} texts")
        print(f"   Batches: {self.metrics.batch_count} completed, {self.metrics.failed_batch_count} failed")
        print(f"   Avg Throughput: {self.metrics.texts_per_sec:.2f} texts/sec")
        print(f"{'='*60}")
        
        # Save failed batches report
        if failed_batches:
            failed_path = "reports/batch_optimizer_failed.json"
            try:
                os.makedirs("reports", exist_ok=True)
                with open(failed_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "timestamp": datetime.now().isoformat(),
                        "model": self.model,
                        "total_batches": total_batches,
                        "failed_batches": failed_batches
                    }, f, indent=2)
                print(f"⚠️  Failed batches saved to: {failed_path}")
            except Exception:
                pass
        
        return results


# Convenience function for simple batch processing
def optimized_batch_call(
    step: str,
    rows: List[Dict[str, Any]],
    model: str,
    system_prompt: Union[str, Callable[[List[Dict]], str]],
    user_prompt_template: Callable[[List[Dict]], str],
    content_type: str = "normal",
    retry: int = 1,
    config: Optional[BatchConfig] = None,
    pre_computed_glossary: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Optimized batch LLM call with dynamic sizing and parallel processing.
    
    Args:
        step: Step name for logging
        rows: List of rows with 'id' and 'source_text'
        model: Model name
        system_prompt: System prompt (string or callable)
        user_prompt_template: Function to build user prompt from items
        content_type: "normal" or "long_text"
        retry: Number of retries
        config: Optional BatchConfig (loads from YAML if not provided)
        pre_computed_glossary: Optional pre-computed glossary context
    
    Returns:
        List of processed results
    """
    print(f"\n🚀 Optimized Batch Call: {step}")
    print(f"   Model: {model} | Content Type: {content_type}")
    print(f"   Total rows: {len(rows)}")
    
    processor = BatchProcessor(
        model=model,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
        config=config,
        content_type=content_type,
        retry=retry
    )
    
    return processor.process(rows, pre_computed_glossary)


# Backward-compatible wrapper
def batch_llm_call_optimized(
    step: str,
    rows: List[Dict[str, Any]],
    model: str,
    system_prompt: Union[str, Callable[[List[Dict]], str]],
    user_prompt_template: Callable[[List[Dict]], str],
    content_type: str = "normal",
    retry: int = 1,
    allow_fallback: bool = False,
    partial_match: bool = False,
    save_partial: bool = True,
    output_dir: str = None
) -> List[Dict[str, Any]]:
    """
    Drop-in replacement for runtime_adapter.batch_llm_call with optimizations.
    
    Uses optimized batch processing if enabled in config, otherwise falls back
    to standard batch processing.
    """
    config = BatchConfig.from_yaml()
    
    if not config.dynamic_sizing and config.max_workers <= 1:
        # Use standard batch processing if optimizations disabled
        from runtime_adapter import batch_llm_call
        return batch_llm_call(
            step=step,
            rows=rows,
            model=model,
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            content_type=content_type,
            retry=retry,
            allow_fallback=allow_fallback,
            partial_match=partial_match,
            save_partial=save_partial,
            output_dir=output_dir
        )
    
    # Use optimized processing
    return optimized_batch_call(
        step=step,
        rows=rows,
        model=model,
        system_prompt=system_prompt,
        user_prompt_template=user_prompt_template,
        content_type=content_type,
        retry=retry,
        config=config
    )


if __name__ == "__main__":
    # Example usage
    print("Batch Optimizer Module - Run tests with: python -m pytest tests/test_batch_optimization.py")
