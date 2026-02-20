#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for glossary_translate_llm.py

Tests the core functions without requiring actual LLM API calls.
Uses direct imports and mocking for pytest compatibility.
"""

import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open
from dataclasses import asdict

# Add src/scripts to path for import
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "scripts"))

# Mock yaml before import
mock_yaml = MagicMock()
sys.modules['yaml'] = mock_yaml

import glossary_translate_llm as gtl


class TestTranslatedTerm:
    """Tests for TranslatedTerm dataclass."""
    
    def test_translated_term_creation(self):
        """Test creating a TranslatedTerm with all fields."""
        term = gtl.TranslatedTerm(
            term_zh="测试",
            term_ru="тест",
            confidence=0.95,
            reason="test reason",
            context="test context"
        )
        assert term.term_zh == "测试"
        assert term.term_ru == "тест"
        assert term.confidence == 0.95
        assert term.reason == "test reason"
        assert term.context == "test context"
    
    def test_translated_term_defaults(self):
        """Test TranslatedTerm with default values."""
        term = gtl.TranslatedTerm(
            term_zh="测试",
            term_ru="тест",
            confidence=0.95,
            reason="test"
        )
        assert term.context is None
    
    def test_translated_term_asdict(self):
        """Test converting TranslatedTerm to dict."""
        term = gtl.TranslatedTerm(
            term_zh="测试",
            term_ru="тест",
            confidence=0.95,
            reason="test reason",
            context="context"
        )
        d = asdict(term)
        assert d["term_zh"] == "测试"
        assert d["term_ru"] == "тест"
        assert d["confidence"] == 0.95
        assert d["reason"] == "test reason"
        assert d["context"] == "context"


class TestLoadProposals:
    """Tests for load_proposals function."""
    
    def test_load_proposals_file_not_exists(self):
        """Test loading when file doesn't exist."""
        with patch.object(Path, 'exists', return_value=False):
            result = gtl.load_proposals("/nonexistent/path.yaml")
            assert result == []
    
    def test_load_proposals_with_candidates_key(self):
        """Test loading proposals with 'candidates' key."""
        mock_data = {
            "candidates": [
                {"term_zh": "测试", "context": "test context"},
                {"term_zh": "示例", "context": "example context"}
            ]
        }
        mock_yaml.safe_load.return_value = mock_data
        
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='')):
                result = gtl.load_proposals("/fake/path.yaml")
                
        assert len(result) == 2
        assert result[0]["term_zh"] == "测试"
        assert result[1]["term_zh"] == "示例"
    
    def test_load_proposals_with_entries_key(self):
        """Test loading proposals with 'entries' key."""
        mock_data = {
            "entries": [
                {"term_zh": "术语1", "context": "context1"},
                {"term_zh": "术语2", "context": "context2"}
            ]
        }
        mock_yaml.safe_load.return_value = mock_data
        
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='')):
                result = gtl.load_proposals("/fake/path.yaml")
                
        assert len(result) == 2
        assert result[0]["term_zh"] == "术语1"
    
    def test_load_proposals_with_proposals_key(self):
        """Test loading proposals with 'proposals' key."""
        mock_data = {
            "proposals": [
                {"term_zh": "提案1", "context": "context1"}
            ]
        }
        mock_yaml.safe_load.return_value = mock_data
        
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='')):
                result = gtl.load_proposals("/fake/path.yaml")
                
        assert len(result) == 1
        assert result[0]["term_zh"] == "提案1"
    
    def test_load_proposals_empty_file(self):
        """Test loading from empty file."""
        mock_yaml.safe_load.return_value = None
        
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='')):
                result = gtl.load_proposals("/fake/path.yaml")
                
        assert result == []
    
    def test_load_proposals_empty_dict(self):
        """Test loading from file with empty dict."""
        mock_yaml.safe_load.return_value = {}
        
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data='')):
                result = gtl.load_proposals("/fake/path.yaml")
                
        assert result == []
    
    def test_load_proposals_yaml_not_installed(self):
        """Test error when PyYAML is not installed."""
        with patch.object(gtl, 'yaml', None):
            with patch.object(Path, 'exists', return_value=True):
                try:
                    result = gtl.load_proposals("/fake/path.yaml")
                    assert False, "Should have raised RuntimeError"
                except RuntimeError as e:
                    assert "PyYAML required" in str(e)


