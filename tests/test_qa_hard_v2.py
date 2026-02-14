#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Unit Tests for qa_hard.py
Target: 90%+ test coverage

Test Categories:
    - Placeholder Map Loading
    - Schema Loading (v1.0 & v2.0)
    - Forbidden Patterns Loading
    - Token Extraction
    - Token Mismatch Checking
    - Tag Balance Checking (Paired & Count-based)
    - Forbidden Pattern Detection
    - New Placeholder Detection
    - CSV Validation
    - Length Overflow Checking
    - Report Generation
    - Main Run Flow
"""

import sys
import os
import json
import csv
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, mock_open, MagicMock
import pytest

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from qa_hard import QAHardValidator


class TestPlaceholderMapLoading:
    """Tests for load_placeholder_map() method"""
    
    def test_load_valid_placeholder_map(self, tmp_path):
        """Test loading valid placeholder map JSON"""
        placeholder_file = tmp_path / "placeholder_map.json"
        placeholder_file.write_text(json.dumps({
            "mappings": {
                "PH_001": "<player>",
                "PH_002": "<npc>",
                "TAG_001": "<b>",
                "TAG_002": "</b>"
            }
        }))
        
        validator = QAHardValidator(
            "dummy.csv", str(placeholder_file), "dummy.yaml", "dummy.txt", "report.json"
        )
        
        result = validator.load_placeholder_map()
        
        assert result is True
        assert len(validator.placeholder_map) == 4
        assert validator.placeholder_map["PH_001"] == "<player>"
    
    def test_load_placeholder_map_missing_mappings_key(self, tmp_path):
        """Test loading placeholder map without 'mappings' key"""
        placeholder_file = tmp_path / "placeholder_map.json"
        placeholder_file.write_text(json.dumps({}))
        
        validator = QAHardValidator(
            "dummy.csv", str(placeholder_file), "dummy.yaml", "dummy.txt", "report.json"
        )
        
        result = validator.load_placeholder_map()
        
        assert result is True
        assert validator.placeholder_map == {}
    
    def test_load_placeholder_map_file_not_found(self):
        """Test handling missing placeholder map file"""
        validator = QAHardValidator(
            "dummy.csv", "nonexistent.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        result = validator.load_placeholder_map()
        
        assert result is False
    
    def test_load_placeholder_map_invalid_json(self, tmp_path):
        """Test handling invalid JSON in placeholder map"""
        placeholder_file = tmp_path / "placeholder_map.json"
        placeholder_file.write_text("{invalid json}")
        
        validator = QAHardValidator(
            "dummy.csv", str(placeholder_file), "dummy.yaml", "dummy.txt", "report.json"
        )
        
        result = validator.load_placeholder_map()
        
        assert result is False


class TestSchemaLoading:
    """Tests for load_schema() method with v1.0 and v2.0 formats"""
    
    def test_load_schema_v2_format(self, tmp_path):
        """Test loading schema v2.0 format with patterns and paired_tags"""
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("""
version: 2
patterns:
  - name: "player_placeholder"
    regex: "<player>"
  - name: "npc_placeholder"
    regex: "<npc>"
paired_tags:
  - open: "<b>"
    close: "</b>"
    description: "bold tags"
  - open: "<i>"
    close: "</i>"
    description: "italic tags"
""")
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", str(schema_file), "dummy.txt", "report.json"
        )
        
        result = validator.load_schema()
        
        assert result is True
        assert len(validator.compiled_patterns) == 2
        assert len(validator.paired_tags) == 2
    
    def test_load_schema_v1_fallback(self, tmp_path):
        """Test fallback to v1.0 format (placeholder_patterns)"""
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("""
placeholder_patterns:
  - name: "test"
    pattern: "<test>"
""")
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", str(schema_file), "dummy.txt", "report.json"
        )
        
        result = validator.load_schema()
        
        assert result is True
        assert len(validator.compiled_patterns) == 1
    
    def test_load_schema_empty_patterns(self, tmp_path):
        """Test loading schema with empty patterns list"""
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("""
version: 2
patterns: []
""")
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", str(schema_file), "dummy.txt", "report.json"
        )
        
        result = validator.load_schema()
        
        assert result is True
        assert len(validator.compiled_patterns) == 0
    
    def test_load_schema_invalid_regex(self, tmp_path, capsys):
        """Test handling invalid regex in patterns"""
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("""
version: 2
patterns:
  - name: "invalid"
    regex: "[invalid("
  - name: "valid"
    regex: "<valid>"
