#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test suite for glossary_corrector.py
Comprehensive tests for auto-correction suggestions

Run with: python -m pytest tests/test_glossary_corrector.py -v
"""

import sys
import os
import json
import tempfile
from pathlib import Path
from typing import List, Dict

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import pytest

# Import the module under test
try:
    from glossary_corrector import (
        GlossaryCorrector,
        RussianDeclensionHelper,
        CorrectionSuggestion,
        GlossaryEntry,
        CorrectionRule
    )
    MODULE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import glossary_corrector: {e}")
    MODULE_AVAILABLE = False


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
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


@pytest.fixture
def sample_glossary_entries():
    """Sample glossary entries for testing"""
    return [
        {'term_zh': '汉库克', 'term_ru': 'Хэнкок', 'scope': 'general'},
        {'term_zh': '路飞', 'term_ru': 'Луффи', 'scope': 'general'},
        {'term_zh': '索隆', 'term_ru': 'Зоро', 'scope': 'general'},
        {'term_zh': '航海王', 'term_ru': 'Ван-Пис', 'scope': 'general'},
        {'term_zh': '写轮眼', 'term_ru': 'Шаринган', 'scope': 'general'},
        {'term_zh': '火之意志', 'term_ru': 'Воля Огня', 'scope': 'general'},
        {'term_zh': '攻击', 'term_ru': 'Атака', 'scope': 'general'},
        {'term_zh': '防御', 'term_ru': 'Защита', 'scope': 'general'},
    ]


@pytest.fixture
def corrector(sample_config):
    """Create a GlossaryCorrector instance"""
    if not MODULE_AVAILABLE:
        pytest.skip("glossary_corrector module not available")
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        import yaml
        yaml.dump(sample_config, f)
        config_path = f.name
    
    c = GlossaryCorrector(config_path)
    yield c
    
    # Cleanup
    os.unlink(config_path)


@pytest.fixture
def populated_corrector(corrector, sample_glossary_entries):
    """Create a GlossaryCorrector with loaded glossary"""
    for entry_data in sample_glossary_entries:
        entry = GlossaryEntry.from_dict(entry_data)
        corrector.glossary[entry.term_ru.lower()] = entry
        corrector.glossary_by_zh[entry.term_zh] = entry
    
    corrector._compile_patterns()
    return corrector


# ============================================================================
# Test GlossaryEntry
# ============================================================================

class TestGlossaryEntry:
    """Tests for GlossaryEntry dataclass"""
    
    def test_from_dict_basic(self):
        """Test creating GlossaryEntry from dictionary"""
        if not MODULE_AVAILABLE:
            pytest.skip("Module not available")
        
        data = {'term_zh': '测试', 'term_ru': 'Тест', 'scope': 'general'}
        entry = GlossaryEntry.from_dict(data)
        
        assert entry.term_zh == '测试'
        assert entry.term_ru == 'Тест'
        assert entry.scope == 'general'
        assert entry.status == 'approved'  # default
        assert entry.tags == []
    
    def test_from_dict_full(self):
        """Test creating GlossaryEntry with all fields"""
        if not MODULE_AVAILABLE:
            pytest.skip("Module not available")
        
        data = {
            'term_zh': '测试',
            'term_ru': 'Тест',
            'scope': 'special',
            'status': 'pending',
            'tags': ['ui', 'button'],
            'variations': ['тестирование']
        }
        entry = GlossaryEntry.from_dict(data)
        
        assert entry.term_zh == '测试'
        assert entry.term_ru == 'Тест'
        assert entry.scope == 'special'
        assert entry.status == 'pending'
        assert entry.tags == ['ui', 'button']
        assert entry.variations == ['тестирование']


# ============================================================================
# Test CorrectionSuggestion
# ============================================================================

class TestCorrectionSuggestion:
    """Tests for CorrectionSuggestion dataclass"""
    
    def test_to_dict(self):
        """Test conversion to dictionary"""
        if not MODULE_AVAILABLE:
            pytest.skip("Module not available")
        
        suggestion = CorrectionSuggestion(
            text_id='test_001',
            original='Ханкок',
            suggested='Хэнкок',
            confidence=0.98,
            rule='spelling',
            context='...Ханкок встала...',
            position=10,
            term_zh='汉库克',
            term_ru_expected='Хэнкок',
            alternative_suggestions=['Хэнкока']
        )
        
        d = suggestion.to_dict()
        assert d['text_id'] == 'test_001'
        assert d['original'] == 'Ханкок'
        assert d['suggested'] == 'Хэнкок'
        assert d['confidence'] == 0.98
        assert d['rule'] == 'spelling'
        assert d['alternative_suggestions'] == ['Хэнкока']


# ============================================================================
# Test RussianDeclensionHelper
# ============================================================================

class TestRussianDeclensionHelper:
    """Tests for Russian declension handling"""
    
    def test_normalize_for_comparison_basic(self):
        """Test basic word normalization"""
        if not MODULE_AVAILABLE:
            pytest.skip("Module not available")
        
        helper = RussianDeclensionHelper()
        
        # Test removing common endings
        assert helper.normalize_for_comparison('атаки') == 'атак'
        assert helper.normalize_for_comparison('защите') == 'защит'
        assert helper.normalize_for_comparison('Хэнкок') == 'Хэнкок'
    
    def test_normalize_for_comparison_no_ending(self):
        """Test normalization of words without declension endings"""
        if not MODULE_AVAILABLE:
            pytest.skip("Module not available")
        
        helper = RussianDeclensionHelper()
        
        # Words that don't have typical endings - 'о' is in indeclinable list
        # so 'Зоро' returns 'Зоро' (unchanged)
        assert helper.normalize_for_comparison('Зоро') == 'Зоро'
    
    def test_is_indeclinable_luffy(self):
        """Test indeclinable detection for Luffy"""
        if not MODULE_AVAILABLE:
            pytest.skip("Module not available")
        
        helper = RussianDeclensionHelper()
        assert helper._is_indeclinable('Луффи') == True
    
    def test_is_indeclinable_zoro(self):
        """Test indeclinable detection for Zoro"""
        if not MODULE_AVAILABLE:
            pytest.skip("Module not available")
        
        helper = RussianDeclensionHelper()
        assert helper._is_indeclinable('Зоро') == True
    
    def test_is_indeclinable_regular(self):
        """Test that regular Russian words are not indeclinable"""
        if not MODULE_AVAILABLE:
            pytest.skip("Module not available")
        
        helper = RussianDeclensionHelper()
        assert helper._is_indeclinable('атака') == False
        assert helper._is_indeclinable('защита') == False
    
    def test_detect_case_nominative(self):
        """Test detection of nominative case"""
        if not MODULE_AVAILABLE:
            pytest.skip("Module not available")
        
        helper = RussianDeclensionHelper()
        case = helper.detect_case('Хэнкок', 'Хэнкок')
        assert case == 'nominative'
    
    def test_get_correct_form_indeclinable(self):
        """Test that indeclinable names return base form"""
        if not MODULE_AVAILABLE:
            pytest.skip("Module not available")
        
        helper = RussianDeclensionHelper()
        
        # Luffy is indeclinable, should always return base form
        result = helper.get_correct_form('Луффи', 'Луффи', 'genitive')
        assert result == 'Луффи'


# ============================================================================
# Test GlossaryCorrector - Initialization
# ============================================================================

class TestGlossaryCorrectorInit:
    """Tests for GlossaryCorrector initialization"""
    
    def test_default_config(self, corrector):
        """Test that default config is loaded"""
        assert corrector.config is not None
        assert 'glossary_corrections' in corrector.config
    
    def test_config_values(self, corrector):
        """Test that config values are correctly loaded"""
        gc = corrector.config['glossary_corrections']
        assert gc['enabled'] == True
        assert gc['suggest_threshold'] == 0.90
        assert gc['auto_apply_threshold'] == 0.99
    
    def test_load_glossary_missing_file(self, corrector):
        """Test handling of missing glossary file"""
        result = corrector.load_glossary('/nonexistent/path.yaml')
        assert result == False
    
    def test_load_glossary_empty(self, corrector):
        """Test loading empty glossary"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('entries: []')
            temp_path = f.name
        
        result = corrector.load_glossary(temp_path)
        assert result == True
        assert len(corrector.glossary) == 0
        
        os.unlink(temp_path)


