#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for translate_llm.py

Tests the core utility functions without requiring runtime_adapter.
Uses direct imports (not subprocess) for pytest compatibility.
"""

import sys
import os
import json
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add src/scripts to path for import
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "scripts"))

import translate_llm as tl


class TestGlossaryEntry:
    """Tests for GlossaryEntry dataclass."""
    
    def test_glossary_entry_creation(self):
        """Test creating a GlossaryEntry."""
        entry = tl.GlossaryEntry(
            term_zh="测试",
            term_ru="тест",
            status="approved",
            notes="test note"
        )
        assert entry.term_zh == "测试"
        assert entry.term_ru == "тест"
        assert entry.status == "approved"
        assert entry.notes == "test note"
    
    def test_glossary_entry_defaults(self):
        """Test GlossaryEntry with default values."""
        entry = tl.GlossaryEntry(
            term_zh="测试",
            term_ru="тест",
            status="approved"
        )
        assert entry.notes == ""


class TestBuildGlossaryConstraints:
    """Tests for build_glossary_constraints function."""
    
    def test_empty_glossary(self):
        """Test with empty glossary."""
        result = tl.build_glossary_constraints([], "some text")
        assert result == {}
    
    def test_no_matching_terms(self):
        """Test when no terms match the source."""
        glossary = [
            tl.GlossaryEntry("不存在", "не существует", "approved"),
        ]
        result = tl.build_glossary_constraints(glossary, "测试文本")
        assert result == {}
    
    def test_matching_approved_term(self):
        """Test matching approved term."""
        glossary = [
            tl.GlossaryEntry("测试", "тест", "approved"),
        ]
        result = tl.build_glossary_constraints(glossary, "这是一个测试文本")
        assert result == {"测试": "тест"}
    
    def test_non_approved_term_excluded(self):
        """Test that non-approved terms are excluded."""
        glossary = [
            tl.GlossaryEntry("测试", "тест", "pending"),
            tl.GlossaryEntry("文本", "текст", "approved"),
        ]
        result = tl.build_glossary_constraints(glossary, "测试文本")
        assert result == {"文本": "текст"}
    
    def test_multiple_matches(self):
        """Test multiple matching terms."""
        glossary = [
            tl.GlossaryEntry("测试", "тест", "approved"),
            tl.GlossaryEntry("文本", "текст", "approved"),
        ]
        result = tl.build_glossary_constraints(glossary, "测试文本")
        assert result == {"测试": "тест", "文本": "текст"}
    
    def test_partial_match(self):
        """Test partial term matching."""
        glossary = [
            tl.GlossaryEntry("测试", "тест", "approved"),
            tl.GlossaryEntry("测试用例", "тестовый случай", "approved"),
        ]
        result = tl.build_glossary_constraints(glossary, "这是一个测试用例")
        # Both should match since "测试" is in "测试用例"
        assert "测试" in result
        assert "测试用例" in result


class TestLoadText:
    """Tests for load_text function."""
    
    def test_load_existing_file(self, tmp_path):
        """Test loading an existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello World", encoding="utf-8")
        result = tl.load_text(str(test_file))
        assert result == "Hello World"
    
    def test_load_nonexistent_file(self):
        """Test loading a non-existent file."""
        result = tl.load_text("/nonexistent/path/file.txt")
        assert result == ""
    
    def test_load_strips_whitespace(self, tmp_path):
        """Test that content is stripped of whitespace."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("  Hello World  \n\n", encoding="utf-8")
        result = tl.load_text(str(test_file))
        assert result == "Hello World"


class TestLoadGlossary:
    """Tests for load_glossary function."""

    def test_no_path(self):
        """Test with no path provided."""
        entries, hash_val = tl.load_glossary("")
        assert entries == []
        assert hash_val is None

    def test_nonexistent_path(self):
        """Test with non-existent path."""
        entries, hash_val = tl.load_glossary("/nonexistent/glossary.yaml")
        assert entries == []
        assert hash_val is None

    def test_load_glossary_success(self, tmp_path):
        """Test loading glossary with mocked YAML (success case)."""
        glossary_file = tmp_path / "glossary.yaml"
        # Create an empty file (mock will handle content)
        glossary_file.write_text("", encoding="utf-8")

        mock_yaml_data = {
            "meta": {"compiled_hash": "test_hash_123"},
            "entries": [
                {"term_zh": "测试", "term_ru": "тест", "status": "approved"},
                {"term_zh": "文本", "term_ru": "текст", "status": "approved"},
                {"term_zh": "待定", "term_ru": "ожидается", "status": "pending"},
            ]
        }

        with patch.object(tl.yaml, 'safe_load', return_value=mock_yaml_data):
            entries, hash_val = tl.load_glossary(str(glossary_file))

        assert len(entries) == 2  # Only approved entries
        assert hash_val == "test_hash_123"
        assert entries[0].term_zh == "测试"
        assert entries[0].term_ru == "тест"
        assert entries[0].status == "approved"
        assert entries[1].term_zh == "文本"
        assert entries[1].term_ru == "текст"

    def test_valid_yaml_glossary(self, tmp_path):
        """Test loading a valid YAML glossary."""
        glossary_file = tmp_path / "glossary.yaml"
        glossary_content = """