""")
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", str(schema_file), "dummy.txt", "report.json"
        )
        
        result = validator.load_schema()
        
        assert result is True
        assert len(validator.compiled_patterns) == 1  # Only valid one
        captured = capsys.readouterr()
        assert "Invalid regex" in captured.out or "Invalid regex" in captured.err
    
    def test_load_schema_file_not_found(self):
        """Test handling missing schema file"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "nonexistent.yaml", "dummy.txt", "report.json"
        )
        
        result = validator.load_schema()
        
        assert result is True  # Returns True with warning


class TestForbiddenPatternsLoading:
    """Tests for load_forbidden_patterns() method"""
    
    def test_load_valid_forbidden_patterns(self, tmp_path):
        """Test loading valid forbidden patterns"""
        forbidden_file = tmp_path / "forbidden.txt"
        forbidden_file.write_text("""
# This is a comment
\\\\bbad_word\\\\b
\\\\d{4,}
invalid_\\w+
""")
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", str(forbidden_file), "report.json"
        )
        
        result = validator.load_forbidden_patterns()
        
        assert result is True
        assert len(validator.compiled_forbidden) == 3
    
    def test_load_forbidden_with_empty_lines(self, tmp_path):
        """Test loading forbidden patterns with empty lines"""
        forbidden_file = tmp_path / "forbidden.txt"
        forbidden_file.write_text("""
pattern1

pattern2

""")
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", str(forbidden_file), "report.json"
        )
        
        result = validator.load_forbidden_patterns()
        
        assert result is True
        assert len(validator.compiled_forbidden) == 2
    
    def test_load_forbidden_invalid_regex(self, tmp_path, capsys):
        """Test handling invalid regex in forbidden patterns"""
        forbidden_file = tmp_path / "forbidden.txt"
        forbidden_file.write_text("""
valid_pattern
[invalid(
""")
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", str(forbidden_file), "report.json"
        )
        
        result = validator.load_forbidden_patterns()
        
        assert result is True
        assert len(validator.compiled_forbidden) == 1
        captured = capsys.readouterr()
        assert "Invalid forbidden pattern" in captured.out or "Invalid forbidden pattern" in captured.err
    
    def test_load_forbidden_file_not_found(self):
        """Test handling missing forbidden patterns file"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "nonexistent.txt", "report.json"
        )
        
        result = validator.load_forbidden_patterns()
        
        assert result is True  # Returns True with warning


class TestTokenExtraction:
    """Tests for extract_tokens() method"""
    
    def test_extract_single_token(self):
        """Test extracting single token"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        tokens = validator.extract_tokens("Hello ⟦PH_001⟧ world")
        
        assert tokens == {"PH_001"}
    
    def test_extract_multiple_tokens(self):
        """Test extracting multiple different tokens"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        tokens = validator.extract_tokens("⟦PH_001⟧ and ⟦PH_002⟧ and ⟦TAG_001⟧")
        
        assert tokens == {"PH_001", "PH_002", "TAG_001"}
    
    def test_extract_duplicate_tokens(self):
        """Test that duplicate tokens are deduplicated"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        tokens = validator.extract_tokens("⟦PH_001⟧ ⟦PH_001⟧ ⟦PH_001⟧")
        
        assert tokens == {"PH_001"}
    
    def test_extract_no_tokens(self):
        """Test extracting from text with no tokens"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        tokens = validator.extract_tokens("Hello world, no tokens here!")
        
        assert tokens == set()
    
    def test_extract_empty_text(self):
        """Test extracting from empty text"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        tokens = validator.extract_tokens("")
        
        assert tokens == set()
    
    def test_extract_none_text(self):
        """Test extracting from None"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        tokens = validator.extract_tokens(None)
        
        assert tokens == set()


class TestTokenMismatch:
    """Tests for check_token_mismatch() method"""
    
    def test_no_mismatch(self):
        """Test when source and target have matching tokens"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        validator.check_token_mismatch(
            "id1",
            "Hello ⟦PH_001⟧ world",
            "Привет ⟦PH_001⟧ мир",
            2
        )
        
        assert len(validator.errors) == 0
        assert validator.error_counts["token_mismatch"] == 0
    
    def test_missing_token(self):
        """Test detecting missing token in target"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        validator.check_token_mismatch(
            "id1",
            "Hello ⟦PH_001⟧ and ⟦PH_002⟧",
            "Привет ⟦PH_001⟧",
            2
        )
        
        assert len(validator.errors) == 1
        assert validator.error_counts["token_mismatch"] == 1
        assert "missing" in validator.errors[0]["detail"]
        assert "PH_002" in validator.errors[0]["detail"]
    
    def test_extra_token(self):
        """Test detecting extra token in target"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        validator.check_token_mismatch(
            "id1",
            "Hello ⟦PH_001⟧",
            "Привет ⟦PH_001⟧ and ⟦PH_002⟧",
            2
        )
        
        assert len(validator.errors) == 1
        assert validator.error_counts["token_mismatch"] == 1
        assert "extra" in validator.errors[0]["detail"]
        assert "PH_002" in validator.errors[0]["detail"]
    
    def test_multiple_mismatches(self):
        """Test detecting both missing and extra tokens"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        validator.check_token_mismatch(
            "id1",
            "Hello ⟦PH_001⟧ and ⟦PH_002⟧",
            "Привет ⟦PH_002⟧ and ⟦PH_003⟧",
            2
        )
        
        assert len(validator.errors) == 2
        assert validator.error_counts["token_mismatch"] == 2
    
    def test_empty_target(self):
        """Test with empty target text"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        validator.check_token_mismatch(
            "id1",
            "Hello ⟦PH_001⟧",
            "",
            2
        )
        
        assert len(validator.errors) == 1
        assert "missing" in validator.errors[0]["detail"]