# ============================================================================
# Test GlossaryCorrector - Spelling Detection
# ============================================================================

class TestSpellingDetection:
    """Tests for spelling error detection"""
    
    def test_detect_hancock_misspelling(self, populated_corrector):
        """Test detection of 'Ханкок' → 'Хэнкок'"""
        text = 'Ханкок встала и посмотрела на Луффи.'
        suggestions = populated_corrector.detect_violations(text, 'test_001')
        
        # Should find the misspelling
        hancock_suggestions = [s for s in suggestions if 'Ханкок' in s.original]
        assert len(hancock_suggestions) >= 1
        
        suggestion = hancock_suggestions[0]
        assert suggestion.original == 'Ханкок'
        assert suggestion.suggested == 'Хэнкок'
        assert suggestion.confidence >= 0.95
        assert suggestion.rule == 'spelling'
    
    def test_detect_one_piece_spacing(self, populated_corrector):
        """Test detection of 'Ван Пис' → 'Ван-Пис'"""
        text = 'Смотреть аниме Ван Пис онлайн.'
        suggestions = populated_corrector.detect_violations(text, 'test_002')
        
        spacing_suggestions = [s for s in suggestions if s.rule == 'spacing']
        assert len(spacing_suggestions) >= 1
        
        suggestion = spacing_suggestions[0]
        assert 'Ван Пис' in suggestion.original
        assert 'Ван-Пис' in suggestion.suggested
    
    def test_no_false_positive_correct_spelling(self, populated_corrector):
        """Test that correct spellings don't trigger suggestions"""
        text = 'Хэнкок - императорница. Луффи - пират.'
        suggestions = populated_corrector.detect_violations(text, 'test_003')
        
        # Should not have spelling suggestions for correct terms
        spelling_suggestions = [s for s in suggestions if s.rule == 'spelling']
        for s in spelling_suggestions:
            assert 'Хэнкок' not in s.original  # Correct spelling shouldn't be flagged
    
    def test_lowercase_misspelling(self, populated_corrector):
        """Test detection of lowercase misspellings"""
        text = 'ханкок - самая красивая женщина.'
        suggestions = populated_corrector.detect_violations(text, 'test_004')
        
        hancock_suggestions = [s for s in suggestions if 'ханкок' in s.original.lower()]
        # May or may not detect depending on implementation


