#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Glossary Auto-Corrector
Intelligent correction suggestions for glossary violations

Features:
- Detect glossary term violations in translations
- Suggest corrections based on glossary definitions
- Handle Russian declensions and conjugations
- Context-aware replacement suggestions

Usage:
    python glossary_corrector.py <input_csv> --config config/glossary.yaml
    python glossary_corrector.py <input_csv> --suggest-corrections --output corrections.jsonl
"""

import csv
import json
import re
import sys
from pathlib import Path
from typing import List, Dict, Set, Tuple, Optional, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import argparse

# Ensure UTF-8 output
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

try:
    import yaml
except ImportError:
    print("❌ Error: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(1)


class CorrectionRule(Enum):
    """Types of correction rules"""
    SPELLING = "spelling"
    CAPITALIZATION = "capitalization"
    CASE_ENDING = "case_ending"
    SPACING = "spacing"
    DIRECT_REPLACEMENT = "direct_replacement"
    CONTEXT_DEPENDENT = "context_dependent"


@dataclass
class CorrectionSuggestion:
    """A single correction suggestion"""
    text_id: str
    original: str
    suggested: str
    confidence: float
    rule: str
    context: str
    position: int = 0
    term_zh: str = ""
    term_ru_expected: str = ""
    alternative_suggestions: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text_id": self.text_id,
            "original": self.original,
            "suggested": self.suggested,
            "confidence": self.confidence,
            "rule": self.rule,
            "context": self.context,
            "position": self.position,
            "term_zh": self.term_zh,
            "term_ru_expected": self.term_ru_expected,
            "alternative_suggestions": self.alternative_suggestions
        }


@dataclass
class GlossaryEntry:
    """Glossary entry with term information"""
    term_zh: str
    term_ru: str
    scope: str = "general"
    status: str = "approved"
    tags: List[str] = field(default_factory=list)
    variations: List[str] = field(default_factory=list)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'GlossaryEntry':
        return cls(
            term_zh=data.get('term_zh', ''),
            term_ru=data.get('term_ru', ''),
            scope=data.get('scope', 'general'),
            status=data.get('status', 'approved'),
            tags=data.get('tags', []),
            variations=data.get('variations', [])
        )


class RussianDeclensionHelper:
    """Helper for Russian declensions and case endings"""
    
    # Russian case endings by gender
    CASE_ENDINGS = {
        'masculine': {
            'nominative': ['', 'а', 'я', 'ь', 'й'],
            'genitive': ['а', 'я', 'и', 'я', 'я'],
            'dative': ['у', 'ю', 'и', 'ю', 'ю'],
            'accusative': ['а', 'я', 'я', 'я', 'я'],
            'instrumental': ['ом', 'ем', 'ью', 'ем', 'ем'],
            'prepositional': ['е', 'е', 'и', 'е', 'е'],
        },
        'feminine': {
            'nominative': ['а', 'я', 'ь', 'ия'],
            'genitive': ['ы', 'и', 'и', 'ии'],
            'dative': ['е', 'е', 'и', 'ии'],
            'accusative': ['у', 'ю', 'ь', 'ию'],
            'instrumental': ['ой', 'ей', 'ью', 'ией'],
            'prepositional': ['е', 'е', 'и', 'ии'],
        },
        'neuter': {
            'nominative': ['о', 'е', 'ие'],
            'genitive': ['а', 'я', 'ия'],
            'dative': ['у', 'ю', 'ию'],
            'accusative': ['о', 'е', 'ие'],
            'instrumental': ['ом', 'ем', 'ием'],
            'prepositional': ['е', 'е', 'ии'],
        }
    }
    
    # Common Russian name patterns
    NAME_PATTERNS = {
        'Хэнкок': {
            'gender': 'feminine',
            'base': 'Хэнкок',
            'cases': {
                'nominative': 'Хэнкок',
                'genitive': 'Хэнкок',
                'dative': 'Хэнкок',
                'accusative': 'Хэнкок',
                'instrumental': 'Хэнкок',
                'prepositional': 'Хэнкок',
            }
        },
        'Луффи': {
            'gender': 'masculine', 
            'base': 'Луффи',
            'cases': {
                'nominative': 'Луффи',
                'genitive': 'Луффи',
                'dative': 'Луффи',
                'accusative': 'Луффи',
                'instrumental': 'Луффи',
                'prepositional': 'Луффи',
            }
        },
    }
    
    @classmethod
    def detect_case(cls, word: str, base_form: str) -> Optional[str]:
        """Detect which grammatical case a word is in"""
        if word.lower() == base_form.lower():
            return 'nominative'
        
        # Check for each case pattern
        for case_name in ['genitive', 'dative', 'accusative', 'instrumental', 'prepositional']:
            for gender in ['masculine', 'feminine', 'neuter']:
                endings = cls.CASE_ENDINGS[gender][case_name]
                for ending in endings:
                    if word.lower().endswith(ending.lower()):
                        # Verify it's likely a declension of the base
                        base_without_ending = word[:-len(ending)] if ending else word
                        if base_form.lower().startswith(base_without_ending.lower()[:3]):
                            return case_name
        return None
    
    @classmethod
    def get_correct_form(cls, incorrect_form: str, correct_base: str, 
                         target_case: Optional[str] = None) -> str:
        """Generate correct form preserving case if possible"""
        if target_case is None:
            target_case = cls.detect_case(incorrect_form, incorrect_form) or 'nominative'
        
        # Check if we have a specific pattern for this name
        for name, pattern in cls.NAME_PATTERNS.items():
            if correct_base == name or correct_base in name:
                return pattern['cases'].get(target_case, correct_base)
        
        # For indeclinable names (many foreign names), just return base form
        if cls._is_indeclinable(correct_base):
            return correct_base
        
        # Try to apply appropriate ending
        return cls._apply_case_ending(correct_base, target_case)
    
    @classmethod
    def _is_indeclinable(cls, word: str) -> bool:
        """Check if a word is indeclinable (doesn't change form)"""
        indeclinable_suffixes = ['и', 'о', 'у', 'ы', 'э', 'ю']
        # Many foreign names ending in certain letters are indeclinable
        if any(word.endswith(suffix) for suffix in indeclinable_suffixes):
            return True
        # Names ending in consonant + o/u are often indeclinable
        if re.match(r'.+[бвгджзклмнпрстфхцчшщ][оу]$', word, re.IGNORECASE):
            return True
        return False
    
    @classmethod
    def _apply_case_ending(cls, base: str, case: str) -> str:
        """Apply appropriate case ending to base form"""
        # Default to nominative (base form)
        return base
    
    @classmethod
    def normalize_for_comparison(cls, word: str) -> str:
        """Normalize word for fuzzy comparison"""
        # Remove common declension endings for comparison
        endings = ['а', 'я', 'у', 'ю', 'ом', 'ем', 'ой', 'ей', 'е', 'и', 'ов', 'ев', 'ам', 'ям']
        word_lower = word.lower()
        for ending in sorted(endings, key=len, reverse=True):
            if word_lower.endswith(ending):
                return word[:-len(ending)]
        return word


class GlossaryCorrector:
    """Main glossary correction engine"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else None
        self.config: Dict = {}
        self.glossary: Dict[str, GlossaryEntry] = {}  # term_ru -> entry
        self.glossary_by_zh: Dict[str, GlossaryEntry] = {}  # term_zh -> entry
        self.compiled_patterns: List[Tuple[re.Pattern, GlossaryEntry]] = []
        self.ru_helper = RussianDeclensionHelper()
        
        # Statistics
        self.stats = {
            'total_checked': 0,
            'violations_found': 0,
            'suggestions_generated': 0,
            'by_rule': defaultdict(int)
        }
        
        if self.config_path:
            self.load_config()
    
    def load_config(self) -> bool:
        """Load configuration from YAML file"""
        try:
            if self.config_path and self.config_path.exists():
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = yaml.safe_load(f) or {}
                print(f"✅ Loaded config from {self.config_path}")
                return True
            else:
                # Use default config
                self.config = self._default_config()
                print("⚠️  Using default config")
                return True
        except Exception as e:
            print(f"❌ Error loading config: {e}")
            self.config = self._default_config()
            return False
    
    def _default_config(self) -> Dict:
        """Default configuration"""
        return {
            'glossary_corrections': {
                'enabled': True,
                'suggest_threshold': 0.90,
                'auto_apply_threshold': 0.99,
                'preserve_case': True,
                'language_rules': {
                    'ru': 'russian_declensions',
                    'ja': 'japanese_particles'
                },
                'spelling_variants': {
                    'fuzzy_match_threshold': 0.85
                }
            }
        }
    
    def load_glossary(self, glossary_path: str) -> bool:
        """Load glossary from YAML file"""
        try:
            path = Path(glossary_path)
            if not path.exists():
                print(f"❌ Glossary file not found: {glossary_path}")
                return False
            
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            
            entries_data = data.get('entries', [])
            if not entries_data and 'entries' not in data:
                # Try root level entries (compiled.yaml format)
                entries_data = data.get('entries', [])
            
            for entry_data in entries_data:
                entry = GlossaryEntry.from_dict(entry_data)
                if entry.term_ru:
                    self.glossary[entry.term_ru.lower()] = entry
                    # Store normalized form for fuzzy matching
                    normalized = self.ru_helper.normalize_for_comparison(entry.term_ru)
                    if normalized.lower() != entry.term_ru.lower():
                        self.glossary[normalized.lower()] = entry
                if entry.term_zh:
                    self.glossary_by_zh[entry.term_zh] = entry
            
            self._compile_patterns()
            print(f"✅ Loaded {len(self.glossary)} glossary entries")
            return True
            
        except Exception as e:
            print(f"❌ Error loading glossary: {e}")
            return False
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for glossary terms"""
        self.compiled_patterns = []
        
        for term_ru, entry in self.glossary.items():
            # Escape special regex characters
            escaped = re.escape(term_ru)
            # Create word boundary pattern
            pattern = rf'\b{escaped}\b'
            try:
                compiled = re.compile(pattern, re.IGNORECASE | re.UNICODE)
                self.compiled_patterns.append((compiled, entry))
            except re.error:
                continue
    
    def detect_violations(self, text: str, text_id: str = "") -> List[CorrectionSuggestion]:
        """Detect glossary violations in text and suggest corrections"""
        suggestions = []
        self.stats['total_checked'] += 1
        
        # Strategy 1: Direct spelling errors (common misspellings)
        spelling_suggestions = self._check_spelling_errors(text, text_id)
        suggestions.extend(spelling_suggestions)
        
        # Strategy 2: Capitalization errors
        cap_suggestions = self._check_capitalization(text, text_id)
        suggestions.extend(cap_suggestions)
        
        # Strategy 3: Russian case ending errors
        case_suggestions = self._check_case_endings(text, text_id)
        suggestions.extend(case_suggestions)
        
        # Strategy 4: Spacing issues
        spacing_suggestions = self._check_spacing(text, text_id)
        suggestions.extend(spacing_suggestions)
        
        # Strategy 5: Fuzzy match for similar terms
        fuzzy_suggestions = self._check_fuzzy_matches(text, text_id)
        suggestions.extend(fuzzy_suggestions)
        
        if suggestions:
            self.stats['violations_found'] += 1
            self.stats['suggestions_generated'] += len(suggestions)
        
        return suggestions
    
    def _check_spelling_errors(self, text: str, text_id: str) -> List[CorrectionSuggestion]:
        """Check for common spelling errors"""
        suggestions = []
        
        # Common misspellings mapping
        spelling_fixes = {
            'ханкок': ('Хэнкок', 0.98),
            'хancock': ('Хэнкок', 0.95),
            'ван пис': ('Ван-Пис', 0.97),
            'ванпис': ('Ван-Пис', 0.95),
            'лuffy': ('Луффи', 0.95),
            'зоро': ('Зоро', 0.90),  # Might be valid, lower confidence
            'наруто': ('Наруто', 0.90),
            'шаринган': ('Шаринган', 0.95),
            'шарингэн': ('Шаринган', 0.92),
            'пис': ('Пис', 0.85),
            'бoa': ('Боа', 0.90),
        }
        
        text_lower = text.lower()
        
        for misspelling, (correction, confidence) in spelling_fixes.items():
            # Find all occurrences
            for match in re.finditer(rf'\b{re.escape(misspelling)}\b', text_lower):
                original = text[match.start():match.end()]
                
                # Preserve original capitalization pattern
                if original[0].isupper() if original else False:
                    suggested = correction.capitalize()
                else:
                    suggested = correction
                
                # Get context
                context_start = max(0, match.start() - 20)
                context_end = min(len(text), match.end() + 20)
                context = text[context_start:context_end]
                
                suggestion = CorrectionSuggestion(
                    text_id=text_id,
                    original=original,
                    suggested=suggested,
                    confidence=confidence,
                    rule=CorrectionRule.SPELLING.value,
                    context=context,
                    position=match.start()
                )
                suggestions.append(suggestion)
                self.stats['by_rule'][CorrectionRule.SPELLING.value] += 1
        
        return suggestions
    
    def _check_capitalization(self, text: str, text_id: str) -> List[CorrectionSuggestion]:
        """Check for capitalization errors"""
        suggestions = []
        
        for term_ru, entry in self.glossary.items():
            correct_term = entry.term_ru
            
            # Skip if term is too short
            if len(correct_term) < 2:
                continue
            
            # Look for lowercase version of proper nouns
            if correct_term[0].isupper():
                lowercase_pattern = rf'\b{re.escape(correct_term.lower())}\b'
                
                for match in re.finditer(lowercase_pattern, text.lower()):
                    # Check if it's actually lowercase in original
                    original = text[match.start():match.end()]
                    if original != correct_term:  # Different capitalization
                        context_start = max(0, match.start() - 20)
                        context_end = min(len(text), match.end() + 20)
                        context = text[context_start:context_end]
                        
                        suggestion = CorrectionSuggestion(
                            text_id=text_id,
                            original=original,
                            suggested=correct_term,
                            confidence=0.95,
                            rule=CorrectionRule.CAPITALIZATION.value,
                            context=context,
                            position=match.start(),
                            term_zh=entry.term_zh,
                            term_ru_expected=correct_term
                        )
                        suggestions.append(suggestion)
                        self.stats['by_rule'][CorrectionRule.CAPITALIZATION.value] += 1
        
        return suggestions
    
    def _check_case_endings(self, text: str, text_id: str) -> List[CorrectionSuggestion]:
        """Check for incorrect Russian case endings"""
        suggestions = []
        
        # Terms that commonly have case ending issues
        case_sensitive_terms = {
            'Хэнкок': ['Хэнкоку', 'Хэнкока', 'Хэнкоком', 'Хэнкоке'],
            'Луффи': ['Луффи', 'Луффи'],
            'Зоро': ['Зоро'],
            'Наруто': ['Наруто'],
            'Саске': ['Саске'],
            'Коноха': ['Конохе', 'Коноху', 'Конохой'],
            'Шаринган': ['Шарингана', 'Шарингану', 'Шаринганом'],
            'Чидори': ['Чидори'],
            'Расенган': ['Расенгана', 'Расенгану'],
        }
        
        for correct_form, incorrect_forms in case_sensitive_terms.items():
            for incorrect in incorrect_forms:
                pattern = rf'\b{re.escape(incorrect)}\b'
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    original = text[match.start():match.end()]
                    
                    # Get context to verify it's the same entity
                    context_start = max(0, match.start() - 30)
                    context_end = min(len(text), match.end() + 30)
                    context = text[context_start:context_end]
                    
                    # Calculate confidence based on similarity
                    if incorrect.lower() == correct_form.lower():
                        confidence = 0.90  # Same word, different case
                    else:
                        confidence = 0.85  # Different case ending
                    
                    suggestion = CorrectionSuggestion(
                        text_id=text_id,
                        original=original,
                        suggested=correct_form,
                        confidence=confidence,
                        rule=CorrectionRule.CASE_ENDING.value,
                        context=context,
                        position=match.start()
                    )
                    suggestions.append(suggestion)
                    self.stats['by_rule'][CorrectionRule.CASE_ENDING.value] += 1
        
        return suggestions
    
    def _check_spacing(self, text: str, text_id: str) -> List[CorrectionSuggestion]:
        """Check for spacing issues (e.g., 'Ван Пис' vs 'Ван-Пис')"""
        suggestions = []
        
        spacing_fixes = [
            # (pattern_with_space, correct_with_hyphen, confidence)
            (r'\bВан\s+Пис\b', 'Ван-Пис', 0.97),
            (r'\bван\s+пис\b', 'Ван-Пис', 0.95),
            (r'\bОдин\s+Кусок\b', 'Один-Кусок', 0.90),  # Less common
            (r'\bНаруто\s+Ураганные\s+Хроники\b', 'Наруто: Ураганные Хроники', 0.92),
        ]
        
        for pattern, correction, confidence in spacing_fixes:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                original = text[match.start():match.end()]
                
                # Preserve capitalization
                if original[0].isupper():
                    suggested = correction
                else:
                    suggested = correction.lower()
                
                context_start = max(0, match.start() - 20)
                context_end = min(len(text), match.end() + 20)
                context = text[context_start:context_end]
                
                suggestion = CorrectionSuggestion(
                    text_id=text_id,
                    original=original,
                    suggested=suggested,
                    confidence=confidence,
                    rule=CorrectionRule.SPACING.value,
                    context=context,
                    position=match.start()
                )
                suggestions.append(suggestion)
                self.stats['by_rule'][CorrectionRule.SPACING.value] += 1
        
        return suggestions
    
    def _check_fuzzy_matches(self, text: str, text_id: str) -> List[CorrectionSuggestion]:
        """Check for terms that are similar but not exact matches"""
        suggestions = []
        
        # Words that look similar to glossary terms
        words = re.findall(r'\b[\u0400-\u04FF]+\b', text)  # Russian words
        
        for word in words:
            word_lower = word.lower()
            
            for term_ru, entry in self.glossary.items():
                if len(term_ru) < 3 or len(word) < 3:
                    continue
                
                # Skip exact matches
                if word_lower == term_ru.lower():
                    continue
                
                # Calculate similarity
                similarity = self._calculate_similarity(word_lower, term_ru.lower())
                
                threshold = self.config.get('glossary_corrections', {}).get(
                    'spelling_variants', {}).get('fuzzy_match_threshold', 0.85)
                
                if similarity >= threshold:
                    context_pattern = rf'.{{0,20}}\b{re.escape(word)}\b.{{0,20}}'
                    context_match = re.search(context_pattern, text)
                    context = context_match.group(0) if context_match else word
                    
                    suggestion = CorrectionSuggestion(
                        text_id=text_id,
                        original=word,
                        suggested=entry.term_ru,
                        confidence=round(similarity, 2),
                        rule=CorrectionRule.DIRECT_REPLACEMENT.value,
                        context=context,
                        position=text.find(word),
                        term_zh=entry.term_zh,
                        term_ru_expected=entry.term_ru
                    )
                    suggestions.append(suggestion)
                    self.stats['by_rule'][CorrectionRule.DIRECT_REPLACEMENT.value] += 1
        
        return suggestions
    
    def _calculate_similarity(self, s1: str, s2: str) -> float:
        """Calculate similarity between two strings (0-1)"""
        # Use Levenshtein distance ratio
        import difflib
        return difflib.SequenceMatcher(None, s1, s2).ratio()
    
    def apply_corrections(self, text: str, suggestions: List[CorrectionSuggestion],
                         auto_apply_threshold: Optional[float] = None) -> str:
        """Apply corrections to text based on confidence threshold"""
        if auto_apply_threshold is None:
            auto_apply_threshold = self.config.get('glossary_corrections', {}).get(
                'auto_apply_threshold', 0.99)
        
        # Sort by position in reverse order to apply from end to start
        sorted_suggestions = sorted(
            [s for s in suggestions if s.confidence >= auto_apply_threshold],
            key=lambda x: x.position,
            reverse=True
        )
        
        result = text
        applied = 0
        
        for suggestion in sorted_suggestions:
            # Verify the original still exists at that position
            if result[suggestion.position:suggestion.position + len(suggestion.original)] == suggestion.original:
                result = (result[:suggestion.position] + 
                         suggestion.suggested + 
                         result[suggestion.position + len(suggestion.original):])
                applied += 1
        
        return result
    
    def process_csv(self, csv_path: str, text_column: str = 'target_text',
                    id_column: str = 'string_id') -> List[CorrectionSuggestion]:
        """Process a CSV file and return all suggestions"""
        all_suggestions = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.DictReader(f)
                
                for row in reader:
                    text_id = row.get(id_column, '')
                    text = row.get(text_column, '')
                    
                    if not text:
                        continue
                    
                    suggestions = self.detect_violations(text, text_id)
                    all_suggestions.extend(suggestions)
            
            return all_suggestions
            
        except FileNotFoundError:
            print(f"❌ CSV file not found: {csv_path}")
            return []
        except Exception as e:
            print(f"❌ Error processing CSV: {e}")
            return []
    
    def save_suggestions(self, suggestions: List[CorrectionSuggestion], 
                         output_path: str) -> bool:
        """Save suggestions to JSONL file"""
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                for suggestion in suggestions:
                    f.write(json.dumps(suggestion.to_dict(), ensure_ascii=False) + '\n')
            
            print(f"✅ Saved {len(suggestions)} suggestions to {output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving suggestions: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """Get correction statistics"""
        return dict(self.stats)
    
    def print_summary(self) -> None:
        """Print summary of corrections"""
        print("\n📊 Glossary Correction Summary:")
        print(f"   Total texts checked: {self.stats['total_checked']}")
        print(f"   Texts with violations: {self.stats['violations_found']}")
        print(f"   Suggestions generated: {self.stats['suggestions_generated']}")
        print("\n   By rule:")
        for rule, count in sorted(self.stats['by_rule'].items()):
            print(f"     - {rule}: {count}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Glossary Auto-Corrector - Intelligent correction suggestions"
    )
    parser.add_argument("input", help="Input CSV file with translations")
    parser.add_argument("--config", "-c", default="config/glossary.yaml",
                       help="Configuration file path")
    parser.add_argument("--glossary", "-g", default="glossary/compiled.yaml",
                       help="Glossary file path")
    parser.add_argument("--output", "-o", default="correction_suggestions.jsonl",
                       help="Output JSONL file for suggestions")
    parser.add_argument("--text-column", default="target_text",
                       help="Column name containing translated text")
    parser.add_argument("--id-column", default="string_id",
                       help="Column name for text ID")
    parser.add_argument("--suggest-corrections", action="store_true",
                       help="Generate correction suggestions")
    parser.add_argument("--auto-apply", action="store_true",
                       help="Automatically apply high-confidence corrections")
    parser.add_argument("--threshold", type=float, default=0.90,
                       help="Minimum confidence threshold for suggestions")
    parser.add_argument("--apply-threshold", type=float, default=0.99,
                       help="Threshold for auto-applying corrections")
    
    args = parser.parse_args()
    
    # Initialize corrector
    corrector = GlossaryCorrector(args.config)
    corrector.load_glossary(args.glossary)
    
    print(f"🚀 Processing {args.input}...")
    
    # Process CSV
    suggestions = corrector.process_csv(args.input, args.text_column, args.id_column)
    
    # Filter by threshold
    threshold = args.threshold
    filtered_suggestions = [s for s in suggestions if s.confidence >= threshold]
    
    print(f"✅ Found {len(filtered_suggestions)} suggestions (from {len(suggestions)} total)")
    
    # Save suggestions
    if filtered_suggestions:
        corrector.save_suggestions(filtered_suggestions, args.output)
        
        # Print sample suggestions
        print("\n📝 Sample suggestions:")
        for suggestion in filtered_suggestions[:5]:
            print(f"   [{suggestion.rule}] '{suggestion.original}' → '{suggestion.suggested}' "
                  f"(confidence: {suggestion.confidence:.2f})")
    
    # Print summary
    corrector.print_summary()
    
    # Auto-apply if requested
    if args.auto_apply and filtered_suggestions:
        print(f"\n⚙️  Auto-applying corrections with threshold {args.apply_threshold}...")
        # This would require reading the CSV, applying corrections, and saving
        # Implementation depends on specific workflow requirements
        print("   (Auto-apply feature requires additional implementation)")
    
    return 0 if len(filtered_suggestions) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
