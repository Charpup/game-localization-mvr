#!/usr/bin/env python3
"""
Unit tests for qa_hard.py
Comprehensive tests for QAHardValidator class with mocked dependencies
"""

import pytest
import json
import sys
import re
from pathlib import Path
from unittest.mock import Mock, patch, mock_open, MagicMock
from datetime import datetime

# Add src/scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "scripts"))

from qa_hard import QAHardValidator


class TestExtractTokens:
    """Tests for extract_tokens method"""
    
    def test_extract_single_token(self):
        """Test extracting a single token"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "e.json")
        text = "Hello ⟦PH_123⟧ world"
        tokens = validator.extract_tokens(text)
        assert tokens == {"PH_123"}
    
    def test_extract_multiple_tokens(self):
        """Test extracting multiple tokens"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "e.json")
        text = "⟦PH_1⟧ test ⟦TAG_2⟧ more ⟦PH_3⟧"
        tokens = validator.extract_tokens(text)
        assert tokens == {"PH_1", "TAG_2", "PH_3"}
    
    def test_extract_empty_string(self):
        """Test extracting from empty string"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "e.json")
        assert validator.extract_tokens("") == set()
    
    def test_extract_none(self):
        """Test extracting from None"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "e.json")
        assert validator.extract_tokens(None) == set()
    
    def test_extract_no_tokens(self):
        """Test extracting from text without tokens"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "e.json")
        text = "Hello world, no tokens here!"
        assert validator.extract_tokens(text) == set()
    
    def test_extract_mixed_valid_invalid_tokens(self):
        """Test extracting with invalid token formats"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "e.json")
        text = "⟦PH_1⟧ ⟦INVALID⟧ ⟦TAG_2⟧ {PH_3} [PH_4]"
        tokens = validator.extract_tokens(text)
        # Only PH_1 and TAG_2 match the pattern
        assert tokens == {"PH_1", "TAG_2"}