class TestTagBalance:
    """Tests for check_tag_balance() method with paired tags and count fallback"""
    
    def test_balanced_paired_tags(self, tmp_path):
        """Test balanced tags with paired_tags configuration"""
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("""
version: 2
patterns: []
paired_tags:
  - open: "<b>"
    close: "</b>"
    description: "bold tags"
""")
        
        placeholder_file = tmp_path / "placeholder_map.json"
        placeholder_file.write_text(json.dumps({
            "mappings": {
                "TAG_001": "<b>",
                "TAG_002": "</b>"
            }
        }))
        
        validator = QAHardValidator(
            "dummy.csv", str(placeholder_file), str(schema_file), "dummy.txt", "report.json"
        )
        validator.load_placeholder_map()
        validator.load_schema()
        
        validator.check_tag_balance("id1", "⟦TAG_001⟧Text⟦TAG_002⟧", 2)
        
        assert len(validator.errors) == 0
        assert validator.error_counts["tag_unbalanced"] == 0
    
    def test_unbalanced_paired_tags(self, tmp_path):
        """Test unbalanced tags with paired_tags configuration"""
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("""
version: 2
patterns: []
paired_tags:
  - open: "<b>"
    close: "</b>"
    description: "bold tags"
""")
        
        placeholder_file = tmp_path / "placeholder_map.json"
        placeholder_file.write_text(json.dumps({
            "mappings": {
                "TAG_001": "<b>",
                "TAG_002": "</b>"
            }
        }))
        
        validator = QAHardValidator(
            "dummy.csv", str(placeholder_file), str(schema_file), "dummy.txt", "report.json"
        )
        validator.load_placeholder_map()
        validator.load_schema()
        
        # Only opening tag
        validator.check_tag_balance("id1", "⟦TAG_001⟧Text", 2)
        
        assert len(validator.errors) == 1
        assert validator.error_counts["tag_unbalanced"] == 1
        assert "unbalanced" in validator.errors[0]["detail"].lower()
    
    def test_tag_balance_fallback(self, tmp_path):
        """Test tag balance check without paired_tags (count-based fallback)"""
        placeholder_file = tmp_path / "placeholder_map.json"
        placeholder_file.write_text(json.dumps({
            "mappings": {
                "TAG_001": "<b>",
                "TAG_002": "</b>"
            }
        }))
        
        validator = QAHardValidator(
            "dummy.csv", str(placeholder_file), "dummy.yaml", "dummy.txt", "report.json"
        )
        validator.load_placeholder_map()
        # No schema loaded, so paired_tags is empty
        
        validator.check_tag_balance("id1", "⟦TAG_001⟧Text", 2)
        
        assert len(validator.errors) == 1
        assert validator.error_counts["tag_unbalanced"] == 1
    
    def test_no_tags(self):
        """Test with no tags in text"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        validator.check_tag_balance("id1", "Plain text without tags", 2)
        
        assert len(validator.errors) == 0
    
    def test_empty_text(self):
        """Test with empty text"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        validator.check_tag_balance("id1", "", 2)
        
        assert len(validator.errors) == 0