meta:
  compiled_hash: "abc123"
entries:
  - term_zh: "测试"
    term_ru: "тест"
    status: "approved"
  - term_zh: "文本"
    term_ru: "текст"
    status: "approved"
  - term_zh: "待定"
    term_ru: "ожидается"
    status: "pending"
"""
        glossary_file.write_text(glossary_content, encoding="utf-8")
        entries, hash_val = tl.load_glossary(str(glossary_file))
        
        assert len(entries) == 2  # Only approved entries
        assert hash_val == "abc123"
        assert entries[0].term_zh == "测试"
        assert entries[0].term_ru == "тест"
    
    def test_yaml_not_available(self, tmp_path):
        """Test when yaml module is not available."""
        with patch.object(tl, 'yaml', None):
            entries, hash_val = tl.load_glossary(str(tmp_path / "test.yaml"))
            assert entries == []
            assert hash_val is None


class TestBuildGlossarySummary:
    """Tests for build_glossary_summary function."""
    
    def test_empty_glossary(self):
        """Test with empty glossary."""
        result = tl.build_glossary_summary([])
        assert result == "(无)"
    
    def test_single_entry(self):
        """Test with single entry."""
        entries = [tl.GlossaryEntry("测试", "тест", "approved")]
        result = tl.build_glossary_summary(entries)
        assert "测试" in result
        assert "тест" in result
        assert "→" in result
    
    def test_multiple_entries(self):
        """Test with multiple entries."""
        entries = [
            tl.GlossaryEntry("测试", "тест", "approved"),
            tl.GlossaryEntry("文本", "текст", "approved"),
        ]
        result = tl.build_glossary_summary(entries)
        lines = result.split("\n")
        assert len(lines) == 2
        assert "- " in lines[0]
    
    def test_limit_to_50_entries(self):
        """Test that summary is limited to 50 entries."""
        entries = [tl.GlossaryEntry(f"term{i}", f"ru{i}", "approved") for i in range(60)]
        result = tl.build_glossary_summary(entries)
        lines = [l for l in result.split("\n") if l.strip()]
        assert len(lines) == 50


class TestTokensSignature:
    """Tests for tokens_signature function."""
    
    def test_empty_text(self):
        """Test with empty text."""
        result = tl.tokens_signature("")
        assert result == {}
    
    def test_no_tokens(self):
        """Test text with no tokens."""
        result = tl.tokens_signature("普通文本没有标记")
        assert result == {}
    
    def test_single_ph_token(self):
        """Test with single PH token."""
        result = tl.tokens_signature("文本⟦PH_0⟧结束")
        assert result == {"PH_0": 1}
    
    def test_single_tag_token(self):
        """Test with single TAG token."""
        result = tl.tokens_signature("文本⟦TAG_5⟧结束")
        assert result == {"TAG_5": 1}
    
    def test_multiple_tokens(self):
        """Test with multiple different tokens."""
        result = tl.tokens_signature("⟦PH_0⟧和⟦PH_1⟧以及⟦TAG_0⟧")
        assert result == {"PH_0": 1, "PH_1": 1, "TAG_0": 1}
    
    def test_duplicate_tokens(self):
        """Test with duplicate tokens."""
        result = tl.tokens_signature("⟦PH_0⟧重复⟦PH_0⟧两次")
        assert result == {"PH_0": 2}
    
    def test_none_text(self):
        """Test with None text."""
        result = tl.tokens_signature(None)
        assert result == {}


class TestValidateTranslation:
    """Tests for validate_translation function."""
    
    def test_valid_translation(self):
        """Test a valid translation."""
        ok, err = tl.validate_translation(
            "原文⟦PH_0⟧结束",
            "перевод⟦PH_0⟧конец"
        )
        assert ok is True
        assert err == "ok"
    
    def test_token_mismatch_missing(self):
        """Test when token is missing in translation."""
        ok, err = tl.validate_translation(
            "原文⟦PH_0⟧结束",
            "перевод конец"
        )
        assert ok is False
        assert err == "token_mismatch"
    
    def test_token_mismatch_extra(self):
        """Test when extra token in translation."""
        ok, err = tl.validate_translation(
            "原文结束",
            "перевод⟦PH_0⟧конец"
        )
        assert ok is False
        assert err == "token_mismatch"
    
    def test_cjk_remaining(self):
        """Test when CJK characters remain in translation."""
        ok, err = tl.validate_translation(
            "原文⟦PH_0⟧",
            "перевод⟦PH_0⟧中文"
        )
        assert ok is False
        assert err == "cjk_remaining"
    
    def test_empty_translation_with_tokens(self):
        """Test when translation is empty but source has tokens - token mismatch first."""
        ok, err = tl.validate_translation(
            "原文⟦PH_0⟧",
            ""
        )
        assert ok is False
        # Token mismatch is detected before empty check
        assert err == "token_mismatch"
    
    def test_empty_translation_no_tokens(self):
        """Test when both source and translation are empty."""
        ok, err = tl.validate_translation("", "")
        # Both empty is considered valid
        assert ok is True
        assert err == "ok"
    
    def test_whitespace_translation_with_tokens(self):
        """Test whitespace translation when source has tokens."""
        ok, err = tl.validate_translation(
            "原文⟦PH_0⟧",
            "   "
        )
        assert ok is False
        # Token mismatch detected before empty check
        assert err == "token_mismatch"
    
    def test_empty_source_allowed(self):
        """Test when source is empty."""
        ok, err = tl.validate_translation("", "")
        # Empty source, empty target should be valid
        assert ok is True
        assert err == "ok"


class TestBuildSystemPromptFactory:
    """Tests for build_system_prompt_factory function."""
    
    def test_factory_returns_function(self):
        """Test that factory returns a callable."""
        factory = tl.build_system_prompt_factory("style", "glossary")
        assert callable(factory)
    
    def test_system_prompt_content(self):
        """Test system prompt contains expected content."""
        factory = tl.build_system_prompt_factory("style guide content", "glossary summary")
        rows = [{"string_id": "test1", "max_length_target": 100}]
        prompt = factory(rows)
        
        assert '你是严谨的手游本地化译者' in prompt
        assert 'Output Contract v6' in prompt
        assert 'style guide content' in prompt
        assert 'glossary summary' in prompt
    
    def test_system_prompt_with_constraints(self):
        """Test system prompt includes length constraints."""
        factory = tl.build_system_prompt_factory("style", "glossary")
        rows = [
            {"string_id": "id1", "max_length_target": 50},
            {"string_id": "id2", "max_length_target": 100},
        ]
        prompt = factory(rows)
        
        assert 'Length Constraints' in prompt
        assert 'Row id1: max 50 chars' in prompt
        assert 'Row id2: max 100 chars' in prompt
    
    def test_system_prompt_no_constraints(self):
        """Test system prompt without length constraints."""
        factory = tl.build_system_prompt_factory("style", "glossary")
        rows = [{"string_id": "id1"}]
        prompt = factory(rows)
        
        assert 'Length Constraints' not in prompt


class TestBuildUserPrompt:
    """Tests for build_user_prompt function."""
    
    def test_single_row(self):
        """Test with single row."""
        rows = [{"id": "test1", "source_text": "原文"}]
        result = tl.build_user_prompt(rows)
        
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["id"] == "test1"
    
    def test_multiple_rows(self):
        """Test with multiple rows."""
        rows = [
            {"id": "test1", "source_text": "原文1"},
            {"id": "test2", "source_text": "原文2"},
        ]
        result = tl.build_user_prompt(rows)
        
        parsed = json.loads(result)
        assert len(parsed) == 2
    
    def test_valid_json_output(self):
        """Test that output is valid JSON."""
        rows = [{"id": "test", "source_text": "测试⟦PH_0⟧"}]
        result = tl.build_user_prompt(rows)
        
        # Should not raise
        parsed = json.loads(result)
        assert isinstance(parsed, list)


class TestCheckpointFunctions:
    """Tests for checkpoint load/save functions."""
    
    def test_load_checkpoint_nonexistent(self, tmp_path):
        """Test loading non-existent checkpoint."""
        result = tl.load_checkpoint(str(tmp_path / "nonexistent.json"))
        assert result == set()
    
    def test_load_checkpoint_valid(self, tmp_path):
        """Test loading valid checkpoint."""
        checkpoint_file = tmp_path / "checkpoint.json"
        checkpoint_file.write_text(
            json.dumps({"done_ids": ["id1", "id2", "id3"]}),
            encoding="utf-8"
        )
        result = tl.load_checkpoint(str(checkpoint_file))
        assert result == {"id1", "id2", "id3"}
    
    def test_load_checkpoint_invalid_json(self, tmp_path):
        """Test loading invalid JSON."""
        checkpoint_file = tmp_path / "checkpoint.json"
        checkpoint_file.write_text("invalid json", encoding="utf-8")
        result = tl.load_checkpoint(str(checkpoint_file))
        assert result == set()
    
    def test_save_checkpoint(self, tmp_path):
        """Test saving checkpoint."""
        checkpoint_file = tmp_path / "checkpoint.json"
        tl.save_checkpoint(str(checkpoint_file), {"id1", "id2"})
        
        content = json.loads(checkpoint_file.read_text(encoding="utf-8"))
        assert set(content["done_ids"]) == {"id1", "id2"}
    
    def test_save_checkpoint_creates_directory(self, tmp_path):
        """Test that save_checkpoint creates parent directories."""
        checkpoint_file = tmp_path / "subdir" / "checkpoint.json"
        tl.save_checkpoint(str(checkpoint_file), {"id1"})
        
        assert checkpoint_file.exists()


class TestRuntimeAdapterAvailability:
    """Tests for runtime adapter availability flag."""
    
    def test_runtime_adapter_flag_exists(self):
        """Test that the availability flag exists."""
        assert hasattr(tl, '_runtime_adapter_available')
        assert isinstance(tl._runtime_adapter_available, bool)
    
    def test_imports_are_none_when_unavailable(self):
        """Test that imports are None when runtime_adapter unavailable."""
        # These should exist (either imported or set to None)
        assert hasattr(tl, 'LLMClient')
        assert hasattr(tl, 'LLMError')
        assert hasattr(tl, 'batch_llm_call')
        assert hasattr(tl, 'log_llm_progress')


class TestMainFunction:
    """Tests for main() function behavior."""
    
    def test_main_exits_without_runtime_adapter(self):
        """Test that main exits when runtime_adapter is not available."""
        with patch.object(tl, '_runtime_adapter_available', False):
            with patch.object(sys, 'exit') as mock_exit:
                # Prevent argparse from accessing sys.argv
                with patch.object(tl, 'argparse'):
                    tl.main()
                    mock_exit.assert_called_once_with(1)


# Integration-style tests that verify the module can be imported correctly
class TestModuleImport:
    """Tests for module import behavior."""
    
    def test_module_imports_without_exit(self):
        """Test that importing the module doesn't call sys.exit."""
        # This test verifies that the module-level import handling
        # doesn't call sys.exit when runtime_adapter is missing
        
        # The fact that this test file runs at all proves the module
        # can be imported without sys.exit being called
        assert tl is not None
    
    def test_regex_patterns_exist(self):
        """Test that regex patterns are defined."""
        assert tl.TOKEN_RE is not None
        assert tl.CJK_RE is not None
        
        # Test patterns work
        assert tl.TOKEN_RE.search("⟦PH_0⟧") is not None
        assert tl.CJK_RE.search("中文") is not None
        assert tl.CJK_RE.search("English") is None