class TestCheckTokenMismatch:
    """Tests for check_token_mismatch method"""
    
    def setup_validator(self):
        """Helper to create a validator with empty errors"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "e.json")
        validator.errors = []
        validator.error_counts = {
            'token_mismatch': 0,
            'tag_unbalanced': 0,
            'forbidden_hit': 0,
            'new_placeholder_found': 0
        }
        return validator
    
    def test_no_mismatch_same_tokens(self):
        """Test when source and target have same tokens"""
        validator = self.setup_validator()
        validator.check_token_mismatch("id1", "⟦PH_1⟧ hello", "world ⟦PH_1⟧", 1)
        assert len(validator.errors) == 0
        assert validator.error_counts['token_mismatch'] == 0
    
    def test_missing_token(self):
        """Test when target is missing a token from source"""
        validator = self.setup_validator()
        validator.check_token_mismatch("id1", "⟦PH_1⟧ ⟦PH_2⟧ hello", "world ⟦PH_1⟧", 1)
        assert len(validator.errors) == 1
        assert validator.errors[0]['type'] == 'token_mismatch'
        assert 'missing' in validator.errors[0]['detail']
        assert 'PH_2' in validator.errors[0]['detail']
        assert validator.error_counts['token_mismatch'] == 1
    
    def test_extra_token(self):
        """Test when target has extra token not in source"""
        validator = self.setup_validator()
        validator.check_token_mismatch("id1", "⟦PH_1⟧ hello", "world ⟦PH_1⟧ ⟦PH_2⟧", 1)
        assert len(validator.errors) == 1
        assert validator.errors[0]['type'] == 'token_mismatch'
        assert 'extra' in validator.errors[0]['detail']
        assert 'PH_2' in validator.errors[0]['detail']
        assert validator.error_counts['token_mismatch'] == 1
    
    def test_multiple_missing_and_extra(self):
        """Test multiple missing and extra tokens"""
        validator = self.setup_validator()
        validator.check_token_mismatch(
            "id1", 
            "⟦PH_1⟧ ⟦PH_2⟧ ⟦PH_3⟧", 
            "⟦PH_1⟧ ⟦PH_4⟧ ⟦PH_5⟧", 
            1
        )
        assert len(validator.errors) == 4  # 2 missing + 2 extra
        assert validator.error_counts['token_mismatch'] == 4
    
    def test_empty_source_and_target(self):
        """Test with empty source and target"""
        validator = self.setup_validator()
        validator.check_token_mismatch("id1", "", "", 1)
        assert len(validator.errors) == 0


class TestCheckTagBalance:
    """Tests for check_tag_balance method"""
    
    def setup_validator(self):
        """Helper to create a validator"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "e.json")
        validator.errors = []
        validator.error_counts = {
            'token_mismatch': 0,
            'tag_unbalanced': 0,
            'forbidden_hit': 0,
            'new_placeholder_found': 0
        }
        validator.placeholder_map = {
            'TAG_1': '<b>',
            'TAG_2': '</b>',
            'TAG_3': '<i>',
            'TAG_4': '</i>',
        }
        return validator
    
    def test_balanced_tags_simple(self):
        """Test with balanced simple tags"""
        validator = self.setup_validator()
        # Without paired_tags, uses simple counting
        validator.check_tag_balance("id1", "⟦TAG_1⟧bold⟦TAG_2⟧", 1)
        assert len(validator.errors) == 0
    
    def test_unbalanced_tags_simple(self):
        """Test with unbalanced simple tags"""
        validator = self.setup_validator()
        validator.check_tag_balance("id1", "⟦TAG_1⟧bold", 1)
        assert len(validator.errors) == 1
        assert validator.errors[0]['type'] == 'tag_unbalanced'
        assert validator.error_counts['tag_unbalanced'] == 1
    
    def test_empty_text(self):
        """Test with empty text"""
        validator = self.setup_validator()
        validator.check_tag_balance("id1", "", 1)
        assert len(validator.errors) == 0
    
    def test_no_tags(self):
        """Test text without any tags"""
        validator = self.setup_validator()
        validator.check_tag_balance("id1", "Hello world", 1)
        assert len(validator.errors) == 0
    
    def test_paired_tags_balanced(self):
        """Test with paired_tags config - balanced"""
        validator = self.setup_validator()
        validator.paired_tags = [
            {'open': '<b>', 'close': '</b>', 'description': 'bold tags'}
        ]
        validator.check_tag_balance("id1", "⟦TAG_1⟧text⟦TAG_2⟧", 1)
        assert len(validator.errors) == 0
    
    def test_paired_tags_unbalanced(self):
        """Test with paired_tags config - unbalanced"""
        validator = self.setup_validator()
        validator.paired_tags = [
            {'open': '<b>', 'close': '</b>', 'description': 'bold tags'}
        ]
        validator.check_tag_balance("id1", "⟦TAG_1⟧text", 1)
        assert len(validator.errors) == 1
        assert validator.errors[0]['type'] == 'tag_unbalanced'
        assert 'bold tags' in validator.errors[0]['detail']


class TestCheckForbiddenPatterns:
    """Tests for check_forbidden_patterns method"""
    
    def setup_validator(self):
        """Helper to create a validator"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "e.json")
        validator.errors = []
        validator.error_counts = {
            'token_mismatch': 0,
            'tag_unbalanced': 0,
            'forbidden_hit': 0,
            'new_placeholder_found': 0
        }
        return validator
    
    def test_no_forbidden_patterns(self):
        """Test with no forbidden patterns configured"""
        validator = self.setup_validator()
        validator.compiled_forbidden = []
        validator.check_forbidden_patterns("id1", "Hello world", 1)
        assert len(validator.errors) == 0
    
    def test_no_match(self):
        """Test when text doesn't match forbidden patterns"""
        validator = self.setup_validator()
        validator.compiled_forbidden = [re.compile(r'forbidden_word')]
        validator.check_forbidden_patterns("id1", "Hello world", 1)
        assert len(validator.errors) == 0
    
    def test_single_match(self):
        """Test when text matches a forbidden pattern"""
        validator = self.setup_validator()
        validator.compiled_forbidden = [re.compile(r'bad_word')]
        validator.check_forbidden_patterns("id1", "This has bad_word in it", 1)
        assert len(validator.errors) == 1
        assert validator.errors[0]['type'] == 'forbidden_hit'
        assert validator.error_counts['forbidden_hit'] == 1
    
    def test_multiple_patterns_first_match(self):
        """Test that only first match is reported"""
        validator = self.setup_validator()
        validator.compiled_forbidden = [
            re.compile(r'word1'),
            re.compile(r'word2')
        ]
        validator.check_forbidden_patterns("id1", "word1 and word2", 1)
        assert len(validator.errors) == 1  # Only reports first match
        assert 'word1' in validator.errors[0]['detail']
    
    def test_empty_text(self):
        """Test with empty text"""
        validator = self.setup_validator()
        validator.compiled_forbidden = [re.compile(r'test')]
        validator.check_forbidden_patterns("id1", "", 1)
        assert len(validator.errors) == 0


