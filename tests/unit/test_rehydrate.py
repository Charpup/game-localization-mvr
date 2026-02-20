#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test rehydrate_export.py using direct imports for coverage measurement.

Refactored from subprocess-based tests to direct function calls.
All file operations use explicit UTF-8 encoding for Windows compatibility.
"""

import csv
import json
import sys
import shutil
import pytest
from pathlib import Path

# Add src to path for direct imports (must be before importing src modules)
src_path = str(Path(__file__).parent.parent.parent / "src")
if src_path not in sys.path:
    sys.path.insert(0, src_path)

# Also add parent to path for proper src.scripts import
parent_path = str(Path(__file__).parent.parent.parent)
if parent_path not in sys.path:
    sys.path.insert(0, parent_path)

# Import using the path that coverage expects
from src.scripts.rehydrate_export import RehydrateExporter


# Fixtures directory path
FIXTURES_DIR = Path(__file__).parent.parent.parent / "data" / "fixtures"


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create a temporary directory for test outputs."""
    return tmp_path


@pytest.fixture
def valid_translated_csv():
    """Path to valid translated CSV fixture."""
    return FIXTURES_DIR / "translated_valid.csv"


@pytest.fixture
def invalid_translated_csv():
    """Path to invalid translated CSV fixture (contains unknown token)."""
    return FIXTURES_DIR / "translated_invalid.csv"


@pytest.fixture
def placeholder_map_path():
    """Path to placeholder map JSON fixture."""
    return FIXTURES_DIR / "placeholder_map.json"