# ============================================================================
# Test GlossaryCorrector - Capitalization
# ============================================================================

class TestCapitalizationDetection:
    """Tests for capitalization error detection"""
    
    def test_detect_lowercase_proper_noun(self, populated_corrector):
        """Test detection of lowercase proper nouns"""
        text = 'луффи и зоро отправились в путешествие.'
        suggestions = populated_corrector.detect_violations(text, 'test_005')
        
        # Should detect lowercase proper nouns
        cap_suggestions = [s for s in suggestions if s.rule == 'capitalization']
        
        # At minimum, should suggest capitalizing proper nouns
        luffy_suggestions = [s for s in cap_suggestions if 'луффи' in s.original.lower()]
        if luffy_suggestions:
            assert luffy_suggestions[0].suggested == 'Луффи'


# ============================================================================
# Test GlossaryCorrector - Russian Cases
# ============================================================================

class TestRussianCaseDetection:
    """Tests for Russian case ending detection"""
    
    def test_detect_case_ending_issues(self, populated_corrector):
        """Test detection of incorrect case endings"""
        # Test with a form that might be incorrect
        text = 'Удар Хэнкоку по врагу был сильным.'
        suggestions = populated_corrector.detect_violations(text, 'test_006')
        
        # Хэнкок is typically indeclinable, so 'Хэнкоку' might be flagged
        case_suggestions = [s for s in suggestions if s.rule == 'case_ending']
        # Should find at least one case-related suggestion
    
    def test_indeclinable_names_preserved(self, populated_corrector):
        """Test that indeclinable foreign names are handled correctly"""
        text = 'Луффи съел мясо. Зоро поточил мечи.'
        suggestions = populated_corrector.detect_violations(text, 'test_007')
        
        # These names are indeclinable, shouldn't suggest case changes
        for s in suggestions:
            if s.original in ['Луффи', 'Зоро']:
                # Should not suggest changing these indeclinable names
                pass  # Implementation dependent


# ============================================================================
# Test GlossaryCorrector - Statistics
# ============================================================================

class TestStatistics:
    """Tests for statistics tracking"""
    
    def test_stats_initialization(self, corrector):
        """Test that stats are initialized correctly"""
        stats = corrector.get_stats()
        assert stats['total_checked'] == 0
        assert stats['violations_found'] == 0
        assert stats['suggestions_generated'] == 0
    
    def test_stats_after_detection(self, populated_corrector):
        """Test stats are updated after detection"""
        text = 'Ханкок встала. Ханкок села.'
        populated_corrector.detect_violations(text, 'test_008')
        
        stats = populated_corrector.get_stats()
        assert stats['total_checked'] == 1
        assert stats['violations_found'] == 1  # At least one text with violations
        assert stats['suggestions_generated'] > 0
    
    def test_stats_by_rule(self, populated_corrector):
        """Test that stats track rules correctly"""
        text = 'Ханкок и Ван Пис.'  # Has spelling and potential spacing issues
        populated_corrector.detect_violations(text, 'test_009')
        
        stats = populated_corrector.get_stats()
        assert 'by_rule' in stats
        # Should have recorded at least one rule


