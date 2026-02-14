#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
model_router.py (v1.0 - Intelligent Model Router)

Purpose:
  Route LLM requests to different models based on content complexity analysis.
  Optimizes cost/quality trade-offs by selecting cheaper models for simple text
  and better models for complex text.

Key Features:
  - Complexity scoring based on text length, placeholders, special chars, glossary density
  - Historical QA failure rate tracking per text pattern
  - Cost tracking per model with configurable pricing
  - Seamless integration with existing runtime_adapter

Usage:
    from model_router import ModelRouter, ComplexityAnalyzer
    
    router = ModelRouter()
    model = router.select_model(
        text="Your text to translate",
        step="translate",
        glossary_terms=["term1", "term2"]
    )
    
    # Or use the integrated client
    result = router.translate_with_routing(text, step="translate")
"""

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Set, Callable
from collections import defaultdict
import hashlib

try:
    import yaml
except ImportError:
    yaml = None

# Import existing runtime adapter components
try:
    from runtime_adapter import (
        LLMClient, LLMError, LLMResult, 
        batch_llm_call, log_llm_progress,
        _estimate_tokens, _estimate_cost
    )
except ImportError:
    # Define minimal fallback if runtime_adapter not available
    class LLMError(Exception):
        def __init__(self, kind: str, message: str, retryable: bool = True):
            super().__init__(message)
            self.kind = kind
            self.retryable = retryable
    
    LLMResult = dict
    LLMClient = None


# -----------------------------
# Constants & Patterns
# -----------------------------
PLACEHOLDER_RE = re.compile(r"⟦(PH_\d+|TAG_\d+|\w+)⟧|\{(\w+)\}|<(\w+)>|")
SPECIAL_CHARS_RE = re.compile(r"[^\w\s\u4e00-\u9fff]")
CJK_RE = re.compile(r"[\u4e00-\u9fff]")
WHITESPACE_RE = re.compile(r"\s+")


# -----------------------------
# Data Classes
# -----------------------------
@dataclass
class ComplexityMetrics:
    """Metrics for text complexity analysis."""
    text_length: int = 0
    char_count: int = 0
    word_count: int = 0
    cjk_count: int = 0
    placeholder_count: int = 0
    placeholder_density: float = 0.0  # placeholders per 100 chars
    special_char_count: int = 0
    special_char_density: float = 0.0
    glossary_term_count: int = 0
    glossary_term_density: float = 0.0  # glossary terms per 100 chars
    sentence_count: int = 0
    avg_word_length: float = 0.0
    complexity_score: float = 0.0  # 0.0 - 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text_length": self.text_length,
            "char_count": self.char_count,
            "word_count": self.word_count,
            "cjk_count": self.cjk_count,
            "placeholder_count": self.placeholder_count,
            "placeholder_density": round(self.placeholder_density, 4),
            "special_char_count": self.special_char_count,
            "special_char_density": round(self.special_char_density, 4),
            "glossary_term_count": self.glossary_term_count,
            "glossary_term_density": round(self.glossary_term_density, 4),
            "sentence_count": self.sentence_count,
            "avg_word_length": round(self.avg_word_length, 2),
            "complexity_score": round(self.complexity_score, 4)
        }


@dataclass
class RoutingDecision:
    """Record of a routing decision."""
    timestamp: str
    text_hash: str
    text_preview: str
    step: str
    selected_model: str
    complexity_metrics: ComplexityMetrics
    complexity_score: float
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    estimated_cost: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "text_hash": self.text_hash,
            "text_preview": self.text_preview[:100] if self.text_preview else "",
            "step": self.step,
            "selected_model": self.selected_model,
            "complexity_metrics": self.complexity_metrics.to_dict(),
            "complexity_score": round(self.complexity_score, 4),
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "estimated_cost": round(self.estimated_cost, 6)
        }


@dataclass
class ModelConfig:
    """Configuration for a model in the routing table."""
    name: str
    cost_per_1k: float  # USD per 1K tokens
    max_complexity: float = 1.0  # Maximum complexity this model can handle
    batch_capable: bool = True
    quality_tier: str = "medium"  # low, medium, high
    fallback_to: Optional[str] = None
    
    def estimate_cost(self, prompt_tokens: int, completion_tokens: int = 0) -> float:
        """Estimate cost for given token counts."""
        total_tokens = prompt_tokens + completion_tokens
        return (total_tokens / 1000) * self.cost_per_1k


# -----------------------------
# Complexity Analyzer
# -----------------------------
class ComplexityAnalyzer:
    """
    Analyze text complexity for model routing decisions.
    
    Factors considered:
    1. Text length (longer = more complex)
    2. Placeholder density (more placeholders = more complex)
    3. Special character density (more special chars = more complex)
    4. Glossary term density (more terms = more complex)
    5. Historical QA failure rate (tracked separately)
    """
    
    # Weight configuration for complexity factors
    DEFAULT_WEIGHTS = {
        "length": 0.20,
        "placeholder_density": 0.25,
        "special_char_density": 0.15,
        "glossary_density": 0.25,
        "historical_failure": 0.15
    }
    
    # Thresholds for normalization
    LENGTH_THRESHOLDS = {
        "short": 50,      # chars
        "medium": 150,
        "long": 300,
        "very_long": 500
    }
    
    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self._failure_history: Dict[str, float] = {}
        self._pattern_failure_rate: Dict[str, Dict[str, float]] = defaultdict(
            lambda: {"failures": 0, "total": 0, "rate": 0.0}
        )
        self._load_failure_history()
    
    def _get_text_hash(self, text: str) -> str:
        """Generate hash for text identification."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()[:16]
    
    def _load_failure_history(self):
        """Load historical QA failure data."""
        history_path = os.getenv("MODEL_ROUTER_HISTORY_PATH", 
                                  "data/model_router_history.json")
        if Path(history_path).exists():
            try:
                with open(history_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._pattern_failure_rate = defaultdict(
                        lambda: {"failures": 0, "total": 0, "rate": 0.0},
                        data.get("patterns", {})
                    )
            except Exception:
                pass
    
    def _save_failure_history(self):
        """Save historical QA failure data."""
        history_path = os.getenv("MODEL_ROUTER_HISTORY_PATH",
                                  "data/model_router_history.json")
        Path(history_path).parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(history_path, 'w', encoding='utf-8') as f:
                json.dump({
                    "patterns": dict(self._pattern_failure_rate),
                    "updated_at": datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def _extract_pattern(self, text: str) -> str:
        """Extract pattern signature from text for failure tracking."""
        # Normalize text for pattern matching
        normalized = text.lower()
        # Replace placeholders with generic markers
        normalized = PLACEHOLDER_RE.sub("{PH}", normalized)
        # Replace CJK with marker
        normalized = CJK_RE.sub("{CJK}", normalized)
        # Take first 50 chars as pattern signature
        return normalized[:50]
    
    def record_failure(self, text: str, failure_type: str = "qa_fail"):
        """Record a QA failure for pattern tracking."""
        pattern = self._extract_pattern(text)
        self._pattern_failure_rate[pattern]["failures"] += 1
        self._pattern_failure_rate[pattern]["total"] += 1
        # Recalculate rate
        total = self._pattern_failure_rate[pattern]["total"]
        failures = self._pattern_failure_rate[pattern]["failures"]
        self._pattern_failure_rate[pattern]["rate"] = failures / total if total > 0 else 0.0
        self._save_failure_history()
    
    def record_success(self, text: str):
        """Record a successful translation for pattern tracking."""
        pattern = self._extract_pattern(text)
        self._pattern_failure_rate[pattern]["total"] += 1
        total = self._pattern_failure_rate[pattern]["total"]
        failures = self._pattern_failure_rate[pattern]["failures"]
        self._pattern_failure_rate[pattern]["rate"] = failures / total if total > 0 else 0.0
        self._save_failure_history()
    
    def analyze(self, text: str, glossary_terms: Optional[List[str]] = None) -> ComplexityMetrics:
        """
        Analyze text and return complexity metrics.
        
        Args:
            text: Text to analyze
            glossary_terms: List of glossary terms to check for
            
        Returns:
            ComplexityMetrics with detailed analysis
        """
        if not text:
            return ComplexityMetrics()
        
        metrics = ComplexityMetrics()
        
        # Basic counts
        metrics.text_length = len(text)
        metrics.char_count = len(text.replace(" ", "").replace("\n", ""))
        
        # Word count (split by whitespace)
        words = WHITESPACE_RE.split(text.strip())
        metrics.word_count = len([w for w in words if w])
        metrics.avg_word_length = metrics.char_count / max(metrics.word_count, 1)
        
        # CJK characters
        metrics.cjk_count = len(CJK_RE.findall(text))
        
        # Placeholder analysis
        placeholders = PLACEHOLDER_RE.findall(text)
        metrics.placeholder_count = len([p for p in placeholders if any(p)])
        metrics.placeholder_density = (metrics.placeholder_count / max(metrics.text_length, 1)) * 100
        
        # Special character analysis
        special_chars = SPECIAL_CHARS_RE.findall(text)
        metrics.special_char_count = len(special_chars)
        metrics.special_char_density = (metrics.special_char_count / max(metrics.text_length, 1)) * 100
        
        # Sentence count (rough estimate)
        sentence_endings = text.count('。') + text.count('．') + text.count('.') + \
                          text.count('！') + text.count('!') + \
                          text.count('？') + text.count('?')
        metrics.sentence_count = max(sentence_endings, 1)
        
        # Glossary term analysis
        if glossary_terms:
            metrics.glossary_term_count = sum(1 for term in glossary_terms if term in text)
            metrics.glossary_term_density = (metrics.glossary_term_count / max(metrics.text_length, 1)) * 100
        
        # Calculate overall complexity score
        metrics.complexity_score = self._calculate_complexity_score(metrics, text)
        
        return metrics
    
    def _calculate_complexity_score(self, metrics: ComplexityMetrics, text: str) -> float:
        """Calculate overall complexity score from 0.0 to 1.0."""
        scores = {}
        
        # Length score (0-1 based on thresholds)
        length = metrics.text_length
        if length <= self.LENGTH_THRESHOLDS["short"]:
            scores["length"] = 0.1
        elif length <= self.LENGTH_THRESHOLDS["medium"]:
            scores["length"] = 0.3
        elif length <= self.LENGTH_THRESHOLDS["long"]:
            scores["length"] = 0.6
        else:
            scores["length"] = min(1.0, 0.7 + (length - self.LENGTH_THRESHOLDS["long"]) / 1000)
        
        # Placeholder density score (normalize to 0-1, cap at 5 per 100 chars)
        scores["placeholder_density"] = min(1.0, metrics.placeholder_density / 5.0)
        
        # Special char density score (normalize to 0-1, cap at 10 per 100 chars)
        scores["special_char_density"] = min(1.0, metrics.special_char_density / 10.0)
        
        # Glossary density score (normalize to 0-1, cap at 3 per 100 chars)
        scores["glossary_density"] = min(1.0, metrics.glossary_term_density / 3.0)
        
        # Historical failure rate for similar patterns
        pattern = self._extract_pattern(text)
        historical_rate = self._pattern_failure_rate[pattern]["rate"]
        scores["historical_failure"] = historical_rate
        
        # Weighted sum
        total_score = 0.0
        for factor, weight in self.weights.items():
            total_score += scores.get(factor, 0.0) * weight
        
        return min(1.0, max(0.0, total_score))
    
    def get_historical_failure_rate(self, text: str) -> float:
        """Get historical failure rate for text pattern."""
        pattern = self._extract_pattern(text)
        return self._pattern_failure_rate[pattern]["rate"]


# -----------------------------
# Model Router
# -----------------------------
class ModelRouter:
    """
    Intelligent model router for cost/quality optimization.
    
    Routes requests to different models based on content complexity,
    with support for cost tracking and historical performance.
    """
    
    DEFAULT_CONFIG_PATH = "config/model_routing.yaml"
    
    # Default model configurations
    DEFAULT_MODELS = {
        "gpt-3.5-turbo": ModelConfig(
            name="gpt-3.5-turbo",
            cost_per_1k=0.0015,
            max_complexity=0.5,
            batch_capable=True,
            quality_tier="medium",
            fallback_to=None
        ),
        "kimi-k2.5": ModelConfig(
            name="kimi-k2.5",
            cost_per_1k=0.012,
            max_complexity=1.0,
            batch_capable=True,
            quality_tier="high",
            fallback_to=None
        ),
        "gpt-4": ModelConfig(
            name="gpt-4",
            cost_per_1k=0.03,
            max_complexity=1.0,
            batch_capable=True,
            quality_tier="high",
            fallback_to="kimi-k2.5"
        ),
        "claude-haiku-4-5-20251001": ModelConfig(
            name="claude-haiku-4-5-20251001",
            cost_per_1k=0.008,
            max_complexity=0.7,
            batch_capable=True,
            quality_tier="medium",
            fallback_to="claude-sonnet-4-5-20250929"
        ),
        "claude-sonnet-4-5-20250929": ModelConfig(
            name="claude-sonnet-4-5-20250929",
            cost_per_1k=0.024,
            max_complexity=1.0,
            batch_capable=True,
            quality_tier="high",
            fallback_to=None
        ),
        "gpt-4.1-mini": ModelConfig(
            name="gpt-4.1-mini",
            cost_per_1k=0.004,
            max_complexity=0.6,
            batch_capable=True,
            quality_tier="medium",
            fallback_to="gpt-4.1"
        ),
        "gpt-4.1": ModelConfig(
            name="gpt-4.1",
            cost_per_1k=0.02,
            max_complexity=1.0,
            batch_capable=False,  # Not suitable for batch
            quality_tier="high",
            fallback_to=None
        ),
        "gpt-4.1-nano": ModelConfig(
            name="gpt-4.1-nano",
            cost_per_1k=0.001,
            max_complexity=0.4,
            batch_capable=True,
            quality_tier="low",
            fallback_to="gpt-4.1-mini"
        )
    }
    
    def __init__(self, config_path: Optional[str] = None, 
                 llm_client: Optional[Any] = None,
                 analyzer: Optional[ComplexityAnalyzer] = None):
        """
        Initialize the model router.
        
        Args:
            config_path: Path to model routing configuration
            llm_client: LLMClient instance (will create one if not provided)
            analyzer: ComplexityAnalyzer instance (will create one if not provided)
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = self._load_config()
        self.analyzer = analyzer or ComplexityAnalyzer()
        self.llm_client = llm_client
        
        # Initialize models from config or defaults
        self.models: Dict[str, ModelConfig] = self._initialize_models()
        
        # Routing statistics
        self.routing_history: List[RoutingDecision] = []
        self.cost_tracking: Dict[str, Dict[str, float]] = defaultdict(lambda: {
            "calls": 0,
            "tokens_in": 0,
            "tokens_out": 0,
            "cost_usd": 0.0
        })
        
        # Trace configuration
        self.trace_path = os.getenv("MODEL_ROUTER_TRACE_PATH", 
                                     "data/model_router_trace.jsonl")
        
        self.enabled = self.config.get("enabled", True) if self.config else True
        self.default_model = self.config.get("default_model", "kimi-k2.5") if self.config else "kimi-k2.5"
        self.complexity_threshold = self.config.get("complexity_threshold", 0.7) if self.config else 0.7
        
        self._trace({
            "type": "router_init",
            "enabled": self.enabled,
            "default_model": self.default_model,
            "complexity_threshold": self.complexity_threshold,
            "models_loaded": list(self.models.keys())
        })
    
    def _load_config(self) -> Dict[str, Any]:
        """Load model routing configuration."""
        if yaml is None:
            return {}
        
        # Try multiple paths
        paths_to_try = [
            self.config_path,
            os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                        self.config_path),
            "config/model_routing.yaml",
            "../config/model_routing.yaml"
        ]
        
        for path in paths_to_try:
            if Path(path).exists():
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        return yaml.safe_load(f) or {}
                except Exception as e:
                    print(f"Warning: Could not load config from {path}: {e}")
        
        return {}
    
    def _initialize_models(self) -> Dict[str, ModelConfig]:
        """Initialize models from config or defaults."""
        models = {}
        
        # Load from config if available
        if self.config and "models" in self.config:
            for m in self.config["models"]:
                name = m.get("name")
                if name:
                    models[name] = ModelConfig(
                        name=name,
                        cost_per_1k=m.get("cost_per_1k", 0.01),
                        max_complexity=m.get("max_complexity", 1.0),
                        batch_capable=m.get("batch_capable", True),
                        quality_tier=m.get("quality_tier", "medium"),
                        fallback_to=m.get("fallback_to")
                    )
        
        # Fill in defaults for missing models
        for name, config in self.DEFAULT_MODELS.items():
            if name not in models:
                models[name] = config
        
        return models
    
    def _trace(self, event: Dict[str, Any]):
        """Append trace event to JSONL file."""
        if not self.trace_path:
            return
        try:
            Path(self.trace_path).parent.mkdir(parents=True, exist_ok=True)
            event["timestamp"] = datetime.now().isoformat()
            with open(self.trace_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception:
            pass
    
    def _get_text_hash(self, text: str) -> str:
        """Generate short hash for text."""
        return hashlib.md5(text.encode('utf-8')).hexdigest()[:16]
    
    def analyze_complexity(self, text: str, 
                          glossary_terms: Optional[List[str]] = None) -> ComplexityMetrics:
        """Analyze text complexity."""
        return self.analyzer.analyze(text, glossary_terms)
    
    def select_model(self, text: str, 
                    step: str = "translate",
                    glossary_terms: Optional[List[str]] = None,
                    force_model: Optional[str] = None,
                    is_batch: bool = False) -> Tuple[str, ComplexityMetrics, float]:
        """
        Select appropriate model for text based on complexity.
        
        Args:
            text: Text to process
            step: Processing step (translate, qa, etc)
            glossary_terms: List of glossary terms for complexity analysis
            force_model: Override routing and use this model
            is_batch: Whether this is a batch operation
            
        Returns:
            Tuple of (selected_model_name, complexity_metrics, estimated_cost)
        """
        # If routing disabled or forced model, skip analysis
        if not self.enabled or force_model:
            model_name = force_model or self.default_model
            metrics = self.analyze_complexity(text, glossary_terms) if self.enabled else ComplexityMetrics()
            model_config = self.models.get(model_name, self.DEFAULT_MODELS.get("kimi-k2.5"))
            estimated_tokens = _estimate_tokens(text) if '_estimate_tokens' in dir() else len(text) // 4
            cost = model_config.estimate_cost(estimated_tokens, estimated_tokens // 2)
            return model_name, metrics, cost
        
        # Analyze complexity
        metrics = self.analyze_complexity(text, glossary_terms)
        complexity = metrics.complexity_score
        
        # Find cheapest model that can handle this complexity
        suitable_models = []
        for name, config in self.models.items():
            # Check complexity capability
            if config.max_complexity >= complexity:
                # Check batch capability if needed
                if not is_batch or config.batch_capable:
                    suitable_models.append(config)
        
        if not suitable_models:
            # No suitable model found, use default
            selected_model = self.default_model
            fallback_reason = f"No model found for complexity {complexity:.2f}"
        else:
            # Sort by cost and select cheapest
            suitable_models.sort(key=lambda m: m.cost_per_1k)
            selected_config = suitable_models[0]
            selected_model = selected_config.name
            fallback_reason = None
        
        # Estimate cost
        estimated_tokens = len(text) // 4  # Rough estimate
        model_config = self.models.get(selected_model, self.DEFAULT_MODELS.get("kimi-k2.5"))
        estimated_cost = model_config.estimate_cost(estimated_tokens, estimated_tokens // 2)
        
        # Record routing decision
        decision = RoutingDecision(
            timestamp=datetime.now().isoformat(),
            text_hash=self._get_text_hash(text),
            text_preview=text[:200],
            step=step,
            selected_model=selected_model,
            complexity_metrics=metrics,
            complexity_score=complexity,
            fallback_reason=fallback_reason,
            estimated_cost=estimated_cost
        )
        self.routing_history.append(decision)
        
        # Trace routing decision
        self._trace({
            "type": "routing_decision",
            "step": step,
            "text_hash": decision.text_hash,
            "complexity": round(complexity, 4),
            "selected_model": selected_model,
            "estimated_cost": round(estimated_cost, 6),
            "fallback_reason": fallback_reason,
            "is_batch": is_batch
        })
        
        return selected_model, metrics, estimated_cost
    
    def select_model_for_batch(self, texts: List[str],
                              step: str = "translate",
                              glossary_terms: Optional[List[str]] = None,
                              force_model: Optional[str] = None) -> Tuple[str, float, List[ComplexityMetrics]]:
        """
        Select model for a batch of texts.
        Uses the highest complexity in the batch for selection.
        
        Args:
            texts: List of texts to process
            step: Processing step
            glossary_terms: Glossary terms for analysis
            force_model: Override routing
            
        Returns:
            Tuple of (selected_model_name, batch_complexity_score, list_of_metrics)
        """
        if not texts:
            return self.default_model, 0.0, []
        
        # Analyze all texts
        all_metrics = []
        max_complexity = 0.0
        total_estimated_tokens = 0
        
        for text in texts:
            metrics = self.analyze_complexity(text, glossary_terms)
            all_metrics.append(metrics)
            max_complexity = max(max_complexity, metrics.complexity_score)
            total_estimated_tokens += len(text) // 4
        
        # Use max complexity for model selection
        # Create a representative text for selection logic
        representative_text = texts[all_metrics.index(max(all_metrics, key=lambda m: m.complexity_score))]
        
        selected_model, _, _ = self.select_model(
            representative_text,
            step=step,
            glossary_terms=glossary_terms,
            force_model=force_model,
            is_batch=True
        )
        
        # Estimate batch cost
        model_config = self.models.get(selected_model, self.DEFAULT_MODELS.get("kimi-k2.5"))
        estimated_cost = model_config.estimate_cost(total_estimated_tokens, total_estimated_tokens // 2)
        
        # Trace batch routing
        self._trace({
            "type": "batch_routing_decision",
            "step": step,
            "batch_size": len(texts),
            "max_complexity": round(max_complexity, 4),
            "selected_model": selected_model,
            "estimated_cost": round(estimated_cost, 6)
        })
        
        return selected_model, max_complexity, all_metrics
    
    def translate_with_routing(self, 
                              text: str,
                              system_prompt: str,
                              step: str = "translate",
                              glossary_terms: Optional[List[str]] = None,
                              force_model: Optional[str] = None,
                              **llm_kwargs) -> Dict[str, Any]:
        """
        Translate text with intelligent model routing.
        
        Args:
            text: Text to translate
            system_prompt: System prompt for translation
            step: Processing step
            glossary_terms: Glossary terms for analysis
            force_model: Override routing
            **llm_kwargs: Additional arguments for LLM call
            
        Returns:
            Dict with result, model used, complexity metrics, and cost
        """
        # Select model
        selected_model, metrics, estimated_cost = self.select_model(
            text, step, glossary_terms, force_model
        )
        
        # Initialize LLM client if needed
        if self.llm_client is None:
            if LLMClient is None:
                raise RuntimeError("LLMClient not available")
            self.llm_client = LLMClient()
        
        # Make the call
        start_time = time.time()
        try:
            result = self.llm_client.chat(
                system=system_prompt,
                user=text,
                metadata={
                    "step": step,
                    "model_override": selected_model,
                    **llm_kwargs.pop("metadata", {})
                },
                **llm_kwargs
            )
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            # Track actual cost if usage available
            actual_cost = estimated_cost
            if hasattr(result, 'usage') and result.usage:
                prompt_tokens = result.usage.get('prompt_tokens', 0)
                completion_tokens = result.usage.get('completion_tokens', 0)
                actual_cost = self.models[selected_model].estimate_cost(
                    prompt_tokens, completion_tokens
                )
                self.cost_tracking[selected_model]["tokens_in"] += prompt_tokens
                self.cost_tracking[selected_model]["tokens_out"] += completion_tokens
            
            self.cost_tracking[selected_model]["calls"] += 1
            self.cost_tracking[selected_model]["cost_usd"] += actual_cost
            
            # Record success for historical tracking
            self.analyzer.record_success(text)
            
            return {
                "success": True,
                "text": result.text if hasattr(result, 'text') else str(result),
                "model": selected_model,
                "complexity": metrics.complexity_score,
                "complexity_metrics": metrics.to_dict(),
                "estimated_cost": estimated_cost,
                "actual_cost": actual_cost,
                "latency_ms": latency_ms,
                "request_id": getattr(result, 'request_id', None)
            }
            
        except Exception as e:
            # Record failure
            self.analyzer.record_failure(text, str(e))
            
            return {
                "success": False,
                "error": str(e),
                "model": selected_model,
                "complexity": metrics.complexity_score,
                "complexity_metrics": metrics.to_dict(),
                "estimated_cost": estimated_cost
            }
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics and cost summary."""
        total_routings = len(self.routing_history)
        if total_routings == 0:
            return {
                "total_routings": 0,
                "cost_tracking": {},
                "model_distribution": {}
            }
        
        # Model distribution
        model_counts = defaultdict(int)
        for decision in self.routing_history:
            model_counts[decision.selected_model] += 1
        
        model_distribution = {
            model: {
                "count": count,
                "percentage": round(count / total_routings * 100, 2)
            }
            for model, count in model_counts.items()
        }
        
        # Complexity distribution
        complexity_buckets = {"low": 0, "medium": 0, "high": 0}
        for decision in self.routing_history:
            score = decision.complexity_score
            if score < 0.33:
                complexity_buckets["low"] += 1
            elif score < 0.66:
                complexity_buckets["medium"] += 1
            else:
                complexity_buckets["high"] += 1
        
        return {
            "total_routings": total_routings,
            "total_estimated_cost": round(
                sum(d.estimated_cost for d in self.routing_history), 6
            ),
            "cost_tracking": dict(self.cost_tracking),
            "model_distribution": model_distribution,
            "complexity_distribution": complexity_buckets,
            "average_complexity": round(
                sum(d.complexity_score for d in self.routing_history) / total_routings, 4
            )
        }
    
    def save_routing_history(self, path: Optional[str] = None):
        """Save routing history to file."""
        save_path = path or "reports/model_router_history.json"
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "routing_history": [d.to_dict() for d in self.routing_history],
            "statistics": self.get_routing_stats(),
            "saved_at": datetime.now().isoformat()
        }
        
        with open(save_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def get_cost_comparison(self, baseline_model: str = "kimi-k2.5") -> Dict[str, Any]:
        """
        Compare actual routing costs vs baseline (using single model for all).
        
        Returns cost savings analysis.
        """
        if not self.routing_history:
            return {"savings_percent": 0, "savings_usd": 0}
        
        baseline_config = self.models.get(baseline_model)
        if not baseline_config:
            return {"error": f"Baseline model {baseline_model} not found"}
        
        # Calculate baseline cost (if all used baseline model)
        total_tokens = sum(
            d.complexity_metrics.text_length // 4 * 1.5  # estimate total tokens
            for d in self.routing_history
        )
        baseline_cost = baseline_config.estimate_cost(total_tokens, total_tokens // 3)
        
        # Actual cost
        actual_cost = sum(d.estimated_cost for d in self.routing_history)
        
        savings = baseline_cost - actual_cost
        savings_percent = (savings / baseline_cost * 100) if baseline_cost > 0 else 0
        
        return {
            "baseline_model": baseline_model,
            "baseline_cost_usd": round(baseline_cost, 6),
            "actual_cost_usd": round(actual_cost, 6),
            "savings_usd": round(savings, 6),
            "savings_percent": round(savings_percent, 2),
            "routings_count": len(self.routing_history)
        }


# -----------------------------
# Integration Helper
# -----------------------------
def patch_translate_llm_with_router(translate_llm_module=None):
    """
    Patch the translate_llm module to use ModelRouter.
    
    This function monkey-patches the batch_llm_call function to use
    intelligent model routing.
    """
    if translate_llm_module is None:
        # Try to import translate_llm
        try:
            import translate_llm
            translate_llm_module = translate_llm
        except ImportError:
            print("Warning: Could not import translate_llm for patching")
            return None
    
    # Create router instance
    router = ModelRouter()
    
    # Store original function
    original_batch_llm_call = translate_llm_module.batch_llm_call
    
    def routed_batch_llm_call(step, rows, model, system_prompt, user_prompt_template,
                              content_type="normal", retry=1, allow_fallback=False,
                              **kwargs):
        """Wrapped batch_llm_call with model routing."""
        
        # Get glossary terms if available
        glossary_terms = kwargs.get('glossary_terms', [])
        
        # Select model for batch
        texts = [r.get("source_text", "") for r in rows]
        selected_model, complexity, metrics = router.select_model_for_batch(
            texts, step, glossary_terms, force_model=model if not router.enabled else None
        )
        
        print(f"[ModelRouter] Selected {selected_model} for batch "
              f"(complexity: {complexity:.2f}, {len(rows)} rows)")
        
        # Call original with selected model
        return original_batch_llm_call(
            step=step,
            rows=rows,
            model=selected_model,
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            content_type=content_type,
            retry=retry,
            allow_fallback=allow_fallback,
            **kwargs
        )
    
    # Replace function
    translate_llm_module.batch_llm_call = routed_batch_llm_call
    translate_llm_module._model_router = router
    
    print("[ModelRouter] Successfully patched translate_llm with intelligent routing")
    return router


# -----------------------------
# CLI Interface
# -----------------------------
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Model Router CLI")
    parser.add_argument("--analyze", "-a", help="Text to analyze for complexity")
    parser.add_argument("--select", "-s", help="Select model for text")
    parser.add_argument("--step", default="translate", help="Processing step")
    parser.add_argument("--stats", action="store_true", help="Show routing statistics")
    parser.add_argument("--config", help="Path to model routing config")
    parser.add_argument("--glossary", help="Path to glossary YAML file")
    
    args = parser.parse_args()
    
    router = ModelRouter(config_path=args.config)
    
    # Load glossary if provided
    glossary_terms = []
    if args.glossary and yaml and Path(args.glossary).exists():
        try:
            with open(args.glossary, 'r', encoding='utf-8') as f:
                g = yaml.safe_load(f)
                glossary_terms = [e.get("term_zh", "") for e in g.get("entries", [])]
        except Exception as e:
            print(f"Warning: Could not load glossary: {e}")
    
    if args.analyze:
        metrics = router.analyze_complexity(args.analyze, glossary_terms)
        print("Complexity Analysis:")
        print(json.dumps(metrics.to_dict(), indent=2, ensure_ascii=False))
    
    if args.select:
        model, metrics, cost = router.select_model(
            args.select, args.step, glossary_terms
        )
        print(f"\nSelected Model: {model}")
        print(f"Complexity Score: {metrics.complexity_score:.4f}")
        print(f"Estimated Cost: ${cost:.6f}")
        print("\nDetailed Metrics:")
        print(json.dumps(metrics.to_dict(), indent=2, ensure_ascii=False))
    
    if args.stats:
        stats = router.get_routing_stats()
        print("\nRouting Statistics:")
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        
        comparison = router.get_cost_comparison()
        print("\nCost Comparison:")
        print(json.dumps(comparison, indent=2, ensure_ascii=False))