@pytest.fixture
def placeholder_map_data():
    """Load placeholder map data as dict."""
    with open(FIXTURES_DIR / "placeholder_map.json", 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get('mappings', data)


class TestRehydrateExporter:
    """Test RehydrateExporter class directly."""
    
    def test_initialization(self, temp_output_dir, valid_translated_csv, placeholder_map_path):
        """Test RehydrateExporter initialization."""
        output_path = temp_output_dir / "final.csv"
        
        exporter = RehydrateExporter(
            translated_csv=str(valid_translated_csv),
            placeholder_map=str(placeholder_map_path),
            final_csv=str(output_path),
            overwrite_mode=False
        )
        
        assert exporter.translated_csv == valid_translated_csv
        assert exporter.placeholder_map_path == placeholder_map_path
        assert exporter.final_csv == output_path
        assert exporter.overwrite_mode is False
        assert exporter.errors == []
    
    def test_load_placeholder_map_v2_format(self, temp_output_dir, valid_translated_csv, placeholder_map_path):
        """Test loading placeholder map in v2.0 format (with metadata and mappings)."""
        output_path = temp_output_dir / "final.csv"
        
        exporter = RehydrateExporter(
            translated_csv=str(valid_translated_csv),
            placeholder_map=str(placeholder_map_path),
            final_csv=str(output_path)
        )
        
        result = exporter.load_placeholder_map()
        assert result is True
        assert exporter.map_version == "2.0"
        assert len(exporter.placeholder_map) == 5
        assert exporter.placeholder_map["PH_0"] == "{0}"
        assert exporter.placeholder_map["PH_1"] == "{level}"
    
    def test_load_placeholder_map_v1_format(self, temp_output_dir, valid_translated_csv):
        """Test loading placeholder map in v1.0 format (direct dict)."""
        # Create v1 format map
        v1_map = {"PH_0": "{0}", "PH_1": "{level}"}
        v1_map_path = temp_output_dir / "v1_map.json"
        with open(v1_map_path, 'w', encoding='utf-8') as f:
            json.dump(v1_map, f)
        
        output_path = temp_output_dir / "final.csv"
        
        exporter = RehydrateExporter(
            translated_csv=str(valid_translated_csv),
            placeholder_map=str(v1_map_path),
            final_csv=str(output_path)
        )
        
        result = exporter.load_placeholder_map()
        assert result is True
        assert exporter.map_version == "1.0"
        assert len(exporter.placeholder_map) == 2
    
    def test_load_placeholder_map_not_found(self, temp_output_dir, valid_translated_csv):
        """Test loading non-existent placeholder map."""
        output_path = temp_output_dir / "final.csv"
        
        exporter = RehydrateExporter(
            translated_csv=str(valid_translated_csv),
            placeholder_map=str(temp_output_dir / "nonexistent.json"),
            final_csv=str(output_path)
        )
        
        result = exporter.load_placeholder_map()
        assert result is False
    
    def test_extract_tokens(self, temp_output_dir, valid_translated_csv, placeholder_map_path):
        """Test token extraction from text."""
        output_path = temp_output_dir / "final.csv"
        
        exporter = RehydrateExporter(
            translated_csv=str(valid_translated_csv),
            placeholder_map=str(placeholder_map_path),
            final_csv=str(output_path)
        )
        
        # Test extracting various tokens
        text1 = "Welcome ⟦PH_0⟧ player"
        tokens1 = exporter.extract_tokens(text1)
        assert "PH_0" in tokens1
        
        text2 = "⟦TAG_0⟧Colored text⟦TAG_1⟧"
        tokens2 = exporter.extract_tokens(text2)
        assert "TAG_0" in tokens2
        assert "TAG_1" in tokens2
        
        text3 = "No tokens here"
        tokens3 = exporter.extract_tokens(text3)
        assert len(tokens3) == 0
        
        text4 = "Multiple ⟦PH_0⟧ and ⟦PH_1⟧ tokens"
        tokens4 = exporter.extract_tokens(text4)
        assert "PH_0" in tokens4
        assert "PH_1" in tokens4
    
    def test_rehydrate_text_success(self, temp_output_dir, valid_translated_csv, placeholder_map_path, placeholder_map_data):
        """Test successful text rehydration."""
        output_path = temp_output_dir / "final.csv"
        
        exporter = RehydrateExporter(
            translated_csv=str(valid_translated_csv),
            placeholder_map=str(placeholder_map_path),
            final_csv=str(output_path)
        )
        
        exporter.placeholder_map = placeholder_map_data
        
        # Test C# numbered placeholder
        result = exporter.rehydrate_text("Welcome ⟦PH_0⟧ player", "welcome_msg", 1)
        assert result == "Welcome {0} player"
        assert exporter.tokens_restored == 1
        
        # Test C# named placeholder
        result = exporter.rehydrate_text("Level ⟦PH_1⟧ reached", "level_up", 2)
        assert result == "Level {level} reached"
        assert exporter.tokens_restored == 2
        
        # Test Unity color tags
        result = exporter.rehydrate_text("⟦TAG_0⟧Red text⟦TAG_1⟧", "color_text", 3)
        assert result == "<color=#FF00FF>Red text</color>"
        assert exporter.tokens_restored == 4
        
        # Test printf placeholder
        result = exporter.rehydrate_text("Got ⟦PH_2⟧ gold", "printf_test", 4)
        assert result == "Got %d gold"
        assert exporter.tokens_restored == 5
    
    def test_rehydrate_text_unknown_token(self, temp_output_dir, valid_translated_csv, placeholder_map_path, placeholder_map_data):
        """Test rehydration with unknown token - should record error."""
        output_path = temp_output_dir / "final.csv"
        
        exporter = RehydrateExporter(
            translated_csv=str(valid_translated_csv),
            placeholder_map=str(placeholder_map_path),
            final_csv=str(output_path)
        )
        
        exporter.placeholder_map = placeholder_map_data
        
        result = exporter.rehydrate_text("Test with ⟦PH_99⟧ unknown", "test_id", 1)
        assert result is None
        assert len(exporter.errors) == 1
        assert "PH_99" in exporter.errors[0]
        assert "Unknown token" in exporter.errors[0]
    
    def test_rehydrate_text_empty(self, temp_output_dir, valid_translated_csv, placeholder_map_path, placeholder_map_data):
        """Test rehydration with empty text."""
        output_path = temp_output_dir / "final.csv"
        
        exporter = RehydrateExporter(
            translated_csv=str(valid_translated_csv),
            placeholder_map=str(placeholder_map_path),
            final_csv=str(output_path)
        )
        
        exporter.placeholder_map = placeholder_map_data
        
        result = exporter.rehydrate_text("", "empty_test", 1)
        assert result == ""
        
        result = exporter.rehydrate_text(None, "none_test", 2)
        assert result is None
    
    def test_process_csv_add_column_mode(self, temp_output_dir, valid_translated_csv, placeholder_map_path, placeholder_map_data):
        """Test processing CSV with add-column mode (default)."""
        output_path = temp_output_dir / "final.csv"
        
        exporter = RehydrateExporter(
            translated_csv=str(valid_translated_csv),
            placeholder_map=str(placeholder_map_path),
            final_csv=str(output_path),
            overwrite_mode=False
        )
        
        exporter.placeholder_map = placeholder_map_data
        
        result = exporter.process_csv()
        assert result is True
        
        # Verify output file exists
        assert output_path.exists()
        
        # Verify content
        with open(output_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 4
        
        # Check rehydrated_text column exists
        assert 'rehydrated_text' in rows[0]
        
        # Verify tokens were replaced
        for row in rows:
            rehydrated = row['rehydrated_text']
            assert '⟦' not in rehydrated
            assert '⟧' not in rehydrated
    
    def test_process_csv_overwrite_mode(self, temp_output_dir, valid_translated_csv, placeholder_map_path, placeholder_map_data):
        """Test processing CSV with overwrite mode."""
        output_path = temp_output_dir / "final.csv"
        
        exporter = RehydrateExporter(
            translated_csv=str(valid_translated_csv),
            placeholder_map=str(placeholder_map_path),
            final_csv=str(output_path),
            overwrite_mode=True
        )
        
        exporter.placeholder_map = placeholder_map_data
        
        result = exporter.process_csv()
        assert result is True
        
        # Verify output file exists
        assert output_path.exists()
        
        # Verify content
        with open(output_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        # In overwrite mode, target_text should be modified
        welcome_row = next(r for r in rows if r['string_id'] == 'welcome_msg')
        assert '{0}' in welcome_row['target_text']
        assert '⟦' not in welcome_row['target_text']
    
    def test_process_csv_unknown_token_error(self, temp_output_dir, invalid_translated_csv, placeholder_map_path, placeholder_map_data):
        """Test processing CSV with unknown token - should fail."""
        output_path = temp_output_dir / "final.csv"
        
        exporter = RehydrateExporter(
            translated_csv=str(invalid_translated_csv),
            placeholder_map=str(placeholder_map_path),
            final_csv=str(output_path)
        )
        
        exporter.placeholder_map = placeholder_map_data
        
        result = exporter.process_csv()
        assert result is False
        assert len(exporter.errors) == 1
        assert "PH_99" in exporter.errors[0]
    
    def test_write_final_csv(self, temp_output_dir, placeholder_map_data):
        """Test writing final CSV output."""
        output_path = temp_output_dir / "final.csv"
        
        exporter = RehydrateExporter(
            translated_csv="dummy.csv",
            placeholder_map="dummy.json",
            final_csv=str(output_path)
        )
        
        # Test data
        rows = [
            {'string_id': 'test1', 'source_zh': '测试1', 'target_text': 'Test 1', 'rehydrated_text': 'Test 1'},
            {'string_id': 'test2', 'source_zh': '测试2', 'target_text': 'Test 2', 'rehydrated_text': 'Test 2'}
        ]
        headers = ['string_id', 'source_zh', 'target_text']
        
        result = exporter.write_final_csv(rows, headers, 'target_text')
        assert result is True
        
        # Verify file content
        with open(output_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            written_rows = list(reader)
        
        assert len(written_rows) == 2
        assert written_rows[0]['string_id'] == 'test1'
    
    def test_run_full_workflow(self, temp_output_dir, valid_translated_csv, placeholder_map_path):
        """Test complete run workflow."""
        output_path = temp_output_dir / "final.csv"
        
        exporter = RehydrateExporter(
            translated_csv=str(valid_translated_csv),
            placeholder_map=str(placeholder_map_path),
            final_csv=str(output_path)
        )
        
        result = exporter.run()
        assert result is True
        
        # Verify output file exists and has content
        assert output_path.exists()
        
        with open(output_path, 'r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        
        assert len(rows) == 4
        
        # Verify all placeholders restored
        welcome_row = next(r for r in rows if r['string_id'] == 'welcome_msg')
        assert '{0}' in welcome_row['rehydrated_text']
        
        level_row = next(r for r in rows if r['string_id'] == 'level_up')
        assert '{level}' in level_row['rehydrated_text']
        
        color_row = next(r for r in rows if r['string_id'] == 'color_text')
        assert '<color=#FF00FF>' in color_row['rehydrated_text']
        
        printf_row = next(r for r in rows if r['string_id'] == 'printf_test')
        assert '%d' in printf_row['rehydrated_text']
        
        # Verify stats
        assert exporter.total_rows == 4
        assert exporter.tokens_restored > 0
    
    def test_run_with_error(self, temp_output_dir, invalid_translated_csv, placeholder_map_path):
        """Test complete run workflow with error."""
        output_path = temp_output_dir / "final.csv"
        
        exporter = RehydrateExporter(
            translated_csv=str(invalid_translated_csv),
            placeholder_map=str(placeholder_map_path),
            final_csv=str(output_path)
        )
        
        result = exporter.run()
        assert result is False


def test_rehydrate_valid(temp_output_dir, valid_translated_csv, placeholder_map_path):
    """Integration test: rehydrate with valid translations."""
    output_path = temp_output_dir / "final.csv"
    
    exporter = RehydrateExporter(
        translated_csv=str(valid_translated_csv),
        placeholder_map=str(placeholder_map_path),
        final_csv=str(output_path)
    )
    
    result = exporter.run()
    assert result is True
    
    # Load output with BOM handling
    with open(output_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Verify tokens were replaced with original placeholders
    test_cases = [
        {
            'string_id': 'welcome_msg',
            'expected_contains': '{0}',
            'description': 'C# numbered placeholder'
        },
        {
            'string_id': 'level_up',
            'expected_contains': '{level}',
            'description': 'C# named placeholder'
        },
        {
            'string_id': 'color_text',
            'expected_contains': '<color=#FF00FF>',
            'description': 'Unity color tag'
        },
        {
            'string_id': 'printf_test',
            'expected_contains': '%d',
            'description': 'Printf placeholder'
        }
    ]
    
    for test in test_cases:
        string_id = test['string_id']
        expected = test['expected_contains']
        
        row = next((r for r in rows if r.get('string_id') == string_id), None)
        assert row is not None, f"Row with string_id '{string_id}' not found"
        
        rehydrated = row.get('rehydrated_text', '')
        
        # Check token was replaced
        assert '⟦' not in rehydrated, f"Tokens still present in {string_id}"
        assert '⟧' not in rehydrated, f"Tokens still present in {string_id}"
        
        # Check original placeholder restored
        assert expected in rehydrated, f"Expected '{expected}' not found in {string_id}: {rehydrated}"


def test_rehydrate_unknown_token(temp_output_dir, invalid_translated_csv, placeholder_map_path):
    """Integration test: rehydrate correctly fails on unknown tokens."""
    output_path = temp_output_dir / "final.csv"
    
    exporter = RehydrateExporter(
        translated_csv=str(invalid_translated_csv),
        placeholder_map=str(placeholder_map_path),
        final_csv=str(output_path)
    )
    
    result = exporter.run()
    
    # Should fail with error
    assert result is False
    assert len(exporter.errors) > 0
    assert any("PH_99" in err for err in exporter.errors)


def test_rehydrate_empty_input(temp_output_dir, placeholder_map_path, placeholder_map_data):
    """Integration test: rehydrate with empty/minimal input."""
    # Create minimal CSV
    minimal_csv = temp_output_dir / "minimal.csv"
    with open(minimal_csv, 'w', encoding='utf-8', newline='') as f:
        f.write("string_id,source_zh,tokenized_zh,target_text\n")
        f.write("simple,你好,你好,Hello\n")
    
    output_path = temp_output_dir / "final.csv"
    
    exporter = RehydrateExporter(
        translated_csv=str(minimal_csv),
        placeholder_map=str(placeholder_map_path),
        final_csv=str(output_path)
    )
    
    exporter.placeholder_map = placeholder_map_data
    
    result = exporter.process_csv()
    assert result is True
    
    # Verify output
    with open(output_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    assert len(rows) == 1
    assert rows[0]['string_id'] == 'simple'
    assert rows[0]['rehydrated_text'] == 'Hello'


def test_rehydrate_various_target_fields(temp_output_dir, placeholder_map_path, placeholder_map_data):
    """Test rehydration with different target field names."""
    # Test with 'translated_text' field
    csv_with_translated = temp_output_dir / "with_translated.csv"
    with open(csv_with_translated, 'w', encoding='utf-8', newline='') as f:
        f.write("string_id,source_zh,tokenized_zh,translated_text\n")
        f.write("test1,你好,你好⟦PH_0⟧,Hello {0}\n")
    
    output_path = temp_output_dir / "final.csv"
    
    exporter = RehydrateExporter(
        translated_csv=str(csv_with_translated),
        placeholder_map=str(placeholder_map_path),
        final_csv=str(output_path)
    )
    
    exporter.placeholder_map = placeholder_map_data
    
    result = exporter.process_csv()
    assert result is True
    
    with open(output_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    assert len(rows) == 1
    assert '{0}' in rows[0]['rehydrated_text']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
