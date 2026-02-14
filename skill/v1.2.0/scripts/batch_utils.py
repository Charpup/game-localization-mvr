#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_utils.py

Universal batch splitting utilities for LLM calls.
Provides token-aware batching and binary-split fallback for parse failures.

Features:
- Token budget estimation (len(text)/4 heuristic)
- Configurable max_items_per_batch, max_tokens_per_batch
- Order preservation
- Binary-split fallback on parse failure
"""

from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Callable

# Token estimation: ~4 chars per token (conservative for CJK/Cyrillic mix)
CHARS_PER_TOKEN = 4


@dataclass
class BatchConfig:
    """Configuration for batch splitting."""
    max_items: int = 20
    max_tokens: int = 6000
    min_items: int = 1
    
    # Token estimation fields to sum
    text_fields: List[str] = field(default_factory=lambda: ["tokenized_zh", "source_zh", "target_text"])


def estimate_tokens(text: str) -> int:
    """Estimate token count from text using chars/4 heuristic."""
    return max(1, len(text or "") // CHARS_PER_TOKEN)


def estimate_row_tokens(row: Dict[str, Any], text_fields: List[str]) -> int:
    """Estimate total tokens for a row by summing text fields."""
    total = 0
    for field in text_fields:
        val = row.get(field, "")
        if isinstance(val, str):
            total += estimate_tokens(val)
    # Add overhead for JSON structure (~20 tokens per item)
    return total + 20


def split_into_batches(
    rows: List[Dict[str, Any]],
    config: Optional[BatchConfig] = None
) -> List[List[Dict[str, Any]]]:
    """
    Split rows into batches respecting item count and token limits.
    
    Args:
        rows: List of row dictionaries
        config: BatchConfig with limits
        
    Returns:
        List of batches, each batch is a list of rows.
        Order is preserved.
    """
    if config is None:
        config = BatchConfig()
    
    if not rows:
        return []
    
    batches: List[List[Dict[str, Any]]] = []
    current_batch: List[Dict[str, Any]] = []
    current_tokens = 0
    
    for row in rows:
        row_tokens = estimate_row_tokens(row, config.text_fields)
        
        # Check if adding this row would exceed limits
        would_exceed_items = len(current_batch) >= config.max_items
        would_exceed_tokens = (current_tokens + row_tokens) > config.max_tokens and len(current_batch) > 0
        
        if would_exceed_items or would_exceed_tokens:
            # Flush current batch
            if current_batch:
                batches.append(current_batch)
            current_batch = [row]
            current_tokens = row_tokens
        else:
            current_batch.append(row)
            current_tokens += row_tokens
    
    # Don't forget the last batch
    if current_batch:
        batches.append(current_batch)
    
    return batches


def binary_split(batch: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Split a batch in half for retry.
    
    Returns:
        (first_half, second_half) - both may be empty if input has <= 1 item
    """
    if len(batch) <= 1:
        return batch, []
    
    mid = len(batch) // 2
    return batch[:mid], batch[mid:]


@dataclass
class BatchResult:
    """Result of processing a batch."""
    batch_idx: int
    success: bool
    items: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    raw_response: Optional[str] = None
    escalated: List[Dict[str, Any]] = field(default_factory=list)


def parse_json_array(text: str) -> Optional[List[Dict[str, Any]]]:
    """
    Parse JSON array from LLM response.
    Handles issues: <thinking> tags, markdown content, prefix/suffix text.
    """
    if not text:
        return None
        
    # 1. Strip <thinking> tags (DotAll)
    text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL).strip()
    
    # 2. Extract from markdown code blocks
    code_block_match = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
    if code_block_match:
        content = code_block_match.group(1).strip()
        try:
            obj = json.loads(content)
            if isinstance(obj, list): return obj
            # Check inner keys
            for key in ["results", "items", "data", "translations"]:
                if isinstance(obj, dict) and key in obj and isinstance(obj[key], list):
                    return obj[key]
        except json.JSONDecodeError:
            text = content # Try falling through with inner content
            
    # 3. Direct parse
    try:
        obj = json.loads(text)
        if isinstance(obj, list): return obj
        for key in ["results", "items", "data", "translations"]:
            if isinstance(obj, dict) and key in obj and isinstance(obj[key], list):
                return obj[key]
    except json.JSONDecodeError:
        pass
        
    # 4. Greedy match: find first '[' to last ']'
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1 and end > start:
        try:
            obj = json.loads(text[start:end + 1])
            if isinstance(obj, list): return obj
        except json.JSONDecodeError:
            pass
            
    return None