class TestForbiddenPatterns:
    """Tests for check_forbidden_patterns() method"""
    
    def test_forbidden_pattern_detected(self, tmp_path):
        """Test detecting forbidden pattern in text"""
        forbidden_file = tmp_path / "forbidden.txt"
        forbidden_file.write_text(r"\bpassword\b")
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", str(forbidden_file), "report.json"
        )
        validator.load_forbidden_patterns()
        
        validator.check_forbidden_patterns("id1", "Please enter your password", 2)
        
        assert len(validator.errors) == 1
        assert validator.error_counts["forbidden_hit"] == 1
        assert "forbidden" in validator.errors[0]["detail"].lower()
    
    def test_no_forbidden_pattern(self, tmp_path):
        """Test when no forbidden pattern matches"""
        forbidden_file = tmp_path / "forbidden.txt"
        forbidden_file.write_text(r"\bpassword\b")
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", str(forbidden_file), "report.json"
        )
        validator.load_forbidden_patterns()
        
        validator.check_forbidden_patterns("id1", "Safe text without forbidden words", 2)
        
        assert len(validator.errors) == 0
        assert validator.error_counts["forbidden_hit"] == 0
    
    def test_multiple_patterns_only_first_reported(self, tmp_path):
        """Test that only first matching forbidden pattern is reported"""
        forbidden_file = tmp_path / "forbidden.txt"
        forbidden_file.write_text("""
password
credit_card
""")
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", str(forbidden_file), "report.json"
        )
        validator.load_forbidden_patterns()
        
        validator.check_forbidden_patterns("id1", "password and credit_card", 2)
        
        # Only first match should be reported
        assert validator.error_counts["forbidden_hit"] == 1
    
    def test_empty_text(self):
        """Test with empty text"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        validator.check_forbidden_patterns("id1", "", 2)
        
        assert len(validator.errors) == 0


class TestNewPlaceholders:
    """Tests for check_new_placeholders() method"""
    
    def test_new_placeholder_detected(self, tmp_path):
        """Test detecting unfrozen placeholder"""
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("""
version: 2
patterns:
  - name: "angle_brackets"
    regex: "<([^>]+)>"
""")
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", str(schema_file), "dummy.txt", "report.json"
        )
        validator.load_schema()
        
        validator.check_new_placeholders("id1", "Text with <unfrozen> placeholder", 2)
        
        assert len(validator.errors) == 1
        assert validator.error_counts["new_placeholder_found"] == 1
        assert "unfrozen" in validator.errors[0]["detail"].lower()
    
    def test_no_new_placeholder(self, tmp_path):
        """Test when no new placeholders are found"""
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("""
version: 2
patterns:
  - name: "angle_brackets"
    regex: "<([^>]+)>"
""")
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", str(schema_file), "dummy.txt", "report.json"
        )
        validator.load_schema()
        
        validator.check_new_placeholders("id1", "Plain text without placeholders", 2)
        
        assert len(validator.errors) == 0
        assert validator.error_counts["new_placeholder_found"] == 0
    
    def test_skip_token_format(self, tmp_path):
        """Test that already-tokenized placeholders are skipped"""
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("""
version: 2
patterns:
  - name: "angle_brackets"
    regex: "<([^>]+)>"
""")
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", str(schema_file), "dummy.txt", "report.json"
        )
        validator.load_schema()
        
        # Token format should be skipped
        validator.check_new_placeholders("id1", "Text with ⟦PH_001⟧ token", 2)
        
        assert len(validator.errors) == 0
    
    def test_empty_text(self):
        """Test with empty text"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        validator.check_new_placeholders("id1", "", 2)
        
        assert len(validator.errors) == 0


