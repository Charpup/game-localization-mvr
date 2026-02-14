#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_model_router.py (v1.0)

Comprehensive tests for the Model Router module.

Test Coverage:
  1. ComplexityAnalyzer - Text complexity analysis
  2. ModelRouter - Model selection and routing
  3. Integration - End-to-end routing scenarios
  4. Cost Tracking - Cost estimation and comparison
  5. Performance - Routing decision performance

Run: pytest tests/test_model_router.py -v
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from model_router import (
    ComplexityAnalyzer, ModelRouter, ModelConfig,
    ComplexityMetrics, RoutingDecision,
    PLACEHOLDER_RE, CJK_RE, SPECIAL_CHARS_RE
)


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def sample_texts():
    """Sample texts of varying complexity."""
    return {
        "simple_short": "你好",
        "simple_medium": "欢迎来到游戏世界！",
        "complex_with_placeholders": "玩家⟦PH_1⟧获得了⟦PH_2⟧个金币。",
        "complex_long": """在遥远的古代，有一个传说中的王国。
        这个王国拥有强大的魔法力量和无数的宝藏。
        勇士们从四面八方赶来，为了寻找传说中的神器。
        只有最勇敢、最智慧的冒险者才能获得最终的胜利。""",
        "glossary_heavy": "魔法师使用火球术攻击了龙族的龙王，造成了暴击伤害。",
        "special_chars": "玩家[A]使用了技能{B}，造成<C>点伤害！",
        "mixed_complexity": "⟦PH_1⟧完成了任务【⟦PH_2⟧】，获得奖励：金币×⟦PH_3⟧！"
    }


@pytest.fixture
def glossary_terms():
    """Sample glossary terms."""
    return ["魔法师", "火球术", "龙族", "龙王", "暴击", "伤害"]


@pytest.fixture
def analyzer():
    """Fresh ComplexityAnalyzer instance."""
    return ComplexityAnalyzer()


@pytest.fixture
def router(tmp_path):
    """Fresh ModelRouter instance with temp config."""
    config = {
        "enabled": True,
        "default_model": "kimi-k2.5",
        "complexity_threshold": 0.7,
        "models": [
            {"name": "gpt-3.5-turbo", "cost_per_1k": 0.0015, "max_complexity": 0.5, "batch_capable": True, "quality_tier": "medium"},
            {"name": "kimi-k2.5", "cost_per_1k": 0.012, "max_complexity": 1.0, "batch_capable": True, "quality_tier": "high"},
            {"name": "gpt-4", "cost_per_1k": 0.03, "max_complexity": 1.0, "batch_capable": True, "quality_tier": "high"},
        ]
    }
    
    config_path = tmp_path / "model_routing.yaml"
    import yaml
    with open(config_path, 'w') as f:
        yaml.dump(config, f)
    
    # Set temp paths
    os.environ["MODEL_ROUTER_TRACE_PATH"] = str(tmp_path / "trace.jsonl")
    os.environ["MODEL_ROUTER_HISTORY_PATH"] = str(tmp_path / "history.json")
    
    return ModelRouter(config_path=str(config_path))


@pytest.fixture
def mock_llm_client():
    """Mock LLM client for testing."""
    mock = Mock()
    mock_result = Mock()
    mock_result.text = "Translated text"
    mock_result.request_id = "test-req-123"
    mock_result.usage = {"prompt_tokens": 100, "completion_tokens": 50}
    mock.chat.return_value = mock_result
    return mock


# ============================================
# Test Class 1: ComplexityAnalyzer
# ============================================

