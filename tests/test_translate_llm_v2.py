#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_translate_llm_v2.py

Comprehensive unit tests for translate_llm.py
Target: 90%+ code coverage

Test coverage includes:
- Text translation logic
- Glossary application
- Batch processing
- Model routing
- Error handling
"""

import pytest
import json
import csv
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, mock_open
from io import StringIO
from dataclasses import dataclass

# Add the scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

# Mock runtime_adapter before importing translate_llm
sys.modules['runtime_adapter'] = Mock()

from runtime_adapter import LLMClient, LLMError, batch_llm_call, log_llm_progress

# Import the module under test
import translate_llm as tl


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)


@pytest.fixture
def sample_glossary_entries():
    """Sample glossary entries for testing."""
    return [
        tl.GlossaryEntry(term_zh="战士", term_ru="Воин", status="approved"),
        tl.GlossaryEntry(term_zh="法师", term_ru="Маг", status="approved"),
        tl.GlossaryEntry(term_zh="盗贼", term_ru="Вор", status="pending"),  # Not approved
        tl.GlossaryEntry(term_zh="", term_ru="Пустой", status="approved"),  # Empty term_zh
    ]


@pytest.fixture
def sample_csv_data():
    """Sample CSV data for testing."""
    return [
        {"string_id": "1", "source_zh": "战士攻击", "tokenized_zh": "⟦PH_1⟧战士攻击⟦PH_2⟧"},
        {"string_id": "2", "source_zh": "法师施法", "tokenized_zh": "⟦TAG_1⟧法师施法"},
        {"string_id": "3", "source_zh": "普通文本", "tokenized_zh": "普通文本"},
    ]


@pytest.fixture
def mock_batch_results():
    """Mock batch LLM call results."""
    return [
        {"id": "1", "target_ru": "⟦PH_1⟧Воин атакует⟦PH_2⟧"},
        {"id": "2", "target_ru": "⟦TAG_1⟧Маг колдует"},
        {"id": "3", "target_ru": "Обычный текст"},
    ]


# =============================================================================
# Glossary Tests
# =============================================================================

class TestGlossaryConstraints:
    """Tests for glossary constraint building."""
    
    def test_build_glossary_constraints_with_matches(self, sample_glossary_entries):
        """Test building constraints when terms match."""
        source_zh = "战士和法师一起战斗"
        result = tl.build_glossary_constraints(sample_glossary_entries, source_zh)
        
        assert "战士" in result
        assert "法师" in result
        assert result["战士"] == "Воин"
        assert result["法师"] == "Маг"
        assert "盗贼" not in result  # Not approved
    
    def test_build_glossary_constraints_no_matches(self, sample_glossary_entries):
        """Test building constraints when no terms match."""
        source_zh = "没有任何匹配"
        result = tl.build_glossary_constraints(sample_glossary_entries, source_zh)
        assert result == {}
    
    def test_build_glossary_constraints_empty_source(self, sample_glossary_entries):
        """Test building constraints with empty source."""
        result = tl.build_glossary_constraints(sample_glossary_entries, "")
        assert result == {}
    
    def test_build_glossary_constraints_empty_glossary(self):
        """Test building constraints with empty glossary."""
        result = tl.build_glossary_constraints([], "任何文本")
        assert result == {}


class TestLoadGlossary:
    """Tests for glossary loading."""
    
    def test_load_glossary_success(self, temp_dir):
        """Test successful glossary loading."""
        glossary_path = os.path.join(temp_dir, "glossary.yaml")
        glossary_data = {
            "entries": [
                {"term_zh": "战士", "term_ru": "Воин", "status": "approved"},
                {"term_zh": "法师", "term_ru": "Маг", "status": "approved"},
            ],
            "meta": {"compiled_hash": "abc123"}
        }
        
        with open(glossary_path, 'w', encoding='utf-8') as f:
            import yaml
            yaml.dump(glossary_data, f)
        
        entries, hash_val = tl.load_glossary(glossary_path)
        
        assert len(entries) == 2
        assert entries[0].term_zh == "战士"
        assert entries[0].term_ru == "Воин"
        assert entries[0].status == "approved"
        assert hash_val == "abc123"
    
    def test_load_glossary_file_not_found(self):
        """Test loading non-existent glossary file."""
        entries, hash_val = tl.load_glossary("/nonexistent/path.yaml")
        assert entries == []
        assert hash_val is None
    
    def test_load_glossary_none_path(self):
        """Test loading with None path."""
        entries, hash_val = tl.load_glossary(None)
        assert entries == []
        assert hash_val is None
    
    def test_load_glossary_no_meta(self, temp_dir):
        """Test loading glossary without meta."""
        glossary_path = os.path.join(temp_dir, "glossary.yaml")
        glossary_data = {
            "entries": [
                {"term_zh": "战士", "term_ru": "Воин", "status": "approved"},
            ]
        }
        
        with open(glossary_path, 'w', encoding='utf-8') as f:
            import yaml
            yaml.dump(glossary_data, f)
        
        entries, hash_val = tl.load_glossary(glossary_path)
        assert len(entries) == 1
        assert hash_val is None
    
    def test_load_glossary_yaml_not_installed(self, temp_dir):
        """Test loading when yaml is not available."""
        with patch.object(tl, 'yaml', None):
            entries, hash_val = tl.load_glossary("/some/path.yaml")
            assert entries == []
            assert hash_val is None


class TestGlossarySummary:
    """Tests for glossary summary building."""
    
    def test_build_glossary_summary_with_entries(self, sample_glossary_entries):
        """Test summary with entries."""
        # Filter to only approved entries
        approved = [e for e in sample_glossary_entries if e.status == "approved" and e.term_zh]
        result = tl.build_glossary_summary(approved)
        
        assert "战士" in result
        assert "Воин" in result
        assert "法师" in result
        assert "Маг" in result
    
    def test_build_glossary_summary_empty(self):
        """Test summary with no entries."""
        result = tl.build_glossary_summary([])
        assert result == "(无)"
    
    def test_build_glossary_summary_limit_50(self):
        """Test that summary is limited to 50 entries."""
        entries = [tl.GlossaryEntry(term_zh=f"term{i}", term_ru=f"term_ru{i}", status="approved") 
                   for i in range(100)]
        result = tl.build_glossary_summary(entries)
        
        lines = result.strip().split('\n')
        assert len(lines) == 50


# =============================================================================
# Token Validation Tests
# =============================================================================

class TestTokenSignature:
    """Tests for token signature calculation."""
    
    def test_tokens_signature_with_phs(self):
        """Test signature with PH tokens."""
        text = "⟦PH_1⟧文本⟦PH_2⟧更多⟦PH_1⟧"
        result = tl.tokens_signature(text)
        
        assert result["PH_1"] == 2
        assert result["PH_2"] == 1
    
    def test_tokens_signature_with_tags(self):
        """Test signature with TAG tokens."""
        text = "⟦TAG_1⟧开始⟦TAG_2⟧结束"
        result = tl.tokens_signature(text)
        
        assert result["TAG_1"] == 1
        assert result["TAG_2"] == 1
    
    def test_tokens_signature_mixed(self):
        """Test signature with mixed tokens."""
        text = "⟦PH_1⟧⟦TAG_1⟧文本⟦PH_1⟧"
        result = tl.tokens_signature(text)
        
        assert result["PH_1"] == 2
        assert result["TAG_1"] == 1
    
    def test_tokens_signature_empty(self):
        """Test signature with empty text."""
        result = tl.tokens_signature("")
        assert result == {}
    
    def test_tokens_signature_none(self):
        """Test signature with None text."""
        result = tl.tokens_signature(None)
        assert result == {}


class TestValidateTranslation:
    """Tests for translation validation."""
    
    def test_validate_translation_success(self):
        """Test successful validation."""
        tokenized_zh = "⟦PH_1⟧战士⟦PH_2⟧"
        ru = "⟦PH_1⟧Воин⟦PH_2⟧"
        ok, err = tl.validate_translation(tokenized_zh, ru)
        
        assert ok is True
        assert err == "ok"
    
    def test_validate_translation_token_mismatch(self):
        """Test validation with token mismatch."""
        tokenized_zh = "⟦PH_1⟧战士"
        ru = "Воин"  # Missing PH_1
        ok, err = tl.validate_translation(tokenized_zh, ru)
        
        assert ok is False
        assert err == "token_mismatch"
    
    def test_validate_translation_cjk_remaining(self):
        """Test validation with CJK characters remaining."""
        tokenized_zh = "⟦PH_1⟧战士"
        ru = "⟦PH_1⟧战士"  # Still has Chinese
        ok, err = tl.validate_translation(tokenized_zh, ru)
        
        assert ok is False
        assert err == "cjk_remaining"
    
    def test_validate_translation_empty(self):
        """Test validation with empty translation."""
        tokenized_zh = "战士"  # No tokens
        ru = ""  # Empty translation
        ok, err = tl.validate_translation(tokenized_zh, ru)
        
        assert ok is False
        assert err == "empty"
    
    def test_validate_translation_both_empty(self):
        """Test validation with both empty."""
        ok, err = tl.validate_translation("", "")
        assert ok is True  # Both empty is consistent


# =============================================================================
# Prompt Builder Tests
# =============================================================================

class TestSystemPromptFactory:
    """Tests for system prompt factory."""
    
    def test_build_system_prompt_factory_basic(self):
        """Test basic prompt building."""
        style_guide = "Use formal tone"
        glossary_summary = "战士 → Воин"
        
        factory = tl.build_system_prompt_factory(style_guide, glossary_summary)
        
        rows = [{"string_id": "1", "source_text": "test"}]
        prompt = factory(rows)
        
        assert "手游本地化译者" in prompt
        assert "Output Contract v6" in prompt
        assert "Use formal tone" in prompt
        assert "战士 → Воин" in prompt
    
    def test_build_system_prompt_with_length_constraints(self):
        """Test prompt with length constraints."""
        style_guide = ""
        glossary_summary = ""
        
        factory = tl.build_system_prompt_factory(style_guide, glossary_summary)
        
        rows = [
            {"string_id": "1", "source_text": "test", "max_length_target": 50},
            {"string_id": "2", "source_text": "test2", "max_len_target": 100},
        ]
        prompt = factory(rows)
        
        assert "Length Constraints" in prompt
        assert "max 50 chars" in prompt
        assert "max 100 chars" in prompt
    
    def test_build_system_prompt_no_constraints(self):
        """Test prompt without length constraints."""
        factory = tl.build_system_prompt_factory("", "")
        
        rows = [{"string_id": "1", "source_text": "test"}]
        prompt = factory(rows)
        
        assert "Length Constraints" not in prompt


class TestUserPrompt:
    """Tests for user prompt building."""
    
    def test_build_user_prompt(self):
        """Test user prompt building."""
        rows = [
            {"id": "1", "source_text": "战士攻击"},
            {"id": "2", "source_text": "法师施法"},
        ]
        
        prompt = tl.build_user_prompt(rows)
        data = json.loads(prompt)
        
        assert len(data) == 2
        assert data[0]["id"] == "1"
        assert data[0]["source_text"] == "战士攻击"


# =============================================================================
# Checkpoint Tests
# =============================================================================

class TestCheckpoint:
    """Tests for checkpoint functionality."""
    
    def test_load_checkpoint_exists(self, temp_dir):
        """Test loading existing checkpoint."""
        checkpoint_path = os.path.join(temp_dir, "checkpoint.json")
        checkpoint_data = {"done_ids": ["1", "2", "3"]}
        
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump(checkpoint_data, f)
        
        result = tl.load_checkpoint(checkpoint_path)
        assert result == {"1", "2", "3"}
    
    def test_load_checkpoint_not_exists(self, temp_dir):
        """Test loading non-existent checkpoint."""
        checkpoint_path = os.path.join(temp_dir, "nonexistent.json")
        result = tl.load_checkpoint(checkpoint_path)
        assert result == set()
    
    def test_load_checkpoint_invalid_json(self, temp_dir):
        """Test loading invalid JSON checkpoint."""
        checkpoint_path = os.path.join(temp_dir, "checkpoint.json")
        
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            f.write("invalid json")
        
        result = tl.load_checkpoint(checkpoint_path)
        assert result == set()
    
    def test_save_checkpoint(self, temp_dir):
        """Test saving checkpoint."""
        checkpoint_path = os.path.join(temp_dir, "checkpoint.json")
        done_ids = {"1", "2", "3"}
        
        tl.save_checkpoint(checkpoint_path, done_ids)
        
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert set(data["done_ids"]) == done_ids
    
    def test_save_checkpoint_creates_parent_dir(self, temp_dir):
        """Test that save_checkpoint creates parent directories."""
        checkpoint_path = os.path.join(temp_dir, "subdir1", "subdir2", "checkpoint.json")
        done_ids = {"1"}
        
        tl.save_checkpoint(checkpoint_path, done_ids)
        
        assert os.path.exists(checkpoint_path)


# =============================================================================
# File Loading Tests
# =============================================================================

class TestLoadText:
    """Tests for text file loading."""
    
    def test_load_text_success(self, temp_dir):
        """Test successful text loading."""
        file_path = os.path.join(temp_dir, "test.txt")
        content = "Hello World"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        result = tl.load_text(file_path)
        assert result == content
    
    def test_load_text_not_exists(self):
        """Test loading non-existent file."""
        result = tl.load_text("/nonexistent/file.txt")
        assert result == ""
    
    def test_load_text_strips_whitespace(self, temp_dir):
        """Test that text is stripped of whitespace."""
        file_path = os.path.join(temp_dir, "test.txt")
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("  content  \n")
        
        result = tl.load_text(file_path)
        assert result == "content"


# =============================================================================
# Main Function Tests (Integration)
# =============================================================================

class TestMainIntegration:
    """Integration tests for main function."""
    
    def create_test_csv(self, temp_dir, data):
        """Helper to create test CSV file."""
        csv_path = os.path.join(temp_dir, "input.csv")
        with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
            if data:
                writer = csv.DictWriter(f, fieldnames=data[0].keys())
                writer.writeheader()
                writer.writerows(data)
        return csv_path
    
    @patch('translate_llm.batch_llm_call')
    @patch('translate_llm.LLMClient')
    def test_main_success(self, mock_llm_client_class, mock_batch_call, temp_dir):
        """Test successful main execution."""
        # Setup
        csv_data = [
            {"string_id": "1", "source_zh": "战士", "tokenized_zh": "⟦PH_1⟧战士"},
        ]
        input_path = self.create_test_csv(temp_dir, csv_data)
        output_path = os.path.join(temp_dir, "output.csv")
        style_path = os.path.join(temp_dir, "style.md")
        glossary_path = os.path.join(temp_dir, "glossary.yaml")
        checkpoint_path = os.path.join(temp_dir, "checkpoint.json")
        
        # Create style guide
        with open(style_path, 'w', encoding='utf-8') as f:
            f.write("Style guide content")
        
        # Create glossary
        import yaml
        with open(glossary_path, 'w', encoding='utf-8') as f:
            yaml.dump({"entries": []}, f)
        
        # Mock batch_llm_call
        mock_batch_call.return_value = [
            {"id": "1", "target_ru": "⟦PH_1⟧Воин"}
        ]
        
        # Execute
        with patch.object(sys, 'argv', [
            'translate_llm.py',
            '--input', input_path,
            '--output', output_path,
            '--style', style_path,
            '--glossary', glossary_path,
            '--checkpoint', checkpoint_path,
            '--model', 'test-model'
        ]):
            tl.main()
        
        # Verify
        assert os.path.exists(output_path)
        with open(output_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 1
            assert rows[0]["target_text"] == "⟦PH_1⟧Воин"
    
    @patch('translate_llm.batch_llm_call')
    def test_main_with_checkpoint_resume(self, mock_batch_call, temp_dir):
        """Test main with checkpoint resume."""
        # Setup
        csv_data = [
            {"string_id": "1", "source_zh": "战士", "tokenized_zh": "战士"},
            {"string_id": "2", "source_zh": "法师", "tokenized_zh": "法师"},
        ]
        input_path = self.create_test_csv(temp_dir, csv_data)
        output_path = os.path.join(temp_dir, "output.csv")
        style_path = os.path.join(temp_dir, "style.md")
        glossary_path = os.path.join(temp_dir, "glossary.yaml")
        checkpoint_path = os.path.join(temp_dir, "checkpoint.json")
        
        # Create existing checkpoint (string_id 1 is done)
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump({"done_ids": ["1"]}, f)
        
        with open(style_path, 'w', encoding='utf-8') as f:
            f.write("Style")
        
        import yaml
        with open(glossary_path, 'w', encoding='utf-8') as f:
            yaml.dump({"entries": []}, f)
        
        mock_batch_call.return_value = [
            {"id": "2", "target_ru": "Маг"}
        ]
        
        # Execute
        with patch.object(sys, 'argv', [
            'translate_llm.py',
            '--input', input_path,
            '--output', output_path,
            '--style', style_path,
            '--glossary', glossary_path,
            '--checkpoint', checkpoint_path,
        ]):
            tl.main()
        
        # Verify only string_id 2 was processed
        mock_batch_call.assert_called_once()
        call_args = mock_batch_call.call_args
        batch_inputs = call_args.kwargs['rows']
        assert len(batch_inputs) == 1
        assert batch_inputs[0]["id"] == "2"
    
    @patch('translate_llm.batch_llm_call')
    def test_main_no_pending_rows(self, mock_batch_call, temp_dir):
        """Test main when all rows are already processed."""
        csv_data = [
            {"string_id": "1", "source_zh": "战士", "tokenized_zh": "战士"},
        ]
        input_path = self.create_test_csv(temp_dir, csv_data)
        output_path = os.path.join(temp_dir, "output.csv")
        checkpoint_path = os.path.join(temp_dir, "checkpoint.json")
        
        # All rows already done
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump({"done_ids": ["1"]}, f)
        
        with patch.object(sys, 'argv', [
            'translate_llm.py',
            '--input', input_path,
            '--output', output_path,
            '--checkpoint', checkpoint_path,
        ]):
            tl.main()
        
        # batch_llm_call should not be called
        mock_batch_call.assert_not_called()
    
    @patch('translate_llm.batch_llm_call')
    def test_main_detects_long_text(self, mock_batch_call, temp_dir):
        """Test that long_text content type is detected."""
        csv_data = [
            {"string_id": "1", "source_zh": "战士", "tokenized_zh": "战士", "is_long_text": "1"},
        ]
        input_path = self.create_test_csv(temp_dir, csv_data)
        output_path = os.path.join(temp_dir, "output.csv")
        checkpoint_path = os.path.join(temp_dir, "checkpoint.json")
        
        mock_batch_call.return_value = [
            {"id": "1", "target_ru": "Воин"}
        ]
        
        with patch.object(sys, 'argv', [
            'translate_llm.py',
            '--input', input_path,
            '--output', output_path,
            '--checkpoint', checkpoint_path,
        ]):
            tl.main()
        
        # Verify content_type was set to long_text
        call_args = mock_batch_call.call_args
        assert call_args.kwargs['content_type'] == "long_text"
    
    @patch('translate_llm.batch_llm_call')
    def test_main_validation_failure_handling(self, mock_batch_call, temp_dir, capsys):
        """Test handling of validation failures."""
        csv_data = [
            {"string_id": "1", "source_zh": "战士", "tokenized_zh": "⟦PH_1⟧战士"},
        ]
        input_path = self.create_test_csv(temp_dir, csv_data)
        output_path = os.path.join(temp_dir, "output.csv")
        checkpoint_path = os.path.join(temp_dir, "checkpoint.json")
        
        # Return invalid result (missing token)
        mock_batch_call.return_value = [
            {"id": "1", "target_ru": "Воин"}  # Missing ⟦PH_1⟧
        ]
        
        with patch.object(sys, 'argv', [
            'translate_llm.py',
            '--input', input_path,
            '--output', output_path,
            '--checkpoint', checkpoint_path,
        ]):
            tl.main()
        
        # Verify validation error was logged
        captured = capsys.readouterr()
        assert "Validation failed" in captured.out or "Validation failed" in captured.err
        
        # Verify checkpoint was not updated with failed row
        with open(checkpoint_path, 'r', encoding='utf-8') as f:
            checkpoint_data = json.load(f)
            assert "1" not in checkpoint_data.get("done_ids", [])
    
    def test_main_input_not_found(self, temp_dir, capsys):
        """Test handling of missing input file."""
        with patch.object(sys, 'argv', [
            'translate_llm.py',
            '--input', '/nonexistent/input.csv',
            '--output', os.path.join(temp_dir, 'output.csv'),
        ]):
            tl.main()
        
        captured = capsys.readouterr()
        assert "Input not found" in captured.out or "Input not found" in captured.err
    
    @patch('translate_llm.batch_llm_call')
    def test_main_adds_target_text_header(self, mock_batch_call, temp_dir):
        """Test that target_text column is added if missing."""
        csv_data = [
            {"string_id": "1", "source_zh": "战士"},  # No target_text column
        ]
        input_path = self.create_test_csv(temp_dir, csv_data)
        output_path = os.path.join(temp_dir, "output.csv")
        checkpoint_path = os.path.join(temp_dir, "checkpoint.json")
        
        mock_batch_call.return_value = [
            {"id": "1", "target_ru": "Воин"}
        ]
        
        with patch.object(sys, 'argv', [
            'translate_llm.py',
            '--input', input_path,
            '--output', output_path,
            '--checkpoint', checkpoint_path,
        ]):
            tl.main()
        
        # Verify output has target_text column
        with open(output_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert "target_text" in row
            assert row["target_text"] == "Воин"


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error handling scenarios."""
    
    @patch('translate_llm.batch_llm_call')
    def test_main_batch_exception(self, mock_batch_call, temp_dir):
        """Test handling of batch_llm_call exception."""
        csv_data = [{"string_id": "1", "source_zh": "战士", "tokenized_zh": "战士"}]
        
        input_path = os.path.join(temp_dir, "input.csv")
        with open(input_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_data[0].keys())
            writer.writeheader()
            writer.writerows(csv_data)
        
        mock_batch_call.side_effect = Exception("LLM API Error")
        
        with patch.object(sys, 'argv', [
            'translate_llm.py',
            '--input', input_path,
            '--output', os.path.join(temp_dir, 'output.csv'),
            '--checkpoint', os.path.join(temp_dir, 'checkpoint.json'),
        ]):
            with pytest.raises(SystemExit) as exc_info:
                tl.main()
            assert exc_info.value.code == 1