class TestLengthOverflow:
    """Tests for check_length_overflow() method"""
    
    def test_length_overflow_major(self):
        """Test detecting major length overflow"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        row = {"max_length_target": "20"}
        validator.check_length_overflow("id1", "A" * 30, row, 2)
        
        assert len(validator.errors) == 1
        assert validator.errors[0]["severity"] == "major"
        assert "30 > 20" in validator.errors[0]["detail"]
    
    def test_length_overflow_critical(self):
        """Test detecting critical length overflow (>150%)"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        row = {"max_length_target": "10"}
        validator.check_length_overflow("id1", "A" * 20, row, 2)
        
        assert len(validator.errors) == 1
        assert validator.errors[0]["severity"] == "critical"
    
    def test_no_overflow(self):
        """Test when length is within limit"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        row = {"max_length_target": "100"}
        validator.check_length_overflow("id1", "Short text", row, 2)
        
        assert len(validator.errors) == 0
    
    def test_no_max_length(self):
        """Test when max_length is not specified"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        row = {}
        validator.check_length_overflow("id1", "A" * 1000, row, 2)
        
        assert len(validator.errors) == 0
    
    def test_invalid_max_length(self):
        """Test handling invalid max_length value"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        row = {"max_length_target": "invalid"}
        validator.check_length_overflow("id1", "Text", row, 2)
        
        assert len(validator.errors) == 0
    
    def test_max_len_target_alias(self):
        """Test max_len_target field alias"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        row = {"max_len_target": "10"}
        validator.check_length_overflow("id1", "A" * 20, row, 2)
        
        assert len(validator.errors) == 1


class TestCSVValidation:
    """Tests for validate_csv() method"""
    
    def test_valid_csv_with_target_text(self, tmp_path):
        """Test validating CSV with target_text column"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("""string_id,tokenized_zh,target_text
id1,Hello ⟦PH_001⟧,Привет ⟦PH_001⟧
id2,World,Мир
""")
        
        placeholder_file = tmp_path / "placeholder_map.json"
        placeholder_file.write_text(json.dumps({"mappings": {"PH_001": "<player>"}}))
        
        validator = QAHardValidator(
            str(csv_file), str(placeholder_file), "dummy.yaml", "dummy.txt", str(tmp_path / "report.json")
        )
        validator.load_placeholder_map()
        
        result = validator.validate_csv()
        
        assert result is True
        assert validator.total_rows == 2
    
    def test_valid_csv_with_translated_text(self, tmp_path):
        """Test validating CSV with translated_text column (alternative name)"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("""string_id,tokenized_zh,translated_text
id1,Hello,Привет
""")
        
        placeholder_file = tmp_path / "placeholder_map.json"
        placeholder_file.write_text(json.dumps({"mappings": {}}))
        
        validator = QAHardValidator(
            str(csv_file), str(placeholder_file), "dummy.yaml", "dummy.txt", str(tmp_path / "report.json")
        )
        validator.load_placeholder_map()
        
        result = validator.validate_csv()
        
        assert result is True
    
    def test_csv_missing_required_field(self, tmp_path):
        """Test CSV missing required string_id field"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("""tokenized_zh,target_text
Hello,Привет
""")
        
        validator = QAHardValidator(
            str(csv_file), "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        result = validator.validate_csv()
        
        assert result is False
    
    def test_csv_no_target_field(self, tmp_path):
        """Test CSV with no target translation field"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("""string_id,tokenized_zh
Hello
""")
        
        placeholder_file = tmp_path / "placeholder_map.json"
        placeholder_file.write_text(json.dumps({"mappings": {}}))
        
        validator = QAHardValidator(
            str(csv_file), str(placeholder_file), "dummy.yaml", "dummy.txt", "report.json"
        )
        validator.load_placeholder_map()
        
        result = validator.validate_csv()
        
        assert result is False
    
    def test_csv_file_not_found(self):
        """Test handling missing CSV file"""
        validator = QAHardValidator(
            "nonexistent.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        result = validator.validate_csv()
        
        assert result is False
    
    def test_csv_empty_translation_skipped(self, tmp_path):
        """Test that empty translations are skipped"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("""string_id,tokenized_zh,target_text