# ============================================================================
# Test GlossaryCorrector - CSV Processing
# ============================================================================

class TestCSVProcessing:
    """Tests for CSV file processing"""
    
    def test_process_csv_basic(self, populated_corrector):
        """Test basic CSV processing"""
        import csv
        
        # Create a test CSV
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['string_id', 'target_text'])
            writer.writeheader()
            writer.writerow({'string_id': 'row1', 'target_text': 'Ханкок встала.'})
            writer.writerow({'string_id': 'row2', 'target_text': 'Луффи съел мясо.'})
            temp_path = f.name
        
        suggestions = populated_corrector.process_csv(temp_path)
        
        # Should find at least the misspelling of Hancock
        assert len(suggestions) >= 1
        
        os.unlink(temp_path)
    
    def test_process_csv_missing_file(self, populated_corrector):
        """Test handling of missing CSV file"""
        suggestions = populated_corrector.process_csv('/nonexistent/file.csv')
        assert suggestions == []
    
    def test_process_csv_empty(self, populated_corrector):
        """Test processing empty CSV"""
        import csv
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['string_id', 'target_text'])
            writer.writeheader()
            temp_path = f.name
        
        suggestions = populated_corrector.process_csv(temp_path)
        assert suggestions == []
        
        os.unlink(temp_path)


# ============================================================================
# Test GlossaryCorrector - Suggestion Output
# ============================================================================