# =============================================================================
# Edge Cases and Boundary Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundaries."""
    
    def test_glossary_entry_dataclass(self):
        """Test GlossaryEntry dataclass."""
        entry = tl.GlossaryEntry(term_zh="测试", term_ru="Тест", status="approved", notes="note")
        assert entry.term_zh == "测试"
        assert entry.term_ru == "Тест"
        assert entry.status == "approved"
        assert entry.notes == "note"
    
    def test_build_glossary_constraints_partial_match(self):
        """Test glossary constraints with partial matches."""
        entries = [
            tl.GlossaryEntry(term_zh="战士", term_ru="Воин", status="approved"),
            tl.GlossaryEntry(term_zh="勇敢战士", term_ru="Храбрый воин", status="approved"),
        ]
        
        # Both should match even though one contains the other
        source = "战士和勇敢战士"
        result = tl.build_glossary_constraints(entries, source)
        
        assert "战士" in result
        assert "勇敢战士" in result
    
    @patch('translate_llm.batch_llm_call')
    def test_main_empty_csv(self, mock_batch_call, temp_dir):
        """Test main with empty CSV."""
        input_path = os.path.join(temp_dir, "empty.csv")
        with open(input_path, 'w', encoding='utf-8-sig', newline='') as f:
            f.write("string_id,source_zh\n")  # Just header
        
        output_path = os.path.join(temp_dir, "output.csv")
        checkpoint_path = os.path.join(temp_dir, "checkpoint.json")
        
        with patch.object(sys, 'argv', [
            'translate_llm.py',
            '--input', input_path,
            '--output', output_path,
            '--checkpoint', checkpoint_path,
        ]):
            tl.main()
        
        # Should handle gracefully
        mock_batch_call.assert_not_called()


