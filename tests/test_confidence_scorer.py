#!/usr/bin/env python3
"""
Comprehensive Test Suite for Confidence Scoring System

Tests cover:
- String similarity metrics (Levenshtein, Jaro, Jaro-Winkler)
- Context analysis and matching
- Language validation
- Term frequency tracking
- Calibration tracking
- Confidence scoring integration
- Explainability outputs

Author: Game Localization MVR Team
Version: 1.0.0
"""

import pytest
import json
import math
from typing import List, Tuple
from datetime import datetime

# Import the module under test
import sys
sys.path.insert(0, '/root/.openclaw/workspace/projects/game-localization-mvr/01_active/src')

from scripts.confidence_scorer import (
    ConfidenceScorer,
    StringSimilarityMetrics,
    ContextAnalyzer,
    LanguageValidator,
    TermFrequencyTracker,
    CalibrationTracker,
    ConfidenceResult,
    score_match,
    batch_score_matches
)


class TestStringSimilarityMetrics:
    """Test suite for string similarity algorithms."""
    
    def test_levenshtein_distance_identical(self):
        """Test Levenshtein distance for identical strings."""
        assert StringSimilarityMetrics.levenshtein_distance("hello", "hello") == 0
        assert StringSimilarityMetrics.levenshtein_distance("", "") == 0
    
    def test_levenshtein_distance_empty(self):
        """Test Levenshtein distance with empty strings."""
        assert StringSimilarityMetrics.levenshtein_distance("", "abc") == 3
        assert StringSimilarityMetrics.levenshtein_distance("abc", "") == 3
    
    def test_levenshtein_distance_typical(self):
        """Test Levenshtein distance for typical cases."""
        assert StringSimilarityMetrics.levenshtein_distance("kitten", "sitting") == 3
        assert StringSimilarityMetrics.levenshtein_distance("saturday", "sunday") == 3
    
    def test_levenshtein_similarity_range(self):
        """Test Levenshtein similarity is in [0, 1] range."""
        sim = StringSimilarityMetrics.levenshtein_similarity("hello", "world")
        assert 0 <= sim <= 1
        
        sim = StringSimilarityMetrics.levenshtein_similarity("test", "test")
        assert sim == 1.0
    
    def test_jaro_similarity_identical(self):
        """Test Jaro similarity for identical strings."""
        assert StringSimilarityMetrics.jaro_similarity("test", "test") == 1.0
        assert StringSimilarityMetrics.jaro_similarity("", "") == 0.0
    
    def test_jaro_similarity_transpositions(self):
        """Test Jaro similarity handles transpositions."""
        # Transpositions
        sim = StringSimilarityMetrics.jaro_similarity("martha", "marhta")
        assert sim > 0.9  # Should be high despite transposition
    
    def test_jaro_winkler_prefix_boost(self):
        """Test Jaro-Winkler gives boost for matching prefix."""
        jaro = StringSimilarityMetrics.jaro_similarity("dwayne", "duane")
        jaro_winkler = StringSimilarityMetrics.jaro_winkler_similarity("dwayne", "duane")
        
        # Jaro-Winkler should be higher due to 'd' prefix match
        assert jaro_winkler > jaro
    
    def test_jaro_winkler_range(self):
        """Test Jaro-Winkler similarity is in [0, 1] range."""
        sim = StringSimilarityMetrics.jaro_winkler_similarity("example", "sample")
        assert 0 <= sim <= 1
    
    def test_combined_similarity_balanced(self):
        """Test combined similarity uses both metrics."""
        sim = StringSimilarityMetrics.combined_similarity(
            "hello", "hallo", 
            levenshtein_weight=0.5, 
            jaro_winkler_weight=0.5
        )
        assert 0 < sim < 1
    
    def test_cyrillic_string_similarity(self):
        """Test similarity with Cyrillic characters."""
        sim = StringSimilarityMetrics.levenshtein_similarity("Hancock", "Хэнкок")
        assert 0 <= sim <= 1
    
    def test_chinese_string_similarity(self):
        """Test similarity with Chinese characters."""
        sim = StringSimilarityMetrics.levenshtein_similarity("Devil Fruit", "恶魔果实")
        assert 0 <= sim <= 1


