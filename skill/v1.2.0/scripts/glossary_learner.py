"""
Glossary Learning System for Continuous Improvement

This module implements a learning system that:
- Tracks human reviewer decisions on glossary matches
- Learns from accepted/rejected matches to improve confidence
- Discovers new glossary candidates from project data
- Generates reports on learning progress and accuracy improvements

Target: 5% improvement in auto-approval rate per week of usage
"""

import json
import yaml
import math
import hashlib
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional, Any, Set
from dataclasses import dataclass, field, asdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class FeedbackEntry:
    """Single feedback entry from human reviewer"""
    timestamp: str
    term_zh: str
    term_ru: str
    source_text: str
    context: str
    decision: str  # 'accepted', 'rejected', 'corrected'
    reviewer_id: Optional[str] = None
    correction: Optional[str] = None  # If decision is 'corrected'
    confidence: float = 0.0
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'FeedbackEntry':
        return cls(**data)


@dataclass
class TermStats:
    """Statistics for a single glossary term"""
    term_zh: str
    term_ru: str
    total_uses: int = 0
    accepted_count: int = 0
    rejected_count: int = 0
    corrected_count: int = 0
    confidence: float = 0.5  # Bayesian prior
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    contexts: List[str] = field(default_factory=list)
    variants: Set[str] = field(default_factory=set)
    
    @property
    def accuracy(self) -> float:
        """Calculate accuracy rate"""
        total = self.accepted_count + self.rejected_count + self.corrected_count
        if total == 0:
            return 0.5
        return (self.accepted_count + self.corrected_count * 0.5) / total
    
    @property
    def auto_approve_eligible(self) -> bool:
        """Check if term can be auto-approved"""
        return self.confidence >= 0.8 and self.total_uses >= 5
    
    def update_confidence(self, update_rate: float = 0.1):
        """Update confidence using Bayesian approach"""
        # Bayesian update: confidence moves toward accuracy
        accuracy = self.accuracy
        self.confidence = self.confidence * (1 - update_rate) + accuracy * update_rate
        self.last_updated = datetime.now().isoformat()


@dataclass
class SuggestedTerm:
    """A newly discovered term suggestion"""
    term_zh: str
    term_ru: str
    confidence: float
    occurrences: int
    contexts: List[str]
    similarity_to_known: float
    suggested_by: str
    timestamp: str
    
    def to_dict(self) -> Dict:
        return {
            'term_zh': self.term_zh,
            'term_ru': self.term_ru,
            'confidence': self.confidence,
            'occurrences': self.occurrences,
            'contexts': self.contexts[:5],  # Limit contexts
            'similarity_to_known': self.similarity_to_known,
            'suggested_by': self.suggested_by,
            'timestamp': self.timestamp
        }


class SimilarityClusterer:
    """Clusters similar terms using character n-gram similarity"""
    
    def __init__(self, n: int = 2):
        self.n = n
    
    def ngrams(self, text: str) -> Set[str]:
        """Generate character n-grams from text"""
        text = text.lower()
        return set(text[i:i+self.n] for i in range(len(text) - self.n + 1))
    
    def similarity(self, text1: str, text2: str) -> float:
        """Calculate Jaccard similarity between two texts"""
        ngrams1 = self.ngrams(text1)
        ngrams2 = self.ngrams(text2)
        
        if not ngrams1 or not ngrams2:
            return 0.0
        
        intersection = len(ngrams1 & ngrams2)
        union = len(ngrams1 | ngrams2)
        
        return intersection / union if union > 0 else 0.0
    
    def find_variants(self, term: str, all_terms: List[str], threshold: float = 0.7) -> List[str]:
        """Find variants of a term from list of all terms"""
        variants = []
        for other in all_terms:
            if other != term and self.similarity(term, other) >= threshold:
                variants.append(other)
        return variants