id1,Hello,
id2,World,Мир
""")
        
        placeholder_file = tmp_path / "placeholder_map.json"
        placeholder_file.write_text(json.dumps({"mappings": {}}))
        
        validator = QAHardValidator(
            str(csv_file), str(placeholder_file), "dummy.yaml", "dummy.txt", str(tmp_path / "report.json")
        )
        validator.load_placeholder_map()
        
        result = validator.validate_csv()
        
        assert result is True
        assert validator.total_rows == 2  # Both rows counted
        # Empty translation row should not trigger errors


class TestReportGeneration:
    """Tests for generate_report() method"""
    
    def test_report_with_errors(self, tmp_path):
        """Test generating report with errors"""
        report_file = tmp_path / "report.json"
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", str(report_file)
        )
        validator.total_rows = 10
        validator.errors = [
            {"row": 2, "type": "token_mismatch", "detail": "test"},
            {"row": 3, "type": "tag_unbalanced", "detail": "test"}
        ]
        validator.error_counts = {
            "token_mismatch": 1,
            "tag_unbalanced": 1,
            "forbidden_hit": 0,
            "new_placeholder_found": 0
        }
        
        validator.generate_report()
        
        assert report_file.exists()
        report = json.loads(report_file.read_text())
        assert report["has_errors"] is True
        assert report["total_rows"] == 10
        assert len(report["errors"]) == 2
    
    def test_report_no_errors(self, tmp_path):
        """Test generating report without errors"""
        report_file = tmp_path / "report.json"
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", str(report_file)
        )
        validator.total_rows = 5
        validator.errors = []
        validator.error_counts = {
            "token_mismatch": 0,
            "tag_unbalanced": 0,
            "forbidden_hit": 0,
            "new_placeholder_found": 0
        }
        
        validator.generate_report()
        
        report = json.loads(report_file.read_text())
        assert report["has_errors"] is False
        assert report["metadata"]["total_errors"] == 0
    
    def test_report_error_limit(self, tmp_path):
        """Test that report limits errors to 2000"""
        report_file = tmp_path / "report.json"
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", str(report_file)
        )
        validator.total_rows = 2500
        validator.errors = [
            {"row": i, "type": "token_mismatch", "detail": f"error {i}"}
            for i in range(2500)
        ]
        validator.error_counts = {"token_mismatch": 2500}
        
        validator.generate_report()
        
        report = json.loads(report_file.read_text())
        assert len(report["errors"]) == 2000
        assert report["metadata"]["errors_truncated"] is True
        assert report["metadata"]["total_errors"] == 2500
    
    def test_report_metadata(self, tmp_path):
        """Test report metadata fields"""
        report_file = tmp_path / "report.json"
        
        validator = QAHardValidator(
            "test.csv", "dummy.json", "dummy.yaml", "dummy.txt", str(report_file)
        )
        validator.total_rows = 10
        validator.errors = []
        
        validator.generate_report()
        
        report = json.loads(report_file.read_text())
        assert "metadata" in report
        assert report["metadata"]["version"] == "2.0"
        assert "generated_at" in report["metadata"]
        assert report["metadata"]["input_file"] == "test.csv"


class TestIntegrationRun:
    """Integration tests for the full run() method"""
    
    def test_successful_run_no_errors(self, tmp_path):
        """Test complete successful run with no errors"""
        # Create test files
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("""string_id,tokenized_zh,target_text
id1,Hello ⟦PH_001⟧,Привет ⟦PH_001⟧
id2,World ⟦PH_002⟧,Мир ⟦PH_002⟧
""")
        
        placeholder_file = tmp_path / "placeholder_map.json"
        placeholder_file.write_text(json.dumps({
            "mappings": {
                "PH_001": "<player>",
                "PH_002": "<world>"
            }
        }))
        
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("""
version: 2
patterns: []
""")
        
        forbidden_file = tmp_path / "forbidden.txt"
        forbidden_file.write_text("")
        
        report_file = tmp_path / "report.json"
        
        validator = QAHardValidator(
            str(csv_file), str(placeholder_file), str(schema_file),
            str(forbidden_file), str(report_file)
        )
        
        success = validator.run()
        
        assert success is True
        assert report_file.exists()
        report = json.loads(report_file.read_text())
        assert report["has_errors"] is False
    
    def test_run_with_errors(self, tmp_path):
        """Test complete run with validation errors"""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("""string_id,tokenized_zh,target_text