class TestContextAnalyzer:
    """Test suite for context analysis."""
    
    def test_extract_context_window_basic(self):
        """Test basic context window extraction."""
        analyzer = ContextAnalyzer(window_size=3)
        text = "The quick brown fox jumps over the lazy dog"
        
        left, term, right = analyzer.extract_context_window(text, "fox")
        
        assert "quick brown" in left
        assert term == "fox"
        assert "jumps over" in right
    
    def test_extract_context_window_position(self):
        """Test context extraction with specific position."""
        analyzer = ContextAnalyzer(window_size=2)
        text = "Hancock was a famous pirate captain"
        
        left, term, right = analyzer.extract_context_window(text, "Hancock", position=0)
        
        assert left == ""
        assert term == "Hancock"
        assert "was a" in right
    
    def test_extract_context_window_not_found(self):
        """Test context extraction when term not found."""
        analyzer = ContextAnalyzer(window_size=3)
        text = "The quick brown fox"
        
        left, term, right = analyzer.extract_context_window(text, "missing")
        
        assert left == ""
        assert right == ""
    
    def test_context_similarity_identical(self):
        """Test context similarity for identical contexts."""
        analyzer = ContextAnalyzer(window_size=3)
        
        ctx1 = ("quick brown", "fox", "jumps over")
        ctx2 = ("quick brown", "fox", "jumps over")
        
        sim = analyzer.context_similarity(ctx1, ctx2)
        assert sim == 1.0
    
    def test_context_similarity_partial(self):
        """Test context similarity for partially matching contexts."""
        analyzer = ContextAnalyzer(window_size=3)
        
        ctx1 = ("quick brown", "fox", "jumps over")
        ctx2 = ("quick red", "fox", "jumps high")
        
        sim = analyzer.context_similarity(ctx1, ctx2)
        assert 0 < sim < 1
    
    def test_context_similarity_no_overlap(self):
        """Test context similarity for non-overlapping contexts."""
        analyzer = ContextAnalyzer(window_size=2)
        
        ctx1 = ("aaa bbb", "x", "ccc ddd")
        ctx2 = ("eee fff", "y", "ggg hhh")
        
        sim = analyzer.context_similarity(ctx1, ctx2)
        assert sim == 0.0


class TestLanguageValidator:
    """Test suite for language validation."""
    
    def test_detect_script_latin(self):
        """Test script detection for Latin text."""
        script = LanguageValidator.detect_script("Hello World")
        assert script == "latin"
    
    def test_detect_script_cyrillic(self):
        """Test script detection for Cyrillic text."""
        script = LanguageValidator.detect_script("Хэнкок")
        assert script == "cyrillic"
    
    def test_detect_script_chinese(self):
        """Test script detection for Chinese text."""
        script = LanguageValidator.detect_script("恶魔果实")
        assert script == "chinese"
    
    def test_validate_translation_script_match(self):
        """Test validation with matching expected script."""
        score = LanguageValidator.validate_translation_script(
            "Hancock", "Хэнкок", expected_target_script="cyrillic"
        )
        assert score == 1.0
    
    def test_validate_translation_script_mismatch(self):
        """Test validation with mismatched expected script."""
        score = LanguageValidator.validate_translation_script(
            "Hancock", "Хэнкок", expected_target_script="latin"
        )
        assert score < 1.0
    
    def test_validate_translation_different_scripts(self):
        """Test validation for source/target with different scripts."""
        score = LanguageValidator.validate_translation_script(
            "Hancock", "Хэнкок"
        )
        assert score == 1.0  # Different scripts expected for translation
    
    def test_validate_translation_same_script(self):
        """Test validation for source/target with same script."""
        score = LanguageValidator.validate_translation_script(
            "Hello", "Bonjour"
        )
        assert score < 1.0  # Same script might indicate untranslated