class TFIDFDiscoverer:
    """Discovers new terms using TF-IDF analysis"""
    
    def __init__(self):
        self.document_freq = Counter()
        self.total_documents = 0
        self.term_contexts = defaultdict(list)
    
    def add_document(self, doc_id: str, text_zh: str, text_ru: str):
        """Add a parallel document for analysis"""
        self.total_documents += 1
        
        # Extract potential terms (phrases of 1-4 characters)
        zh_terms = self._extract_phrases(text_zh)
        ru_terms = self._extract_phrases_ru(text_ru)
        
        # Update document frequency
        for term in set(zh_terms):
            self.document_freq[term] += 1
            self.term_contexts[term].append({
                'doc_id': doc_id,
                'context_zh': text_zh,
                'context_ru': text_ru
            })
    
    def _extract_phrases(self, text: str) -> List[str]:
        """Extract Chinese phrases of various lengths"""
        # Remove punctuation and split
        text = re.sub(r'[^\u4e00-\u9fff]', '', text)
        phrases = []
        
        for length in range(1, 5):
            for i in range(len(text) - length + 1):
                phrases.append(text[i:i+length])
        
        return phrases
    
    def _extract_phrases_ru(self, text: str) -> List[str]:
        """Extract Russian words/phrases"""
        # Simple word extraction
        words = re.findall(r'[а-яА-ЯёЁ]+', text.lower())
        return words
    
    def calculate_tfidf(self, term: str, count: int) -> float:
        """Calculate TF-IDF score for a term"""
        if self.total_documents == 0:
            return 0.0
        
        tf = math.log1p(count)  # Log normalization
        df = self.document_freq.get(term, 1)
        idf = math.log(self.total_documents / df)
        
        return tf * idf
    
    def get_top_candidates(self, min_count: int = 3, top_n: int = 50) -> List[Tuple[str, float]]:
        """Get top term candidates by TF-IDF"""
        scores = []
        
        for term, count in self.document_freq.items():
            if count >= min_count and len(term) >= 2:
                tfidf = self.calculate_tfidf(term, count)
                scores.append((term, tfidf))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_n]


class PatternMiner:
    """Mines common translation patterns from approved translations"""
    
    def __init__(self):
        self.patterns = defaultdict(lambda: defaultdict(int))
        self.total_count = 0
    
    def extract_patterns(self, text_zh: str, text_ru: str) -> List[Tuple[str, str]]:
        """Extract potential term pairs from parallel text"""
        patterns = []
        
        # Pattern 1: Bracketed terms
        zh_brackets = re.findall(r'[（(]([^）)]+)[）)]', text_zh)
        ru_brackets = re.findall(r'[\[(]([^\])]+)[\])]', text_ru)
        
        if len(zh_brackets) == len(ru_brackets):
            for zh, ru in zip(zh_brackets, ru_brackets):
                if len(zh) >= 2 and len(ru) >= 2:
                    patterns.append((zh, ru))
        
        # Pattern 2: Capitalized sections (potential proper nouns)
        zh_sections = re.findall(r'[「"]([^"」]+)["」]', text_zh)
        ru_capitalized = re.findall(r'\b([А-Я][а-яё]+)\b', text_ru)
        
        if len(zh_sections) <= len(ru_capitalized):
            for zh, ru in zip(zh_sections, ru_capitalized[:len(zh_sections)]):
                patterns.append((zh, ru))
        
        # Pattern 3: Repeated phrases
        zh_phrases = self._get_repeated_phrases(text_zh)
        ru_phrases = self._get_repeated_phrases(text_ru)
        
        for zh_phrase in zh_phrases:
            for ru_phrase in ru_phrases:
                # Simple alignment by position
                patterns.append((zh_phrase, ru_phrase))
        
        return patterns
    
    def _get_repeated_phrases(self, text: str) -> List[str]:
        """Find repeated phrases in text"""
        # Simplified - in production would use more sophisticated method
        words = re.findall(r'\w+', text)
        word_counts = Counter(words)
        return [w for w, c in word_counts.items() if c >= 2 and len(w) >= 2]
    
    def add_pattern(self, zh: str, ru: str):
        """Add a pattern observation"""
        self.patterns[zh][ru] += 1
        self.total_count += 1
    
    def get_common_patterns(self, min_occurrences: int = 2) -> List[Tuple[str, str, int]]:
        """Get patterns that occur frequently"""
        result = []
        for zh, ru_counts in self.patterns.items():
            for ru, count in ru_counts.items():
                if count >= min_occurrences:
                    result.append((zh, ru, count))
        
        result.sort(key=lambda x: x[2], reverse=True)
        return result