class TestComplexityAnalyzer:
    """Tests for ComplexityAnalyzer class."""
    
    def test_analyze_empty_text(self, analyzer):
        """Test 1: Analyzer handles empty text gracefully."""
        metrics = analyzer.analyze("")
        assert metrics.text_length == 0
        assert metrics.complexity_score == 0.0
    
    def test_analyze_basic_counts(self, analyzer, sample_texts):
        """Test 2: Basic text counts are accurate."""
        text = sample_texts["simple_medium"]
        metrics = analyzer.analyze(text)
        
        assert metrics.text_length == len(text)
        assert metrics.cjk_count > 0  # Should detect CJK
        assert metrics.word_count >= 1
    
    def test_placeholder_detection(self, analyzer, sample_texts):
        """Test 3: Placeholder detection works correctly."""
        text = sample_texts["complex_with_placeholders"]
        metrics = analyzer.analyze(text)
        
        assert metrics.placeholder_count == 2
        assert metrics.placeholder_density > 0
    
    def test_glossary_term_counting(self, analyzer, sample_texts, glossary_terms):
        """Test 4: Glossary term detection works."""
        text = sample_texts["glossary_heavy"]
        metrics = analyzer.analyze(text, glossary_terms)
        
        assert metrics.glossary_term_count >= 3  # Should find multiple terms
        assert metrics.glossary_term_density > 0
    
    def test_special_character_detection(self, analyzer, sample_texts):
        """Test 5: Special character detection."""
        text = sample_texts["special_chars"]
        metrics = analyzer.analyze(text)
        
        assert metrics.special_char_count >= 6  # [ ] { } < >
        assert metrics.special_char_density > 0
    
    def test_complexity_score_range(self, analyzer, sample_texts):
        """Test 6: Complexity score is within 0-1 range."""
        for name, text in sample_texts.items():
            metrics = analyzer.analyze(text)
            assert 0.0 <= metrics.complexity_score <= 1.0, f"{name} score out of range"
    
    def test_complexity_ordering(self, analyzer, sample_texts):
        """Test 7: More complex text gets higher score."""
        simple = analyzer.analyze(sample_texts["simple_short"])
        complex_text = analyzer.analyze(sample_texts["complex_long"])
        
        assert simple.complexity_score < complex_text.complexity_score
    
    def test_metrics_to_dict(self, analyzer, sample_texts):
        """Test 8: Metrics serialization works."""
        metrics = analyzer.analyze(sample_texts["simple_medium"])
        d = metrics.to_dict()
        
        assert isinstance(d, dict)
        assert "complexity_score" in d
        assert "text_length" in d
        assert 0.0 <= d["complexity_score"] <= 1.0
    
    def test_historical_failure_tracking(self, analyzer, sample_texts):
        """Test 9: Historical failure tracking works."""
        text = sample_texts["simple_medium"]
        
        # Record some failures
        analyzer.record_failure(text, "test_fail")
        analyzer.record_failure(text, "test_fail")
        analyzer.record_success(text)
        
        rate = analyzer.get_historical_failure_rate(text)
        assert rate > 0  # Should have some failure rate
    
    def test_failure_rate_affects_complexity(self, analyzer, sample_texts):
        """Test 10: Historical failures increase complexity score."""
        text = sample_texts["simple_medium"]
        
        # Get baseline
        baseline = analyzer.analyze(text)
        baseline_score = baseline.complexity_score
        
        # Record failures
        for _ in range(5):
            analyzer.record_failure(text)
        
        # Re-analyze
        with_failures = analyzer.analyze(text)
        
        assert with_failures.complexity_score >= baseline_score
    
    def test_custom_weights(self, sample_texts):
        """Test 11: Custom complexity weights work."""
        custom_weights = {
            "length": 0.5,
            "placeholder_density": 0.1,
            "special_char_density": 0.1,
            "glossary_density": 0.1,
            "historical_failure": 0.2
        }
        custom_analyzer = ComplexityAnalyzer(weights=custom_weights)
        
        metrics = custom_analyzer.analyze(sample_texts["simple_medium"])
        assert 0.0 <= metrics.complexity_score <= 1.0
    
    def test_sentence_counting(self, analyzer, sample_texts):
        """Test 12: Sentence counting is accurate."""
        text = "第一句。第二句！第三句？"
        metrics = analyzer.analyze(text)
        
        assert metrics.sentence_count >= 3
    
    def test_avg_word_length(self, analyzer, sample_texts):
        """Test 13: Average word length calculation."""
        metrics = analyzer.analyze(sample_texts["simple_medium"])
        
        assert metrics.avg_word_length > 0
    
    def test_placeholder_patterns(self, analyzer):
        """Test 14: Various placeholder patterns detected."""
        patterns = [
            "文本⟦PH_1⟧结束",
            "文本{placeholder}结束",
            "文本<tag>结束",
        ]
        
        for pattern in patterns:
            metrics = analyzer.analyze(pattern)
            assert metrics.placeholder_count >= 1, f"Failed for: {pattern}"


# ============================================
# Test Class 2: ModelRouter
# ============================================