# =============================================================================
# Batch Processing Tests
# =============================================================================

class TestBatchProcessing:
    """Tests for batch processing logic."""
    
    @patch('translate_llm.batch_llm_call')
    def test_batch_inputs_format(self, mock_batch_call, temp_dir):
        """Test that batch inputs are correctly formatted."""
        csv_data = [
            {"string_id": "1", "source_zh": "战士", "tokenized_zh": "⟦PH_1⟧战士"},
            {"string_id": "2", "source_zh": "法师", "tokenized_zh": "法师"},
        ]
        input_path = os.path.join(temp_dir, "input.csv")
        with open(input_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_data[0].keys())
            writer.writeheader()
            writer.writerows(csv_data)
        
        output_path = os.path.join(temp_dir, "output.csv")
        checkpoint_path = os.path.join(temp_dir, "checkpoint.json")
        
        mock_batch_call.return_value = [
            {"id": "1", "target_ru": "Воин"},
            {"id": "2", "target_ru": "Маг"},
        ]
        
        with patch.object(sys, 'argv', [
            'translate_llm.py',
            '--input', input_path,
            '--output', output_path,
            '--checkpoint', checkpoint_path,
        ]):
            tl.main()
        
        # Verify batch_inputs format
        call_args = mock_batch_call.call_args
        batch_inputs = call_args.kwargs['rows']
        
        assert len(batch_inputs) == 2
        assert batch_inputs[0] == {"id": "1", "source_text": "⟦PH_1⟧战士"}
        assert batch_inputs[1] == {"id": "2", "source_text": "法师"}
    
    @patch('translate_llm.batch_llm_call')
    def test_system_prompt_builder_callable(self, mock_batch_call, temp_dir):
        """Test that system_prompt_builder is passed correctly."""
        csv_data = [{"string_id": "1", "source_zh": "战士", "tokenized_zh": "战士"}]
        input_path = os.path.join(temp_dir, "input.csv")
        with open(input_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_data[0].keys())
            writer.writeheader()
            writer.writerows(csv_data)
        
        output_path = os.path.join(temp_dir, "output.csv")
        checkpoint_path = os.path.join(temp_dir, "checkpoint.json")
        style_path = os.path.join(temp_dir, "style.md")
        glossary_path = os.path.join(temp_dir, "glossary.yaml")
        
        with open(style_path, 'w') as f:
            f.write("style")
        
        import yaml
        with open(glossary_path, 'w') as f:
            yaml.dump({"entries": []}, f)
        
        mock_batch_call.return_value = [{"id": "1", "target_ru": "Воин"}]
        
        with patch.object(sys, 'argv', [
            'translate_llm.py',
            '--input', input_path,
            '--output', output_path,
            '--checkpoint', checkpoint_path,
            '--style', style_path,
            '--glossary', glossary_path,
        ]):
            tl.main()
        
        # Verify system_prompt_builder is callable
        call_args = mock_batch_call.call_args
        system_prompt = call_args.kwargs['system_prompt']
        assert callable(system_prompt)