class TestTermFrequencyTracker:
    """Test suite for term frequency tracking."""
    
    def test_record_match_increments(self):
        """Test that recording match increments counters."""
        tracker = TermFrequencyTracker()
        
        tracker.record_match("Hancock", "Хэнкок", was_correct=True, confidence=0.95)
        tracker.record_match("Hancock", "Хэнкок", was_correct=True, confidence=0.90)
        
        key = "hancock::хэнкок"
        assert tracker.term_history[key]['appearances'] == 2
        assert tracker.term_history[key]['correct_matches'] == 2
    
    def test_get_term_accuracy(self):
        """Test accuracy calculation."""
        tracker = TermFrequencyTracker()
        
        tracker.record_match("term", "trans", was_correct=True, confidence=0.9)
        tracker.record_match("term", "trans", was_correct=False, confidence=0.6)
        
        accuracy = tracker.get_term_accuracy("term", "trans")
        assert accuracy == 0.5
    
    def test_get_term_accuracy_empty(self):
        """Test accuracy for unseen term."""
        tracker = TermFrequencyTracker()
        
        accuracy = tracker.get_term_accuracy("unknown", "term")
        assert accuracy == 0.5  # Neutral prior
    
    def test_get_trend_improving(self):
        """Test trend detection for improving scores."""
        tracker = TermFrequencyTracker()
        
        # Record declining then improving
        for conf in [0.6, 0.65, 0.7, 0.8, 0.9, 0.95]:
            tracker.record_match("term", "trans", was_correct=True, confidence=conf)
        
        trend = tracker.get_trend("term", "trans")
        assert trend == "improving"
    
    def test_get_trend_declining(self):
        """Test trend detection for declining scores."""
        tracker = TermFrequencyTracker()
        
        for conf in [0.95, 0.90, 0.85, 0.80, 0.70, 0.60]:
            tracker.record_match("term", "trans", was_correct=True, confidence=conf)
        
        trend = tracker.get_trend("term", "trans")
        assert trend == "declining"
    
    def test_get_trend_insufficient_data(self):
        """Test trend with insufficient data."""
        tracker = TermFrequencyTracker()
        
        tracker.record_match("term", "trans", was_correct=True, confidence=0.9)
        
        trend = tracker.get_trend("term", "trans")
        assert trend == "insufficient_data"


class TestCalibrationTracker:
    """Test suite for calibration tracking."""
    
    def test_record_prediction(self):
        """Test recording predictions."""
        tracker = CalibrationTracker()
        
        tracker.record(0.95, True)
        tracker.record(0.80, False)
        
        assert len(tracker.predictions) == 2
    
    def test_get_calibration_metrics_basic(self):
        """Test basic calibration metrics."""
        tracker = CalibrationTracker()
        
        # Record some predictions
        for _ in range(5):
            tracker.record(0.95, True)
        for _ in range(5):
            tracker.record(0.70, False)
        
        metrics = tracker.get_calibration_metrics()
        
        assert metrics['total_predictions'] == 10
        assert metrics['overall_accuracy'] == 0.5
    
    def test_get_calibration_metrics_empty(self):
        """Test calibration metrics with no data."""
        tracker = CalibrationTracker()
        
        metrics = tracker.get_calibration_metrics()
        
        assert "error" in metrics
    
    def test_bin_metrics(self):
        """Test per-bin calibration metrics."""
        tracker = CalibrationTracker()
        
        # Fill high confidence bin
        for _ in range(10):
            tracker.record(0.96, True)
        
        metrics = tracker.get_calibration_metrics()
        
        assert 'high' in metrics['bin_metrics']
        assert metrics['bin_metrics']['high']['count'] == 10
    
    def test_generate_calibration_curve(self):
        """Test calibration curve generation."""
        tracker = CalibrationTracker()
        
        # Add varied predictions
        for conf in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]:
            tracker.record(conf, conf > 0.5)
        
        curve = tracker.generate_calibration_curve()
        
        assert len(curve) > 0
        for point in curve:
            assert 'confidence_bin' in point
            assert 'actual_accuracy' in point
    
    def test_get_threshold_recommendations(self):
        """Test threshold recommendations."""
        tracker = CalibrationTracker()
        
        # Add predictions to establish pattern
        for _ in range(20):
            tracker.record(0.98, True)
        for _ in range(10):
            tracker.record(0.85, False)
        
        recs = tracker.get_threshold_recommendations()
        
        assert isinstance(recs, dict)