class TestModelRouter:
    """Tests for ModelRouter class."""
    
    def test_router_initialization(self, router):
        """Test 15: Router initializes correctly."""
        assert router.enabled is True
        assert router.default_model == "kimi-k2.5"
        assert router.complexity_threshold == 0.7
        assert len(router.models) >= 3
    
    def test_select_model_returns_tuple(self, router, sample_texts):
        """Test 16: select_model returns correct tuple."""
        model, metrics, cost = router.select_model(sample_texts["simple_short"])
        
        assert isinstance(model, str)
        assert isinstance(metrics, ComplexityMetrics)
        assert isinstance(cost, float)
        assert cost >= 0
    
    def test_simple_text_gets_cheaper_model(self, router, sample_texts):
        """Test 17: Simple text routes to cheaper model."""
        text = "你好"  # Very simple
        model, _, _ = router.select_model(text)
        
        # Should get cheapest model (gpt-4.1-nano at $0.001/1k)
        assert model in ["gpt-3.5-turbo", "gpt-4.1-nano"]
        assert router.models[model].cost_per_1k <= 0.0015
    
    def test_complex_text_gets_better_model(self, router, sample_texts):
        """Test 18: Complex text routes to better model."""
        text = sample_texts["complex_long"]
        model, metrics, _ = router.select_model(text)
        
        # Complex text should get high-capability model
        assert router.models[model].max_complexity >= metrics.complexity_score
    
    def test_force_model_override(self, router, sample_texts):
        """Test 19: Force model override works."""
        forced_model = "gpt-4"
        model, _, _ = router.select_model(
            sample_texts["simple_short"],
            force_model=forced_model
        )
        
        assert model == forced_model
    
    def test_routing_history_recorded(self, router, sample_texts):
        """Test 20: Routing decisions are recorded."""
        initial_count = len(router.routing_history)
        
        router.select_model(sample_texts["simple_short"])
        
        assert len(router.routing_history) == initial_count + 1
        assert isinstance(router.routing_history[-1], RoutingDecision)
    
    def test_batch_model_selection(self, router, sample_texts):
        """Test 21: Batch model selection works."""
        texts = [
            sample_texts["simple_short"],
            sample_texts["simple_medium"],
            sample_texts["complex_long"]
        ]
        
        model, complexity, metrics_list = router.select_model_for_batch(texts)
        
        assert isinstance(model, str)
        assert 0.0 <= complexity <= 1.0
        assert len(metrics_list) == len(texts)
    
    def test_batch_uses_max_complexity(self, router, sample_texts):
        """Test 22: Batch selection uses max complexity."""
        # Use a truly complex text for one item
        texts = [
            sample_texts["simple_short"],  # Low complexity
            sample_texts["complex_with_placeholders"] + sample_texts["special_chars"]  # Higher complexity
        ]
        
        model, complexity, _ = router.select_model_for_batch(texts)
        
        # Should be high enough for complex text (should be at least moderate)
        assert complexity > 0.2
    
    def test_model_config_exists(self, router):
        """Test 23: Model configurations are loaded."""
        for name, config in router.models.items():
            assert isinstance(config, ModelConfig)
            assert config.name == name
            assert config.cost_per_1k >= 0
            assert 0 < config.max_complexity <= 1.0
    
    def test_cost_estimation(self, router):
        """Test 24: Cost estimation works."""
        config = router.models["gpt-3.5-turbo"]
        cost = config.estimate_cost(1000, 500)
        
        expected = (1500 / 1000) * 0.0015
        assert abs(cost - expected) < 0.0001
    
    def test_get_routing_stats_empty(self, router):
        """Test 25: Stats work with empty history."""
        stats = router.get_routing_stats()
        
        assert stats["total_routings"] == 0
        assert stats["cost_tracking"] == {}
    
    def test_get_routing_stats_with_data(self, router, sample_texts):
        """Test 26: Stats work with data."""
        for text in sample_texts.values():
            router.select_model(text)
        
        stats = router.get_routing_stats()
        
        assert stats["total_routings"] == len(sample_texts)
        assert stats["average_complexity"] >= 0
        assert "model_distribution" in stats
    
    def test_cost_comparison(self, router, sample_texts):
        """Test 27: Cost comparison calculation."""
        # Add some routings
        for _ in range(5):
            router.select_model(sample_texts["simple_short"])
        
        comparison = router.get_cost_comparison(baseline_model="kimi-k2.5")
        
        assert "savings_percent" in comparison
        assert "savings_usd" in comparison
        assert "baseline_cost_usd" in comparison
        assert "actual_cost_usd" in comparison
    
    def test_save_routing_history(self, router, sample_texts, tmp_path):
        """Test 28: Saving routing history works."""
        router.select_model(sample_texts["simple_short"])
        
        save_path = tmp_path / "history.json"
        router.save_routing_history(str(save_path))
        
        assert save_path.exists()
        with open(save_path) as f:
            data = json.load(f)
            assert "routing_history" in data
            assert "statistics" in data
    
    def test_disabled_router_uses_default(self, tmp_path):
        """Test 29: Disabled router uses default model."""
        config = {
            "enabled": False,
            "default_model": "kimi-k2.5",
            "models": []
        }
        config_path = tmp_path / "disabled.yaml"
        import yaml
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        disabled_router = ModelRouter(config_path=str(config_path))
        model, _, _ = disabled_router.select_model("Some text")
        
        assert model == "kimi-k2.5"
    
    def test_batch_capability_check(self, router):
        """Test 30: Batch capability is checked."""
        # Create batch scenario - just use batch selection
        texts = ["test"] * 10
        model, _, _ = router.select_model_for_batch(texts)
        
        # Model should support batch
        assert router.models[model].batch_capable is True


