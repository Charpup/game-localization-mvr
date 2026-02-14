#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
translate_llm.py (v6.1 - Caching Enabled)
Purpose:
  Translate tokenized Chinese strings using the unified batch infrastructure.
  - Supports --model argument
  - Dynamically switches to content_type="long_text" if is_long_text is present
  - Preserves token consistency validation
  - Added response caching for cost reduction (v6.1)

Cache Features:
  - SQLite-based persistent cache
  - Cache key: hash(source_text + glossary_hash + model_name)
  - TTL support (configurable, default 7 days)
  - Cache hit/miss statistics
  - Size limits with LRU eviction
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Ensure UTF-8 output on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import yaml
except ImportError:
    yaml = None

# Integrated runtime adapter
try:
    from runtime_adapter import LLMClient, LLMError, batch_llm_call, log_llm_progress
except ImportError:
    print("ERROR: scripts/runtime_adapter.py not found.")
    sys.exit(1)

# Cache manager integration
try:
    from cache_manager import CacheManager, load_cache_config
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False
    print("⚠️  Cache manager not available. Caching disabled.")

# Model Router integration
try:
    from model_router import ModelRouter, ComplexityAnalyzer
    ROUTER_AVAILABLE = True
except ImportError:
    ROUTER_AVAILABLE = False
    print("⚠️  Model Router not available. Using default model selection.")

TOKEN_RE = re.compile(r"⟦(PH_\d+|TAG_\d+)⟧")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")

# -----------------------------
# Glossary & Style Utils
# -----------------------------
@dataclass
class GlossaryEntry:
    term_zh: str
    term_ru: str
    status: str
    notes: str = ""

def build_glossary_constraints(glossary: List[GlossaryEntry], source_zh: str) -> Dict[str, str]:
    approved = {}
    for e in glossary:
        if e.term_zh and e.term_zh in source_zh and e.status.lower() == "approved":
            approved[e.term_zh] = e.term_ru
    return approved

def load_text(p: str) -> str:
    if not Path(p).exists(): return ""
    with open(p, "r", encoding="utf-8") as f:
        return f.read().strip()

def load_glossary(path: str) -> Tuple[List[GlossaryEntry], Optional[str]]:
    if not path or not Path(path).exists() or yaml is None:
        return [], None
    with open(path, "r", encoding="utf-8") as f:
        g = yaml.safe_load(f) or {}
    entries = []
    for it in g.get("entries", []):
        term_zh = (it.get("term_zh") or "").strip()
        term_ru = (it.get("term_ru") or "").strip()
        status = (it.get("status") or "").lower().strip()
        if term_zh and status == "approved":
            entries.append(GlossaryEntry(term_zh, term_ru, status))
    meta = g.get("meta", {})
    return entries, meta.get("compiled_hash")

def build_glossary_summary(glossary: List[GlossaryEntry]) -> str:
    if not glossary: return "(无)"
    return "\n".join([f"- {e.term_zh} → {e.term_ru}" for e in glossary[:50]])

# -----------------------------
# Token Validation
# -----------------------------
def tokens_signature(text: str) -> Dict[str, int]:
    counts = {}
    for m in TOKEN_RE.finditer(text or ""):
        counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts

def validate_translation(tokenized_zh: str, ru: str) -> Tuple[bool, str]:
    if tokens_signature(tokenized_zh) != tokens_signature(ru):
        return False, "token_mismatch"
    if CJK_RE.search(ru or ""):
        return False, "cjk_remaining"
    if not (ru or "").strip() and (tokenized_zh or "").strip():
        return False, "empty"
    return True, "ok"

# -----------------------------
# Prompt Builders
# -----------------------------
def build_system_prompt_factory(style_guide: str, glossary_summary: str):
    """Factory to create a dynamic system prompt builder."""
    def _builder(rows: List[Dict]) -> str:
        constraints = ""
        for r in rows:
            max_len = r.get("max_length_target") or r.get("max_len_target")
            if max_len and int(max_len) > 0:
                constraints += f"- Row {r.get('string_id')}: max {max_len} chars\n"
        
        constraint_section = ""
        if constraints:
            constraint_section = (
                f"\n【Length Constraints (Mandatory)】\n"
                f"Each translation MUST NOT exceed its limit:\n{constraints}\n"
                f"If too long: use abbreviations/synonyms but preserve meaning.\n"
            )

        return (
            '你是严谨的手游本地化译者（zh-CN → ru-RU）。\n\n'
            '【Output Contract v6】\n'
            '1. Output MUST be valid JSON (Object with "items" key).\n'
            '2. Structure MUST be: {"items": [{"id": "...", "target_ru": "..."}]}\n'
            '3. Every input "id" MUST appear in the output.\n\n'
            '【Translation Rules】\n'
            '- 术语匹配必须一致。\n'
            '- 占位符 ⟦PH_xx⟧ / ⟦TAG_xx⟧ 必须保留。\n'
            '- 禁止中文括号【】。\n'
            f'{constraint_section}\n'
            f'术语表摘要：\n{glossary_summary}\n\n'
            f'style_guide：\n{style_guide}\n'
        )
    return _builder