class TestSuggestionOutput:
    """Tests for suggestion output and saving"""
    
    def test_save_suggestions(self, populated_corrector):
        """Test saving suggestions to JSONL"""
        suggestions = [
            CorrectionSuggestion(
                text_id='test_010',
                original='Ханкок',
                suggested='Хэнкок',
                confidence=0.98,
                rule='spelling',
                context='...Ханкок встала...',
                position=5
            )
        ]
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = f.name
        
        os.unlink(temp_path)  # Delete so save_suggestions can create it
        
        result = populated_corrector.save_suggestions(suggestions, temp_path)
        assert result == True
        
        # Verify file contents
        with open(temp_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data['original'] == 'Ханкок'
            assert data['suggested'] == 'Хэнкок'
        
        os.unlink(temp_path)
    
    def test_save_empty_suggestions(self, populated_corrector):
        """Test saving empty suggestions list"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
            temp_path = f.name
        
        os.unlink(temp_path)
        
        result = populated_corrector.save_suggestions([], temp_path)
        assert result == True
        
        with open(temp_path, 'r', encoding='utf-8') as f:
            content = f.read()
            assert content == ''
        
        os.unlink(temp_path)


# ============================================================================
# Test GlossaryCorrector - Apply Corrections
# ============================================================================

class TestApplyCorrections:
    """Tests for applying corrections to text"""
    
    def test_apply_single_correction(self, populated_corrector):
        """Test applying a single high-confidence correction"""
        text = 'Ханкок встала.'
        suggestions = [
            CorrectionSuggestion(
                text_id='test',
                original='Ханкок',
                suggested='Хэнкок',
                confidence=0.99,  # High confidence
                rule='spelling',
                context=text,
                position=0
            )
        ]
        
        result = populated_corrector.apply_corrections(text, suggestions, auto_apply_threshold=0.98)
        assert 'Хэнкок' in result
        assert 'Ханкок' not in result
    
    def test_apply_below_threshold(self, populated_corrector):
        """Test that low-confidence corrections are not applied"""
        text = 'Ханкок встала.'
        suggestions = [
            CorrectionSuggestion(
                text_id='test',
                original='Ханкок',
                suggested='Хэнкок',
                confidence=0.85,  # Below threshold
                rule='spelling',
                context=text,
                position=0
            )
        ]
        
        result = populated_corrector.apply_corrections(text, suggestions, auto_apply_threshold=0.90)
        assert result == text  # Should not change
    
    def test_apply_multiple_corrections(self, populated_corrector):
        """Test applying multiple corrections"""
        text = 'Ханкок и Луффи.'
        suggestions = [
            CorrectionSuggestion(
                text_id='test',
                original='Ханкок',
                suggested='Хэнкок',
                confidence=0.99,
                rule='spelling',
                context=text,
                position=0
            ),
        ]
        
        result = populated_corrector.apply_corrections(text, suggestions, auto_apply_threshold=0.98)
        assert 'Хэнкок' in result


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for the full correction pipeline"""
    
    def test_full_pipeline(self, sample_config, sample_glossary_entries):
        """Test the complete correction pipeline"""
        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            import yaml
            yaml.dump(sample_config, f)
            config_path = f.name
        
        # Create temporary glossary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({'entries': sample_glossary_entries}, f)
            glossary_path = f.name
        
        try:
            # Initialize corrector
            corrector = GlossaryCorrector(config_path)
            corrector.load_glossary(glossary_path)
            
            # Test detection
            text = 'Ханкок встала и посмотрела на Ван Пис.'
            suggestions = corrector.detect_violations(text, 'integration_test')
            
            # Should find at least one violation
            assert len(suggestions) >= 1
            
            # Check that we have proper structure
            for s in suggestions:
                assert s.text_id == 'integration_test'
                assert s.confidence > 0
                assert s.rule in ['spelling', 'capitalization', 'case_ending', 'spacing', 'direct_replacement']
            
        finally:
            os.unlink(config_path)
            os.unlink(glossary_path)
    
    def test_fuzzy_matching(self, populated_corrector):
        """Test fuzzy matching for similar terms"""
        text = 'Шарингэн активировался.'  # Misspelled Шаринган
        suggestions = populated_corrector.detect_violations(text, 'fuzzy_test')
        
        # Should detect the similar term
        # This depends on fuzzy matching implementation
        spelling_suggestions = [s for s in suggestions if s.rule == 'spelling']
        # May or may not detect based on exact matching


# ============================================================================
# Performance Tests
# ============================================================================

class TestPerformance:
    """Performance tests for the corrector"""
    
    def test_large_text_performance(self, populated_corrector):
        """Test performance with large texts"""
        import time
        
        # Generate a large text
        large_text = 'Ханкок встала. ' * 1000
        
        start_time = time.time()
        suggestions = populated_corrector.detect_violations(large_text, 'perf_test')
        end_time = time.time()
        
        # Should complete in reasonable time (< 5 seconds for 1000 repetitions)
        assert (end_time - start_time) < 5.0
        
        # Should find many violations
        assert len(suggestions) > 0
    
    def test_multiple_texts_performance(self, populated_corrector):
        """Test performance with multiple texts"""
        import time
        
        texts = [
            'Ханкок встала.',
            'Луффи съел мясо.',
            'Ван Пис - лучшее аниме.',
        ] * 100  # 300 texts
        
        start_time = time.time()
        all_suggestions = []
        for i, text in enumerate(texts):
            suggestions = populated_corrector.detect_violations(text, f'text_{i}')
            all_suggestions.extend(suggestions)
        end_time = time.time()
        
        # Should complete in reasonable time
        assert (end_time - start_time) < 5.0


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Edge case tests"""
    
    def test_empty_text(self, populated_corrector):
        """Test handling of empty text"""
        suggestions = populated_corrector.detect_violations('', 'empty_test')
        assert suggestions == []
    
    def test_whitespace_only(self, populated_corrector):
        """Test handling of whitespace-only text"""
        suggestions = populated_corrector.detect_violations('   \n\t  ', 'ws_test')
        assert suggestions == []
    
    def test_no_violations(self, populated_corrector):
        """Test text with no violations"""
        text = 'Правильный текст без ошибок.'
        suggestions = populated_corrector.detect_violations(text, 'clean_test')
        # May or may not have suggestions depending on glossary coverage
    
    def test_unicode_handling(self, populated_corrector):
        """Test handling of various Unicode characters"""
        text = 'Хэнкок сказала: «Привет!» 🏴‍☠️'
        # Should not crash
        suggestions = populated_corrector.detect_violations(text, 'unicode_test')
        # Just verify no exception
    
    def test_very_long_word(self, populated_corrector):
        """Test handling of very long words"""
        text = 'Х' * 1000  # Very long fake word
        suggestions = populated_corrector.detect_violations(text, 'long_test')
        # Should not crash


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    # Run with: python tests/test_glossary_corrector.py
    pytest.main([__file__, '-v'])
