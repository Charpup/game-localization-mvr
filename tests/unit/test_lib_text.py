#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive unit tests for lib_text.py
Target: 90%+ coverage on load_punctuation_config and sanitize_punctuation
"""

import unittest
import os
import tempfile
import sys
from unittest.mock import patch, mock_open
from io import StringIO

# Import yaml fresh to avoid interference from other test mocks
import importlib
import yaml

from src.lib.lib_text import load_punctuation_config, sanitize_punctuation


class TestLoadPunctuationConfig(unittest.TestCase):
    """Test cases for load_punctuation_config function."""

    def setUp(self):
        """Set up temporary directory for test files."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary files."""
        for f in os.listdir(self.temp_dir):
            os.remove(os.path.join(self.temp_dir, f))
        os.rmdir(self.temp_dir)

    def _create_yaml_file(self, filename, data):
        """Helper to create YAML files for testing."""
        filepath = os.path.join(self.temp_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, allow_unicode=True)
        return filepath

    def test_base_config_only(self):
        """Test loading base config without locale override."""
        base_data = {'replace': {'...': '…', '--': '–'}}
        base_path = self._create_yaml_file('base.yaml', base_data)
        
        with patch('src.lib.lib_text.yaml') as mock_yaml:
            mock_yaml.safe_load.return_value = base_data
            result = load_punctuation_config(base_path)
        
        self.assertEqual(len(result), 2)
        self.assertIn({'source': '...', 'target': '…'}, result)
        self.assertIn({'source': '--', 'target': '–'}, result)

    def test_base_plus_locale_merge(self):
        """Test merging base config with locale overrides."""
        base_data = {'replace': {'...': '…', '--': '–', 'old': 'value'}}
        locale_data = {'replace': {'--': '—', 'new': 'addition'}}
        
        base_path = self._create_yaml_file('base.yaml', base_data)
        locale_path = self._create_yaml_file('locale.yaml', locale_data)
        
        with patch('src.lib.lib_text.yaml') as mock_yaml:
            mock_yaml.safe_load.side_effect = [base_data, locale_data]
            result = load_punctuation_config(base_path, locale_path)
        
        # Should have 4 mappings (base 3 + 1 new from locale)
        self.assertEqual(len(result), 4)
        
        # Check that '--' was updated from base
        dash_mapping = next(m for m in result if m['source'] == '--')
        self.assertEqual(dash_mapping['target'], '—')
        
        # Check that new mapping was added
        self.assertIn({'source': 'new', 'target': 'addition'}, result)
        
        # Check that old mapping is still there
        self.assertIn({'source': 'old', 'target': 'value'}, result)

    def test_missing_base_file(self):
        """Test behavior when base file doesn't exist."""
        nonexistent_path = os.path.join(self.temp_dir, 'nonexistent.yaml')
        
        result = load_punctuation_config(nonexistent_path)
        
        self.assertEqual(result, [])

    def test_missing_locale_file(self):
        """Test behavior when locale file doesn't exist."""
        base_data = {'replace': {'...': '…'}}
        base_path = self._create_yaml_file('base.yaml', base_data)
        nonexistent_locale = os.path.join(self.temp_dir, 'nonexistent_locale.yaml')
        
        with patch('src.lib.lib_text.yaml') as mock_yaml:
            mock_yaml.safe_load.return_value = base_data
            result = load_punctuation_config(base_path, nonexistent_locale)
        
        # Should still return base config
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], {'source': '...', 'target': '…'})

    def test_invalid_yaml_base(self):
        """Test behavior when base file has invalid YAML."""
        filepath = os.path.join(self.temp_dir, 'invalid.yaml')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('invalid: yaml: content: [')
        
        result = load_punctuation_config(filepath)
        
        self.assertEqual(result, [])

    def test_invalid_yaml_locale(self):
        """Test behavior when locale file has invalid YAML."""
        base_data = {'replace': {'...': '…'}}
        base_path = self._create_yaml_file('base.yaml', base_data)
        
        invalid_locale = os.path.join(self.temp_dir, 'invalid_locale.yaml')
        with open(invalid_locale, 'w', encoding='utf-8') as f:
            f.write('invalid: yaml: {{')
        
        with patch('src.lib.lib_text.yaml') as mock_yaml:
            mock_yaml.safe_load.side_effect = [base_data, Exception("Invalid YAML")]
            result = load_punctuation_config(base_path, invalid_locale)
        
        # Should return base config since locale failed
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], {'source': '...', 'target': '…'})

    def test_empty_replace_section(self):
        """Test config with empty replace section."""
        base_data = {'replace': {}}
        base_path = self._create_yaml_file('base.yaml', base_data)
        
        result = load_punctuation_config(base_path)
        
        self.assertEqual(result, [])

    def test_missing_replace_section(self):
        """Test config without replace section."""
        base_data = {'other_key': 'value'}
        base_path = self._create_yaml_file('base.yaml', base_data)
        
        result = load_punctuation_config(base_path)
        
        self.assertEqual(result, [])

    def test_unicode_mappings(self):
        """Test loading mappings with unicode characters."""
        base_data = {
            'replace': {
                '【': '«',
                '】': '»',
                '…': '...',
                '—': '--',
                '你好': 'Hello',
                '😀': '🙂'
            }
        }
        base_path = self._create_yaml_file('base.yaml', base_data)
        
        with patch('src.lib.lib_text.yaml') as mock_yaml:
            mock_yaml.safe_load.return_value = base_data
            result = load_punctuation_config(base_path)
        
        self.assertEqual(len(result), 6)
        self.assertIn({'source': '【', 'target': '«'}, result)
        self.assertIn({'source': '】', 'target': '»'}, result)
        self.assertIn({'source': '你好', 'target': 'Hello'}, result)
        self.assertIn({'source': '😀', 'target': '🙂'}, result)

    def test_locale_only_no_base(self):
        """Test loading only locale config when base is missing."""
        base_data = {'replace': {}}  # Empty base
        locale_data = {'replace': {'...': '…'}}
        
        base_path = self._create_yaml_file('base.yaml', base_data)
        locale_path = self._create_yaml_file('locale.yaml', locale_data)
        
        with patch('src.lib.lib_text.yaml') as mock_yaml:
            mock_yaml.safe_load.side_effect = [base_data, locale_data]
            result = load_punctuation_config(base_path, locale_path)
        
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0], {'source': '...', 'target': '…'})

    def test_none_locale_path(self):
        """Test that None locale_path is handled correctly."""
        base_data = {'replace': {'...': '…'}}
        base_path = self._create_yaml_file('base.yaml', base_data)
        
        with patch('src.lib.lib_text.yaml') as mock_yaml:
            mock_yaml.safe_load.return_value = base_data
            result = load_punctuation_config(base_path, None)
        
        self.assertEqual(len(result), 1)