id1,Hello ⟦PH_001⟧,Привет
""")
        
        placeholder_file = tmp_path / "placeholder_map.json"
        placeholder_file.write_text(json.dumps({
            "mappings": {"PH_001": "<player>"}
        }))
        
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("version: 2\npatterns: []\n")
        
        forbidden_file = tmp_path / "forbidden.txt"
        forbidden_file.write_text("")
        
        report_file = tmp_path / "report.json"
        
        validator = QAHardValidator(
            str(csv_file), str(placeholder_file), str(schema_file),
            str(forbidden_file), str(report_file)
        )
        
        success = validator.run()
        
        assert success is False
        report = json.loads(report_file.read_text())
        assert report["has_errors"] is True
        assert report["error_counts"]["token_mismatch"] == 1
    
    def test_run_missing_placeholder_map(self, tmp_path):
        """Test run fails when placeholder map is missing"""
        validator = QAHardValidator(
            "dummy.csv", "nonexistent.json", "dummy.yaml", "dummy.txt", str(tmp_path / "report.json")
        )
        
        success = validator.run()
        
        assert success is False


class TestEdgeCases:
    """Edge cases and boundary tests"""
    
    def test_unicode_handling(self):
        """Test handling of unicode text"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        tokens = validator.extract_tokens("こんにちは⟦PH_001⟧世界⟦PH_002⟧🎮")
        
        assert tokens == {"PH_001", "PH_002"}
    
    def test_special_characters_in_tokens(self):
        """Test tokens with special characters don't break extraction"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        # Valid token format should still extract
        tokens = validator.extract_tokens("Text with ⟦PH_001⟧ and ⟦TAG_999⟧")
        
        assert "PH_001" in tokens
        assert "TAG_999" in tokens
    
    def test_zero_max_length(self):
        """Test handling zero max_length"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        row = {"max_length_target": "0"}
        validator.check_length_overflow("id1", "Any text", row, 2)
        
        # Should not trigger error for zero/negative limit
        assert len(validator.errors) == 0
    
    def test_negative_max_length(self):
        """Test handling negative max_length"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        row = {"max_length_target": "-5"}
        validator.check_length_overflow("id1", "Any text", row, 2)
        
        # Should not trigger error for zero/negative limit
        assert len(validator.errors) == 0


class TestPrintSummary:
    """Tests for print_summary() method"""
    
    def test_summary_with_errors(self, capsys):
        """Test printing summary with errors"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        validator.total_rows = 100
        validator.errors = [
            {"row": 2, "string_id": "id1", "type": "token_mismatch", "detail": "test"}
        ]
        validator.error_counts = {
            "token_mismatch": 1,
            "tag_unbalanced": 0,
            "forbidden_hit": 0,
            "new_placeholder_found": 0
        }
        
        validator.print_summary()
        
        captured = capsys.readouterr()
        assert "100" in captured.out
        assert "FAILED" in captured.out
    
    def test_summary_no_errors(self, capsys):
        """Test printing summary with no errors"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        validator.total_rows = 50
        validator.errors = []
        validator.error_counts = {
            "token_mismatch": 0,
            "tag_unbalanced": 0,
            "forbidden_hit": 0,
            "new_placeholder_found": 0
        }
        
        validator.print_summary()
        
        captured = capsys.readouterr()
        assert "50" in captured.out
        assert "passed" in captured.out.lower()
    
    def test_summary_all_error_types(self, capsys):
        """Test summary with all error types"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        validator.total_rows = 100
        validator.errors = [
            {"row": i, "string_id": f"id{i}", "type": "test", "detail": f"error {i}"}
            for i in range(10)
        ]
        validator.error_counts = {
            "token_mismatch": 2,
            "tag_unbalanced": 3,
            "forbidden_hit": 4,
            "new_placeholder_found": 1
        }
        
        validator.print_summary()
        
        captured = capsys.readouterr()
        assert "Token mismatch" in captured.out or "token_mismatch" in captured.out
        assert "Tag unbalanced" in captured.out or "tag_unbalanced" in captured.out
        assert "Forbidden" in captured.out or "forbidden_hit" in captured.out