def process_batch_with_fallback(
    batch: List[Dict[str, Any]],
    processor: Callable[[List[Dict[str, Any]]], str],
    parser: Callable[[str], Optional[List[Dict[str, Any]]]] = parse_json_array,
    id_field: str = "string_id",
    max_depth: int = 10
) -> BatchResult:
    """
    Process a batch with binary-split fallback on parse failure.
    
    Args:
        batch: Items to process
        processor: Function that takes batch and returns LLM response string
        parser: Function that parses response string to list of dicts
        id_field: Field name for item ID (for escalation)
        max_depth: Maximum recursion depth for binary splitting
        
    Returns:
        BatchResult with all successfully processed items and any escalated items.
    """
    result = BatchResult(batch_idx=0, success=False)
    
    if not batch:
        result.success = True
        return result
    
    # Try full batch
    try:
        response = processor(batch)
        result.raw_response = response
        parsed = parser(response)
        
        if parsed is not None:
            result.success = True
            result.items = parsed
            return result
    except Exception as e:
        result.error = str(e)
    
    # Parse failed - binary split if possible
    if len(batch) == 1:
        # Single item failed - escalate
        result.escalated = [
            {
                id_field: batch[0].get(id_field, "unknown"),
                "reason": f"parse_failed: {result.error or 'invalid JSON'}",
                "raw_output": result.raw_response[:500] if result.raw_response else ""
            }
        ]
        result.success = True  # We handled it (via escalation)
        return result
    
    if max_depth <= 0:
        # Max depth reached - escalate all
        for item in batch:
            result.escalated.append({
                id_field: item.get(id_field, "unknown"),
                "reason": "max_split_depth_reached",
                "raw_output": ""
            })
        result.success = True
        return result
    
    # Binary split and recurse
    left, right = binary_split(batch)
    
    left_result = process_batch_with_fallback(left, processor, parser, id_field, max_depth - 1)
    right_result = process_batch_with_fallback(right, processor, parser, id_field, max_depth - 1)
    
    result.success = left_result.success and right_result.success
    result.items = left_result.items + right_result.items
    result.escalated = left_result.escalated + right_result.escalated
    
    return result


# -----------------------------
# Checkpoint utilities
# -----------------------------

@dataclass 
class BatchCheckpoint:
    """Checkpoint for batch processing with resume support."""
    version: str = "1.0"
    total_batches: int = 0
    completed_batches: int = 0
    completed_ids: Dict[str, bool] = field(default_factory=dict)
    stats: Dict[str, int] = field(default_factory=lambda: {"ok": 0, "fail": 0, "escalated": 0})
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "total_batches": self.total_batches,
            "completed_batches": self.completed_batches,
            "completed_ids": self.completed_ids,
            "stats": self.stats
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchCheckpoint":
        return cls(
            version=data.get("version", "1.0"),
            total_batches=data.get("total_batches", 0),
            completed_batches=data.get("completed_batches", 0),
            completed_ids=data.get("completed_ids", {}),
            stats=data.get("stats", {"ok": 0, "fail": 0, "escalated": 0})
        )


def filter_pending(
    rows: List[Dict[str, Any]], 
    checkpoint: BatchCheckpoint,
    id_field: str = "string_id"
) -> List[Dict[str, Any]]:
    """Filter rows to only those not yet completed."""
    return [r for r in rows if r.get(id_field) not in checkpoint.completed_ids]


# -----------------------------
# Progress reporting
# -----------------------------

def format_progress(
    completed: int,
    total: int,
    batch_idx: int,
    total_batches: int,
    elapsed_s: float,
    batch_time_s: float
) -> str:
    """Format progress string for console output."""
    pct = (completed / total * 100) if total > 0 else 0
    rate = completed / elapsed_s if elapsed_s > 0 else 0
    
    return (
        f"[PROGRESS] {completed}/{total} ({pct:.1f}%) | "
        f"batch {batch_idx}/{total_batches} ({batch_time_s:.1f}s) | "
        f"total={int(elapsed_s)}s | rate={rate:.2f}/s"
    )