class TestCheckNewPlaceholders:
    """Tests for check_new_placeholders method"""
    
    def setup_validator(self):
        """Helper to create a validator"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "e.json")
        validator.errors = []
        validator.error_counts = {
            'token_mismatch': 0,
            'tag_unbalanced': 0,
            'forbidden_hit': 0,
            'new_placeholder_found': 0
        }
        return validator
    
    def test_no_patterns(self):
        """Test with no compiled patterns"""
        validator = self.setup_validator()
        validator.compiled_patterns = []
        validator.check_new_placeholders("id1", "Hello {NEW_PLACEHOLDER}", 1)
        assert len(validator.errors) == 0
    
    def test_pattern_no_match(self):
        """Test when text doesn't match pattern"""
        validator = self.setup_validator()
        validator.compiled_patterns = [re.compile(r'\{OLD_PH\}')]
        validator.check_new_placeholders("id1", "Hello world", 1)
        assert len(validator.errors) == 0
    
    def test_pattern_finds_new_placeholder(self):
        """Test when new unfrozen placeholder is found"""
        validator = self.setup_validator()
        validator.compiled_patterns = [re.compile(r'\{(\w+)\}')]
        validator.check_new_placeholders("id1", "Hello {NEW_PH}", 1)
        assert len(validator.errors) == 1
        assert validator.errors[0]['type'] == 'new_placeholder_found'
        assert validator.error_counts['new_placeholder_found'] == 1
    
    def test_skips_already_tokenized(self):
        """Test that already tokenized placeholders (⟦...⟧ format) are skipped"""
        validator = self.setup_validator()
        # Pattern that would match {PH_123} but text contains already tokenized version
        validator.compiled_patterns = [re.compile(r'(\{PH_\d+\}|⟦PH_\d+⟧)')]
        validator.check_new_placeholders("id1", "Hello ⟦PH_123⟧ world", 1)
        # Should skip because match contains '⟦'
        assert len(validator.errors) == 0