class GlossaryLearner:
    """
    Main class for glossary learning and improvement.
    
    Features:
    - Feedback tracking and logging
    - Bayesian confidence calibration
    - TF-IDF term discovery
    - Pattern mining for common phrases
    - Similarity clustering for variant detection
    """
    
    def __init__(self, config_path: str = "config/glossary.yaml"):
        self.config = self._load_config(config_path)
        self.base_path = Path(self.config.get('learning_data_path', 'learning_data/'))
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize components
        self.similarity_clusterer = SimilarityClusterer()
        self.tfidf_discoverer = TFIDFDiscoverer()
        self.pattern_miner = PatternMiner()
        
        # Data stores
        self.term_stats: Dict[str, TermStats] = {}
        self.suggested_terms: List[SuggestedTerm] = []
        
        # Load existing data
        self._load_learning_data()
        
        logger.info(f"GlossaryLearner initialized with config from {config_path}")
    
    def _load_config(self, path: str) -> Dict:
        """Load configuration from YAML"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                return config.get('glossary_learning', {})
        except FileNotFoundError:
            logger.warning(f"Config not found at {path}, using defaults")
            return self._default_config()
    
    def _default_config(self) -> Dict:
        """Default configuration"""
        return {
            'enabled': True,
            'min_feedback_count': 5,
            'confidence_update_rate': 0.1,
            'auto_suggest_new_terms': True,
            'term_discovery_threshold': 0.8,
            'learning_data_path': 'learning_data/'
        }
    
    def _load_learning_data(self):
        """Load existing learning data from JSONL files"""
        # Load accepted matches
        accepted_path = self.base_path / 'accepted_matches.jsonl'
        if accepted_path.exists():
            with open(accepted_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        entry = FeedbackEntry.from_dict(json.loads(line))
                        self._update_term_stats(entry)
        
        # Load rejected matches
        rejected_path = self.base_path / 'rejected_matches.jsonl'
        if rejected_path.exists():
            with open(rejected_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        entry = FeedbackEntry.from_dict(json.loads(line))
                        self._update_term_stats(entry)
        
        # Load corrections
        corrections_path = self.base_path / 'human_corrections.jsonl'
        if corrections_path.exists():
            with open(corrections_path, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        entry = FeedbackEntry.from_dict(json.loads(line))
                        self._update_term_stats(entry)
        
        logger.info(f"Loaded learning data: {len(self.term_stats)} terms")
    
    def _update_term_stats(self, entry: FeedbackEntry):
        """Update statistics for a term based on feedback"""
        key = f"{entry.term_zh}|{entry.term_ru}"
        
        if key not in self.term_stats:
            self.term_stats[key] = TermStats(
                term_zh=entry.term_zh,
                term_ru=entry.term_ru
            )
        
        stats = self.term_stats[key]
        stats.total_uses += 1
        
        if entry.decision == 'accepted':
            stats.accepted_count += 1
        elif entry.decision == 'rejected':
            stats.rejected_count += 1
        elif entry.decision == 'corrected':
            stats.corrected_count += 1
            if entry.correction:
                stats.variants.add(entry.correction)
        
        if entry.context:
            stats.contexts.append(entry.context)
            # Keep only recent contexts
            stats.contexts = stats.contexts[-10:]
        
        # Update confidence
        stats.update_confidence(self.config.get('confidence_update_rate', 0.1))
    
    def record_feedback(self, 
                       term_zh: str, 
                       term_ru: str,
                       source_text: str,
                       decision: str,
                       context: str = "",
                       reviewer_id: Optional[str] = None,
                       correction: Optional[str] = None,
                       notes: Optional[str] = None) -> FeedbackEntry:
        """
        Record human reviewer feedback on a glossary match.
        
        Args:
            term_zh: Chinese term
            term_ru: Russian term (proposed or actual)
            source_text: Full source text where match occurred
            decision: 'accepted', 'rejected', or 'corrected'
            context: Additional context
            reviewer_id: Optional reviewer identifier
            correction: If decision is 'corrected', the corrected translation
            notes: Optional reviewer notes
        
        Returns:
            The created FeedbackEntry
        """
        if not self.config.get('enabled', True):
            logger.info("Learning is disabled, skipping feedback recording")
            return None
        
        entry = FeedbackEntry(
            timestamp=datetime.now().isoformat(),
            term_zh=term_zh,
            term_ru=term_ru,
            source_text=source_text,
            context=context,
            decision=decision,
            reviewer_id=reviewer_id,
            correction=correction,
            notes=notes
        )
        
        # Save to appropriate file
        if decision == 'accepted':
            self._append_to_jsonl('accepted_matches.jsonl', entry.to_dict())
        elif decision == 'rejected':
            self._append_to_jsonl('rejected_matches.jsonl', entry.to_dict())
        elif decision == 'corrected':
            self._append_to_jsonl('human_corrections.jsonl', entry.to_dict())
        
        # Update in-memory stats
        self._update_term_stats(entry)
        
        # Mine patterns if accepted or corrected
        if decision in ('accepted', 'corrected'):
            ru_translation = correction if correction else term_ru
            patterns = self.pattern_miner.extract_patterns(source_text, ru_translation)
            for zh, ru in patterns:
                self.pattern_miner.add_pattern(zh, ru)
        
        logger.info(f"Recorded {decision} feedback for '{term_zh}' -> '{term_ru}'")
        return entry
    
    def _append_to_jsonl(self, filename: str, data: Dict):
        """Append a record to a JSONL file"""
        filepath = self.base_path / filename
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False) + '\n')
    
    def process_parallel_corpus(self, corpus: List[Dict[str, str]]):
        """
        Process parallel corpus for term discovery.
        
        Args:
            corpus: List of dicts with 'id', 'zh', 'ru' keys
        """
        if not self.config.get('auto_suggest_new_terms', True):
            return
        
        for item in corpus:
            self.tfidf_discoverer.add_document(
                item['id'],
                item['zh'],
                item['ru']
            )
        
        logger.info(f"Processed {len(corpus)} documents for term discovery")
    
    def discover_new_terms(self, known_terms: List[Dict[str, str]]) -> List[SuggestedTerm]:
        """
        Discover new glossary candidates from processed corpus.
        
        Args:
            known_terms: List of existing glossary entries with 'term_zh' and 'term_ru'
        
        Returns:
            List of suggested new terms
        """
        if not self.config.get('auto_suggest_new_terms', True):
            return []
        
        known_zh = {t['term_zh'] for t in known_terms}
        threshold = self.config.get('term_discovery_threshold', 0.8)
        
        candidates = []
        top_candidates = self.tfidf_discoverer.get_top_candidates(min_count=3, top_n=100)
        
        for term_zh, tfidf_score in top_candidates:
            if term_zh in known_zh:
                continue
            
            # Find most likely Russian translation from contexts
            contexts = self.tfidf_discoverer.term_contexts.get(term_zh, [])
            ru_candidates = self._extract_ru_candidates(contexts, term_zh)
            
            for term_ru, ru_score in ru_candidates[:3]:
                # Calculate similarity to known terms
                similarity = self._calculate_similarity_to_known(term_zh, known_terms)
                
                # Combined confidence score
                confidence = (tfidf_score * 0.4 + ru_score * 0.4 + similarity * 0.2)
                
                if confidence >= threshold:
                    suggestion = SuggestedTerm(
                        term_zh=term_zh,
                        term_ru=term_ru,
                        confidence=min(confidence, 0.99),
                        occurrences=len(contexts),
                        contexts=[c['context_zh'] for c in contexts[:3]],
                        similarity_to_known=similarity,
                        suggested_by='tfidf_discovery',
                        timestamp=datetime.now().isoformat()
                    )
                    candidates.append(suggestion)
        
        # Add pattern-mined candidates
        patterns = self.pattern_miner.get_common_patterns(min_occurrences=3)
        for zh, ru, count in patterns:
            if zh not in known_zh:
                similarity = self._calculate_similarity_to_known(zh, known_terms)
                suggestion = SuggestedTerm(
                    term_zh=zh,
                    term_ru=ru,
                    confidence=min(0.5 + count * 0.05, 0.9),
                    occurrences=count,
                    contexts=[],
                    similarity_to_known=similarity,
                    suggested_by='pattern_mining',
                    timestamp=datetime.now().isoformat()
                )
                candidates.append(suggestion)
        
        # Sort by confidence
        candidates.sort(key=lambda x: x.confidence, reverse=True)
        
        self.suggested_terms = candidates[:50]  # Keep top 50
        logger.info(f"Discovered {len(self.suggested_terms)} new term candidates")
        
        return self.suggested_terms
    
    def _extract_ru_candidates(self, contexts: List[Dict], zh_term: str) -> List[Tuple[str, float]]:
        """Extract Russian translation candidates from contexts"""
        ru_freq = Counter()
        
        for ctx in contexts:
            ru_text = ctx.get('context_ru', '')
            # Extract Russian words/phrases
            words = re.findall(r'\b[а-яА-ЯёЁ]+\b', ru_text)
            ru_freq.update(words)
        
        # Return top candidates with scores
        total = sum(ru_freq.values())
        if total == 0:
            return []
        
        return [(word, count/total) for word, count in ru_freq.most_common(5)]
    
    def _calculate_similarity_to_known(self, term_zh: str, known_terms: List[Dict]) -> float:
        """Calculate average similarity to known terms"""
        if not known_terms:
            return 0.0
        
        similarities = []
        for known in known_terms:
            sim = self.similarity_clusterer.similarity(term_zh, known.get('term_zh', ''))
            similarities.append(sim)
        
        return max(similarities) if similarities else 0.0
    
    def get_confidence_report(self) -> Dict[str, Any]:
        """
        Generate confidence report for all tracked terms.
        
        Returns:
            Dictionary with confidence statistics
        """
        if not self.term_stats:
            return {
                'generated_at': datetime.now().isoformat(),
                'total_terms': 0,
                'message': 'No learning data available'
            }
        
        confidences = [s.confidence for s in self.term_stats.values()]
        accuracies = [s.accuracy for s in self.term_stats.values()]
        
        high_confidence = sum(1 for c in confidences if c >= 0.8)
        medium_confidence = sum(1 for c in confidences if 0.5 <= c < 0.8)
        low_confidence = sum(1 for c in confidences if c < 0.5)
        
        auto_approve_eligible = sum(
            1 for s in self.term_stats.values() 
            if s.auto_approve_eligible
        )
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'total_terms': len(self.term_stats),
            'confidence_distribution': {
                'high': high_confidence,
                'medium': medium_confidence,
                'low': low_confidence
            },
            'confidence_stats': {
                'mean': sum(confidences) / len(confidences),
                'median': sorted(confidences)[len(confidences) // 2],
                'min': min(confidences),
                'max': max(confidences)
            },
            'accuracy_stats': {
                'mean': sum(accuracies) / len(accuracies) if accuracies else 0,
                'median': sorted(accuracies)[len(accuracies) // 2] if accuracies else 0
            },
            'auto_approve_eligible': auto_approve_eligible,
            'auto_approve_rate': auto_approve_eligible / len(self.term_stats) if self.term_stats else 0,
            'term_details': [
                {
                    'term_zh': s.term_zh,
                    'term_ru': s.term_ru,
                    'confidence': round(s.confidence, 3),
                    'accuracy': round(s.accuracy, 3),
                    'total_uses': s.total_uses,
                    'auto_approve_eligible': s.auto_approve_eligible
                }
                for s in sorted(
                    self.term_stats.values(), 
                    key=lambda x: x.confidence, 
                    reverse=True
                )
            ]
        }
        
        return report
    
    def generate_weekly_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive weekly learning report.
        
        Returns:
            Dictionary with weekly learning metrics
        """
        one_week_ago = (datetime.now() - timedelta(days=7)).isoformat()
        
        # Count recent feedback
        recent_accepted = 0
        recent_rejected = 0
        recent_corrected = 0
        
        # Read recent entries
        for filename in ['accepted_matches.jsonl', 'rejected_matches.jsonl', 'human_corrections.jsonl']:
            filepath = self.base_path / filename
            if not filepath.exists():
                continue
            
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    if not line.strip():
                        continue
                    entry = json.loads(line)
                    if entry.get('timestamp', '') >= one_week_ago:
                        if 'accepted' in filename:
                            recent_accepted += 1
                        elif 'rejected' in filename:
                            recent_rejected += 1
                        else:
                            recent_corrected += 1
        
        total_feedback = recent_accepted + recent_rejected + recent_corrected
        acceptance_rate = recent_accepted / total_feedback if total_feedback > 0 else 0
        
        # Calculate improvement in auto-approval rate
        previous_auto_approve = getattr(self, '_last_week_auto_approve', 0)
        current_auto_approve = sum(
            1 for s in self.term_stats.values() 
            if s.auto_approve_eligible
        )
        auto_approve_improvement = (
            (current_auto_approve - previous_auto_approve) / len(self.term_stats) * 100
            if self.term_stats and previous_auto_approve > 0
            else 0
        )
        
        # Save for next comparison
        self._last_week_auto_approve = current_auto_approve
        
        report = {
            'report_period': 'weekly',
            'generated_at': datetime.now().isoformat(),
            'period_start': one_week_ago,
            'feedback_summary': {
                'total': total_feedback,
                'accepted': recent_accepted,
                'rejected': recent_rejected,
                'corrected': recent_corrected,
                'acceptance_rate': round(acceptance_rate, 3)
            },
            'learning_progress': {
                'total_terms_tracked': len(self.term_stats),
                'new_terms_discovered': len(self.suggested_terms),
                'auto_approve_eligible': current_auto_approve,
                'auto_approve_rate_improvement': round(auto_approve_improvement, 2)
            },
            'top_improved_terms': [
                {
                    'term_zh': s.term_zh,
                    'term_ru': s.term_ru,
                    'confidence': round(s.confidence, 3),
                    'accuracy': round(s.accuracy, 3)
                }
                for s in sorted(
                    self.term_stats.values(),
                    key=lambda x: x.confidence,
                    reverse=True
                )[:10]
            ],
            'suggested_terms': [
                s.to_dict() for s in self.suggested_terms[:20]
            ]
        }
        
        return report
    
    def save_glossary_suggestions(self, output_path: str = "glossary_suggestions.json"):
        """Save discovered term suggestions to JSON"""
        data = {
            'generated_at': datetime.now().isoformat(),
            'total_suggestions': len(self.suggested_terms),
            'suggestions': [s.to_dict() for s in self.suggested_terms]
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(self.suggested_terms)} suggestions to {output_path}")
    
    def save_confidence_report(self, output_path: str = "confidence_report.json"):
        """Save confidence report to JSON"""
        report = self.get_confidence_report()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved confidence report to {output_path}")
    
    def save_weekly_report(self, output_path: str = "weekly_learning_report.json"):
        """Save weekly learning report to JSON"""
        report = self.generate_weekly_report()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved weekly report to {output_path}")
    
    def update_glossary_confidence(self, glossary_path: str, output_path: str):
        """
        Update existing glossary with learned confidence scores.
        
        Args:
            glossary_path: Path to existing glossary YAML
            output_path: Path to save updated glossary
        """
        with open(glossary_path, 'r', encoding='utf-8') as f:
            glossary = yaml.safe_load(f)
        
        # Update entries with confidence scores
        for entry in glossary.get('entries', []):
            term_zh = entry.get('term_zh', '')
            term_ru = entry.get('term_ru', '')
            key = f"{term_zh}|{term_ru}"
            
            if key in self.term_stats:
                stats = self.term_stats[key]
                entry['confidence'] = round(stats.confidence, 3)
                entry['auto_approve_eligible'] = stats.auto_approve_eligible
                entry['learning_stats'] = {
                    'total_uses': stats.total_uses,
                    'accuracy': round(stats.accuracy, 3)
                }
        
        # Update metadata
        if 'meta' not in glossary:
            glossary['meta'] = {}
        glossary['meta']['last_learning_update'] = datetime.now().isoformat()
        glossary['meta']['terms_with_confidence'] = len([
            e for e in glossary.get('entries', []) 
            if 'confidence' in e
        ])
        
        with open(output_path, 'w', encoding='utf-8') as f:
            yaml.dump(glossary, f, allow_unicode=True, sort_keys=False)
        
        logger.info(f"Updated glossary saved to {output_path}")
    
    def get_term_frequency_data(self) -> Dict[str, Any]:
        """Get term frequency analysis data"""
        frequency_data = {
            'generated_at': datetime.now().isoformat(),
            'total_terms_analyzed': len(self.tfidf_discoverer.document_freq),
            'top_frequent_terms': [
                {'term': term, 'documents': count}
                for term, count in self.tfidf_discoverer.document_freq.most_common(100)
            ],
            'tfidf_scores': [
                {'term': term, 'tfidf': round(score, 4)}
                for term, score in self.tfidf_discoverer.get_top_candidates(top_n=100)
            ]
        }
        
        return frequency_data
    
    def save_term_frequency(self, output_path: str = "learning_data/term_frequency.json"):
        """Save term frequency data to JSON"""
        data = self.get_term_frequency_data()
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved term frequency data to {output_path}")
    
    def find_term_variants(self, term_zh: str, all_terms: List[str], threshold: float = 0.7) -> List[str]:
        """
        Find variants of a term using similarity clustering.
        
        Args:
            term_zh: The term to find variants for
            all_terms: List of all known terms
            threshold: Similarity threshold (0-1)
        
        Returns:
            List of variant terms
        """
        return self.similarity_clusterer.find_variants(term_zh, all_terms, threshold)
    
    def get_learning_metrics(self) -> Dict[str, Any]:
        """
        Get comprehensive learning metrics.
        
        Returns:
            Dictionary with all learning metrics
        """
        conf_report = self.get_confidence_report()
        
        # Calculate weekly trend
        weekly = self.generate_weekly_report()
        
        return {
            'system_status': {
                'enabled': self.config.get('enabled', True),
                'learning_data_path': str(self.base_path),
                'total_terms_tracked': len(self.term_stats)
            },
            'confidence_metrics': {
                'mean_confidence': conf_report.get('confidence_stats', {}).get('mean', 0),
                'high_confidence_terms': conf_report.get('confidence_distribution', {}).get('high', 0),
                'auto_approve_eligible': conf_report.get('auto_approve_eligible', 0),
                'auto_approve_rate': conf_report.get('auto_approve_rate', 0)
            },
            'recent_activity': weekly.get('feedback_summary', {}),
            'improvement_rate': weekly.get('learning_progress', {}).get('auto_approve_rate_improvement', 0),
            'target_progress': {
                'target': '5% improvement per week',
                'current_week_improvement': weekly.get('learning_progress', {}).get('auto_approve_rate_improvement', 0),
                'status': 'on_track' if weekly.get('learning_progress', {}).get('auto_approve_rate_improvement', 0) >= 5 else 'needs_attention'
            }
        }