def build_user_prompt(rows: List[Dict]) -> str:
    # rows are items prepared for batch_llm_call
    return json.dumps(rows, ensure_ascii=False, indent=2)

# -----------------------------
# Checkpoint Logic
# -----------------------------
def load_checkpoint(path: str) -> set:
    if not Path(path).exists(): return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return set(data.get("done_ids", []))
    except: return set()

def save_checkpoint(path: str, done_ids: set):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"done_ids": list(done_ids)}, f)

# -----------------------------
# Cache Integration Helpers
# -----------------------------
def process_with_cache(
    pending_rows: List[Dict],
    cache: Optional[CacheManager],
    model: str,
    glossary_hash: Optional[str],
    system_prompt_builder,
    content_type: str,
    use_cache: bool = True
) -> Tuple[List[Dict], List[Dict], Dict[str, str]]:
    """
    Process rows with cache lookup. Returns (cached_results, rows_to_translate, cache_map).
    
    Args:
        pending_rows: All rows pending translation
        cache: CacheManager instance or None
        model: Model name for cache key
        glossary_hash: Glossary hash for cache key
        system_prompt_builder: Function to build system prompt
        content_type: Content type for batch call
        use_cache: Whether to use caching
        
    Returns:
        Tuple of (cached_results, rows_for_llm, cache_result_map)
    """
    if not use_cache or cache is None:
        return [], pending_rows, {}
    
    cached_results = []
    rows_for_llm = []
    cache_map = {}
    
    for row in pending_rows:
        source_text = row.get("tokenized_zh") or row.get("source_zh") or ""
        
        # Check cache
        hit, cached_translation = cache.get(source_text, glossary_hash, model)
        
        if hit and cached_translation:
            # Validate cached result
            ok, err = validate_translation(source_text, cached_translation)
            if ok:
                cached_results.append({
                    **row,
                    "target_text": cached_translation,
                    "from_cache": True
                })
                cache_map[row.get("string_id")] = cached_translation
                continue
        
        rows_for_llm.append(row)
    
    return cached_results, rows_for_llm, cache_map

def store_results_in_cache(
    results: List[Dict],
    cache: Optional[CacheManager],
    model: str,
    glossary_hash: Optional[str]
) -> int:
    """
    Store successful translations in cache.
    
    Returns:
        Number of entries stored
    """
    if cache is None:
        return 0
    
    stored = 0
    for result in results:
        source_text = result.get("tokenized_zh") or result.get("source_zh") or ""
        translated_text = result.get("target_text", "")
        
        if source_text and translated_text:
            if cache.set(source_text, translated_text, glossary_hash, model):
                stored += 1
    
    return stored

def print_cache_stats(cache: Optional[CacheManager]) -> None:
    """Print cache statistics."""
    if cache is None:
        return
    
    stats = cache.get_stats()
    size_info = cache.get_size()
    
    print("\n📊 Cache Statistics:")
    print(f"   Hits: {stats.hits}")
    print(f"   Misses: {stats.misses}")
    print(f"   Hit Rate: {stats.hit_rate:.2%}")
    if stats.hit_rate > 0:
        print(f"   💰 Cost Savings: {stats.hit_rate:.1%} (cache hits = zero cost)")
    print(f"   Cache Size: {size_info['total_mb']:.2f} MB / {size_info['max_mb']} MB")


# -----------------------------
# Model Router Integration Helpers
# -----------------------------
def get_model_router() -> Optional[ModelRouter]:
    """Initialize and return ModelRouter if available."""
    if not ROUTER_AVAILABLE:
        return None
    try:
        return ModelRouter()
    except Exception as e:
        print(f"⚠️  Model Router initialization failed: {e}")
        return None

def select_model_with_routing(
    router: Optional[ModelRouter],
    texts: List[str],
    default_model: str,
    glossary_terms: Optional[List[str]] = None,
    step: str = "translate",
    force_model: Optional[str] = None
) -> Tuple[str, float, List[Any]]:
    """
    Select model using intelligent routing.
    
    Returns:
        Tuple of (selected_model, complexity_score, metrics_list)
    """
    if router is None or not router.enabled:
        # No router available, use default
        return default_model, 0.0, []
    
    if force_model:
        # Forced model override
        return force_model, 0.0, []
    
    # Use batch model selection
    model, complexity, metrics = router.select_model_for_batch(
        texts=texts,
        step=step,
        glossary_terms=glossary_terms,
        force_model=None
    )
    
    return model, complexity, metrics