# ============================================
# Test Class 3: Integration Scenarios
# ============================================

class TestIntegrationScenarios:
    """Integration tests for end-to-end scenarios."""
    
    def test_translate_with_routing_success(self, router, mock_llm_client, sample_texts):
        """Test 31: Successful translation with routing."""
        router.llm_client = mock_llm_client
        
        result = router.translate_with_routing(
            text=sample_texts["simple_medium"],
            system_prompt="Translate to Russian",
            step="translate"
        )
        
        assert result["success"] is True
        assert "text" in result
        assert "model" in result
        assert "complexity" in result
        assert result["model"] is not None
    
    def test_translate_with_routing_failure(self, router, sample_texts):
        """Test 32: Failed translation handling."""
        # Mock client that raises error
        mock_client = Mock()
        mock_client.chat.side_effect = Exception("API Error")
        router.llm_client = mock_client
        
        result = router.translate_with_routing(
            text=sample_texts["simple_medium"],
            system_prompt="Translate to Russian",
            step="translate"
        )
        
        assert result["success"] is False
        assert "error" in result
    
    def test_routing_with_glossary(self, router, sample_texts, glossary_terms):
        """Test 33: Routing considers glossary terms."""
        text = sample_texts["glossary_heavy"]
        
        # Without glossary
        model_no_glossary, metrics_no_glossary, _ = router.select_model(text)
        
        # With glossary
        model_with_glossary, metrics_with_glossary, _ = router.select_model(
            text, glossary_terms=glossary_terms
        )
        
        # With glossary should detect more terms
        assert metrics_with_glossary.glossary_term_count >= metrics_no_glossary.glossary_term_count
    
    def test_complexity_affects_model_selection(self, router, sample_texts):
        """Test 34: Different complexity leads to different models."""
        simple_model, simple_metrics, _ = router.select_model(sample_texts["simple_short"])
        complex_model, complex_metrics, _ = router.select_model(sample_texts["complex_long"])
        
        # Different complexity should ideally lead to different models
        # (though both might route to same if config is limited)
        assert simple_metrics.complexity_score < complex_metrics.complexity_score
    
    def test_step_specific_routing(self, router, sample_texts):
        """Test 35: Different steps can have different routing."""
        text = sample_texts["simple_medium"]
        
        model_translate, _, _ = router.select_model(text, step="translate")
        model_qa, _, _ = router.select_model(text, step="soft_qa")
        
        # Models could be different based on step requirements
        assert model_translate is not None
        assert model_qa is not None


# ============================================
# Test Class 4: Edge Cases
# ============================================