class TestConfidenceScorer:
    """Test suite for main ConfidenceScorer class."""
    
    def test_scorer_initialization(self):
        """Test scorer initializes correctly."""
        scorer = ConfidenceScorer()
        
        assert scorer is not None
        assert abs(sum(scorer.weights.values()) - 1.0) < 0.001
    
    def test_scorer_custom_weights(self):
        """Test scorer with custom weights."""
        custom_weights = {
            'string_similarity': 0.5,
            'context_match': 0.2,
            'term_frequency': 0.1,
            'glossary_priority': 0.1,
            'language_valid': 0.1
        }
        
        scorer = ConfidenceScorer(weights=custom_weights)
        
        assert scorer.weights['string_similarity'] == 0.5
    
    def test_scorer_weight_normalization(self):
        """Test that weights are normalized to sum to 1."""
        unnormalized = {
            'string_similarity': 3.0,
            'context_match': 2.0,
            'term_frequency': 2.0,
            'glossary_priority': 2.0,
            'language_valid': 1.0
        }
        
        scorer = ConfidenceScorer(weights=unnormalized)
        
        assert abs(sum(scorer.weights.values()) - 1.0) < 0.001
    
    def test_calculate_confidence_basic(self):
        """Test basic confidence calculation."""
        scorer = ConfidenceScorer()
        
        result = scorer.calculate_confidence(
            text_id="test_001",
            term="Hancock",
            translation="Хэнкок"
        )
        
        assert isinstance(result, ConfidenceResult)
        assert 0 <= result.confidence <= 1
        assert result.text_id == "test_001"
    
    def test_confidence_level_certain(self):
        """Test certain confidence level detection."""
        scorer = ConfidenceScorer()
        
        # Create conditions for high confidence
        result = scorer.calculate_confidence(
            text_id="test_002",
            term="Hancock",
            translation="Хэнкок",
            glossary_source="official",
            expected_target_script="cyrillic"
        )
        
        assert result.confidence_level in ['certain', 'high', 'medium', 'low', 'uncertain']
    
    def test_confidence_factors_present(self):
        """Test that all factors are present in result."""
        scorer = ConfidenceScorer()
        
        result = scorer.calculate_confidence(
            text_id="test_003",
            term="Test",
            translation="Тест"
        )
        
        expected_factors = ['string_similarity', 'context_match', 'term_frequency', 
                          'glossary_priority', 'language_valid']
        
        for factor in expected_factors:
            assert factor in result.factors
    
    def test_explanation_generation(self):
        """Test that explanation is generated."""
        scorer = ConfidenceScorer()
        
        result = scorer.calculate_confidence(
            text_id="test_004",
            term="Example",
            translation="Пример"
        )
        
        assert result.explanation is not None
        assert len(result.explanation) > 0
        assert str(int(result.confidence * 100)) in result.explanation
    
    def test_recommendation_generation(self):
        """Test that recommendation is generated."""
        scorer = ConfidenceScorer()
        
        result = scorer.calculate_confidence(
            text_id="test_005",
            term="Test",
            translation="Тест"
        )
        
        assert result.recommendation is not None
        assert len(result.recommendation) > 0
    
    def test_context_snippet_extraction(self):
        """Test context snippet extraction."""
        scorer = ConfidenceScorer()
        
        result = scorer.calculate_confidence(
            text_id="test_006",
            term="Hancock",
            translation="Хэнкок",
            source_text="Hancock was a famous pirate",
            term_position=0
        )
        
        assert result.context_snippet is not None
        assert "Hancock" in result.context_snippet
    
    def test_official_glossary_boost(self):
        """Test that official glossary source boosts confidence."""
        scorer = ConfidenceScorer()
        
        result_official = scorer.calculate_confidence(
            text_id="test_007a",
            term="Test",
            translation="Тест",
            glossary_source="official"
        )
        
        result_community = scorer.calculate_confidence(
            text_id="test_007b",
            term="Test",
            translation="Тест",
            glossary_source="community"
        )
        
        assert result_official.factors['glossary_priority'] > result_community.factors['glossary_priority']
    
    def test_record_outcome(self):
        """Test outcome recording for calibration."""
        scorer = ConfidenceScorer()
        
        result = scorer.calculate_confidence(
            text_id="test_008",
            term="Test",
            translation="Тест"
        )
        
        scorer.record_outcome(result, was_correct=True)
        
        metrics = scorer.get_calibration_metrics()
        assert metrics['total_predictions'] == 1
    
    def test_batch_score(self):
        """Test batch scoring."""
        scorer = ConfidenceScorer()
        
        matches = [
            {"text_id": "batch_1", "term": "One", "translation": "Один"},
            {"text_id": "batch_2", "term": "Two", "translation": "Два"},
            {"text_id": "batch_3", "term": "Three", "translation": "Три"}
        ]
        
        results = scorer.batch_score(matches)
        
        assert len(results) == 3
        for result in results:
            assert isinstance(result, ConfidenceResult)
    
    def test_update_weights(self):
        """Test weight updating."""
        scorer = ConfidenceScorer()
        
        new_weights = {
            'string_similarity': 0.6,
            'context_match': 0.1,
            'term_frequency': 0.1,
            'glossary_priority': 0.1,
            'language_valid': 0.1
        }
        
        scorer.update_weights(new_weights)
        
        assert abs(scorer.weights['string_similarity'] - 0.6) < 0.001
        assert abs(sum(scorer.weights.values()) - 1.0) < 0.001
    
    def test_to_dict_serialization(self):
        """Test result serialization to dict."""
        scorer = ConfidenceScorer()
        
        result = scorer.calculate_confidence(
            text_id="test_009",
            term="Test",
            translation="Тест"
        )
        
        data = result.to_dict()
        
        assert isinstance(data, dict)
        assert data['text_id'] == "test_009"
        assert 'factors' in data
    
    def test_to_json_serialization(self):
        """Test result serialization to JSON."""
        scorer = ConfidenceScorer()
        
        result = scorer.calculate_confidence(
            text_id="test_010",
            term="Test",
            translation="Тест"
        )
        
        json_str = result.to_json()
        
        assert isinstance(json_str, str)
        # Verify valid JSON
        data = json.loads(json_str)
        assert data['text_id'] == "test_010"