def get_glossary_terms(glossary: List[GlossaryEntry]) -> List[str]:
    """Extract glossary term strings for complexity analysis."""
    return [e.term_zh for e in glossary if e.term_zh]

# -----------------------------
# Main Process
# -----------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="claude-haiku-4-5-20251001")
    parser.add_argument("--style", default="workflow/style_guide.md")
    parser.add_argument("--glossary", default="data/glossary.yaml")
    parser.add_argument("--checkpoint", default="data/translate_checkpoint.json")
    parser.add_argument("--batch_size", type=int, default=10)
    parser.add_argument("--no-cache", action="store_true", help="Disable cache lookup")
    parser.add_argument("--cache-clear", action="store_true", help="Clear cache before running")
    parser.add_argument("--no-routing", action="store_true", help="Disable intelligent model routing")
    parser.add_argument("--force-model", help="Force specific model (overrides routing)")
    args = parser.parse_args()

    print(f"🚀 Translate LLM v6.2 (Model Router Enabled)")
    
    # Initialize model router
    router = None
    if not args.no_routing:
        router = get_model_router()
        if router and router.enabled:
            print(f"🧠 Model Router enabled: default={router.default_model}")
        elif ROUTER_AVAILABLE:
            print("ℹ️  Model Router available but disabled in config")
    else:
        print("🚫 Model Routing disabled (--no-routing)")
    
    # Initialize cache manager
    cache = None
    cache_hits = 0
    cache_misses = 0
    
    if CACHE_AVAILABLE and not args.no_cache:
        try:
            config = load_cache_config("config/pipeline.yaml")
            cache = CacheManager(config)
            
            if args.cache_clear:
                cleared = cache.clear()
                print(f"🗑️  Cleared {cleared} cache entries")
            
            print(f"💾 Cache enabled: {config.location}")
            print(f"   TTL: {config.ttl_days} days, Max Size: {config.max_size_mb} MB")
        except Exception as e:
            print(f"⚠️  Cache initialization failed: {e}")
            cache = None
    elif args.no_cache:
        print("🚫 Cache disabled (--no-cache)")
    
    # Load resources
    style_guide = load_text(args.style)
    glossary, glossary_hash = load_glossary(args.glossary)
    glossary_summary = build_glossary_summary(glossary)
    
    # Read CSV
    if not Path(args.input).exists():
        print(f"❌ Input not found: {args.input}")
        return
    
    with open(args.input, "r", encoding="utf-8-sig") as f:
        all_rows = list(csv.DictReader(f))
    
    headers = list(all_rows[0].keys()) if all_rows else []
    if "target_text" not in headers: headers.append("target_text")
    if "from_cache" not in headers: headers.append("from_cache")
    
    # Checkpoint
    done_ids = load_checkpoint(args.checkpoint)
    pending_rows = [r for r in all_rows if r.get("string_id") not in done_ids]
    
    if not pending_rows:
        print("✅ No pending rows to process.")
        if cache:
            print_cache_stats(cache)
        if router:
            stats = router.get_routing_stats()
            if stats["total_routings"] > 0:
                print("\n🧠 Model Router Statistics:")
                print(f"   Total routings: {stats['total_routings']}")
                print(f"   Avg complexity: {stats['average_complexity']:.2f}")
                print(f"   Model distribution: {stats['model_distribution']}")
        return

    print(f"   Total rows: {len(all_rows)}, Pending: {len(pending_rows)}")
    
    # Model selection with intelligent routing
    glossary_term_list = get_glossary_terms(glossary)
    source_texts = [r.get("tokenized_zh") or r.get("source_zh") or "" for r in pending_rows]
    
    selected_model, complexity_score, complexity_metrics = select_model_with_routing(
        router=router,
        texts=source_texts,
        default_model=args.model,
        glossary_terms=glossary_term_list,
        step="translate",
        force_model=args.force_model
    )
    
    # Check if routing selected a different model
    if selected_model != args.model and not args.force_model:
        print(f"🎯 Model Router selected: {selected_model} (was: {args.model})")
        if complexity_score > 0:
            print(f"   Batch complexity: {complexity_score:.2f}")
    else:
        print(f"   Using model: {selected_model}")
    
    # Detect long text status for ANY row in the pending set
    has_long_text = any(
        str(r.get("is_long_text", "0")) == "1" or r.get("is_long_text") == 1
        for r in pending_rows
    )
    content_type = "long_text" if has_long_text else "normal"
    
    if has_long_text:
        print("   [Tagger Hint] Long text detected. Using content_type='long_text' for lower batch density.")

    # Process with cache (using selected_model for cache key)
    cached_results, rows_for_llm, cache_map = process_with_cache(
        pending_rows=pending_rows,
        cache=cache,
        model=selected_model,
        glossary_hash=glossary_hash,
        system_prompt_builder=build_system_prompt_factory(style_guide, glossary_summary),
        content_type=content_type,
        use_cache=(cache is not None and not args.no_cache)
    )
    
    cache_hits = len(cached_results)
    
    print(f"\n📋 Translation Plan:")
    print(f"   Cache hits: {cache_hits} (zero cost)")
    print(f"   LLM calls needed: {len(rows_for_llm)}")
    
    # Prepare results
    all_final_rows = list(cached_results)  # Start with cached results
    new_done = set()
    
    # Mark cached results as done
    for r in cached_results:
        new_done.add(str(r.get("string_id")))
    
    # Process rows that need LLM call
    if rows_for_llm:
        # Prepare for batch_llm_call
        batch_inputs = []
        for r in rows_for_llm:
            src = r.get("tokenized_zh") or r.get("source_zh") or ""
            batch_inputs.append({
                "id": r.get("string_id"),
                "source_text": src
            })

        try:
            system_prompt_builder = build_system_prompt_factory(style_guide, glossary_summary)
            
            results = batch_llm_call(
                step="translate",
                rows=batch_inputs,
                model=selected_model,
                system_prompt=system_prompt_builder,
                user_prompt_template=build_user_prompt,
                content_type=content_type,
                retry=2,
                allow_fallback=True
            )
            
            # Merge results back to original rows
            res_map = {str(it.get("id")): it.get("target_ru", "") for it in results}
            
            # Process LLM results
            llm_results = []
            for r in rows_for_llm:
                sid = str(r.get("string_id"))
                ru = res_map.get(sid, "")
                
                # Validation
                ok, err = validate_translation(r.get("tokenized_zh") or r.get("source_zh") or "", ru)
                if ok:
                    row_copy = dict(r)
                    row_copy["target_text"] = ru
                    row_copy["from_cache"] = False
                    llm_results.append(row_copy)
                    new_done.add(sid)
                else:
                    print(f"⚠️  Validation failed for {sid}: {err}")
            
            # Store successful translations in cache
            if cache and not args.no_cache:
                stored = store_results_in_cache(llm_results, cache, selected_model, glossary_hash)
                print(f"💾 Stored {stored} translations in cache")
            
            all_final_rows.extend(llm_results)
            
        except Exception as e:
            print(f"❌ Translation failed: {e}")
            # Still write cached results if we have them
            if not all_final_rows:
                sys.exit(1)
    
    # Write Output
    if all_final_rows:
        write_mode = "a" if Path(args.output).exists() else "w"
        with open(args.output, write_mode, encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            if write_mode == "w": writer.writeheader()
            writer.writerows(all_final_rows)
        
        # Update checkpoint
        done_ids.update(new_done)
        save_checkpoint(args.checkpoint, done_ids)
        
        print(f"\n✅ Processed {len(new_done)} / {len(pending_rows)} rows:")
        print(f"   From cache: {cache_hits}")
        print(f"   From LLM: {len(new_done) - cache_hits}")
    
    # Print final cache stats
    if cache:
        print_cache_stats(cache)
        cache.close()
    
    # Print Model Router stats
    if router and not args.no_routing:
        print("\n🧠 Model Router Statistics:")
        stats = router.get_routing_stats()
        if stats["total_routings"] > 0:
            print(f"   Total routings: {stats['total_routings']}")
            print(f"   Average complexity: {stats['average_complexity']:.4f}")
            print(f"   Model distribution:")
            for model, info in stats["model_distribution"].items():
                print(f"      {model}: {info['count']} ({info['percentage']}%)")
            
            # Cost comparison
            comparison = router.get_cost_comparison(baseline_model="kimi-k2.5")
            if comparison.get("savings_percent", 0) > 0:
                print(f"\n   💰 Cost Savings vs kimi-k2.5 baseline:")
                print(f"      Savings: ${comparison['savings_usd']:.6f} ({comparison['savings_percent']}%)")
            
            # Save routing history
            router.save_routing_history("reports/model_router_history.json")
        else:
            print("   No routing decisions made (all from cache)")

if __name__ == "__main__":
    main()