class TestLoadStyleGuide:
    """Tests for load_style_guide function."""
    
    def test_load_style_guide_file_not_exists(self):
        """Test loading when file doesn't exist."""
        with patch.object(Path, 'exists', return_value=False):
            result = gtl.load_style_guide("/nonexistent/style.md")
            assert result == ""
    
    def test_load_style_guide_success(self):
        """Test successfully loading style guide."""
        content = "# Style Guide\n\nUse formal language."
        
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=content)):
                result = gtl.load_style_guide("/fake/style.md")
                
        assert result == content.strip()
    
    def test_load_style_guide_whitespace_stripped(self):
        """Test that whitespace is stripped from loaded content."""
        content = "  \n  # Style Guide  \n  \n"
        
        with patch.object(Path, 'exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=content)):
                result = gtl.load_style_guide("/fake/style.md")
                
        assert result == content.strip()


class TestBuildSystemPrompt:
    """Tests for build_system_prompt function."""
    
    def test_build_system_prompt_structure(self):
        """Test that system prompt contains expected sections."""
        prompt = gtl.build_system_prompt()
        
        # Check for key sections
        assert "术语表译者" in prompt or "zh-CN → ru-RU" in prompt
        assert "JSON" in prompt
        assert "items" in prompt
        assert "id" in prompt
        assert "term_ru" in prompt
        assert "pos" in prompt
        assert "notes" in prompt
        assert "confidence" in prompt
    
    def test_build_system_prompt_rules(self):
        """Test that system prompt contains hard rules."""
        prompt = gtl.build_system_prompt()
        
        # Check for rules
        assert "id 必须与输入一致" in prompt or "id" in prompt
        assert "【】" in prompt or "term_ru" in prompt
        assert "«»" in prompt or "引号" in prompt
    
    def test_build_system_prompt_is_string(self):
        """Test that system prompt returns a string."""
        prompt = gtl.build_system_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0


class TestBuildUserPrompt:
    """Tests for build_user_prompt function."""
    
    def test_build_user_prompt_empty_items(self):
        """Test building prompt with empty items."""
        items = []
        prompt = gtl.build_user_prompt(items)
        
        assert "language_pair: zh-CN -> ru-RU" in prompt
        assert "candidates:" in prompt
        assert "[]" in prompt
    
    def test_build_user_prompt_single_item(self):
        """Test building prompt with single item."""
        items = [{"id": "测试", "source_text": "测试上下文"}]
        prompt = gtl.build_user_prompt(items)
        
        assert "language_pair: zh-CN -> ru-RU" in prompt
        assert "context_hint: Game Localization" in prompt
        assert "测试" in prompt
        assert "测试上下文" in prompt
    
    def test_build_user_prompt_multiple_items(self):
        """Test building prompt with multiple items."""
        items = [
            {"id": "火之意志", "source_text": "Plot context"},
            {"id": "写轮眼", "source_text": "Skill context"}
        ]
        prompt = gtl.build_user_prompt(items)
        
        assert "火之意志" in prompt
        assert "写轮眼" in prompt
        assert "Plot context" in prompt
        assert "Skill context" in prompt
    
    def test_build_user_prompt_missing_source_text(self):
        """Test building prompt with missing source_text."""
        items = [{"id": "测试"}]
        prompt = gtl.build_user_prompt(items)
        
        assert "测试" in prompt
        # Should handle missing source_text gracefully
        assert '"context": ""' in prompt or '"context":' in prompt
    
    def test_build_user_prompt_valid_json_in_output(self):
        """Test that the candidates section is valid JSON."""
        items = [
            {"id": "术语1", "source_text": "context1"},
            {"id": "术语2", "source_text": "context2"}
        ]
        prompt = gtl.build_user_prompt(items)
        
        # Extract the JSON part after "candidates:\n"
        json_part = prompt.split("candidates:\n")[1]
        parsed = json.loads(json_part)
        
        assert len(parsed) == 2
        assert parsed[0]["term_zh"] == "术语1"
        assert parsed[1]["term_zh"] == "术语2"


class TestProcessBatchResults:
    """Tests for process_batch_results function."""
    
    def test_process_empty_results(self):
        """Test processing empty batch results."""
        result = gtl.process_batch_results([], [])
        assert result == []
    
    def test_process_single_result(self):
        """Test processing single batch result."""
        batch_items = [{
            "id": "火之意志",
            "term_ru": "Воля Огня",
            "pos": "phrase",
            "notes": "Core concept",
            "confidence": 0.95
        }]
        original_entries = [{"term_zh": "火之意志", "context": "Plot"}]
        
        results = gtl.process_batch_results(batch_items, original_entries)
        
        assert len(results) == 1
        assert results[0].term_zh == "火之意志"
        assert results[0].term_ru == "Воля Огня"
        assert results[0].confidence == 0.95
        assert "Core concept" in results[0].reason
        assert "phrase" in results[0].reason
    
    def test_process_multiple_results(self):
        """Test processing multiple batch results."""
        batch_items = [
            {"id": "火之意志", "term_ru": "Воля Огня", "pos": "phrase", "notes": "Core", "confidence": 0.95},
            {"id": "写轮眼", "term_ru": "Шаринган", "pos": "name", "notes": "Dojutsu", "confidence": 0.99}
        ]
        original_entries = [
            {"term_zh": "火之意志", "context": "Plot"},
            {"term_zh": "写轮眼", "context": "Skill"}
        ]
        
        results = gtl.process_batch_results(batch_items, original_entries)
        
        assert len(results) == 2
        assert results[0].term_ru == "Воля Огня"
        assert results[1].term_ru == "Шаринган"
    
    def test_process_missing_term_ru(self):
        """Test that entries without term_ru are skipped."""
        batch_items = [
            {"id": "火之意志", "term_ru": "Воля Огня", "pos": "phrase", "confidence": 0.95},
            {"id": "写轮眼", "term_ru": "", "pos": "name", "confidence": 0.0}
        ]
        original_entries = [
            {"term_zh": "火之意志", "context": "Plot"},
            {"term_zh": "写轮眼", "context": "Skill"}
        ]
        
        results = gtl.process_batch_results(batch_items, original_entries)
        
        assert len(results) == 1
        assert results[0].term_zh == "火之意志"
    
    def test_process_unknown_id_ignored(self):
        """Test that entries with unknown IDs are ignored."""
        batch_items = [
            {"id": "未知术语", "term_ru": "Unknown", "pos": "noun", "confidence": 0.5}
        ]
        original_entries = [
            {"term_zh": "已知术语", "context": "Known"}
        ]
        
        results = gtl.process_batch_results(batch_items, original_entries)
        
        assert len(results) == 0
    
    def test_process_preserves_context(self):
        """Test that context from original entries is preserved."""
        batch_items = [{
            "id": "测试",
            "term_ru": "тест",
            "pos": "noun",
            "confidence": 0.9
        }]
        original_entries = [{"term_zh": "测试", "context": "Original context"}]
        
        results = gtl.process_batch_results(batch_items, original_entries)
        
        assert len(results) == 1
        assert results[0].context == "Original context"
    
    def test_process_confidence_conversion(self):
        """Test that confidence is properly converted to float."""
        batch_items = [{
            "id": "测试",
            "term_ru": "тест",
            "pos": "noun",
            "confidence": "0.85"  # String confidence
        }]
        original_entries = [{"term_zh": "测试", "context": "Test"}]
        
        results = gtl.process_batch_results(batch_items, original_entries)
        
        assert len(results) == 1
        assert results[0].confidence == 0.85
    
    def test_process_missing_notes(self):
        """Test processing with missing notes field."""
        batch_items = [{
            "id": "测试",
            "term_ru": "тест",
            "pos": "noun",
            "confidence": 0.9
        }]
        original_entries = [{"term_zh": "测试", "context": "Test"}]
        
        results = gtl.process_batch_results(batch_items, original_entries)
        
        assert len(results) == 1
        assert results[0].reason == " | noun"


class TestWriteTranslatedYaml:
    """Tests for write_translated_yaml function."""
    
    def setup_method(self):
        """Reset mock before each test."""
        mock_yaml.reset_mock()
    
    def test_write_empty_results(self, tmp_path):
        """Test writing empty results."""
        output_path = tmp_path / "output.yaml"
        meta = {"test": True}
        
        gtl.write_translated_yaml(str(output_path), [], meta)
        
        assert output_path.exists()
        assert mock_yaml.dump.call_count == 1
        call_args = mock_yaml.dump.call_args
        output_data = call_args[0][0]
        
        assert output_data["meta"]["total_translated"] == 0
        assert output_data["entries"] == []
        assert output_data["meta"]["test"] == True
    
    def test_write_single_result(self, tmp_path):
        """Test writing single result."""
        mock_yaml.reset_mock()
        output_path = tmp_path / "output.yaml"
        meta = {"source": "test"}
        results = [
            gtl.TranslatedTerm(
                term_zh="测试",
                term_ru="тест",
                confidence=0.95,
                reason="test reason",
                context="test context"
            )
        ]
        
        gtl.write_translated_yaml(str(output_path), results, meta)
        
        assert mock_yaml.dump.call_count == 1
        call_args = mock_yaml.dump.call_args
        output_data = call_args[0][0]
        
        assert output_data["meta"]["total_translated"] == 1
        assert len(output_data["entries"]) == 1
        assert output_data["entries"][0]["term_zh"] == "测试"
        assert output_data["entries"][0]["term_ru"] == "тест"
    
    def test_write_multiple_results(self, tmp_path):
        """Test writing multiple results."""
        mock_yaml.reset_mock()
        output_path = tmp_path / "output.yaml"
        meta = {"batch_size": 20}
        results = [
            gtl.TranslatedTerm("术语1", "Термин1", 0.9, "reason1", "ctx1"),
            gtl.TranslatedTerm("术语2", "Термин2", 0.85, "reason2", "ctx2"),
            gtl.TranslatedTerm("术语3", "Термин3", 0.95, "reason3", None)
        ]
        
        gtl.write_translated_yaml(str(output_path), results, meta)
        
        call_args = mock_yaml.dump.call_args
        output_data = call_args[0][0]
        
        assert output_data["meta"]["total_translated"] == 3
        assert len(output_data["entries"]) == 3
    
    def test_write_creates_parent_dirs(self, tmp_path):
        """Test that parent directories are created."""
        mock_yaml.reset_mock()
        nested_dir = tmp_path / "nested" / "dirs"
        output_path = nested_dir / "output.yaml"
        meta = {}
        
        # Ensure directory doesn't exist
        assert not nested_dir.exists()
        
        gtl.write_translated_yaml(str(output_path), [], meta)
        
        # Verify directory was created
        assert nested_dir.exists()
        assert output_path.exists()
    
    def test_write_yaml_not_installed(self, tmp_path):
        """Test error when PyYAML is not installed."""
        with patch.object(gtl, 'yaml', None):
            try:
                gtl.write_translated_yaml(str(tmp_path / "out.yaml"), [], {})
                assert False, "Should have raised RuntimeError"
            except RuntimeError as e:
                assert "PyYAML required" in str(e)
    
    def test_write_includes_timestamp(self, tmp_path):
        """Test that output includes generation timestamp."""
        mock_yaml.reset_mock()
        output_path = tmp_path / "output.yaml"
        
        gtl.write_translated_yaml(str(output_path), [], {})
        
        call_args = mock_yaml.dump.call_args
        output_data = call_args[0][0]
        
        assert "generated_at" in output_data["meta"]
        assert "step" in output_data["meta"]
        assert output_data["meta"]["step"] == "glossary_translate"


class TestMainFunction:
    """Tests for main function (integration-style)."""
    
    @patch('glossary_translate_llm.load_proposals')
    @patch('glossary_translate_llm.load_style_guide')
    @patch('glossary_translate_llm.batch_llm_call')
    @patch('glossary_translate_llm.write_translated_yaml')
    @patch('glossary_translate_llm.Path')
    def test_main_dry_run(self, mock_path_class, mock_write, mock_batch, mock_load_style, mock_load_props):
        """Test main function in dry-run mode."""
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_class.return_value = mock_path_instance
        mock_path_class.__truediv__ = MagicMock(return_value=mock_path_instance)
        
        mock_load_props.return_value = [
            {"term_zh": "测试", "context": "test"}
        ]
        mock_load_style.return_value = ""
        
        with patch('sys.argv', ['script', '--proposals', 'test.yaml', '--dry-run']):
            result = gtl.main()
        
        assert result == 0
        mock_batch.assert_not_called()
        mock_write.assert_not_called()
    
    @patch('glossary_translate_llm.load_proposals')
    @patch('glossary_translate_llm.Path')
    def test_main_file_not_found(self, mock_path_class, mock_load_props):
        """Test main when proposals file doesn't exist."""
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = False
        mock_path_class.return_value = mock_path_instance
        
        with patch('sys.argv', ['script', '--proposals', 'missing.yaml']):
            result = gtl.main()
        
        assert result == 1
    
    @patch('glossary_translate_llm.load_proposals')
    @patch('glossary_translate_llm.Path')
    def test_main_empty_proposals(self, mock_path_class, mock_load_props):
        """Test main with empty proposals."""
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_class.return_value = mock_path_instance
        mock_load_props.return_value = []
        
        with patch('sys.argv', ['script', '--proposals', 'empty.yaml']):
            result = gtl.main()
        
        assert result == 0