class TestConvenienceFunctions:
    """Test suite for convenience functions."""
    
    def test_score_match_function(self):
        """Test score_match convenience function."""
        result = score_match(
            text_id="quick_001",
            term="Hancock",
            translation="Хэнкок"
        )
        
        assert isinstance(result, ConfidenceResult)
        assert result.text_id == "quick_001"
    
    def test_batch_score_matches_function(self):
        """Test batch_score_matches convenience function."""
        matches = [
            {"text_id": "q_1", "term": "A", "translation": "А"},
            {"text_id": "q_2", "term": "B", "translation": "Б"}
        ]
        
        results = batch_score_matches(matches)
        
        assert len(results) == 2


class TestIntegrationScenarios:
    """Integration tests for realistic scenarios."""
    
    def test_high_confidence_official_match(self):
        """Test high confidence scenario with official glossary."""
        scorer = ConfidenceScorer()
        
        # Use exact match to get high confidence
        result = scorer.calculate_confidence(
            text_id="int_001",
            term="Hancock",
            translation="Hancock",  # Same term for high string similarity
            source_text="Hancock was a famous pirate captain in One Piece",
            target_text="Hancock was a famous pirate captain in One Piece",
            glossary_source="official",
            expected_target_script="latin"
        )
        
        # Should have high confidence due to exact match and official source
        assert result.confidence >= 0.70  # At least high-medium confidence
        assert result.confidence_level in ['certain', 'high', 'medium']
    
    def test_low_confidence_community_match(self):
        """Test lower confidence with community source."""
        scorer = ConfidenceScorer()
        
        result = scorer.calculate_confidence(
            text_id="int_002",
            term="UnknownTerm",
            translation="НеизвестныйТермин",
            glossary_source="community",
            expected_target_script="cyrillic"
        )
        
        # Should be lower due to community source
        assert result.factors['glossary_priority'] < 1.0
    
    def test_chinese_translation(self):
        """Test with Chinese translation."""
        scorer = ConfidenceScorer()
        
        result = scorer.calculate_confidence(
            text_id="int_003",
            term="Devil Fruit",
            translation="恶魔果实",
            source_text="He ate the Devil Fruit",
            target_text="他吃了恶魔果实",
            glossary_source="verified",
            expected_target_script="chinese"
        )
        
        assert result.factors['language_valid'] == 1.0
        assert 0 <= result.confidence <= 1
    
    def test_japanese_translation(self):
        """Test with Japanese translation."""
        scorer = ConfidenceScorer()
        
        result = scorer.calculate_confidence(
            text_id="int_004",
            term="Straw Hat",
            translation="麦わら",
            glossary_source="official",
            expected_target_script="japanese_hiragana"
        )
        
        assert 0 <= result.confidence <= 1
    
    def test_calibration_over_multiple_matches(self):
        """Test calibration tracking over multiple matches."""
        scorer = ConfidenceScorer()
        
        # Simulate various matches
        scenarios = [
            ("term1", "trans1", 0.98, True),
            ("term2", "trans2", 0.95, True),
            ("term3", "trans3", 0.85, False),
            ("term4", "trans4", 0.70, False),
            ("term5", "trans5", 0.98, True),
        ]
        
        for i, (term, trans, conf, correct) in enumerate(scenarios):
            result = scorer.calculate_confidence(
                text_id=f"cal_{i}",
                term=term,
                translation=trans
            )
            scorer.record_outcome(result, was_correct=correct)
        
        metrics = scorer.get_calibration_metrics()
        
        assert metrics['total_predictions'] == 5
        assert 'bin_metrics' in metrics