# =============================================================================
# Model Routing Tests
# =============================================================================

class TestModelRouting:
    """Tests for model routing functionality."""
    
    @patch('translate_llm.batch_llm_call')
    def test_model_argument_passed(self, mock_batch_call, temp_dir):
        """Test that --model argument is passed to batch_llm_call."""
        csv_data = [{"string_id": "1", "source_zh": "战士", "tokenized_zh": "战士"}]
        input_path = os.path.join(temp_dir, "input.csv")
        with open(input_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_data[0].keys())
            writer.writeheader()
            writer.writerows(csv_data)
        
        output_path = os.path.join(temp_dir, "output.csv")
        checkpoint_path = os.path.join(temp_dir, "checkpoint.json")
        
        mock_batch_call.return_value = [{"id": "1", "target_ru": "Воин"}]
        
        custom_model = "custom-model-v1"
        with patch.object(sys, 'argv', [
            'translate_llm.py',
            '--input', input_path,
            '--output', output_path,
            '--checkpoint', checkpoint_path,
            '--model', custom_model,
        ]):
            tl.main()
        
        call_args = mock_batch_call.call_args
        assert call_args.kwargs['model'] == custom_model
    
    @patch('translate_llm.batch_llm_call')
    def test_default_model(self, mock_batch_call, temp_dir):
        """Test default model when not specified."""
        csv_data = [{"string_id": "1", "source_zh": "战士", "tokenized_zh": "战士"}]
        input_path = os.path.join(temp_dir, "input.csv")
        with open(input_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_data[0].keys())
            writer.writeheader()
            writer.writerows(csv_data)
        
        output_path = os.path.join(temp_dir, "output.csv")
        checkpoint_path = os.path.join(temp_dir, "checkpoint.json")
        
        mock_batch_call.return_value = [{"id": "1", "target_ru": "Воин"}]
        
        with patch.object(sys, 'argv', [
            'translate_llm.py',
            '--input', input_path,
            '--output', output_path,
            '--checkpoint', checkpoint_path,
        ]):
            tl.main()
        
        call_args = mock_batch_call.call_args
        # Should use default model
        assert call_args.kwargs['model'] == "claude-haiku-4-5-20251001"


