#!/usr/bin/env python3
"""
Unit tests for soft_qa_llm.py
Target: 80%+ coverage on soft_qa_llm.py functions
"""
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src" / "scripts"))

# Import the module under test
import soft_qa_llm as sqa


class TestUtilityFunctions:
    """Test basic utility functions."""
    
    def test_load_text(self, tmp_path):
        """Test loading text from file."""
        test_file = tmp_path / "test.txt"
        test_content = "Hello World\n多行内容"
        test_file.write_text(test_content, encoding='utf-8')
        
        result = sqa.load_text(str(test_file))
        assert result == test_content.strip()
    
    def test_load_text_empty(self, tmp_path):
        """Test loading empty text file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_text("", encoding='utf-8')
        
        result = sqa.load_text(str(test_file))
        assert result == ""
    
    def test_load_yaml_success(self, tmp_path):
        """Test loading YAML file."""
        test_file = tmp_path / "test.yaml"
        test_content = "key: value\nlist:\n  - item1\n  - item2"
        test_file.write_text(test_content, encoding='utf-8')
        
        result = sqa.load_yaml(str(test_file))
        assert result['key'] == 'value'
        assert result['list'] == ['item1', 'item2']
    
    def test_load_yaml_not_installed(self, tmp_path):
        """Test loading YAML when PyYAML not available."""
        # Temporarily disable yaml
        original_yaml = sqa.yaml
        sqa.yaml = None
        
        try:
            test_file = tmp_path / "test.yaml"
            test_file.write_text("key: value", encoding='utf-8')
            
            with pytest.raises(RuntimeError, match="PyYAML required"):
                sqa.load_yaml(str(test_file))
        finally:
            sqa.yaml = original_yaml
    
    def test_read_csv(self, tmp_path):
        """Test reading CSV file."""
        test_file = tmp_path / "test.csv"
        test_file.write_text("id,name,value\n1,Alice,100\n2,Bob,200", encoding='utf-8-sig')
        
        result = sqa.read_csv(str(test_file))
        assert len(result) == 2
        assert result[0]['id'] == '1'
        assert result[0]['name'] == 'Alice'
        assert result[1]['value'] == '200'
    
    def test_write_json(self, tmp_path):
        """Test writing JSON file."""
        test_file = tmp_path / "subdir" / "test.json"
        data = {"key": "value", "number": 42, "nested": {"a": 1}}
        
        sqa.write_json(str(test_file), data)
        
        assert test_file.exists()
        loaded = json.loads(test_file.read_text(encoding='utf-8'))
        assert loaded == data
    
    def test_append_jsonl(self, tmp_path):
        """Test appending to JSONL file."""
        test_file = tmp_path / "subdir" / "test.jsonl"
        items = [
            {"id": "1", "value": "a"},
            {"id": "2", "value": "b"},
        ]
        
        sqa.append_jsonl(str(test_file), items)
        
        assert test_file.exists()
        lines = test_file.read_text(encoding='utf-8').strip().split('\n')
        assert len(lines) == 2
        assert json.loads(lines[0])['id'] == '1'
        assert json.loads(lines[1])['value'] == 'b'
    
    def test_token_counts(self):
        """Test token counting."""
        text = "⟦PH_1⟧ and ⟦PH_2⟧ and ⟦PH_1⟧"
        result = sqa.token_counts(text)
        
        assert result['PH_1'] == 2
        assert result['PH_2'] == 1
    
    def test_token_counts_empty(self):
        """Test token counting with empty/None string."""
        assert sqa.token_counts("") == {}
        assert sqa.token_counts(None) == {}


class TestBuildSystemBatch:
    """Test system prompt building."""
    
    def test_build_system_batch_basic(self):
        """Test building system prompt with basic inputs."""
        style = "Use formal tone."
        glossary = "- 你好 → Привет\n- 再见 → Пока"
        
        result = sqa.build_system_batch(style, glossary)
        
        assert "手游本地化软质检" in result
        assert "术语一致性" in result
        assert "JSON" in result
        assert style in result
        assert glossary in result
    
    def test_build_system_batch_long_glossary(self):
        """Test that glossary is truncated in system prompt."""
        style = "Style guide"
        glossary = "- item\n" * 100  # Very long glossary
        
        result = sqa.build_system_batch(style, glossary)
        
        # Should be truncated to 1500 chars
        assert len(result.split("术语表摘要")[1].split("style_guide")[0]) < 2000


class TestBuildUserPrompt:
    """Test user prompt building."""
    
    def test_build_user_prompt_basic(self):
        """Test building user prompt from batch items."""
        items = [
            {"id": "id1", "source_text": "SRC: 你好 | TGT: Привет"},
            {"id": "id2", "source_text": "SRC: 再见 | TGT: Пока"},
        ]
        
        result = sqa.build_user_prompt(items)
        data = json.loads(result)
        
        assert len(data) == 2
        assert data[0]['string_id'] == 'id1'
        assert data[0]['source_zh'] == '你好'
        assert data[0]['target_ru'] == 'Привет'
    
    def test_build_user_prompt_malformed(self):
        """Test building user prompt with malformed source_text."""
        items = [
            {"id": "id1", "source_text": "malformed text without separator"},
        ]
        
        result = sqa.build_user_prompt(items)
        data = json.loads(result)
        
        assert data[0]['source_zh'] == "malformed text without separator"
        assert data[0]['target_ru'] == ""


class TestBuildGlossarySummary:
    """Test glossary summary building."""
    
    def test_build_glossary_summary_with_objects(self):
        """Test summary with GlossaryEntry-like objects."""
        entries = [
            Mock(term_zh="你好", term_ru="Привет", status="approved"),
            Mock(term_zh="再见", term_ru="Пока", status="approved"),
            Mock(term_zh="未批准", term_ru="Not approved", status="draft"),
        ]
        
        result = sqa.build_glossary_summary(entries)
        
        assert "你好 → Привет" in result
        assert "再见 → Пока" in result
        assert "未批准" not in result
    
    def test_build_glossary_summary_with_dicts(self):
        """Test summary with dictionary entries."""
        entries = [
            {"term_zh": "你好", "term_ru": "Привет", "status": "approved"},
            {"term_zh": "再见", "term_ru": "Пока", "status": "approved"},
            {"term_zh": "未批准", "term_ru": "Not approved", "status": "draft"},
        ]
        
        result = sqa.build_glossary_summary(entries)
        
        assert "你好 → Привет" in result
        assert "再见 → Пока" in result
        assert "未批准" not in result
    
    def test_build_glossary_summary_empty(self):
        """Test summary with no entries."""
        result = sqa.build_glossary_summary([])
        assert result == "(无)"
    
    def test_build_glossary_summary_no_approved(self):
        """Test summary with no approved entries."""
        entries = [
            {"term_zh": "未批准", "term_ru": "Not approved", "status": "draft"},
        ]
        result = sqa.build_glossary_summary(entries)
        assert result == "(无)"
    
    def test_build_glossary_summary_max_entries(self):
        """Test that summary respects max_entries limit."""
        entries = [
            {"term_zh": f"term{i}", "term_ru": f"ру{i}", "status": "approved"}
            for i in range(100)
        ]
        
        result = sqa.build_glossary_summary(entries, max_entries=10)
        lines = result.split('\n')
        
        assert len(lines) == 10
        assert "term0" in result
        assert "term9" in result
        assert "term10" not in result


class TestProcessBatchResults:
    """Test batch result processing."""
    
    def test_process_batch_results_basic(self):
        """Test processing normal batch results."""
        batch_items = [
            {
                "id": "id1",
                "issue_type": "tone",
                "severity": "minor",
                "problem": "Too formal",
                "suggestion": "Make it cuter",
                "preferred_fix_ru": "Приветик"
            }
        ]
        
        result = sqa.process_batch_results(batch_items)
        
        assert len(result) == 1
        assert result[0]['string_id'] == 'id1'
        assert result[0]['type'] == 'tone'
        assert result[0]['severity'] == 'minor'
        assert 'Приветик' in result[0]['suggested_fix']
    
    def test_process_batch_results_multiple(self):
        """Test processing multiple results."""
        batch_items = [
            {"id": "id1", "issue_type": "terminology", "severity": "major", "problem": "p1", "suggestion": "s1"},
            {"id": "id2", "issue_type": "brevity", "severity": "minor", "problem": "p2", "suggestion": "s2"},
        ]
        
        result = sqa.process_batch_results(batch_items)
        
        assert len(result) == 2
        assert result[0]['severity'] == 'major'
        assert result[1]['severity'] == 'minor'
    
    def test_process_batch_results_missing_fields(self):
        """Test processing results with missing optional fields."""
        batch_items = [
            {"id": "id1"}  # Minimal item
        ]
        
        result = sqa.process_batch_results(batch_items)
        
        assert len(result) == 1
        assert result[0]['string_id'] == 'id1'
        assert result[0]['type'] == 'issue'  # default
        assert result[0]['severity'] == 'minor'  # default


class TestLazyImports:
    """Test lazy import functionality."""
    
    def test_lazy_import_translate_llm(self):
        """Test that translate_llm imports work lazily."""
        # Reset the lazy import state
        sqa._load_glossary = None
        sqa._build_glossary_constraints = None
        sqa._GlossaryEntry = None
        
        # First call should trigger import
        load_fn, build_fn, entry_class = sqa._import_translate_llm()
        
        assert load_fn is not None
        assert build_fn is not None
        assert entry_class is not None
        
        # Second call should return cached values
        load_fn2, build_fn2, entry_class2 = sqa._import_translate_llm()
        assert load_fn is load_fn2
    
    def test_glossary_entry_proxy(self):
        """Test GlossaryEntry proxy class."""
        entry = sqa.GlossaryEntry("你好", "Привет", "approved", "note")
        
        assert entry.term_zh == "你好"
        assert entry.term_ru == "Привет"
        assert entry.status == "approved"
        assert entry.notes == "note"


class TestMainFunction:
    """Test main function with various arguments."""
    
    def test_main_no_args(self, capsys):
        """Test main with no arguments prints help and returns 1."""
        # argparse exits with 0 for --help, returns 1 for missing required args
        # Since we use nargs="?" for translated_csv, it won't raise SystemExit
        with patch.object(sys, 'argv', ['soft_qa_llm.py']):
            result = sqa.main()
        
        assert result == 1
    
    def test_main_dry_run(self, tmp_path, capsys):
        """Test main with --dry-run flag."""
        # Create test CSV
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("string_id,source_zh,target_text\n1,你好,Привет\n", encoding='utf-8-sig')
        
        # Create style guide
        style_file = tmp_path / "style.md"
        style_file.write_text("Use formal tone.", encoding='utf-8')
        
        with patch.object(sys, 'argv', [
            'soft_qa_llm.py',
            str(csv_file),
            str(style_file),
            '--dry-run'
        ]):
            result = sqa.main()
        
        assert result == 0
        captured = capsys.readouterr()
        assert "DRY-RUN MODE" in captured.out
    
    @patch('soft_qa_llm.LLMClient')
    def test_main_with_llm_success(self, mock_llm_class, tmp_path, capsys):
        """Test main with successful LLM call."""
        # Setup mock
        mock_llm = MagicMock()
        mock_llm.default_model = "test-model"
        mock_llm_class.return_value = mock_llm
        
        # Create test CSV
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("string_id,source_zh,target_text\n1,你好,Привет\n", encoding='utf-8-sig')
        
        # Create style guide
        style_file = tmp_path / "style.md"
        style_file.write_text("Use formal tone.", encoding='utf-8')
        
        # Create output directory
        out_report = tmp_path / "report.json"
        out_tasks = tmp_path / "tasks.jsonl"
        
        with patch.object(sys, 'argv', [
            'soft_qa_llm.py',
            str(csv_file),
            str(style_file),
            '--out_report', str(out_report),
            '--out_tasks', str(out_tasks),
        ]):
            # Mock batch_llm_call
            with patch('soft_qa_llm.batch_llm_call') as mock_batch:
                mock_batch.return_value = [
                    {"id": "1", "issue_type": "tone", "severity": "minor", 
                     "problem": "test", "suggestion": "fix", "preferred_fix_ru": "fixed"}
                ]
                result = sqa.main()
        
        assert result == 0
        assert out_report.exists()
        report = json.loads(out_report.read_text())
        assert report['has_findings'] is True
        assert report['summary']['minor'] == 1


class TestIntegrationEdgeCases:
    """Test edge cases and integration scenarios."""
    
    def test_empty_csv(self, tmp_path, capsys):
        """Test handling of empty CSV."""
        csv_file = tmp_path / "empty.csv"
        csv_file.write_text("string_id,source_zh,target_text\n", encoding='utf-8-sig')
        
        style_file = tmp_path / "style.md"
        style_file.write_text("Style", encoding='utf-8')
        
        with patch.object(sys, 'argv', [
            'soft_qa_llm.py',
            str(csv_file),
            str(style_file),
            '--dry-run'
        ]):
            result = sqa.main()
        
        assert result == 0
        captured = capsys.readouterr()
        assert "Loaded 0 rows" in captured.out
    
    def test_csv_no_target_text(self, tmp_path, capsys):
        """Test handling of CSV with no target translations."""
        csv_file = tmp_path / "notrans.csv"
        csv_file.write_text("string_id,source_zh,target_text\n1,你好,\n", encoding='utf-8-sig')
        
        style_file = tmp_path / "style.md"
        style_file.write_text("Style", encoding='utf-8')
        
        with patch.object(sys, 'argv', [
            'soft_qa_llm.py',
            str(csv_file),
            str(style_file),
            '--dry-run'
        ]):
            result = sqa.main()
        
        assert result == 0
        captured = capsys.readouterr()
        assert "Rows with translations: 0" in captured.out


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