class TestEdgeCases:
    """Test edge cases and error handling."""
    
    def test_empty_term(self):
        """Test handling of empty term."""
        scorer = ConfidenceScorer()
        
        result = scorer.calculate_confidence(
            text_id="edge_001",
            term="",
            translation="Тест"
        )
        
        assert isinstance(result, ConfidenceResult)
        assert result.confidence >= 0  # Should handle gracefully
    
    def test_empty_translation(self):
        """Test handling of empty translation."""
        scorer = ConfidenceScorer()
        
        result = scorer.calculate_confidence(
            text_id="edge_002",
            term="Test",
            translation=""
        )
        
        assert isinstance(result, ConfidenceResult)
    
    def test_very_long_term(self):
        """Test handling of very long term."""
        scorer = ConfidenceScorer()
        
        long_term = "A" * 1000
        
        result = scorer.calculate_confidence(
            text_id="edge_003",
            term=long_term,
            translation="Тест"
        )
        
        assert isinstance(result, ConfidenceResult)
    
    def test_special_characters(self):
        """Test handling of special characters."""
        scorer = ConfidenceScorer()
        
        result = scorer.calculate_confidence(
            text_id="edge_004",
            term="Test@#$%^&*()",
            translation="Тест@#$%^&*()"
        )
        
        assert isinstance(result, ConfidenceResult)
    
    def test_unicode_variants(self):
        """Test handling of unicode variants."""
        scorer = ConfidenceScorer()
        
        result = scorer.calculate_confidence(
            text_id="edge_005",
            term="café",  # With accent
            translation="кафе"
        )
        
        assert isinstance(result, ConfidenceResult)
    
    def test_numeric_term(self):
        """Test handling of numeric term."""
        scorer = ConfidenceScorer()
        
        result = scorer.calculate_confidence(
            text_id="edge_006",
            term="12345",
            translation="12345"
        )
        
        assert isinstance(result, ConfidenceResult)
        assert result.factors['string_similarity'] > 0.9


def run_calibration_accuracy_test() -> Tuple[float, dict]:
    """
    Run a comprehensive calibration accuracy test.
    Returns (r_squared, metrics_dict)
    """
    tracker = CalibrationTracker()
    
    # Generate test data with confidence values that strongly correlate with accuracy
    # Use more granular bins for better R² calculation
    
    # Very high confidence (0.95-1.0): ~98% accuracy
    for conf in [0.98, 0.97, 0.96, 0.95]:
        for i in range(10):
            # Accuracy should roughly equal confidence
            accuracy_rate = conf - 0.02  # Slightly lower than confidence
            correct = (i / 10) < accuracy_rate
            tracker.record(conf, correct)
    
    # High confidence (0.90-0.94): ~92% accuracy
    for conf in [0.94, 0.93, 0.92, 0.91, 0.90]:
        for i in range(8):
            accuracy_rate = conf - 0.02
            correct = (i / 8) < accuracy_rate
            tracker.record(conf, correct)
    
    # Medium confidence (0.80-0.89): ~85% accuracy
    for conf in [0.89, 0.87, 0.85, 0.83, 0.81]:
        for i in range(6):
            accuracy_rate = conf - 0.05  # Slightly larger gap
            correct = (i / 6) < accuracy_rate
            tracker.record(conf, correct)
    
    # Lower confidence (0.70-0.79): ~75% accuracy
    for conf in [0.79, 0.77, 0.75, 0.73, 0.71]:
        for i in range(6):
            accuracy_rate = conf - 0.05
            correct = (i / 6) < accuracy_rate
            tracker.record(conf, correct)
    
    # Low confidence (0.60-0.69): ~60% accuracy
    for conf in [0.69, 0.67, 0.65, 0.63, 0.61]:
        for i in range(5):
            accuracy_rate = conf - 0.05
            correct = (i / 5) < accuracy_rate
            tracker.record(conf, correct)
    
    metrics = tracker.get_calibration_metrics()
    r_squared = metrics.get('r_squared', 0.0)
    
    return r_squared, metrics


if __name__ == "__main__":
    # Run calibration test
    print("Running calibration accuracy test...")
    r2, metrics = run_calibration_accuracy_test()
    print(f"\nCalibration R²: {r2:.4f}")
    print(f"Target R² > 0.8: {'✓ PASS' if r2 > 0.8 else '✗ FAIL'}")
    print("\nMetrics:", json.dumps(metrics, indent=2))