# =============================================================================
# CSV Output Tests
# =============================================================================

class TestCSVOutput:
    """Tests for CSV output handling."""
    
    @patch('translate_llm.batch_llm_call')
    def test_csv_append_mode(self, mock_batch_call, temp_dir):
        """Test that CSV is appended when file exists."""
        csv_data = [{"string_id": "1", "source_zh": "战士", "tokenized_zh": "战士"}]
        input_path = os.path.join(temp_dir, "input.csv")
        with open(input_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=csv_data[0].keys())
            writer.writeheader()
            writer.writerows(csv_data)
        
        output_path = os.path.join(temp_dir, "output.csv")
        checkpoint_path = os.path.join(temp_dir, "checkpoint.json")
        
        # Create existing output
        with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=["string_id", "source_zh", "target_text"])
            writer.writeheader()
            writer.writerow({"string_id": "0", "source_zh": "existing", "target_text": "существующий"})
        
        mock_batch_call.return_value = [{"id": "1", "target_ru": "Воин"}]
        
        with patch.object(sys, 'argv', [
            'translate_llm.py',
            '--input', input_path,
            '--output', output_path,
            '--checkpoint', checkpoint_path,
        ]):
            tl.main()
        
        # Verify both rows are in output
        with open(output_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert len(rows) == 2
            assert rows[0]["string_id"] == "0"
            assert rows[1]["string_id"] == "1"


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