class TestSanitizePunctuation(unittest.TestCase):
    """Test cases for sanitize_punctuation function."""

    def test_basic_replacement(self):
        """Test basic single replacement."""
        mappings = [{'source': '...', 'target': '…'}]
        result = sanitize_punctuation("Loading...", mappings)
        self.assertEqual(result, "Loading…")

    def test_multiple_replacements(self):
        """Test multiple replacements in same text."""
        mappings = [
            {'source': '...', 'target': '…'},
            {'source': '--', 'target': '–'},
            {'source': '!!', 'target': '‼'}
        ]
        text = "Wait... look-- amazing!!"
        expected = "Wait… look– amazing‼"
        result = sanitize_punctuation(text, mappings)
        self.assertEqual(result, expected)

    def test_overlapping_patterns(self):
        """Test that replacements are applied in order."""
        mappings = [
            {'source': '...', 'target': '…'},
            {'source': '..', 'target': '‥'}
        ]
        text = "Wait..."
        # First ... becomes …, so .. at end won't match
        result = sanitize_punctuation(text, mappings)
        self.assertEqual(result, "Wait…")

    def test_empty_text(self):
        """Test with empty text string."""
        mappings = [{'source': '...', 'target': '…'}]
        result = sanitize_punctuation("", mappings)
        self.assertEqual(result, "")

    def test_empty_mappings(self):
        """Test with empty mappings list."""
        result = sanitize_punctuation("Hello world", [])
        self.assertEqual(result, "Hello world")

    def test_none_mappings(self):
        """Test with None mappings (empty list behavior)."""
        result = sanitize_punctuation("Hello world", [])
        self.assertEqual(result, "Hello world")

    def test_no_match(self):
        """Test when no patterns match."""
        mappings = [{'source': '...', 'target': '…'}]
        result = sanitize_punctuation("Hello world", mappings)
        self.assertEqual(result, "Hello world")

    def test_special_characters(self):
        """Test with special unicode characters."""
        mappings = [
            {'source': '【', 'target': '«'},
            {'source': '】', 'target': '»'},
            {'source': '「', 'target': '"'},
            {'source': '」', 'target': '"'}
        ]
        text = '【系统】提示「注意」'
        expected = '«系统»提示"注意"'
        result = sanitize_punctuation(text, mappings)
        self.assertEqual(result, expected)

    def test_multicharacter_replacement(self):
        """Test replacing single char with multiple chars."""
        mappings = [{'source': '&', 'target': ' and '}]
        result = sanitize_punctuation("Tom&Jerry", mappings)
        self.assertEqual(result, "Tom and Jerry")

    def test_delete_pattern(self):
        """Test deleting a pattern (replace with empty string)."""
        mappings = [{'source': '***', 'target': ''}]
        result = sanitize_punctuation("Important***note", mappings)
        self.assertEqual(result, "Importantnote")

    def test_whitespace_replacement(self):
        """Test replacing with whitespace."""
        mappings = [{'source': '_', 'target': ' '}]
        result = sanitize_punctuation("Hello_World", mappings)
        self.assertEqual(result, "Hello World")

    def test_mapping_with_missing_source(self):
        """Test that mappings without source key are skipped."""
        mappings = [
            {'target': '…'},  # Missing source
            {'source': '...', 'target': '…'}
        ]
        result = sanitize_punctuation("Wait...", mappings)
        self.assertEqual(result, "Wait…")

    def test_mapping_with_missing_target(self):
        """Test that mappings without target key raises TypeError."""
        mappings = [
            {'source': '...'},  # Missing target - becomes None
        ]
        # This should raise TypeError since target is None
        with self.assertRaises(TypeError):
            sanitize_punctuation("Wait...", mappings)

    def test_chinese_punctuation(self):
        """Test Chinese punctuation replacement."""
        mappings = [
            {'source': '，', 'target': ', '},
            {'source': '。', 'target': '. '},
            {'source': '！', 'target': '! '}
        ]
        text = "你好，世界。很棒！"
        expected = "你好, 世界. 很棒! "
        result = sanitize_punctuation(text, mappings)
        self.assertEqual(result, expected)

    def test_emoji_replacement(self):
        """Test emoji replacement."""
        mappings = [
            {'source': '😀', 'target': '🙂'},
            {'source': '❤️', 'target': '<3'}
        ]
        text = "Hello 😀 I ❤️ you"
        expected = "Hello 🙂 I <3 you"
        result = sanitize_punctuation(text, mappings)
        self.assertEqual(result, expected)

    def test_multiple_same_pattern(self):
        """Test multiple occurrences of same pattern."""
        mappings = [{'source': '...', 'target': '…'}]
        text = "Wait... then... go..."
        expected = "Wait… then… go…"
        result = sanitize_punctuation(text, mappings)
        self.assertEqual(result, expected)

    def test_case_sensitivity(self):
        """Test that replacement is case sensitive."""
        mappings = [{'source': 'abc', 'target': 'XYZ'}]
        text = "abc ABC abc"
        expected = "XYZ ABC XYZ"
        result = sanitize_punctuation(text, mappings)
        self.assertEqual(result, expected)


if __name__ == '__main__':
    unittest.main()