class TestCheckLengthOverflow:
    """Tests for check_length_overflow method"""
    
    def setup_validator(self):
        """Helper to create a validator"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "e.json")
        validator.errors = []
        validator.error_counts = {
            'token_mismatch': 0,
            'tag_unbalanced': 0,
            'forbidden_hit': 0,
            'new_placeholder_found': 0,
            'length_overflow': 0
        }
        return validator
    
    def test_no_max_length(self):
        """Test when no max_length is set"""
        validator = self.setup_validator()
        row = {}
        validator.check_length_overflow("id1", "Hello world", row, 1)
        assert len(validator.errors) == 0
    
    def test_within_limit(self):
        """Test when text is within length limit"""
        validator = self.setup_validator()
        row = {'max_length_target': '100'}
        validator.check_length_overflow("id1", "Hello", row, 1)
        assert len(validator.errors) == 0
    
    def test_exceeds_limit_major(self):
        """Test when text exceeds limit (major severity)"""
        validator = self.setup_validator()
        row = {'max_length_target': '10'}
        validator.check_length_overflow("id1", "Hello World!!!", row, 1)
        assert len(validator.errors) == 1
        assert validator.errors[0]['type'] == 'length_overflow'
        assert validator.errors[0]['severity'] == 'major'
    
    def test_exceeds_limit_critical(self):
        """Test when text exceeds limit by 50%+ (critical severity)"""
        validator = self.setup_validator()
        row = {'max_length_target': '10'}
        # 16 chars is 1.6x limit (> 1.5x = critical)
        validator.check_length_overflow("id1", "This is way too long!!!", row, 1)
        assert len(validator.errors) == 1
        assert validator.errors[0]['severity'] == 'critical'
    
    def test_invalid_max_length(self):
        """Test with invalid max_length value"""
        validator = self.setup_validator()
        row = {'max_length_target': 'invalid'}
        validator.check_length_overflow("id1", "Hello", row, 1)
        assert len(validator.errors) == 0
    
    def test_zero_max_length(self):
        """Test with zero max_length"""
        validator = self.setup_validator()
        row = {'max_length_target': '0'}
        validator.check_length_overflow("id1", "Hello", row, 1)
        assert len(validator.errors) == 0
    
    def test_alternative_field_name(self):
        """Test with max_len_target field name"""
        validator = self.setup_validator()
        row = {'max_len_target': '5'}
        validator.check_length_overflow("id1", "Hello World", row, 1)
        assert len(validator.errors) == 1


class TestLoadPlaceholderMap:
    """Tests for load_placeholder_map method"""
    
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        'mappings': {'PH_1': '<b>', 'PH_2': '</b>'}
    }))
    def test_load_success(self, mock_file):
        """Test successful loading of placeholder map"""
        validator = QAHardValidator("a.csv", "map.json", "c.yaml", "d.txt", "e.json")
        result = validator.load_placeholder_map()
        assert result is True
        assert validator.placeholder_map == {'PH_1': '<b>', 'PH_2': '</b>'}
    
    @patch('builtins.open', side_effect=FileNotFoundError())
    def test_file_not_found(self, mock_file):
        """Test when placeholder map file not found"""
        validator = QAHardValidator("a.csv", "map.json", "c.yaml", "d.txt", "e.json")
        result = validator.load_placeholder_map()
        assert result is False
    
    @patch('builtins.open', new_callable=mock_open, read_data='invalid json')
    def test_invalid_json(self, mock_file):
        """Test when placeholder map contains invalid JSON"""
        validator = QAHardValidator("a.csv", "map.json", "c.yaml", "d.txt", "e.json")
        result = validator.load_placeholder_map()
        assert result is False


class TestLoadSchema:
    """Tests for load_schema method"""
    
    @patch('builtins.open', new_callable=mock_open, read_data='''
version: 2
patterns:
  - name: test
    regex: \\{\\w+\\}
paired_tags:
  - open: <b>
    close: </b>
    description: bold
''')
    @patch('qa_hard.yaml.safe_load')
    def test_load_v2_schema(self, mock_yaml, mock_file):
        """Test loading v2.0 schema format"""
        mock_yaml.return_value = {
            'version': 2,
            'patterns': [{'name': 'test', 'regex': r'\{\w+\}'}],
            'paired_tags': [{'open': '<b>', 'close': '</b>', 'description': 'bold'}]
        }
        validator = QAHardValidator("a.csv", "b.json", "schema.yaml", "d.txt", "e.json")
        result = validator.load_schema()
        assert result is True
        assert len(validator.compiled_patterns) == 1
        assert len(validator.paired_tags) == 1
    
    @patch('builtins.open', new_callable=mock_open, read_data='''
version: 1
placeholder_patterns:
  - name: test
    pattern: \\{\\w+\\}
''')
    @patch('qa_hard.yaml.safe_load')
    def test_load_v1_schema_fallback(self, mock_yaml, mock_file):
        """Test loading v1.0 schema format (fallback)"""
        mock_yaml.return_value = {
            'version': 1,
            'placeholder_patterns': [{'name': 'test', 'pattern': r'\{\w+\}'}]
        }
        validator = QAHardValidator("a.csv", "b.json", "schema.yaml", "d.txt", "e.json")
        result = validator.load_schema()
        assert result is True
        assert len(validator.compiled_patterns) == 1
    
    @patch('builtins.open', side_effect=FileNotFoundError())
    def test_schema_not_found(self, mock_file):
        """Test when schema file not found (should continue)"""
        validator = QAHardValidator("a.csv", "b.json", "schema.yaml", "d.txt", "e.json")
        result = validator.load_schema()
        assert result is True  # Returns True to continue without schema
    
    @patch('builtins.open', new_callable=mock_open, read_data='invalid yaml')
    @patch('qa_hard.yaml.safe_load', side_effect=Exception("YAML error"))
    def test_invalid_yaml(self, mock_yaml, mock_file):
        """Test with invalid YAML"""
        validator = QAHardValidator("a.csv", "b.json", "schema.yaml", "d.txt", "e.json")
        result = validator.load_schema()
        assert result is True  # Returns True to continue


class TestLoadForbiddenPatterns:
    """Tests for load_forbidden_patterns method"""
    
    @patch('builtins.open', new_callable=mock_open, read_data='''
# Comment line
bad_word_1
another\\.pattern
''')
    def test_load_success(self, mock_file):
        """Test successful loading of forbidden patterns"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "forbidden.txt", "e.json")
        result = validator.load_forbidden_patterns()
        assert result is True
        assert len(validator.compiled_forbidden) == 2
    
    @patch('builtins.open', new_callable=mock_open, read_data='''
valid_pattern
[invalid(regex
''')
    def test_invalid_regex_skipped(self, mock_file):
        """Test that invalid regex patterns are skipped with warning"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "forbidden.txt", "e.json")
        result = validator.load_forbidden_patterns()
        assert result is True
        assert len(validator.compiled_forbidden) == 1  # Only valid one
    
    @patch('builtins.open', side_effect=FileNotFoundError())
    def test_file_not_found(self, mock_file):
        """Test when forbidden patterns file not found (should continue)"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "forbidden.txt", "e.json")
        result = validator.load_forbidden_patterns()
        assert result is True  # Returns True to continue


