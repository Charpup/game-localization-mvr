#!/usr/bin/env python3
"""
Glossary Matcher - Smart glossary matching for automatic approval
of high-confidence translations.

Features:
- Fuzzy matching with Levenshtein distance
- Context-aware matching
- Case-insensitive matching with case preservation check
- Multi-word phrase matching
- Auto-approval based on confidence thresholds
"""

import json
import csv
import re
import yaml
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Optional, Tuple, Set
from pathlib import Path
from datetime import datetime
from difflib import SequenceMatcher


@dataclass
class MatchResult:
    """Result of a glossary match."""
    source_term: str
    target_term: str
    found_text: str
    confidence: float
    match_type: str  # 'exact', 'fuzzy', 'context_validated', 'partial'
    context_before: str = ""
    context_after: str = ""
    position: int = 0
    length: int = 0
    auto_approved: bool = False
    requires_review: bool = False
    case_preserved: bool = True
    confidence_breakdown: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "source_term": self.source_term,
            "target_term": self.target_term,
            "found_text": self.found_text,
            "confidence": round(self.confidence, 4),
            "match_type": self.match_type,
            "context_before": self.context_before,
            "context_after": self.context_after,
            "position": self.position,
            "length": self.length,
            "auto_approved": self.auto_approved,
            "requires_review": self.requires_review,
            "case_preserved": self.case_preserved,
            "confidence_breakdown": self.confidence_breakdown,
            "timestamp": datetime.now().isoformat()
        }