def create_sample_learning_data(learner: GlossaryLearner):
    """Create sample learning data for demonstration/testing"""
    sample_feedback = [
        {
            'term_zh': '攻击',
            'term_ru': 'Атака',
            'source_text': '攻击力提升20%',
            'decision': 'accepted',
            'context': 'UI tooltip'
        },
        {
            'term_zh': '暴击',
            'term_ru': 'Критический удар',
            'source_text': '暴击伤害增加',
            'decision': 'accepted',
            'context': 'Skill description'
        },
        {
            'term_zh': '护盾',
            'term_ru': 'Щит',
            'source_text': '获得护盾保护',
            'decision': 'accepted',
            'context': 'Buff description'
        },
        {
            'term_zh': '生命',
            'term_ru': 'Здоровье',
            'source_text': '生命值恢复',
            'decision': 'accepted',
            'context': 'Healing effect'
        },
        {
            'term_zh': '技能',
            'term_ru': 'Навык',
            'source_text': '技能冷却时间',
            'decision': 'accepted',
            'context': 'Skill panel'
        }
    ]
    
    for feedback in sample_feedback:
        learner.record_feedback(**feedback)
    
    logger.info(f"Created {len(sample_feedback)} sample feedback entries")


if __name__ == '__main__':
    # Example usage
    learner = GlossaryLearner()
    
    # Create sample data
    create_sample_learning_data(learner)
    
    # Generate reports
    learner.save_confidence_report()
    learner.save_weekly_report()
    
    # Print metrics
    metrics = learner.get_learning_metrics()
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
