"""
Comprehensive Tests for Glossary Learning System (P4.3)

Target: 5% improvement in auto-approval rate per week of usage

Test Coverage Areas:
1. Feedback Tracking (4 tests)
2. Confidence Calibration (5 tests)
3. Pattern Discovery (3 tests)
4. TF-IDF Term Discovery (4 tests)
5. Similarity Clustering (3 tests)
6. Report Generation (3 tests)
7. Integration Tests (4 tests)

Total: 26 tests
"""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.glossary_learner import (
    GlossaryLearner,
    FeedbackEntry,
    TermStats,
    SuggestedTerm,
    SimilarityClusterer,
    TFIDFDiscoverer,
    PatternMiner,
    create_sample_learning_data
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test data"""
    temp_path = tempfile.mkdtemp()
    yield Path(temp_path)
    shutil.rmtree(temp_path)


@pytest.fixture
def learner(temp_dir):
    """Create a GlossaryLearner instance with temp directory"""
    config_path = temp_dir / 'test_config.yaml'
    config_content = """
glossary_learning:
  enabled: true
  min_feedback_count: 5
  confidence_update_rate: 0.1
  auto_suggest_new_terms: true
  term_discovery_threshold: 0.8
  learning_data_path: "{temp_dir}/"
""".format(temp_dir=temp_dir)
    
    with open(config_path, 'w') as f:
        f.write(config_content)
    
    return GlossaryLearner(str(config_path))


@pytest.fixture
def sample_feedback_entry():
    """Create a sample feedback entry"""
    return FeedbackEntry(
        timestamp=datetime.now().isoformat(),
        term_zh='攻击',
        term_ru='Атака',
        source_text='攻击力提升20%',
        context='UI tooltip',
        decision='accepted',
        reviewer_id='test_reviewer',
        confidence=0.9
    )


@pytest.fixture
def sample_corpus():
    """Sample parallel corpus for testing"""
    return [
        {
            'id': 'doc1',
            'zh': '攻击力提升20%，暴击伤害增加',
            'ru': 'Атака увеличена на 20%, критический урон повышен'
        },
        {
            'id': 'doc2',
            'zh': '获得护盾保护，生命值恢复',
            'ru': 'Получен щит защиты, здоровье восстановлено'
        },
        {
            'id': 'doc3',
            'zh': '技能冷却时间减少',
            'ru': 'Время перезарядки навыка сокращено'
        }
    ]


# =============================================================================
# Test Class: FeedbackEntry
# =============================================================================

class TestFeedbackEntry:
    """Tests for FeedbackEntry dataclass"""
    
    def test_feedback_entry_creation(self, sample_feedback_entry):
        """Test that FeedbackEntry can be created with all fields"""
        entry = sample_feedback_entry
        assert entry.term_zh == '攻击'
        assert entry.term_ru == 'Атака'
        assert entry.decision == 'accepted'
        assert entry.reviewer_id == 'test_reviewer'
    
    def test_feedback_entry_to_dict(self, sample_feedback_entry):
        """Test conversion to dictionary"""
        data = sample_feedback_entry.to_dict()
        assert isinstance(data, dict)
        assert data['term_zh'] == '攻击'
        assert data['term_ru'] == 'Атака'
        assert data['decision'] == 'accepted'
    
    def test_feedback_entry_from_dict(self):
        """Test creation from dictionary"""
        data = {
            'timestamp': datetime.now().isoformat(),
            'term_zh': '护盾',
            'term_ru': 'Щит',
            'source_text': '获得护盾',
            'context': 'Buff description',
            'decision': 'rejected',
            'reviewer_id': 'reviewer_1',
            'correction': None,
            'confidence': 0.5,
            'notes': 'Incorrect translation'
        }
        entry = FeedbackEntry.from_dict(data)
        assert entry.term_zh == '护盾'
        assert entry.decision == 'rejected'


# =============================================================================
# Test Class: TermStats
# =============================================================================

class TestTermStats:
    """Tests for TermStats dataclass"""
    
    def test_term_stats_creation(self):
        """Test TermStats creation with defaults"""
        stats = TermStats(term_zh='攻击', term_ru='Атака')
        assert stats.term_zh == '攻击'
        assert stats.confidence == 0.5  # Default prior
        assert stats.total_uses == 0
    
    def test_term_stats_accuracy_calculation(self):
        """Test accuracy calculation"""
        stats = TermStats(term_zh='攻击', term_ru='Атака')
        stats.accepted_count = 8
        stats.rejected_count = 2
        stats.corrected_count = 0
        
        assert stats.accuracy == 0.8
    
    def test_term_stats_auto_approve_eligibility(self):
        """Test auto-approve eligibility check"""
        stats = TermStats(term_zh='攻击', term_ru='Атака')
        stats.confidence = 0.85
        stats.total_uses = 10
        
        assert stats.auto_approve_eligible is True
        
        # Test with low confidence
        stats.confidence = 0.7
        assert stats.auto_approve_eligible is False
        
        # Test with insufficient uses
        stats.confidence = 0.9
        stats.total_uses = 3
        assert stats.auto_approve_eligible is False
    
    def test_term_stats_confidence_update(self):
        """Test Bayesian confidence update"""
        stats = TermStats(term_zh='攻击', term_ru='Атака')
        stats.confidence = 0.5
        stats.accepted_count = 9
        stats.rejected_count = 1
        
        initial_confidence = stats.confidence
        stats.update_confidence(update_rate=0.1)
        
        # Confidence should move toward accuracy (0.9)
        assert stats.confidence > initial_confidence
        assert stats.confidence < 0.9  # But not all the way
    
    def test_term_stats_with_corrections(self):
        """Test accuracy calculation with corrections"""
        stats = TermStats(term_zh='技能', term_ru='Навык')
        stats.accepted_count = 5
        stats.rejected_count = 2
        stats.corrected_count = 3
        
        # Corrections count as 0.5
        expected_accuracy = (5 + 3 * 0.5) / 10
        assert stats.accuracy == expected_accuracy


# =============================================================================
# Test Class: SimilarityClusterer
# =============================================================================

class TestSimilarityClusterer:
    """Tests for similarity clustering algorithm"""
    
    def test_ngram_generation(self):
        """Test n-gram generation from text"""
        clusterer = SimilarityClusterer(n=2)
        ngrams = clusterer.ngrams('攻击')
        assert len(ngrams) == 1  # Only one 2-gram in 2-character string
        assert '攻击' in ngrams
    
    def test_similarity_calculation(self):
        """Test Jaccard similarity calculation"""
        clusterer = SimilarityClusterer(n=2)
        
        # Identical strings
        assert clusterer.similarity('攻击', '攻击') == 1.0
        
        # Completely different strings
        assert clusterer.similarity('攻击', '防御') == 0.0
        
        # Partially similar (would need actual overlap)
        sim = clusterer.similarity('攻击力', '攻击')
        assert 0 < sim < 1
    
    def test_variant_detection(self):
        """Test finding term variants"""
        clusterer = SimilarityClusterer(n=2)
        all_terms = ['攻击', '攻击力', '攻击速度', '防御', '防御力']
        
        variants = clusterer.find_variants('攻击', all_terms, threshold=0.3)
        assert '攻击力' in variants
        assert '攻击速度' in variants
        assert '防御' not in variants


# =============================================================================
# Test Class: TFIDFDiscoverer
# =============================================================================

class TestTFIDFDiscoverer:
    """Tests for TF-IDF term discovery"""
    
    def test_document_addition(self):
        """Test adding documents to discoverer"""
        discoverer = TFIDFDiscoverer()
        discoverer.add_document('doc1', '攻击力提升', 'Атака увеличена')
        
        assert discoverer.total_documents == 1
        assert len(discoverer.document_freq) > 0
    
    def test_tfidf_calculation(self):
        """Test TF-IDF score calculation"""
        discoverer = TFIDFDiscoverer()
        
        # Add multiple documents with varying terms
        for i in range(5):
            discoverer.add_document(f'doc{i}', '攻击', 'Атака')
        # Add documents without the term to make IDF non-zero
        for i in range(5, 10):
            discoverer.add_document(f'doc{i}', '防御', 'Защита')
        
        tfidf = discoverer.calculate_tfidf('攻击', 5)
        assert tfidf > 0  # IDF should now be non-zero
    
    def test_top_candidates_extraction(self):
        """Test extracting top term candidates"""
        discoverer = TFIDFDiscoverer()
        
        # Add documents with repeated terms
        for i in range(10):
            discoverer.add_document(f'doc{i}', '攻击力暴击伤害', 'Атака крит урон')
        
        candidates = discoverer.get_top_candidates(min_count=3, top_n=5)
        assert len(candidates) > 0
        assert all(len(term) >= 2 for term, _ in candidates)
    
    def test_phrase_extraction_chinese(self):
        """Test Chinese phrase extraction"""
        discoverer = TFIDFDiscoverer()
        phrases = discoverer._extract_phrases('攻击力提升20%')
        
        assert len(phrases) > 0
        # Should include various lengths
        assert any(len(p) == 1 for p in phrases)
        assert any(len(p) == 2 for p in phrases)


# =============================================================================
# Test Class: PatternMiner
# =============================================================================

class TestPatternMiner:
    """Tests for pattern mining"""
    
    def test_pattern_extraction_brackets(self):
        """Test extracting bracketed terms"""
        miner = PatternMiner()
        patterns = miner.extract_patterns('（攻击）力提升', '[Атака] увеличена')
        
        # Should extract bracketed content
        assert len(patterns) > 0
    
    def test_pattern_addition(self):
        """Test adding patterns"""
        miner = PatternMiner()
        miner.add_pattern('攻击', 'Атака')
        miner.add_pattern('攻击', 'Атака')
        
        assert miner.patterns['攻击']['Атака'] == 2
    
    def test_common_patterns_retrieval(self):
        """Test retrieving common patterns"""
        miner = PatternMiner()
        
        # Add multiple occurrences
        for _ in range(5):
            miner.add_pattern('攻击', 'Атака')
        for _ in range(2):
            miner.add_pattern('防御', 'Защита')
        
        common = miner.get_common_patterns(min_occurrences=3)
        assert len(common) > 0
        assert ('攻击', 'Атака', 5) in common


# =============================================================================
# Test Class: GlossaryLearner - Feedback Tracking
# =============================================================================

class TestFeedbackTracking:
    """Tests for feedback tracking functionality"""
    
    def test_record_accepted_feedback(self, learner):
        """Test recording accepted feedback"""
        entry = learner.record_feedback(
            term_zh='攻击',
            term_ru='Атака',
            source_text='攻击力提升20%',
            decision='accepted',
            context='UI tooltip'
        )
        
        assert entry is not None
        assert entry.decision == 'accepted'
        
        # Check that stats were updated
        key = '攻击|Атака'
        assert key in learner.term_stats
        assert learner.term_stats[key].accepted_count == 1
    
    def test_record_rejected_feedback(self, learner):
        """Test recording rejected feedback"""
        entry = learner.record_feedback(
            term_zh='护盾',
            term_ru='Барьер',  # Incorrect translation
            source_text='获得护盾保护',
            decision='rejected',
            context='Buff description'
        )
        
        key = '护盾|Барьер'
        assert learner.term_stats[key].rejected_count == 1
    
    def test_record_corrected_feedback(self, learner):
        """Test recording corrected feedback"""
        entry = learner.record_feedback(
            term_zh='技能',
            term_ru='Умение',
            source_text='技能冷却时间',
            decision='corrected',
            correction='Навык',
            context='Skill panel'
        )
        
        key = '技能|Умение'
        assert learner.term_stats[key].corrected_count == 1
        assert 'Навык' in learner.term_stats[key].variants
    
    def test_feedback_when_disabled(self, temp_dir):
        """Test that feedback is not recorded when disabled"""
        config_path = temp_dir / 'disabled_config.yaml'
        with open(config_path, 'w') as f:
            f.write('glossary_learning:\n  enabled: false\n')
        
        learner = GlossaryLearner(str(config_path))
        entry = learner.record_feedback(
            term_zh='测试',
            term_ru='Тест',
            source_text='测试文本',
            decision='accepted'
        )
        
        assert entry is None


# =============================================================================
# Test Class: GlossaryLearner - Confidence Calibration
# =============================================================================

class TestConfidenceCalibration:
    """Tests for Bayesian confidence calibration"""
    
    def test_confidence_increases_with_acceptance(self, learner):
        """Test that confidence increases with accepted feedback"""
        term_zh, term_ru = '攻击', 'Атака'
        
        initial_confidence = 0.5
        
        # Record 10 accepted feedback
        for i in range(10):
            learner.record_feedback(
                term_zh=term_zh,
                term_ru=term_ru,
                source_text=f'攻击提升{i}%',
                decision='accepted',
                context=f'Context {i}'
            )
        
        key = f'{term_zh}|{term_ru}'
        final_confidence = learner.term_stats[key].confidence
        
        assert final_confidence > initial_confidence
        assert final_confidence > 0.8  # Should reach high confidence
    
    def test_confidence_decreases_with_rejection(self, learner):
        """Test that confidence decreases with rejected feedback"""
        term_zh, term_ru = '错误', 'Ошибка'
        
        # Set initial high confidence
        key = f'{term_zh}|{term_ru}'
        learner.term_stats[key] = TermStats(term_zh=term_zh, term_ru=term_ru)
        learner.term_stats[key].confidence = 0.9
        
        # Record rejections
        for i in range(5):
            learner.record_feedback(
                term_zh=term_zh,
                term_ru=term_ru,
                source_text='错误文本',
                decision='rejected'
            )
        
        final_confidence = learner.term_stats[key].confidence
        assert final_confidence < 0.9
    
    def test_accuracy_calculation_integration(self, learner):
        """Test accuracy calculation with mixed feedback"""
        term_zh, term_ru = '混合', 'Смешанный'
        
        # Record mixed feedback
        for _ in range(7):
            learner.record_feedback(term_zh, term_ru, 'text', 'accepted')
        for _ in range(2):
            learner.record_feedback(term_zh, term_ru, 'text', 'rejected')
        for _ in range(1):
            learner.record_feedback(term_zh, term_ru, 'text', 'corrected')
        
        key = f'{term_zh}|{term_ru}'
        stats = learner.term_stats[key]
        
        expected_accuracy = (7 + 1 * 0.5) / 10
        assert abs(stats.accuracy - expected_accuracy) < 0.01
    
    def test_confidence_report_generation(self, learner):
        """Test confidence report generation"""
        # Add some feedback
        learner.record_feedback('攻击', 'Атака', 'text', 'accepted')
        learner.record_feedback('护盾', 'Щит', 'text', 'accepted')
        
        report = learner.get_confidence_report()
        
        assert 'generated_at' in report
        assert report['total_terms'] == 2
        assert 'confidence_distribution' in report
        assert 'term_details' in report
    
    def test_auto_approve_eligibility_in_report(self, learner):
        """Test auto-approve eligibility calculation in report"""
        # Add term with high confidence and sufficient uses
        for i in range(10):
            learner.record_feedback('高置信度', 'Высокая', f'text{i}', 'accepted')
        
        report = learner.get_confidence_report()
        
        assert report['auto_approve_eligible'] >= 1
        assert report['auto_approve_rate'] > 0


# =============================================================================
# Test Class: GlossaryLearner - Term Discovery
# =============================================================================

class TestTermDiscovery:
    """Tests for term discovery functionality"""
    
    def test_process_parallel_corpus(self, learner, sample_corpus):
        """Test processing parallel corpus"""
        learner.process_parallel_corpus(sample_corpus)
        
        assert learner.tfidf_discoverer.total_documents == len(sample_corpus)
    
    def test_discover_new_terms_empty(self, learner):
        """Test term discovery with no corpus"""
        known_terms = [{'term_zh': '攻击', 'term_ru': 'Атака'}]
        suggestions = learner.discover_new_terms(known_terms)
        
        assert isinstance(suggestions, list)
    
    def test_discover_new_terms_with_corpus(self, learner, sample_corpus):
        """Test discovering new terms from corpus"""
        learner.process_parallel_corpus(sample_corpus)
        
        known_terms = [{'term_zh': '已知', 'term_ru': 'Известный'}]
        suggestions = learner.discover_new_terms(known_terms)
        
        # Should return suggestions (even if empty due to threshold)
        assert isinstance(suggestions, list)
        for s in suggestions:
            assert hasattr(s, 'term_zh')
            assert hasattr(s, 'term_ru')
            assert hasattr(s, 'confidence')
    
    def test_suggestion_confidence_threshold(self, learner):
        """Test that suggestions respect confidence threshold"""
        learner.config['term_discovery_threshold'] = 0.95  # Very high
        
        # Process minimal corpus
        learner.process_parallel_corpus([
            {'id': '1', 'zh': '测试', 'ru': 'Тест'}
        ])
        
        known_terms = []
        suggestions = learner.discover_new_terms(known_terms)
        
        # With high threshold, should have few/no suggestions
        for s in suggestions:
            assert s.confidence >= 0.95


# =============================================================================
# Test Class: GlossaryLearner - Report Generation
# =============================================================================

class TestReportGeneration:
    """Tests for report generation"""
    
    def test_weekly_report_generation(self, learner):
        """Test weekly report generation"""
        # Add some feedback
        for i in range(5):
            learner.record_feedback(f'术语{i}', f'Терм{i}', 'text', 'accepted')
        
        report = learner.generate_weekly_report()
        
        assert 'report_period' in report
        assert report['report_period'] == 'weekly'
        assert 'feedback_summary' in report
        assert 'learning_progress' in report
    
    def test_weekly_report_feedback_counts(self, learner):
        """Test feedback counts in weekly report"""
        learner.record_feedback('A', 'A', 'text', 'accepted')
        learner.record_feedback('B', 'B', 'text', 'rejected')
        learner.record_feedback('C', 'C', 'text', 'corrected')
        
        report = learner.generate_weekly_report()
        summary = report['feedback_summary']
        
        assert summary['accepted'] >= 1
        assert summary['rejected'] >= 1
        assert summary['corrected'] >= 1
    
    def test_learning_metrics(self, learner):
        """Test comprehensive learning metrics"""
        learner.record_feedback('测试', 'Тест', 'text', 'accepted')
        
        metrics = learner.get_learning_metrics()
        
        assert 'system_status' in metrics
        assert 'confidence_metrics' in metrics
        assert 'target_progress' in metrics
        assert metrics['target_progress']['target'] == '5% improvement per week'


# =============================================================================
# Test Class: GlossaryLearner - File Operations
# =============================================================================

class TestFileOperations:
    """Tests for file I/O operations"""
    
    def test_save_confidence_report(self, learner, temp_dir):
        """Test saving confidence report to file"""
        learner.record_feedback('测试', 'Тест', 'text', 'accepted')
        
        output_path = temp_dir / 'confidence_report.json'
        learner.save_confidence_report(str(output_path))
        
        assert output_path.exists()
        
        with open(output_path) as f:
            data = json.load(f)
            assert 'total_terms' in data
    
    def test_save_glossary_suggestions(self, learner, temp_dir):
        """Test saving glossary suggestions"""
        learner.suggested_terms = [
            SuggestedTerm(
                term_zh='新术语',
                term_ru='Новый термин',
                confidence=0.85,
                occurrences=10,
                contexts=['context1'],
                similarity_to_known=0.6,
                suggested_by='test',
                timestamp=datetime.now().isoformat()
            )
        ]
        
        output_path = temp_dir / 'suggestions.json'
        learner.save_glossary_suggestions(str(output_path))
        
        assert output_path.exists()
        
        with open(output_path) as f:
            data = json.load(f)
            assert data['total_suggestions'] == 1
    
    def test_save_weekly_report(self, learner, temp_dir):
        """Test saving weekly report"""
        output_path = temp_dir / 'weekly_report.json'
        learner.save_weekly_report(str(output_path))
        
        assert output_path.exists()
        
        with open(output_path) as f:
            data = json.load(f)
            assert data['report_period'] == 'weekly'
    
    def test_jsonl_file_creation(self, learner, temp_dir):
        """Test that feedback is written to JSONL files"""
        learner.record_feedback('测试', 'Тест', '测试文本', 'accepted')
        
        accepted_file = Path(learner.base_path) / 'accepted_matches.jsonl'
        assert accepted_file.exists()
        
        with open(accepted_file) as f:
            lines = f.readlines()
            assert len(lines) > 0
            
            data = json.loads(lines[0])
            assert data['term_zh'] == '测试'


# =============================================================================
# Test Class: Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for complete workflows"""
    
    def test_end_to_end_learning_workflow(self, temp_dir):
        """Test complete learning workflow from feedback to report"""
        # Setup
        config_path = temp_dir / 'config.yaml'
        with open(config_path, 'w') as f:
            f.write(f'''
glossary_learning:
  enabled: true
  min_feedback_count: 3
  confidence_update_rate: 0.2
  auto_suggest_new_terms: true
  term_discovery_threshold: 0.6
  learning_data_path: "{temp_dir}/learning/"
''')
        
        learner = GlossaryLearner(str(config_path))
        
        # Simulate feedback over time
        terms = [
            ('攻击', 'Атака'),
            ('防御', 'Защита'),
            ('生命', 'Здоровье'),
            ('暴击', 'Критический удар'),
            ('护盾', 'Щит')
        ]
        
        for term_zh, term_ru in terms:
            for i in range(5):
                learner.record_feedback(
                    term_zh=term_zh,
                    term_ru=term_ru,
                    source_text=f'{term_zh}提升{i*10}%',
                    decision='accepted',
                    context=f'Context {i}'
                )
        
        # Process corpus
        corpus = [
            {'id': f'doc{i}', 'zh': f'{zh}提升', 'ru': f'{ru} увеличен'}
            for i, (zh, ru) in enumerate(terms)
        ]
        learner.process_parallel_corpus(corpus)
        
        # Generate reports
        known_terms = [{'term_zh': zh, 'term_ru': ru} for zh, ru in terms]
        suggestions = learner.discover_new_terms(known_terms)
        confidence_report = learner.get_confidence_report()
        weekly_report = learner.generate_weekly_report()
        
        # Verify
        assert len(learner.term_stats) == 5
        assert confidence_report['total_terms'] == 5
        assert weekly_report['feedback_summary']['total'] == 25
        
        # Check confidence improvements
        for stats in learner.term_stats.values():
            assert stats.confidence > 0.5  # Should have improved from prior
    
    def test_confidence_improvement_over_time(self, temp_dir):
        """Test that confidence improves with more feedback"""
        config_path = temp_dir / 'config.yaml'
        with open(config_path, 'w') as f:
            f.write('glossary_learning:\n  enabled: true\n  confidence_update_rate: 0.1\n')
        
        learner = GlossaryLearner(str(config_path))
        
        term_zh, term_ru = '技能', 'Навык'
        confidences = []
        
        # Record 20 accepted feedback and track confidence
        for i in range(20):
            learner.record_feedback(term_zh, term_ru, f'text{i}', 'accepted')
            key = f'{term_zh}|{term_ru}'
            confidences.append(learner.term_stats[key].confidence)
        
        # Confidence should generally trend upward
        early_avg = sum(confidences[:5]) / 5
        late_avg = sum(confidences[-5:]) / 5
        
        assert late_avg > early_avg
    
    def test_variant_detection_integration(self):
        """Test variant detection with real glossary terms"""
        # Create fresh clusterer to avoid test isolation issues
        clusterer = SimilarityClusterer(n=2)
        known_terms = ['攻击', '攻击力', '攻击速度', '防御', '防御力']
        
        variants = clusterer.find_variants('攻击', known_terms, threshold=0.3)
        
        # '攻击' should be similar to '攻击力' and '攻击速度'
        assert any(v in variants for v in ['攻击力', '攻击速度'])
    
    def test_create_sample_data(self, temp_dir):
        """Test sample data creation function"""
        config_path = temp_dir / 'config.yaml'
        with open(config_path, 'w') as f:
            f.write('glossary_learning:\n  enabled: true\n')
        
        learner = GlossaryLearner(str(config_path))
        create_sample_learning_data(learner)
        
        # Should have at least 5 terms (might have more from sample data creation)
        assert len(learner.term_stats) >= 5


# =============================================================================
# Performance Tests
# =============================================================================

class TestPerformance:
    """Performance-related tests"""
    
    def test_large_corpus_processing(self, learner):
        """Test processing a large corpus efficiently"""
        import time
        
        # Generate large corpus
        large_corpus = [
            {
                'id': f'doc{i}',
                'zh': f'攻击力提升{i}%，暴击伤害增加',
                'ru': f'Атака увеличена на {i}%, критический урон повышен'
            }
            for i in range(1000)
        ]
        
        start = time.time()
        learner.process_parallel_corpus(large_corpus)
        elapsed = time.time() - start
        
        # Should complete in reasonable time
        assert elapsed < 10  # 10 seconds
        assert learner.tfidf_discoverer.total_documents == 1000
    
    def test_memory_efficiency_with_many_terms(self, temp_dir):
        """Test memory efficiency with many tracked terms"""
        config_path = temp_dir / 'config.yaml'
        with open(config_path, 'w') as f:
            f.write('glossary_learning:\n  enabled: true\n')
        
        learner = GlossaryLearner(str(config_path))
        
        # Add many terms
        for i in range(1000):
            learner.record_feedback(f'术语{i}', f'Терм{i}', 'text', 'accepted')
        
        assert len(learner.term_stats) >= 1000
        
        # Generate report should still work
        report = learner.get_confidence_report()
        assert report['total_terms'] >= 1000


# =============================================================================
# Main Entry Point for Standalone Execution
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