class TestGenerateReport:
    """Tests for generate_report method"""
    
    @patch('pathlib.Path.mkdir')
    @patch('json.dump')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_report_empty(self, mock_file, mock_json_dump, mock_mkdir):
        """Test generating report with no errors"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "report.json")
        validator.errors = []
        validator.total_rows = 10
        validator.error_counts = {'token_mismatch': 0}
        
        validator.generate_report()
        
        # Check that json.dump was called
        mock_json_dump.assert_called_once()
        call_args = mock_json_dump.call_args
        report = call_args[0][0]  # First positional argument
        assert report['has_errors'] is False
        assert report['total_rows'] == 10
    
    @patch('pathlib.Path.mkdir')
    @patch('json.dump')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_report_with_errors(self, mock_file, mock_json_dump, mock_mkdir):
        """Test generating report with errors"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "report.json")
        validator.errors = [{'type': 'test', 'detail': 'error'}]
        validator.total_rows = 10
        validator.error_counts = {'token_mismatch': 1}
        
        validator.generate_report()
        
        call_args = mock_json_dump.call_args
        report = call_args[0][0]
        assert report['has_errors'] is True
        assert report['metadata']['total_errors'] == 1
    
    @patch('pathlib.Path.mkdir')
    @patch('json.dump')
    @patch('builtins.open', new_callable=mock_open)
    def test_generate_report_truncation(self, mock_file, mock_json_dump, mock_mkdir):
        """Test that errors are truncated to 2000"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "report.json")
        validator.errors = [{'type': 'test', 'detail': f'error{i}'} for i in range(2500)]
        validator.total_rows = 100
        validator.error_counts = {'token_mismatch': 2500}
        
        validator.generate_report()
        
        call_args = mock_json_dump.call_args
        report = call_args[0][0]
        assert len(report['errors']) == 2000
        assert report['metadata']['errors_truncated'] is True


class TestPairedTagsCheck:
    """Tests for _check_paired_tags method"""
    
    def setup_validator(self):
        """Helper to create a validator with paired tags config"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "e.json")
        validator.errors = []
        validator.error_counts = {'tag_unbalanced': 0}
        validator.placeholder_map = {
            'TAG_1': '<b>',
            'TAG_2': '</b>',
            'TAG_3': '<i>',
            'TAG_4': '</i>',
        }
        validator.paired_tags = [
            {'open': '<b>', 'close': '</b>', 'description': 'bold tags'},
            {'open': '<i>', 'close': '</i>', 'description': 'italic tags'}
        ]
        return validator
    
    def test_balanced_paired_tags(self):
        """Test balanced paired tags"""
        validator = self.setup_validator()
        tag_tokens = ['TAG_1', 'TAG_2']
        validator._check_paired_tags("id1", "text", tag_tokens, 1)
        assert len(validator.errors) == 0
    
    def test_unbalanced_open_more(self):
        """Test unbalanced - more opening tags"""
        validator = self.setup_validator()
        tag_tokens = ['TAG_1', 'TAG_1', 'TAG_2']
        validator._check_paired_tags("id1", "text", tag_tokens, 1)
        assert len(validator.errors) == 1
        assert 'bold tags' in validator.errors[0]['detail']
        assert validator.error_counts['tag_unbalanced'] == 1
    
    def test_unbalanced_close_more(self):
        """Test unbalanced - more closing tags"""
        validator = self.setup_validator()
        tag_tokens = ['TAG_1', 'TAG_2', 'TAG_2']
        validator._check_paired_tags("id1", "text", tag_tokens, 1)
        assert len(validator.errors) == 1
    
    def test_multiple_pairs(self):
        """Test multiple tag pairs"""
        validator = self.setup_validator()
        tag_tokens = ['TAG_1', 'TAG_2', 'TAG_3']  # bold balanced, italic unbalanced
        validator._check_paired_tags("id1", "text", tag_tokens, 1)
        assert len(validator.errors) == 1
        assert 'italic tags' in validator.errors[0]['detail']