class GlossaryMatcher:
    """
    Intelligent glossary matcher with fuzzy matching and context awareness.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the glossary matcher.
        
        Args:
            config_path: Path to glossary configuration YAML file
        """
        self.config = self._load_config(config_path)
        self.glossary: Dict[str, str] = {}  # source_term -> target_term
        self.special_terms = self.config.get('special_terms', {})
        self.abbreviations = set(
            self.special_terms.get('abbreviations', {}).get('examples', [])
        )
        self.brand_names = set(
            self.special_terms.get('brand_names', {}).get('examples', [])
        )
        self.homonyms = self.special_terms.get('homonyms', {})
        
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load configuration from YAML file."""
        # Default configuration
        default_config = {
            'enabled': True,
            'auto_approve_threshold': 0.95,
            'suggest_threshold': 0.90,
            'fuzzy_threshold': 0.90,
            'context_window': 10,
            'case_sensitive': False,
            'preserve_case_check': True,
            'multi_word_phrase_matching': True,
            'target_auto_approval_rate': 0.30,
            'max_false_positive_rate': 0.01,
            'scoring_weights': {
                'exact_match': 1.00,
                'fuzzy_match': 0.95,
                'context_validation': 0.90,
                'partial_match': 0.70,
                'case_preservation': 0.05
            }
        }
        
        if config_path is None:
            # Try default location
            config_path = Path(__file__).parent.parent / "config" / "glossary.yaml"
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                loaded_config = config.get('glossary_matching', {}) if config else {}
                # Merge with defaults (loaded config takes precedence)
                return {**default_config, **loaded_config}
        except FileNotFoundError:
            # Return default config
            return default_config
    
    def load_glossary(self, glossary_data: Dict[str, str]) -> None:
        """
        Load glossary entries.
        
        Args:
            glossary_data: Dictionary mapping source terms to target terms
        """
        self.glossary = glossary_data
    
    def load_glossary_from_yaml(self, yaml_path: str) -> None:
        """
        Load glossary from YAML file (compiled.yaml format).
        
        Args:
            yaml_path: Path to YAML glossary file
        """
        with open(yaml_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        entries = data.get('entries', [])
        for entry in entries:
            term_zh = entry.get('term_zh', '')
            term_ru = entry.get('term_ru', '')
            if term_zh and term_ru:
                self.glossary[term_zh] = term_ru
    
    def _levenshtein_distance(self, s1: str, s2: str) -> int:
        """
        Calculate Levenshtein distance between two strings.
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Edit distance
        """
        if len(s1) < len(s2):
            return self._levenshtein_distance(s2, s1)
        
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
    
    def _similarity_ratio(self, s1: str, s2: str) -> float:
        """
        Calculate similarity ratio between two strings (0.0 to 1.0).
        
        Args:
            s1: First string
            s2: Second string
            
        Returns:
            Similarity ratio
        """
        # Use SequenceMatcher for better performance on longer strings
        return SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
    
    def _is_abbreviation(self, term: str) -> bool:
        """Check if term is an abbreviation."""
        return term.upper() in self.abbreviations or (
            term.isupper() and len(term) <= 4
        )
    
    def _is_brand_name(self, term: str) -> bool:
        """Check if term is a brand name."""
        return term in self.brand_names
    
    def _check_case_preservation(self, source: str, found: str) -> bool:
        """
        Check if case is preserved between source and found text.
        
        Args:
            source: Expected source term
            found: Text found in content
            
        Returns:
            True if case is preserved
        """
        if not self.config.get('preserve_case_check', True):
            return True
        
        # Check if both are all upper, all lower, or title case
        source_pattern = self._get_case_pattern(source)
        found_pattern = self._get_case_pattern(found)
        
        return source_pattern == found_pattern
    
    def _get_case_pattern(self, text: str) -> str:
        """Get the case pattern of text."""
        if text.isupper():
            return 'upper'
        elif text.islower():
            return 'lower'
        elif text.istitle():
            return 'title'
        else:
            return 'mixed'
    
    def _get_context(self, text: str, position: int, length: int) -> Tuple[str, str]:
        """
        Get context around a match position.
        
        Args:
            text: Full text
            position: Start position of match
            length: Length of match
            
        Returns:
            Tuple of (context_before, context_after)
        """
        window = self.config.get('context_window', 10)
        words = text.split()
        
        # Find word indices
        char_count = 0
        start_word_idx = 0
        end_word_idx = len(words)
        
        for i, word in enumerate(words):
            word_start = char_count
            word_end = char_count + len(word)
            
            if word_start <= position < word_end:
                start_word_idx = i
            if word_start < position + length <= word_end:
                end_word_idx = i + 1
                break
            
            char_count += len(word) + 1  # +1 for space
        
        # Get context words
        context_start = max(0, start_word_idx - window)
        context_end = min(len(words), end_word_idx + window)
        
        context_before = ' '.join(words[context_start:start_word_idx])
        context_after = ' '.join(words[end_word_idx:context_end])
        
        return context_before, context_after
    
    def _validate_context(self, source_term: str, context_before: str, 
                          context_after: str) -> Tuple[bool, float]:
        """
        Validate context for ambiguous terms (homonyms).
        
        Args:
            source_term: The matched term
            context_before: Text before the match
            context_after: Text after the match
            
        Returns:
            Tuple of (is_valid, confidence_adjustment)
        """
        if not self.config.get('context_validation_enabled', True):
            return True, 0.0
        
        full_context = (context_before + ' ' + context_after).lower()
        
        # Check if term is a known homonym
        for homonym in self.homonyms.get('examples', []):
            if homonym.get('term', '').lower() == source_term.lower():
                contexts = [c.lower() for c in homonym.get('contexts', [])]
                
                # Check if any context keyword is present
                for ctx in contexts:
                    if ctx in full_context:
                        return True, 0.0
                
                # No matching context found
                return False, -0.20
        
        return True, 0.0
    
    def _calculate_confidence(self, match_type: str, similarity: float,
                              case_preserved: bool, context_valid: bool) -> Tuple[float, Dict]:
        """
        Calculate confidence score with breakdown.
        
        Args:
            match_type: Type of match ('exact', 'fuzzy', etc.)
            similarity: Similarity ratio
            case_preserved: Whether case is preserved
            context_valid: Whether context validation passed
            
        Returns:
            Tuple of (confidence_score, breakdown_dict)
        """
        weights = self.config.get('scoring_weights', {})
        breakdown = {}
        
        # Base confidence from match type
        if match_type == 'exact':
            base_confidence = weights.get('exact_match', 1.00)
        elif match_type == 'fuzzy':
            base_confidence = weights.get('fuzzy_match', 0.95) * similarity
        elif match_type == 'context_validated':
            base_confidence = weights.get('context_validation', 0.90)
        else:  # partial
            base_confidence = weights.get('partial_match', 0.70) * similarity
        
        breakdown['base_confidence'] = round(base_confidence, 4)
        
        # Case preservation bonus
        case_bonus = 0.0
        if case_preserved and self.config.get('preserve_case_check', True):
            case_bonus = weights.get('case_preservation', 0.05)
            breakdown['case_preservation_bonus'] = round(case_bonus, 4)
        
        # Context validation adjustment
        context_adjustment = 0.0
        if not context_valid:
            context_adjustment = -0.10
            breakdown['context_penalty'] = context_adjustment
        
        confidence = min(1.0, base_confidence + case_bonus + context_adjustment)
        breakdown['final_confidence'] = round(confidence, 4)
        
        return confidence, breakdown
    
    def _determine_approval_status(self, confidence: float) -> Tuple[bool, bool]:
        """
        Determine auto-approval and review status based on confidence.
        
        Args:
            confidence: Confidence score
            
        Returns:
            Tuple of (auto_approved, requires_review)
        """
        auto_threshold = self.config.get('auto_approve_threshold', 0.95)
        suggest_threshold = self.config.get('suggest_threshold', 0.90)
        
        if confidence >= auto_threshold:
            return True, False
        elif confidence >= suggest_threshold:
            return False, False  # Suggested, not auto-approved
        else:
            return False, True
    
    def find_matches(self, text: str, target_lang: str = 'ru') -> List[MatchResult]:
        """
        Find all glossary matches in text.
        
        Args:
            text: Text to search
            target_lang: Target language code
            
        Returns:
            List of MatchResult objects
        """
        if not self.config.get('enabled', True):
            return []
        
        matches = []
        
        for source_term, target_term in self.glossary.items():
            # Skip empty terms
            if not source_term or not target_term:
                continue
            
            # Determine if case-sensitive matching
            case_sensitive = self.config.get('case_sensitive', False)
            if self._is_brand_name(source_term):
                case_sensitive = True
            
            # Find all occurrences
            term_matches = self._find_term_matches(
                text, source_term, target_term, case_sensitive
            )
            matches.extend(term_matches)
        
        # Sort by position
        matches.sort(key=lambda m: m.position)
        
        return matches
    
    def _find_term_matches(self, text: str, source_term: str, 
                           target_term: str, case_sensitive: bool) -> List[MatchResult]:
        """
        Find all matches for a specific term in text.
        
        Args:
            text: Text to search
            source_term: Source glossary term
            target_term: Target glossary term
            case_sensitive: Whether to use case-sensitive matching
            
        Returns:
            List of MatchResult objects
        """
        matches = []
        search_text = text if case_sensitive else text.lower()
        search_term = source_term if case_sensitive else source_term.lower()
        
        # Check for abbreviations - require exact match
        if self._is_abbreviation(source_term):
            if search_term in search_text:
                start = 0
                while True:
                    position = search_text.find(search_term, start)
                    if position == -1:
                        break
                    
                    found_text = text[position:position + len(source_term)]
                    context_before, context_after = self._get_context(
                        text, position, len(source_term)
                    )
                    
                    case_preserved = self._check_case_preservation(source_term, found_text)
                    confidence, breakdown = self._calculate_confidence(
                        'exact', 1.0, case_preserved, True
                    )
                    auto_approved, requires_review = self._determine_approval_status(confidence)
                    
                    matches.append(MatchResult(
                        source_term=source_term,
                        target_term=target_term,
                        found_text=found_text,
                        confidence=confidence,
                        match_type='exact',
                        context_before=context_before,
                        context_after=context_after,
                        position=position,
                        length=len(source_term),
                        auto_approved=auto_approved,
                        requires_review=requires_review,
                        case_preserved=case_preserved,
                        confidence_breakdown=breakdown
                    ))
                    start = position + 1
            return matches
        
        # Multi-word phrase and substring matching
        # For Chinese text, we need substring matching, not word-based
        if self.config.get('multi_word_phrase_matching', True):
            # Try to find the term as a substring first (exact match)
            if search_term in search_text:
                start = 0
                while True:
                    position = search_text.find(search_term, start)
                    if position == -1:
                        break
                    
                    found_text = text[position:position + len(source_term)]
                    
                    # Get context
                    context_before, context_after = self._get_context(
                        text, position, len(source_term)
                    )
                    
                    # Validate context for homonyms
                    context_valid, _ = self._validate_context(
                        source_term, context_before, context_after
                    )
                    
                    # Check case preservation
                    case_preserved = self._check_case_preservation(
                        source_term, found_text
                    )
                    
                    # Calculate confidence (exact match = 1.0)
                    confidence, breakdown = self._calculate_confidence(
                        'exact', 1.0, case_preserved, context_valid
                    )
                    
                    # Determine approval status
                    auto_approved, requires_review = self._determine_approval_status(confidence)
                    
                    match = MatchResult(
                        source_term=source_term,
                        target_term=target_term,
                        found_text=found_text,
                        confidence=confidence,
                        match_type='exact',
                        context_before=context_before,
                        context_after=context_after,
                        position=position,
                        length=len(source_term),
                        auto_approved=auto_approved,
                        requires_review=requires_review,
                        case_preserved=case_preserved,
                        confidence_breakdown=breakdown
                    )
                    matches.append(match)
                    start = position + 1
            
            # Try fuzzy matching for similar terms
            fuzzy_threshold = self.config.get('fuzzy_threshold', 0.90)
            
            # For short texts, check all substrings of similar length
            if len(search_term) <= 20:
                # Scan text with sliding window
                for window_len in range(len(search_term) - 1, len(search_term) + 2):
                    if window_len < 1:
                        continue
                    for i in range(len(search_text) - window_len + 1):
                        candidate = search_text[i:i + window_len]
                        similarity = self._similarity_ratio(candidate, search_term)
                        
                        if similarity >= fuzzy_threshold:
                            # Check if we already have an exact match at this position
                            already_matched = any(
                                m.position == i for m in matches
                            )
                            if already_matched:
                                continue
                            
                            original_candidate = text[i:i + window_len]
                            
                            # Get context
                            context_before, context_after = self._get_context(
                                text, i, window_len
                            )
                            
                            # Validate context for homonyms
                            context_valid, _ = self._validate_context(
                                source_term, context_before, context_after
                            )
                            
                            # Check case preservation
                            case_preserved = self._check_case_preservation(
                                source_term, original_candidate
                            )
                            
                            # Determine match type
                            if similarity >= 1.0:
                                match_type = 'exact'
                            elif similarity >= 0.95:
                                match_type = 'fuzzy'
                            else:
                                match_type = 'partial'
                            
                            # Calculate confidence
                            confidence, breakdown = self._calculate_confidence(
                                match_type, similarity, case_preserved, context_valid
                            )
                            
                            # Determine approval status
                            auto_approved, requires_review = self._determine_approval_status(confidence)
                            
                            match = MatchResult(
                                source_term=source_term,
                                target_term=target_term,
                                found_text=original_candidate,
                                confidence=confidence,
                                match_type=match_type,
                                context_before=context_before,
                                context_after=context_after,
                                position=i,
                                length=window_len,
                                auto_approved=auto_approved,
                                requires_review=requires_review,
                                case_preserved=case_preserved,
                                confidence_breakdown=breakdown
                            )
                            matches.append(match)
        else:
            # Simple substring matching
            if search_term in search_text:
                start = 0
                while True:
                    position = search_text.find(search_term, start)
                    if position == -1:
                        break
                    
                    found_text = text[position:position + len(source_term)]
                    
                    context_before, context_after = self._get_context(
                        text, position, len(source_term)
                    )
                    
                    case_preserved = self._check_case_preservation(source_term, found_text)
                    confidence, breakdown = self._calculate_confidence(
                        'exact', 1.0, case_preserved, True
                    )
                    auto_approved, requires_review = self._determine_approval_status(confidence)
                    
                    matches.append(MatchResult(
                        source_term=source_term,
                        target_term=target_term,
                        found_text=found_text,
                        confidence=confidence,
                        match_type='exact',
                        context_before=context_before,
                        context_after=context_after,
                        position=position,
                        length=len(source_term),
                        auto_approved=auto_approved,
                        requires_review=requires_review,
                        case_preserved=case_preserved,
                        confidence_breakdown=breakdown
                    ))
                    start = position + 1
        
        return matches
    
    def process_batch(self, texts: List[str], 
                      translations: Optional[List[str]] = None) -> Dict:
        """
        Process a batch of texts and generate metrics.
        
        Args:
            texts: List of source texts
            translations: Optional list of translations to verify
            
        Returns:
            Dictionary with results and metrics
        """
        all_matches = []
        text_results = []
        
        for i, text in enumerate(texts):
            matches = self.find_matches(text)
            all_matches.extend(matches)
            
            result = {
                'text_index': i,
                'source_text': text,
                'matches': [m.to_dict() for m in matches],
                'match_count': len(matches),
                'auto_approved_count': sum(1 for m in matches if m.auto_approved),
                'review_required_count': sum(1 for m in matches if m.requires_review)
            }
            
            if translations and i < len(translations):
                result['translation'] = translations[i]
            
            text_results.append(result)
        
        # Calculate metrics
        total_matches = len(all_matches)
        auto_approved = sum(1 for m in all_matches if m.auto_approved)
        requires_review = sum(1 for m in all_matches if m.requires_review)
        
        metrics = {
            'total_texts': len(texts),
            'total_matches': total_matches,
            'auto_approved': auto_approved,
            'auto_approval_rate': round(auto_approved / total_matches, 4) if total_matches > 0 else 0.0,
            'requires_review': requires_review,
            'review_rate': round(requires_review / total_matches, 4) if total_matches > 0 else 0.0,
            'suggested': total_matches - auto_approved - requires_review,
            'average_confidence': round(
                sum(m.confidence for m in all_matches) / total_matches, 4
            ) if total_matches > 0 else 0.0
        }
        
        return {
            'metrics': metrics,
            'text_results': text_results,
            'all_matches': [m.to_dict() for m in all_matches]
        }
    
    def export_jsonl(self, matches: List[MatchResult], output_path: str) -> None:
        """
        Export matches to JSONL format.
        
        Args:
            matches: List of MatchResult objects
            output_path: Output file path
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for match in matches:
                f.write(json.dumps(match.to_dict(), ensure_ascii=False) + '\n')
    
    def export_csv(self, matches: List[MatchResult], output_path: str) -> None:
        """
        Export matches to CSV format with annotations.
        
        Args:
            matches: List of MatchResult objects
            output_path: Output file path
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        fieldnames = [
            'source_term', 'target_term', 'found_text', 'confidence',
            'match_type', 'auto_approved', 'requires_review', 'case_preserved',
            'context_before', 'context_after', 'position', 'timestamp'
        ]
        
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for match in matches:
                row = match.to_dict()
                # Flatten for CSV
                row.pop('confidence_breakdown', None)
                row.pop('length', None)
                writer.writerow(row)
    
    def export_highlight_html(self, texts: List[str], matches: List[MatchResult],
                              output_path: str) -> None:
        """
        Export highlighted HTML for human reviewers.
        
        Args:
            texts: Original texts
            matches: List of MatchResult objects
            output_path: Output file path
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Group matches by position for highlighting
        match_by_text = {}
        for match in matches:
            # Find which text this match belongs to
            for i, text in enumerate(texts):
                if match.found_text in text:
                    if i not in match_by_text:
                        match_by_text[i] = []
                    match_by_text[i].append(match)
                    break
        
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Glossary Match Highlights</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .text-block { margin: 20px 0; padding: 15px; border: 1px solid #ddd; }
        .match-exact { background-color: #90EE90; padding: 2px 4px; }
        .match-fuzzy { background-color: #FFD700; padding: 2px 4px; }
        .match-context { background-color: #87CEEB; padding: 2px 4px; }
        .match-partial { background-color: #FFB6C1; padding: 2px 4px; }
        .confidence-high { border-bottom: 3px solid #228B22; }
        .confidence-medium { border-bottom: 3px solid #FFA500; }
        .confidence-low { border-bottom: 3px solid #DC143C; }
        .legend { margin: 20px 0; padding: 10px; background: #f5f5f5; }
        .legend-item { display: inline-block; margin-right: 20px; }
    </style>
</head>
<body>
    <h1>Glossary Match Review</h1>
    <div class="legend">
        <h3>Legend:</h3>
        <div class="legend-item"><span class="match-exact">Exact Match</span></div>
        <div class="legend-item"><span class="match-fuzzy">Fuzzy Match</span></div>
        <div class="legend-item"><span class="match-context">Context Validated</span></div>
        <div class="legend-item"><span class="match-partial">Partial Match</span></div>
        <br><br>
        <div class="legend-item"><span class="confidence-high">Auto-Approved (≥95%)</span></div>
        <div class="legend-item"><span class="confidence-medium">Suggested (90-95%)</span></div>
        <div class="legend-item"><span class="confidence-low">Needs Review (&lt;90%)</span></div>
    </div>
"""
        
        for i, text in enumerate(texts):
            html += f'    <div class="text-block">\n'
            html += f'        <h3>Text {i+1}</h3>\n'
            html += f'        <p>{self._highlight_text(text, match_by_text.get(i, []))}</p>\n'
            html += f'    </div>\n'
        
        html += """</body>
</html>"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
    
    def _highlight_text(self, text: str, matches: List[MatchResult]) -> str:
        """Create highlighted HTML for text with matches."""
        if not matches:
            return text
        
        # Sort matches by position (reverse to replace from end)
        matches = sorted(matches, key=lambda m: m.position, reverse=True)
        
        result = text
        for match in matches:
            # Determine CSS classes
            css_class = f"match-{match.match_type.replace('_', '-')}"
            
            if match.confidence >= 0.95:
                css_class += " confidence-high"
            elif match.confidence >= 0.90:
                css_class += " confidence-medium"
            else:
                css_class += " confidence-low"
            
            # Create tooltip
            tooltip = f"title=\"{match.source_term} → {match.target_term} (confidence: {match.confidence:.2f})\""
            
            # Replace in result
            start = match.position
            end = match.position + match.length
            highlighted = f'<span class="{css_class}" {tooltip}>{match.found_text}</span>'
            result = result[:start] + highlighted + result[end:]
        
        return result


def main():
    """Example usage of GlossaryMatcher."""
    # Create matcher
    matcher = GlossaryMatcher()
    
    # Load glossary
    sample_glossary = {
        "攻击": "Атака",
        "伤害": "Урон",
        "忍者": "Ниндзя",
        "生命": "Здоровье",
        "暴击": "Критический удар",
        "确定": "OK",
        "PlayStation": "PlayStation"
    }
    matcher.load_glossary(sample_glossary)
    
    # Test text
    test_texts = [
        "忍者的攻击力很高，暴击伤害也很强。",
        "点击确定按钮开始游戏。",
        "PlayStation游戏机很受欢迎。"
    ]
    
    # Process batch
    results = matcher.process_batch(test_texts)
    
    # Print metrics
    print("Metrics:", json.dumps(results['metrics'], indent=2, ensure_ascii=False))
    
    # Export results
    all_matches_dicts = results['all_matches']
    all_matches = []
    for m_dict in all_matches_dicts:
        m_dict_copy = m_dict.copy()
        m_dict_copy.pop('timestamp', None)  # Remove timestamp field
        all_matches.append(MatchResult(**m_dict_copy))
    
    matcher.export_jsonl(all_matches, "reports/glossary_matches.jsonl")
    matcher.export_csv(all_matches, "reports/glossary_matches.csv")
    matcher.export_highlight_html(test_texts, all_matches, "reports/glossary_highlights.html")
    
    print("\nResults exported to reports/")


if __name__ == "__main__":
    main()