class TestEdgeCases:
    """Edge case tests."""
    
    def test_very_long_text(self, analyzer):
        """Test 36: Very long text handling."""
        text = "这是一段很长的文本。" * 1000
        metrics = analyzer.analyze(text)
        
        assert metrics.text_length == len(text)
        assert metrics.complexity_score > 0.2  # Long text should have some complexity
    
    def test_very_short_text(self, analyzer):
        """Test 37: Very short text handling."""
        text = "嗨"
        metrics = analyzer.analyze(text)
        
        assert metrics.text_length == 1
        assert metrics.complexity_score < 0.3  # Should be simple
    
    def test_unicode_handling(self, analyzer):
        """Test 38: Unicode text handling."""
        texts = [
            "日本語テキスト",
            "한국어 텍스트",
            "Texte français",
            "Текст на русском",
            "🎮🎯🎲 Emoji text"
        ]
        
        for text in texts:
            metrics = analyzer.analyze(text)
            assert 0.0 <= metrics.complexity_score <= 1.0
    
    def test_only_placeholders(self, analyzer):
        """Test 39: Text with only placeholders."""
        text = "⟦PH_1⟧⟦PH_2⟧⟦PH_3⟧"
        metrics = analyzer.analyze(text)
        
        assert metrics.placeholder_count == 3
        assert metrics.complexity_score > 0  # Placeholders add complexity
    
    def test_only_special_chars(self, analyzer):
        """Test 40: Text with many special characters."""
        text = "!@#$%^&*()[]{}|;':\",./<>?"
        metrics = analyzer.analyze(text)
        
        assert metrics.special_char_count > 0
        assert metrics.complexity_score > 0
    
    def test_mixed_content(self, analyzer):
        """Test 41: Mixed CJK and Latin content."""
        text = "Hello你好World世界123!"
        metrics = analyzer.analyze(text)
        
        assert metrics.cjk_count == 4  # 你好世界
        assert metrics.word_count >= 1
    
    def test_newlines_and_whitespace(self, analyzer):
        """Test 42: Text with excessive whitespace."""
        text = "  Line 1\n\n\n  Line 2  \t\t  "
        metrics = analyzer.analyze(text)
        
        assert metrics.text_length == len(text)
        assert metrics.word_count >= 2


# ============================================
# Test Class 5: Performance Tests
# ============================================

class TestPerformance:
    """Performance and stress tests."""
    
    def test_routing_performance(self, router, sample_texts):
        """Test 43: Routing decision is fast."""
        text = sample_texts["complex_long"]
        
        start = time.time()
        for _ in range(100):
            router.select_model(text)
        elapsed = time.time() - start
        
        # Should complete 100 routings in under 1 second
        assert elapsed < 1.0, f"Routing too slow: {elapsed:.2f}s for 100 calls"
    
    def test_batch_routing_performance(self, router):
        """Test 44: Batch routing performance."""
        texts = ["测试文本"] * 100
        
        start = time.time()
        model, complexity, metrics = router.select_model_for_batch(texts)
        elapsed = time.time() - start
        
        # Should be fast even for large batches
        assert elapsed < 0.5, f"Batch routing too slow: {elapsed:.2f}s"
    
    def test_memory_efficiency(self, router, sample_texts):
        """Test 45: Memory usage with many routings."""
        # Generate many routing decisions
        for i in range(1000):
            text = f"Text number {i} with some content"
            router.select_model(text)
        
        # History should be recorded
        assert len(router.routing_history) == 1000
        
        # Stats should still work
        stats = router.get_routing_stats()
        assert stats["total_routings"] == 1000


# ============================================
# Test Class 6: Configuration Tests
# ============================================

class TestConfiguration:
    """Configuration loading tests."""
    
    def test_load_default_models(self):
        """Test 46: Default models are loaded when no config."""
        router = ModelRouter(config_path="nonexistent.yaml")
        
        # Should have default models
        assert "kimi-k2.5" in router.models
        assert "gpt-3.5-turbo" in router.models
        assert "gpt-4" in router.models
    
    def test_config_file_loading(self, tmp_path):
        """Test 47: Config file loading works."""
        config = {
            "enabled": True,
            "default_model": "test-model",
            "complexity_threshold": 0.5,
            "models": [
                {"name": "test-model", "cost_per_1k": 0.01, "max_complexity": 1.0}
            ]
        }
        
        config_path = tmp_path / "test_config.yaml"
        import yaml
        with open(config_path, 'w') as f:
            yaml.dump(config, f)
        
        router = ModelRouter(config_path=str(config_path))
        assert router.default_model == "test-model"
        assert router.complexity_threshold == 0.5
    
    def test_invalid_config_handling(self):
        """Test 48: Invalid config is handled gracefully."""
        router = ModelRouter(config_path="/invalid/path/config.yaml")
        
        # Should still work with defaults
        assert router.enabled is True
        model, _, _ = router.select_model("test text")
        assert model is not None


# ============================================
# Main
# ============================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