class TestTagCountFallback:
    """Tests for _check_tag_count fallback method"""
    
    def setup_validator(self):
        """Helper to create a validator"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "e.json")
        validator.errors = []
        validator.error_counts = {'tag_unbalanced': 0}
        validator.placeholder_map = {
            'TAG_1': '<b>',
            'TAG_2': '</b>',
            'TAG_3': '<br/>',  # Self-closing
        }
        return validator
    
    def test_balanced_fallback(self):
        """Test balanced tags with fallback method"""
        validator = self.setup_validator()
        tag_tokens = ['TAG_1', 'TAG_2']
        validator._check_tag_count("id1", "text", tag_tokens, 1)
        assert len(validator.errors) == 0
    
    def test_unbalanced_fallback(self):
        """Test unbalanced tags with fallback method"""
        validator = self.setup_validator()
        tag_tokens = ['TAG_1', 'TAG_1', 'TAG_2']
        validator._check_tag_count("id1", "text", tag_tokens, 1)
        assert len(validator.errors) == 1
        assert validator.errors[0]['type'] == 'tag_unbalanced'


class TestEdgeCases:
    """Edge case tests"""
    
    def test_token_pattern_compiled_once(self):
        """Test that token pattern is compiled during init"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "e.json")
        assert validator.token_pattern is not None
        assert validator.token_pattern.pattern == r'⟦(PH_\d+|TAG_\d+)⟧'
    
    def test_unicode_text_handling(self):
        """Test handling of unicode text"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "e.json")
        text = "⟦PH_1⟧ 你好世界 ⟦TAG_1⟧ 🎮"
        tokens = validator.extract_tokens(text)
        assert tokens == {"PH_1", "TAG_1"}
    
    def test_special_characters_in_text(self):
        """Test handling of special characters"""
        validator = QAHardValidator("a.csv", "b.json", "c.yaml", "d.txt", "e.json")
        text = "⟦PH_1⟧ <script>alert('xss')</script> ⟦PH_2⟧"
        tokens = validator.extract_tokens(text)
        assert tokens == {"PH_1", "PH_2"}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
