#!/usr/bin/env python3
"""
Confidence Scoring System for Glossary Match Quality Assessment

This module provides comprehensive match quality scoring for glossary term
matches in game localization workflows. It uses multiple factors to calculate
a normalized confidence score (0-1) with explainability features.

Author: Game Localization MVR Team
Version: 1.0.0
"""

import re
import json
import math
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Union
from collections import defaultdict
from datetime import datetime


@dataclass
class ConfidenceResult:
    """Result container for confidence scoring with full explainability."""
    text_id: str
    term: str
    translation: str
    confidence: float
    confidence_level: str
    factors: Dict[str, float]
    weights: Dict[str, float]
    explanation: str
    recommendation: str
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    context_snippet: Optional[str] = None
    historical_accuracy: Optional[float] = None
    calibration_data: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for JSON serialization."""
        return asdict(self)
    
    def to_json(self, indent: int = 2) -> str:
        """Convert result to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class StringSimilarityMetrics:
    """String similarity algorithms for term matching."""
    
    @staticmethod
    def levenshtein_distance(s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance between two strings.
        Uses dynamic programming with space optimization.
        """
        if len(s1) < len(s2):
            return StringSimilarityMetrics.levenshtein_distance(s2, s1)
        
        if len(s2) == 0:
            return len(s1)
        
        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]
    
    @staticmethod
    def levenshtein_similarity(s1: str, s2: str) -> float:
        """
        Calculate normalized Levenshtein similarity (0-1).
        1.0 = identical strings, 0.0 = completely different.
        """
        if not s1 and not s2:
            return 1.0
        if not s1 or not s2:
            return 0.0
        
        max_len = max(len(s1), len(s2))
        distance = StringSimilarityMetrics.levenshtein_distance(s1, s2)
        return 1.0 - (distance / max_len)
    
    @staticmethod
    def jaro_similarity(s1: str, s2: str) -> float:
        """
        Calculate Jaro similarity between two strings.
        Good for short strings and transpositions.
        """
        if not s1 or not s2:
            return 0.0
        if s1 == s2:
            return 1.0
        
        len1, len2 = len(s1), len(s2)
        match_distance = max(len1, len2) // 2 - 1
        
        s1_matches = [False] * len1
        s2_matches = [False] * len2
        matches = 0
        transpositions = 0
        
        # Find matches
        for i in range(len1):
            start = max(0, i - match_distance)
            end = min(i + match_distance + 1, len2)
            
            for j in range(start, end):
                if s2_matches[j] or s1[i] != s2[j]:
                    continue
                s1_matches[i] = True
                s2_matches[j] = True
                matches += 1
                break
        
        if matches == 0:
            return 0.0
        
        # Count transpositions
        k = 0
        for i in range(len1):
            if not s1_matches[i]:
                continue
            while not s2_matches[k]:
                k += 1
            if s1[i] != s2[k]:
                transpositions += 1
            k += 1
        
        return ((matches / len1) + 
                (matches / len2) + 
                ((matches - transpositions / 2) / matches)) / 3.0
    
    @staticmethod
    def jaro_winkler_similarity(s1: str, s2: str, p: float = 0.1) -> float:
        """
        Calculate Jaro-Winkler similarity with prefix weighting.
        Gives higher weight to matching prefixes (good for name matching).
        """
        jaro = StringSimilarityMetrics.jaro_similarity(s1, s2)
        
        if jaro == 0.0:
            return 0.0
        
        # Find common prefix length (max 4)
        prefix_len = 0
        for i in range(min(len(s1), len(s2), 4)):
            if s1[i] == s2[i]:
                prefix_len += 1
            else:
                break
        
        return jaro + (prefix_len * p * (1 - jaro))
    
    @staticmethod
    def combined_similarity(s1: str, s2: str, 
                           levenshtein_weight: float = 0.4,
                           jaro_winkler_weight: float = 0.6) -> float:
        """
        Combined string similarity using both Levenshtein and Jaro-Winkler.
        Weights can be adjusted based on use case.
        """
        lev_sim = StringSimilarityMetrics.levenshtein_similarity(s1, s2)
        jw_sim = StringSimilarityMetrics.jaro_winkler_similarity(s1, s2)
        
        return (levenshtein_weight * lev_sim + 
                jaro_winkler_weight * jw_sim)


class ContextAnalyzer:
    """Analyze context similarity for term matches."""
    
    def __init__(self, window_size: int = 5):
        self.window_size = window_size
    
    def extract_context_window(self, text: str, term: str, 
                               position: Optional[int] = None) -> Tuple[str, str, str]:
        """
        Extract context window around a term occurrence.
        Returns (left_context, term, right_context).
        """
        if position is None:
            position = text.lower().find(term.lower())
        
        if position == -1:
            return "", term, ""
        
        # Extract surrounding words
        words_before = text[:position].split()
        words_after = text[position + len(term):].split()
        
        left_context = ' '.join(words_before[-self.window_size:])
        right_context = ' '.join(words_after[:self.window_size])
        
        return left_context, term, right_context
    
    def context_similarity(self, source_context: Tuple[str, str, str],
                          target_context: Tuple[str, str, str]) -> float:
        """
        Calculate similarity between two context windows.
        Uses word overlap and position-weighted matching.
        """
        src_left, _, src_right = source_context
        tgt_left, _, tgt_right = target_context
        
        # Calculate left and right context similarities separately
        left_sim = self._word_set_similarity(src_left, tgt_left)
        right_sim = self._word_set_similarity(src_right, tgt_right)
        
        # Weighted average (right context slightly more important for Japanese)
        return 0.45 * left_sim + 0.55 * right_sim
    
    def _word_set_similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard-like similarity between word sets."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 and not words2:
            return 1.0
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0


class LanguageValidator:
    """Validate character sets and scripts for language-specific scoring."""
    
    # Unicode ranges for different scripts
    SCRIPTS = {
        'latin': (0x0041, 0x007A),      # Basic Latin + Latin Extended
        'cyrillic': (0x0400, 0x04FF),   # Cyrillic
        'greek': (0x0370, 0x03FF),      # Greek
        'chinese': (0x4E00, 0x9FFF),    # CJK Unified Ideographs
        'japanese_hiragana': (0x3040, 0x309F),
        'japanese_katakana': (0x30A0, 0x30FF),
        'korean': (0xAC00, 0xD7AF),     # Hangul Syllables
        'arabic': (0x0600, 0x06FF),     # Arabic
    }
    
    @classmethod
    def detect_script(cls, text: str) -> str:
        """Detect the dominant script in text."""
        script_counts = defaultdict(int)
        
        for char in text:
            code = ord(char)
            for script, (start, end) in cls.SCRIPTS.items():
                if start <= code <= end:
                    script_counts[script] += 1
                    break
        
        if not script_counts:
            return 'unknown'
        
        return max(script_counts, key=script_counts.get)
    
    @classmethod
    def validate_translation_script(cls, source: str, translation: str,
                                    expected_target_script: Optional[str] = None) -> float:
        """
        Validate that translation uses appropriate script.
        Returns score 0-1 based on script validity.
        """
        if not translation:
            return 0.0
        
        source_script = cls.detect_script(source)
        target_script = cls.detect_script(translation)
        
        # If expected target script specified, verify match
        if expected_target_script:
            return 1.0 if target_script == expected_target_script else 0.3
        
        # Otherwise, ensure they're different (translation should be in different language)
        if source_script == target_script and source_script != 'unknown':
            # Same script might be okay for some language pairs (e.g., English/French)
            # But generally we expect different scripts for EN->RU, EN->JA, etc.
            return 0.7
        
        return 1.0
    
    @classmethod
    def validate_character_set(cls, text: str, allowed_scripts: List[str]) -> float:
        """Validate that text only contains characters from allowed scripts."""
        if not text:
            return 0.0
        
        valid_count = 0
        for char in text:
            code = ord(char)
            is_valid = False
            
            # Check punctuation and whitespace
            if code <= 0x007F or unicodedata.category(char).startswith('P') or char.isspace():
                is_valid = True
            else:
                for script in allowed_scripts:
                    if script in cls.SCRIPTS:
                        start, end = cls.SCRIPTS[script]
                        if start <= code <= end:
                            is_valid = True
                            break
            
            if is_valid:
                valid_count += 1
        
        return valid_count / len(text) if text else 0.0


# Import unicodedata for LanguageValidator
import unicodedata


class TermFrequencyTracker:
    """Track historical accuracy of term translations for confidence calibration."""
    
    def __init__(self):
        self.term_history: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'appearances': 0,
            'correct_matches': 0,
            'recent_scores': [],
            'last_updated': None
        })
    
    def record_match(self, term: str, translation: str, 
                     was_correct: bool, confidence: float):
        """Record a match result for historical tracking."""
        key = f"{term.lower()}::{translation.lower()}"
        record = self.term_history[key]
        
        record['appearances'] += 1
        if was_correct:
            record['correct_matches'] += 1
        
        record['recent_scores'].append(confidence)
        # Keep last 10 scores
        record['recent_scores'] = record['recent_scores'][-10:]
        record['last_updated'] = datetime.utcnow().isoformat()
    
    def get_term_accuracy(self, term: str, translation: str) -> float:
        """Get historical accuracy for a term-translation pair."""
        key = f"{term.lower()}::{translation.lower()}"
        record = self.term_history[key]
        
        if record['appearances'] == 0:
            return 0.5  # Neutral prior
        
        return record['correct_matches'] / record['appearances']
    
    def get_trend(self, term: str, translation: str) -> str:
        """Get confidence trend direction."""
        key = f"{term.lower()}::{translation.lower()}"
        scores = self.term_history[key]['recent_scores']
        
        if len(scores) < 3:
            return "insufficient_data"
        
        # Simple trend: compare recent avg to older avg
        recent_avg = sum(scores[-3:]) / 3
        older_avg = sum(scores[:-3]) / max(1, len(scores) - 3)
        
        if recent_avg > older_avg + 0.05:
            return "improving"
        elif recent_avg < older_avg - 0.05:
            return "declining"
        return "stable"


class CalibrationTracker:
    """Track confidence vs accuracy for calibration analysis."""
    
    def __init__(self):
        self.predictions: List[Tuple[float, bool]] = []  # (confidence, was_correct)
        self.bins: Dict[str, List[Tuple[float, bool]]] = defaultdict(list)
    
    def record(self, confidence: float, was_correct: bool):
        """Record a prediction outcome."""
        self.predictions.append((confidence, was_correct))
        
        # Bin by confidence level
        if confidence >= 0.98:
            bin_name = "certain"
        elif confidence >= 0.95:
            bin_name = "high"
        elif confidence >= 0.85:
            bin_name = "medium"
        elif confidence >= 0.70:
            bin_name = "low"
        else:
            bin_name = "uncertain"
        
        self.bins[bin_name].append((confidence, was_correct))
    
    def get_calibration_metrics(self) -> Dict[str, Any]:
        """Calculate calibration metrics."""
        if not self.predictions:
            return {"error": "No predictions recorded"}
        
        metrics = {
            'total_predictions': len(self.predictions),
            'overall_accuracy': sum(1 for _, correct in self.predictions if correct) / len(self.predictions),
            'average_confidence': sum(c for c, _ in self.predictions) / len(self.predictions),
            'bin_metrics': {},
            'r_squared': self._calculate_r_squared()
        }
        
        # Calculate per-bin metrics
        for bin_name, predictions in self.bins.items():
            if not predictions:
                continue
            
            avg_confidence = sum(c for c, _ in predictions) / len(predictions)
            actual_accuracy = sum(1 for _, correct in predictions if correct) / len(predictions)
            
            metrics['bin_metrics'][bin_name] = {
                'count': len(predictions),
                'average_confidence': round(avg_confidence, 4),
                'actual_accuracy': round(actual_accuracy, 4),
                'calibration_error': round(abs(avg_confidence - actual_accuracy), 4)
            }
        
        return metrics
    
    def _calculate_r_squared(self) -> float:
        """Calculate R² between confidence and accuracy."""
        if len(self.predictions) < 3:
            return 0.0
        
        # Group by confidence bins for analysis
        confidence_bins: Dict[int, List[bool]] = defaultdict(list)
        for conf, correct in self.predictions:
            bin_idx = int(conf * 10)  # 0.0-0.1, 0.1-0.2, etc.
            confidence_bins[bin_idx].append(correct)
        
        # Calculate bin accuracies
        bin_accuracies = []
        bin_confidences = []
        for bin_idx, results in confidence_bins.items():
            if len(results) >= 2:  # Need at least 2 points per bin
                bin_confidences.append((bin_idx + 0.5) / 10)
                bin_accuracies.append(sum(results) / len(results))
        
        if len(bin_accuracies) < 2:
            return 0.0
        
        # Simple R² calculation
        mean_acc = sum(bin_accuracies) / len(bin_accuracies)
        ss_tot = sum((a - mean_acc) ** 2 for a in bin_accuracies)
        ss_res = sum((a - c) ** 2 for a, c in zip(bin_accuracies, bin_confidences))
        
        if ss_tot == 0:
            return 1.0 if ss_res == 0 else 0.0
        
        return 1 - (ss_res / ss_tot)
    
    def get_threshold_recommendations(self) -> Dict[str, float]:
        """Get recommended confidence thresholds based on calibration data."""
        if not self.predictions:
            return {"error": "Insufficient data"}
        
        # Sort by confidence
        sorted_preds = sorted(self.predictions, key=lambda x: x[0], reverse=True)
        
        recommendations = {}
        
        # Find threshold for 95% precision
        for threshold in [0.98, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70]:
            above_threshold = [(c, correct) for c, correct in sorted_preds if c >= threshold]
            if above_threshold:
                precision = sum(1 for _, correct in above_threshold if correct) / len(above_threshold)
                if precision >= 0.95 and 'high_precision' not in recommendations:
                    recommendations['high_precision'] = threshold
                if precision >= 0.90 and 'balanced' not in recommendations:
                    recommendations['balanced'] = threshold
                if precision >= 0.80 and 'recall_focused' not in recommendations:
                    recommendations['recall_focused'] = threshold
        
        return recommendations
    
    def generate_calibration_curve(self) -> List[Dict[str, float]]:
        """Generate data points for calibration curve plotting."""
        if not self.predictions:
            return []
        
        # Create 10 bins
        curve_data = []
        for i in range(10):
            bin_start = i * 0.1
            bin_end = (i + 1) * 0.1
            bin_preds = [(c, correct) for c, correct in self.predictions 
                        if bin_start <= c < bin_end or (i == 9 and c == 1.0)]
            
            if bin_preds:
                avg_conf = sum(c for c, _ in bin_preds) / len(bin_preds)
                avg_acc = sum(1 for _, correct in bin_preds if correct) / len(bin_preds)
                curve_data.append({
                    'confidence_bin': round((bin_start + bin_end) / 2, 2),
                    'average_confidence': round(avg_conf, 3),
                    'actual_accuracy': round(avg_acc, 3),
                    'count': len(bin_preds)
                })
        
        return curve_data


class ConfidenceScorer:
    """
    Main confidence scoring class for glossary match quality assessment.
    
    Uses multiple factors with configurable weights to calculate a normalized
    confidence score (0-1) with full explainability.
    """
    
    # Default weights for scoring factors
    DEFAULT_WEIGHTS = {
        'string_similarity': 0.30,
        'context_match': 0.25,
        'term_frequency': 0.20,
        'glossary_priority': 0.15,
        'language_valid': 0.10
    }
    
    # Confidence level thresholds
    CONFIDENCE_LEVELS = {
        'certain': (0.98, 1.00),      # Auto-approve
        'high': (0.95, 0.97),         # Suggest with high confidence
        'medium': (0.85, 0.94),       # Suggest for review
        'low': (0.70, 0.84),          # Flag for attention
        'uncertain': (0.00, 0.69)     # Human review required
    }
    
    # Glossary priority scores
    GLOSSARY_PRIORITY = {
        'official': 1.0,
        'verified': 0.9,
        'community_trusted': 0.8,
        'community': 0.6,
        'auto_generated': 0.4,
        'unknown': 0.5
    }
    
    def __init__(self, weights: Optional[Dict[str, float]] = None,
                 window_size: int = 5):
        """
        Initialize the confidence scorer.
        
        Args:
            weights: Optional custom weights for scoring factors
            window_size: Size of context window for context matching
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.string_metrics = StringSimilarityMetrics()
        self.context_analyzer = ContextAnalyzer(window_size=window_size)
        self.language_validator = LanguageValidator()
        self.term_tracker = TermFrequencyTracker()
        self.calibration_tracker = CalibrationTracker()
        
        # Validate weights sum to 1.0
        total_weight = sum(self.weights.values())
        if abs(total_weight - 1.0) > 0.001:
            # Normalize weights
            self.weights = {k: v / total_weight for k, v in self.weights.items()}
    
    def calculate_confidence(self,
                           text_id: str,
                           term: str,
                           translation: str,
                           source_text: Optional[str] = None,
                           target_text: Optional[str] = None,
                           term_position: Optional[int] = None,
                           glossary_source: str = 'unknown',
                           expected_target_script: Optional[str] = None,
                           historical_accuracy: Optional[float] = None) -> ConfidenceResult:
        """
        Calculate comprehensive confidence score for a glossary match.
        
        Args:
            text_id: Unique identifier for the text
            term: Source term
            translation: Proposed translation
            source_text: Full source text for context analysis
            target_text: Full target text for context analysis
            term_position: Position of term in source text
            glossary_source: Source of glossary entry ('official', 'community', etc.)
            expected_target_script: Expected target language script
            historical_accuracy: Optional pre-computed historical accuracy
            
        Returns:
            ConfidenceResult with full scoring details
        """
        factors = {}
        
        # 1. String Similarity (0.30 weight)
        factors['string_similarity'] = self._calculate_string_similarity(term, translation)
        
        # 2. Context Match (0.25 weight)
        factors['context_match'] = self._calculate_context_match(
            term, translation, source_text, target_text, term_position
        )
        
        # 3. Term Frequency / Historical Accuracy (0.20 weight)
        factors['term_frequency'] = self._calculate_term_frequency(
            term, translation, historical_accuracy
        )
        
        # 4. Glossary Priority (0.15 weight)
        factors['glossary_priority'] = self._calculate_glossary_priority(glossary_source)
        
        # 5. Language Specific Validation (0.10 weight)
        factors['language_valid'] = self._calculate_language_validity(
            term, translation, expected_target_script
        )
        
        # Calculate weighted confidence
        confidence = sum(factors[key] * self.weights[key] for key in factors)
        
        # Normalize to 0-1 range
        confidence = max(0.0, min(1.0, confidence))
        
        # Determine confidence level
        confidence_level = self._get_confidence_level(confidence)
        
        # Generate explanation
        explanation = self._generate_explanation(factors, confidence)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(confidence, confidence_level)
        
        # Get context snippet
        context_snippet = None
        if source_text and term_position is not None:
            left, _, right = self.context_analyzer.extract_context_window(
                source_text, term, term_position
            )
            context_snippet = f"...{left} [{term}] {right}..."
        
        # Get trend
        trend = self.term_tracker.get_trend(term, translation)
        
        result = ConfidenceResult(
            text_id=text_id,
            term=term,
            translation=translation,
            confidence=round(confidence, 4),
            confidence_level=confidence_level,
            factors={k: round(v, 4) for k, v in factors.items()},
            weights=self.weights,
            explanation=explanation,
            recommendation=recommendation,
            context_snippet=context_snippet,
            historical_accuracy=round(factors['term_frequency'], 4),
            calibration_data={
                'trend': trend,
                'total_appearances': self.term_tracker.term_history.get(
                    f"{term.lower()}::{translation.lower()}", {}
                ).get('appearances', 0)
            }
        )
        
        return result
    
    def _calculate_string_similarity(self, term: str, translation: str) -> float:
        """Calculate string similarity score using combined metrics."""
        # Use combined Levenshtein + Jaro-Winkler
        similarity = self.string_metrics.combined_similarity(term, translation)
        
        # Boost score for exact matches
        if term.lower() == translation.lower():
            similarity = max(similarity, 0.95)
        
        return similarity
    
    def _calculate_context_match(self, term: str, translation: str,
                                 source_text: Optional[str],
                                 target_text: Optional[str],
                                 position: Optional[int]) -> float:
        """Calculate context match score."""
        if not source_text or not target_text:
            return 0.5  # Neutral when context unavailable
        
        try:
            source_ctx = self.context_analyzer.extract_context_window(
                source_text, term, position
            )
            # For target, try to find translation
            tgt_pos = target_text.find(translation)
            target_ctx = self.context_analyzer.extract_context_window(
                target_text, translation, tgt_pos if tgt_pos != -1 else None
            )
            
            return self.context_analyzer.context_similarity(source_ctx, target_ctx)
        except Exception:
            return 0.5
    
    def _calculate_term_frequency(self, term: str, translation: str,
                                  historical_accuracy: Optional[float]) -> float:
        """Calculate term frequency / historical accuracy score."""
        if historical_accuracy is not None:
            return historical_accuracy
        
        # Use tracked history
        return self.term_tracker.get_term_accuracy(term, translation)
    
    def _calculate_glossary_priority(self, glossary_source: str) -> float:
        """Calculate glossary priority score."""
        return self.GLOSSARY_PRIORITY.get(glossary_source, 0.5)
    
    def _calculate_language_validity(self, term: str, translation: str,
                                     expected_script: Optional[str]) -> float:
        """Calculate language-specific validity score."""
        return self.language_validator.validate_translation_script(
            term, translation, expected_script
        )
    
    def _get_confidence_level(self, confidence: float) -> str:
        """Determine confidence level category."""
        for level, (low, high) in self.CONFIDENCE_LEVELS.items():
            if low <= confidence <= high:
                return level
        return 'uncertain'
    
    def _generate_explanation(self, factors: Dict[str, float], 
                             confidence: float) -> str:
        """Generate human-readable explanation of confidence score."""
        parts = []
        
        # Identify top contributing factors
        sorted_factors = sorted(factors.items(), key=lambda x: x[1] * self.weights[x[0]], reverse=True)
        
        for factor_name, score in sorted_factors[:3]:
            if score >= 0.95:
                quality = "excellent"
            elif score >= 0.80:
                quality = "good"
            elif score >= 0.60:
                quality = "moderate"
            else:
                quality = "poor"
            
            parts.append(f"{factor_name.replace('_', ' ').title()}: {quality} ({score:.0%})")
        
        confidence_pct = int(confidence * 100)
        return f"{confidence_pct}% confidence - " + "; ".join(parts)
    
    def _generate_recommendation(self, confidence: float, level: str) -> str:
        """Generate action recommendation based on confidence level."""
        recommendations = {
            'certain': 'Auto-approve: High confidence match, no review needed',
            'high': 'Suggest with high confidence: Quick spot-check recommended',
            'medium': 'Suggest for review: Standard review process',
            'low': 'Flag for attention: Careful review required',
            'uncertain': 'Human review required: Manual translation recommended'
        }
        return recommendations.get(level, 'Review required')
    
    def record_outcome(self, result: ConfidenceResult, was_correct: bool):
        """Record the actual outcome for calibration tracking."""
        self.calibration_tracker.record(result.confidence, was_correct)
        self.term_tracker.record_match(
            result.term, result.translation, was_correct, result.confidence
        )
    
    def get_calibration_metrics(self) -> Dict[str, Any]:
        """Get current calibration metrics."""
        return self.calibration_tracker.get_calibration_metrics()
    
    def get_threshold_recommendations(self) -> Dict[str, float]:
        """Get recommended thresholds based on calibration data."""
        return self.calibration_tracker.get_threshold_recommendations()
    
    def generate_calibration_curve(self) -> List[Dict[str, float]]:
        """Generate calibration curve data points."""
        return self.calibration_tracker.generate_calibration_curve()
    
    def batch_score(self, matches: List[Dict[str, Any]]) -> List[ConfidenceResult]:
        """
        Score multiple matches in batch.
        
        Args:
            matches: List of match dictionaries with required fields
            
        Returns:
            List of ConfidenceResult objects
        """
        results = []
        for match in matches:
            result = self.calculate_confidence(**match)
            results.append(result)
        return results
    
    def update_weights(self, new_weights: Dict[str, float]) -> None:
        """Update scoring weights and normalize to sum to 1.0."""
        total = sum(new_weights.values())
        self.weights = {k: v / total for k, v in new_weights.items()}


# Convenience functions for quick usage
def score_match(text_id: str, term: str, translation: str, **kwargs) -> ConfidenceResult:
    """Quick scoring function using default scorer."""
    scorer = ConfidenceScorer()
    return scorer.calculate_confidence(text_id, term, translation, **kwargs)


def batch_score_matches(matches: List[Dict[str, Any]]) -> List[ConfidenceResult]:
    """Quick batch scoring function."""
    scorer = ConfidenceScorer()
    return scorer.batch_score(matches)


if __name__ == "__main__":
    # Demo usage
    print("Confidence Scoring System Demo")
    print("=" * 50)
    
    scorer = ConfidenceScorer()
    
    # Example 1: High confidence match
    result1 = scorer.calculate_confidence(
        text_id="text_001",
        term="Hancock",
        translation="Хэнкок",
        source_text="Hancock was a famous pirate captain",
        target_text="Хэнкок был знаменитым капитаном пиратов",
        glossary_source="official",
        expected_target_script="cyrillic"
    )
    print("\nExample 1 - High Confidence Match:")
    print(result1.to_json())
    
    # Example 2: Lower confidence match
    result2 = scorer.calculate_confidence(
        text_id="text_002",
        term="Devil Fruit",
        translation="恶魔果实",
        source_text="He ate the Devil Fruit",
        target_text="他吃了恶魔果实",
        glossary_source="community",
        expected_target_script="chinese"
    )
    print("\nExample 2 - Community Source Match:")
    print(result2.to_json())
    
    print("\nCalibration Metrics (empty):")
    print(json.dumps(scorer.get_calibration_metrics(), indent=2))