class TestMainFunction:
    """Tests for main() function"""
    
    def test_main_success(self, tmp_path, monkeypatch):
        """Test main function with successful validation"""
        import qa_hard as qa_module
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("""string_id,tokenized_zh,target_text
id1,Hello ⟦PH_001⟧,Привет ⟦PH_001⟧
""")
        
        placeholder_file = tmp_path / "placeholder_map.json"
        placeholder_file.write_text(json.dumps({"mappings": {"PH_001": "<player>"}}))
        
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("version: 2\npatterns: []\n")
        
        forbidden_file = tmp_path / "forbidden.txt"
        forbidden_file.write_text("")
        
        report_file = tmp_path / "report.json"
        
        monkeypatch.setattr(sys, 'argv', [
            'qa_hard.py', str(csv_file), str(placeholder_file), 
            str(schema_file), str(forbidden_file), str(report_file)
        ])
        
        with pytest.raises(SystemExit) as exc_info:
            qa_module.main()
        
        assert exc_info.value.code == 0
    
    def test_main_failure(self, tmp_path, monkeypatch):
        """Test main function with validation failure"""
        import qa_hard as qa_module
        
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("""string_id,tokenized_zh,target_text
id1,Hello ⟦PH_001⟧,Привет
""")
        
        placeholder_file = tmp_path / "placeholder_map.json"
        placeholder_file.write_text(json.dumps({"mappings": {"PH_001": "<player>"}}))
        
        schema_file = tmp_path / "schema.yaml"
        schema_file.write_text("version: 2\npatterns: []\n")
        
        forbidden_file = tmp_path / "forbidden.txt"
        forbidden_file.write_text("")
        
        report_file = tmp_path / "report.json"
        
        monkeypatch.setattr(sys, 'argv', [
            'qa_hard.py', str(csv_file), str(placeholder_file), 
            str(schema_file), str(forbidden_file), str(report_file)
        ])
        
        with pytest.raises(SystemExit) as exc_info:
            qa_module.main()
        
        assert exc_info.value.code == 1
    
    def test_main_default_args(self, monkeypatch):
        """Test main function with default arguments"""
        import qa_hard as qa_module
        
        monkeypatch.setattr(sys, 'argv', ['qa_hard.py'])
        
        # Should not raise exception - just uses default paths
        # We need to mock the actual run since default files don't exist
        with patch.object(QAHardValidator, 'run', return_value=True):
            with pytest.raises(SystemExit) as exc_info:
                qa_module.main()


class TestErrorHandling:
    """Additional error handling tests"""
    
    def test_check_tag_balance_exception_handling(self):
        """Test exception handling in tag balance check"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        # This should not raise an exception
        validator.check_tag_balance("id1", None, 2)
        # No assertions needed - just verifying no exception
    
    def test_csv_exception_handling(self, tmp_path):
        """Test CSV validation exception handling"""
        # Create a directory instead of a file to cause read error
        csv_file = tmp_path / "not_a_file"
        csv_file.mkdir()
        
        validator = QAHardValidator(
            str(csv_file / "test.csv"), "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        result = validator.validate_csv()
        
        # Should handle gracefully
        assert result is False
    
    def test_check_forbidden_exception_in_regex(self, tmp_path):
        """Test exception handling during forbidden pattern matching"""
        # Create a pattern that might cause issues
        forbidden_file = tmp_path / "forbidden.txt"
        forbidden_file.write_text(r"test")
        
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", str(forbidden_file), "report.json"
        )
        validator.load_forbidden_patterns()
        
        # Should not raise exception even with unusual input
        validator.check_forbidden_patterns("id1", "test", 2)
        # No assertions needed - just verifying no exception
    
    def test_check_new_placeholder_exception(self):
        """Test exception handling in new placeholder check"""
        validator = QAHardValidator(
            "dummy.csv", "dummy.json", "dummy.yaml", "dummy.txt", "report.json"
        )
        
        # Should handle gracefully
        validator.check_new_placeholders("id1", None, 2)
        # No assertions needed - just verifying no exception


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
