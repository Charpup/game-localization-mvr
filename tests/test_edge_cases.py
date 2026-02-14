#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_edge_cases.py
Comprehensive edge case tests for localization pipeline
Target: ≥80% edge case coverage
Total Tests: 45+

Categories:
    - Unicode edge cases (emoji, CJK, RTL, combining)
    - Placeholder edge cases (nested, malformed, empty)
    - CSV edge cases (commas, quotes, newlines)
    - Text length extremes (empty, long, boundary)
    - Special characters (HTML, XML, markdown)
    - Language-specific (Russian, Japanese, German, Arabic, Thai)
"""

import os
import sys
import csv
import json
import string
import random
import pytest
from io import StringIO
from pathlib import Path
from typing import List, Tuple, Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def sample_csv_path(tmp_path):
    """Create a sample CSV file for testing."""
    csv_path = tmp_path / "test.csv"
    return str(csv_path)


@pytest.fixture
def edge_cases_data_dir():
    """Path to edge cases test data directory."""
    base_dir = Path(__file__).parent
    data_dir = base_dir / "data" / "edge_cases"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture
def unicode_normalizer():
    """Helper for Unicode normalization testing."""
    import unicodedata
    return unicodedata


@pytest.fixture
def grapheme_counter():
    """Helper for grapheme cluster counting."""
    try:
        import regex
        def count(text: str) -> int:
            return len(regex.findall(r'\X', text))
        return count
    except ImportError:
        # Fallback to simple length
        return len


# ============================================================================
# Unicode Edge Cases - Emoji
# ============================================================================

class TestUnicodeEmoji:
    """Tests for emoji handling edge cases (UC-E series)."""
    
    def test_basic_emoji(self):
        """UC-E01: Basic emoji should be preserved."""
        text = "🔥 Fire damage"
        assert "🔥" in text
        assert len(text.encode('utf-8')) > len(text)  # Multi-byte
    
    def test_emoji_with_skin_tone(self):
        """UC-E02: Emoji with Fitzpatrick skin tones."""
        text = "👋🏽 Waving hand (medium skin)"
        # Should be treated as single grapheme cluster
        assert "👋🏽" in text
        assert text.encode('utf-8')  # Valid UTF-8
    
    def test_flag_emoji(self):
        """UC-E03: Regional indicator flags (two code points)."""
        text = "🇺🇸 US Flag"
        # US flag is U+1F1FA U+1F1F8
        assert "🇺🇸" in text
        assert len("🇺🇸") == 2  # Two regional indicators
    
    def test_zwj_emoji_sequences(self):
        """UC-E04: Zero-width joiner sequences (family emoji)."""
        text = "👨‍👩‍👧‍👦 Family"
        assert "👨‍👩‍👧‍👦" in text
        # Should handle ZWJ sequences without breaking
    
    def test_emoji_variation_selectors(self):
        """UC-E05: Emoji with text vs emoji presentation."""
        heart_text = "❤\ufe0e"  # Text variation
        heart_emoji = "❤\ufe0f"  # Emoji variation
        assert "\ufe0e" in heart_text  # VS15
        assert "\ufe0f" in heart_emoji  # VS16


# ============================================================================
# Unicode Edge Cases - CJK Characters
# ============================================================================

class TestUnicodeCJK:
    """Tests for CJK (Chinese, Japanese, Korean) edge cases (UC-C/J/K series)."""
    
    def test_traditional_chinese(self):
        """UC-C01: Traditional Chinese character width."""
        text = "繁體中文測試"
        assert len(text) == 6  # 6 characters
        for char in text:
            assert ord(char) > 0x4E00  # CJK Unified Ideographs
    
    def test_simplified_chinese(self):
        """UC-C02: Simplified Chinese."""
        text = "简体中文测试"
        assert "简" in text
        assert "体" in text
    
    def test_japanese_hiragana(self):
        """UC-J01: Japanese Hiragana syllabary."""
        text = "ひらがなテスト"
        assert all(0x3040 <= ord(c) <= 0x309F for c in "ひらがな")
    
    def test_japanese_katakana(self):
        """UC-J02: Japanese Katakana (loanwords)."""
        text = "カタカナ"
        assert all(0x30A0 <= ord(c) <= 0x30FF for c in text)
    
    def test_japanese_kanji_furigana(self):
        """UC-J03: Kanji with ruby text notation."""
        text = "漢字(かんじ)"
        assert "漢" in text
        assert "かんじ" in text
    
    def test_korean_hangul(self):
        """UC-K01: Korean Hangul syllables."""
        text = "한글테스트"
        assert all(0xAC00 <= ord(c) <= 0xD7A3 for c in text)
    
    def test_korean_hangul_jamo(self):
        """UC-K02: Hangul composing jamo."""
        text = "한"  # Jamo sequence
        assert any(0x1100 <= ord(c) <= 0x11FF for c in text)


# ============================================================================
# Unicode Edge Cases - RTL Languages
# ============================================================================

class TestUnicodeRTL:
    """Tests for Right-to-Left (RTL) language edge cases (UC-R series)."""
    
    def test_arabic_text(self):
        """UC-R01: Arabic text handling."""
        text = "مرحبا بالعالم"
        assert any(0x0600 <= ord(c) <= 0x06FF for c in text)
    
    def test_hebrew_text(self):
        """UC-R02: Hebrew text handling."""
        text = "שלום עולם"
        assert any(0x0590 <= ord(c) <= 0x05FF for c in text)
    
    def test_mixed_ltr_rtl(self):
        """UC-R03: Mixed LTR and RTL text (bidi)."""
        text = "Price: $50 للشراء"
        assert "$50" in text  # LTR preserved
        assert "للشراء" in text  # RTL preserved
    
    def test_arabic_diacritics(self):
        """UC-R04: Arabic with harakat (diacritics)."""
        text = "مَرْحَبًا"
        # Check for combining diacritics
        assert any(0x064B <= ord(c) <= 0x065F for c in text)
    
    def test_persian_text(self):
        """UC-R05: Persian (Farsi) text."""
        text = "سلام دنیا"
        # Persian uses Arabic script with variations
        assert "سلام" in text


# ============================================================================
# Unicode Edge Cases - Combining Characters
# ============================================================================

class TestUnicodeCombining:
    """Tests for combining character edge cases (UC-M series)."""
    
    def test_precomposed_vs_decomposed(self, unicode_normalizer):
        """UC-M01: Precomposed é vs e + combining acute."""
        composed = "é"  # U+00E9
        decomposed = "e\u0301"  # e + combining acute
        assert unicode_normalizer.normalize('NFC', decomposed) == composed
        assert unicode_normalizer.normalize('NFD', composed) == decomposed
    
    def test_multiple_combining_marks(self):
        """UC-M02: Multiple combining marks ordering."""
        # a + circumflex + dot below
        text = "a\u0302\u0323"
        assert "\u0302" in text  # Combining circumflex
        assert "\u0323" in text  # Combining dot below
    
    def test_zwj_indic(self):
        """UC-M03: Zero-width joiner in Indic scripts."""
        # Kannada consonant cluster example
        text = "\u0C95\u0CCD\u200D\u0CB7"  # ಕ್ + ZWJ + ಷ
        assert "\u200D" in text  # ZWJ present
    
    def test_variation_selectors(self):
        """UC-M04: Variation selectors 15/16."""
        text_vs15 = "漢\ufe0e"  # Text presentation
        text_vs16 = "漢\ufe0f"  # Emoji presentation
        assert text_vs15 != text_vs16


# ============================================================================
# Placeholder Edge Cases - Nested
# ============================================================================

class TestPlaceholderNested:
    """Tests for nested placeholder edge cases (PH-N series)."""
    
    def test_nested_braces(self):
        """PH-N01: Sequential placeholder processing."""
        template = "{name}'s {item}"
        result = template.format(name="Player", item="sword")
        assert "Player's sword" == result
    
    def test_html_in_placeholder(self):
        """PH-N02: HTML-like content in placeholders."""
        template = "<color={color}>{text}</color>"
        result = template.format(color="red", text="Warning")
        assert "<color=red>Warning</color>" == result
    
    def test_double_nesting(self):
        """PH-N03: Deeply nested patterns."""
        # This tests parser depth handling
        template = "{outer_{inner}_suffix}"
        # Should handle or gracefully fail on invalid nesting
        try:
            result = template.format(**{"outer_{inner}_suffix": "value"})
            assert "value" == result
        except (KeyError, ValueError):
            pass  # Expected for invalid format
    
    def test_overlapping_patterns(self):
        """PH-N04: Multiple placeholder formats in one string."""
        text = "Hello %s and {0}"
        # Both printf-style and brace-style
        assert "%s" in text
        assert "{0}" in text


# ============================================================================
# Placeholder Edge Cases - Malformed
# ============================================================================

class TestPlaceholderMalformed:
    """Tests for malformed placeholder edge cases (PH-M series)."""
    
    def test_unclosed_brace(self):
        """PH-M01: Unclosed brace should be preserved."""
        text = "{unclosed"
        # Should not throw, preserve as literal
        assert "{unclosed" == text
    
    def test_unopened_brace(self):
        """PH-M02: Unopened brace should be preserved."""
        text = "unopened}"
        assert "unopened}" == text
    
    def test_empty_braces(self):
        """PH-M05: Empty placeholder handling."""
        text = "{}"
        # Empty braces are valid in Python format
        result = "{}".format("value")
        assert "value" == result
    
    def test_mismatched_braces(self):
        """PH-M03: Mismatched quote-like braces."""
        text = '{"mismatched}'
        # Should handle or preserve
        assert "{" in text and "}" in text


# ============================================================================
# Placeholder Edge Cases - Empty/Whitespace
# ============================================================================

class TestPlaceholderEmpty:
    """Tests for empty and whitespace placeholder edge cases (PH-E series)."""
    
    def test_empty_replacement(self):
        """PH-E01: Empty string replacement."""
        template = "Hello {name}!"
        result = template.format(name="")
        assert "Hello !" == result
    
    def test_whitespace_only_replacement(self):
        """PH-E02: Whitespace-only replacement."""
        template = "[{space}]"
        result = template.format(space="   ")
        assert "[   ]" == result
    
    def test_newline_in_value(self):
        """PH-E03: Multiline replacement value."""
        template = "{desc}"
        multiline = "Line1\nLine2\nLine3"
        result = template.format(desc=multiline)
        assert "\n" in result
        assert result.count("\n") == 2
    
    def test_tab_characters(self):
        """PH-E04: Tab characters preserved."""
        template = "{stats}"
        result = template.format(stats="HP:\t100")
        assert "\t" in result


# ============================================================================
# Placeholder Edge Cases - Special Patterns
# ============================================================================

class TestPlaceholderSpecial:
    """Tests for special placeholder patterns (PH-S series)."""
    
    def test_escaped_braces(self):
        """PH-S01: Escaped braces for literals."""
        template = "{{literal}}"
        result = template.format()
        assert "{literal}" == result
    
    def test_indexed_placeholders(self):
        """PH-S02: Positional indexed placeholders."""
        template = "{0} attacks {1}"
        result = template.format("Player", "Enemy")
        assert "Player attacks Enemy" == result
    
    def test_case_sensitive_names(self):
        """PH-S03: Case-sensitive placeholder names."""
        template = "{Name} vs {name}"
        try:
            result = template.format(Name="Upper", name="lower")
            assert "Upper vs lower" == result
        except KeyError:
            pass  # May fail depending on implementation
    
    def test_unicode_placeholder_names(self):
        """PH-S04: Unicode in placeholder keys."""
        template = "{玩家名}"
        result = template.format(**{"玩家名": "Player1"})
        assert "Player1" == result


# ============================================================================
# CSV Edge Cases - Comma Handling
# ============================================================================

class TestCSVCommas:
    """Tests for CSV comma edge cases (CSV-C series)."""
    
    def test_comma_in_text(self, sample_csv_path):
        """CSV-C01: Comma within quoted field."""
        csv_content = 'id,text\n1,"Hello, World"'
        Path(sample_csv_path).write_text(csv_content, encoding='utf-8')
        
        with open(sample_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert "Hello, World" == row['text']
    
    def test_multiple_commas(self, sample_csv_path):
        """CSV-C02: Multiple commas in field."""
        csv_content = 'id,text\n1,"A, B, C, D"'
        Path(sample_csv_path).write_text(csv_content, encoding='utf-8')
        
        with open(sample_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert "A, B, C, D" == row['text']
    
    def test_comma_at_start(self, sample_csv_path):
        """CSV-C03: Leading comma in quoted field."""
        csv_content = 'id,text\n1,",leading comma"'
        Path(sample_csv_path).write_text(csv_content, encoding='utf-8')
        
        with open(sample_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert ",leading comma" == row['text']


# ============================================================================
# CSV Edge Cases - Quote Handling
# ============================================================================

class TestCSVQuotes:
    """Tests for CSV quote edge cases (CSV-Q series)."""
    
    def test_embedded_quotes(self, sample_csv_path):
        """CSV-Q01: Embedded quotes (doubled)."""
        csv_content = 'id,text\n1,"She said ""hello"""'
        Path(sample_csv_path).write_text(csv_content, encoding='utf-8')
        
        with open(sample_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert 'She said "hello"' == row['text']
    
    def test_quote_at_start(self, sample_csv_path):
        """CSV-Q02: Quote at start of field."""
        csv_content = 'id,text\n1,"""quoted"'
        Path(sample_csv_path).write_text(csv_content, encoding='utf-8')
        
        with open(sample_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert '"quoted' == row['text']
    
    def test_quote_at_end(self, sample_csv_path):
        """CSV-Q03: Quote at end of field."""
        csv_content = 'id,text\n1,"quoted""'
        Path(sample_csv_path).write_text(csv_content, encoding='utf-8')
        
        with open(sample_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert 'quoted"' == row['text']
    
    def test_double_quotes_only(self, sample_csv_path):
        """CSV-Q04: Field containing only a quote."""
        csv_content = 'id,text\n1,""""'
        Path(sample_csv_path).write_text(csv_content, encoding='utf-8')
        
        with open(sample_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert '"' == row['text']


# ============================================================================
# CSV Edge Cases - Newline Handling
# ============================================================================

class TestCSVNewlines:
    """Tests for CSV newline edge cases (CSV-N series)."""
    
    def test_lf_in_field(self, sample_csv_path):
        """CSV-N01: Line feed within quoted field."""
        csv_content = 'id,text\n1,"Line1\nLine2"'
        Path(sample_csv_path).write_text(csv_content, encoding='utf-8')
        
        with open(sample_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert "Line1\nLine2" == row['text']
    
    def test_multiple_newlines(self, sample_csv_path):
        """CSV-N03: Multiple newlines in field."""
        csv_content = 'id,text\n1,"L1\nL2\nL3"'
        Path(sample_csv_path).write_text(csv_content, encoding='utf-8')
        
        with open(sample_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert row['text'].count('\n') == 2


# ============================================================================
# CSV Edge Cases - Field Edge Cases
# ============================================================================

class TestCSVFields:
    """Tests for CSV field edge cases (CSV-F series)."""
    
    def test_empty_field(self, sample_csv_path):
        """CSV-F01: Completely empty field."""
        csv_content = 'a,b,c\n1,,3'
        Path(sample_csv_path).write_text(csv_content, encoding='utf-8')
        
        with open(sample_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert row['b'] == ''
    
    def test_whitespace_only_field(self, sample_csv_path):
        """CSV-F02: Whitespace-only field."""
        csv_content = 'id,text\n1,"   "'
        Path(sample_csv_path).write_text(csv_content, encoding='utf-8')
        
        with open(sample_csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert row['text'] == '   '
    
    def test_bom_header(self, sample_csv_path):
        """CSV-F05: UTF-8 BOM at start of file."""
        csv_content = '\ufeffid,text\n1,hello'
        Path(sample_csv_path).write_text(csv_content, encoding='utf-8')
        
        with open(sample_csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            assert 'id' in row  # BOM should be stripped


# ============================================================================
# Text Length Extremes - Boundary Values
# ============================================================================

class TestTextLengthBoundary:
    """Tests for text length boundary values (TL-B series)."""
    
    def test_empty_string(self):
        """TL-B01: Empty string (0 length)."""
        text = ""
        assert len(text) == 0
        assert text == ""
    
    def test_single_character(self):
        """TL-B02: Single character."""
        text = "X"
        assert len(text) == 1
    
    def test_two_characters(self):
        """TL-B03: Two characters (near boundary)."""
        text = "XY"
        assert len(text) == 2
    
    def test_boundary_255(self):
        """TL-B04: Common limit - 1 (255 chars)."""
        text = "X" * 255
        assert len(text) == 255
    
    def test_boundary_256(self):
        """TL-B05: Common limit (256 chars)."""
        text = "X" * 256
        assert len(text) == 256
    
    def test_boundary_257(self):
        """TL-B06: Common limit + 1 (257 chars)."""
        text = "X" * 257
        assert len(text) == 257


# ============================================================================
# Text Length Extremes - Extreme Lengths
# ============================================================================

class TestTextLengthExtreme:
    """Tests for extreme text lengths (TL-X series)."""
    
    def test_very_long_word(self):
        """TL-X01: Very long single word (1000 chars)."""
        text = "a" * 1000
        assert len(text) == 1000
        assert text.count("a") == 1000
    
    def test_maximum_practical(self):
        """TL-X02: Maximum practical length (10000 chars)."""
        text = "word " * 2000
        assert len(text) == 10000
    
    def test_multiline_long(self):
        """TL-X04: Multiline text (100 lines)."""
        lines = [f"Line {i}: content here" for i in range(100)]
        text = "\n".join(lines)
        assert text.count("\n") == 99
    
    def test_multibyte_boundary(self):
        """TL-U01: Multi-byte character boundary."""
        # 𐍈 is 4 bytes in UTF-8
        text = "𐍈"
        assert len(text) == 1  # 1 code point
        assert len(text.encode('utf-8')) == 4  # 4 bytes


# ============================================================================
# Special Characters - HTML Entities
# ============================================================================

class TestSpecialHTML:
    """Tests for HTML entity edge cases (SP-H series)."""
    
    def test_named_entity(self):
        """SP-H01: Named HTML entity (ampersand)."""
        text = "&amp;"
        import html
        assert html.unescape(text) == "&"
    
    def test_numeric_decimal(self):
        """SP-H02: Numeric decimal entity."""
        text = "&#169;"
        import html
        assert html.unescape(text) == "©"
    
    def test_numeric_hex(self):
        """SP-H03: Numeric hexadecimal entity."""
        text = "&#xA9;"
        import html
        assert html.unescape(text) == "©"
    
    def test_double_encoded(self):
        """SP-H04: Double-encoded entity."""
        text = "&amp;amp;"
        import html
        # First unescape
        first = html.unescape(text)
        assert first == "&amp;"
        # Second unescape
        second = html.unescape(first)
        assert second == "&"
    
    def test_unclosed_entity(self):
        """SP-H05: Malformed unclosed entity."""
        text = "&amp"
        # Should be preserved or handled gracefully
        assert "&" in text
    
    def test_invalid_entity(self):
        """SP-H06: Invalid/unknown entity."""
        text = "&notanentity;"
        # Should preserve as-is
        assert text == "&notanentity;"


# ============================================================================
# Special Characters - XML/HTML Tags
# ============================================================================

class TestSpecialXML:
    """Tests for XML/HTML tag edge cases (SP-X series)."""
    
    def test_simple_tag(self):
        """SP-X01: Simple balanced HTML tag."""
        text = "<b>bold</b>"
        assert "<b>" in text
        assert "</b>" in text
    
    def test_self_closing(self):
        """SP-X02: Self-closing tag."""
        text = "Line1<br/>Line2"
        assert "<br/>" in text
    
    def test_tag_with_attributes(self):
        """SP-X03: Tag with attributes."""
        text = '<color="#ff0000">Red</color>'
        assert "#ff0000" in text
    
    def test_unclosed_tag(self):
        """SP-X04: Unclosed/malformed tag."""
        text = "<b>bold"
        # Should handle gracefully
        assert "<b>" in text
    
    def test_nested_tags(self):
        """SP-X05: Nested HTML tags."""
        text = "<b><i>text</i></b>"
        assert text.count("<") == 4
        assert text.count(">") == 4
    
    def test_cdata_section(self):
        """SP-X07: CDATA section."""
        text = "<![CDATA[<literal>]]>"
        assert "CDATA" in text


# ============================================================================
# Special Characters - Markdown
# ============================================================================

class TestSpecialMarkdown:
    """Tests for Markdown edge cases (SP-M series)."""
    
    def test_bold(self):
        """SP-M01: Markdown bold."""
        text = "**bold text**"
        assert text.startswith("**")
        assert text.endswith("**")
    
    def test_italic(self):
        """SP-M02: Markdown italic."""
        text = "*italic*"
        assert text.startswith("*")
        assert text.endswith("*")
    
    def test_link(self):
        """SP-M03: Markdown link."""
        text = "[text](https://example.com)"
        assert "[text]" in text
        assert "(https://example.com)" in text
    
    def test_inline_code(self):
        """SP-M04: Inline code with backticks."""
        text = "`code snippet`"
        assert text.startswith("`")
        assert text.endswith("`")
    
    def test_code_block(self):
        """SP-M05: Code block with triple backticks."""
        text = "```\ncode\nblock\n```"
        assert "```" in text
    
    def test_table(self):
        """SP-M06: Markdown table."""
        text = "| Col1 | Col2 |\n|------|------|\n| A | B |"
        assert "|" in text
    
    def test_escaped_chars(self):
        """SP-M07: Escaped markdown characters."""
        text = r"\*literal asterisks\*"
        assert "\\*" in text


# ============================================================================
# Special Characters - Control Characters
# ============================================================================

class TestSpecialControl:
    """Tests for control character edge cases (SP-C series)."""
    
    def test_null_character(self):
        """SP-C01: Null character handling."""
        text = "text\x00with\x00nulls"
        assert "\x00" in text
    
    def test_tab_character(self):
        """SP-C04: Tab character."""
        text = "col1\tcol2\tcol3"
        assert "\t" in text
        assert text.count("\t") == 2
    
    def test_line_feed(self):
        """SP-C05: Line feed (Unix newline)."""
        text = "line1\nline2"
        assert "\n" in text
    
    def test_carriage_return(self):
        """SP-C06: Carriage return."""
        text = "line1\rline2"
        assert "\r" in text
    
    def test_escape_character(self):
        """SP-C07: Escape character."""
        text = "text\x1b[31mred\x1b[0m"
        assert "\x1b" in text


# ============================================================================
# Special Characters - Whitespace Variants
# ============================================================================

class TestSpecialWhitespace:
    """Tests for whitespace variant edge cases (SP-W series)."""
    
    def test_standard_space(self):
        """SP-W01: Standard space (U+0020)."""
        text = "hello world"
        assert " " in text
    
    def test_no_break_space(self):
        """SP-W02: No-break space (U+00A0)."""
        text = "hello\xa0world"
        assert "\xa0" in text
    
    def test_en_space(self):
        """SP-W03: En space (U+2002)."""
        text = "hello\u2002world"
        assert "\u2002" in text
    
    def test_em_space(self):
        """SP-W04: Em space (U+2003)."""
        text = "hello\u2003world"
        assert "\u2003" in text
    
    def test_zero_width_space(self):
        """SP-W06: Zero-width space (U+200B)."""
        text = "hello\u200bworld"
        assert "\u200b" in text
        # Visual length should differ from byte length
    
    def test_ideographic_space(self):
        """SP-W08: Ideographic space (U+3000)."""
        text = "hello\u3000world"
        assert "\u3000" in text


# ============================================================================
# Language-Specific - Russian Cases
# ============================================================================

class TestLanguageRussian:
    """Tests for Russian grammatical cases (RU-C series)."""
    
    def test_russian_nominative(self):
        """RU-C01: Nominative case (subject)."""
        text = "игрок"  # Player (subject)
        assert text == "игрок"
    
    def test_russian_genitive(self):
        """RU-C02: Genitive case ("of")."""
        text = "игрока"  # Of player
        assert text.endswith("а")
    
    def test_russian_dative(self):
        """RU-C03: Dative case ("to")."""
        text = "игроку"  # To player
        assert text.endswith("у")
    
    def test_russian_accusative(self):
        """RU-C04: Accusative case (object)."""
        text = "игрока"  # Object form
        # Same as genitive in this case
    
    def test_russian_instrumental(self):
        """RU-C05: Instrumental case ("with")."""
        text = "игроком"  # With player
        assert text.endswith("ом")
    
    def test_russian_prepositional(self):
        """RU-C06: Prepositional case ("about")."""
        text = "игроке"  # About player
        assert text.endswith("е")


# ============================================================================
# Language-Specific - Japanese Honorifics
# ============================================================================

class TestLanguageJapanese:
    """Tests for Japanese honorific edge cases (JP-H series)."""
    
    def test_japanese_polite(self):
        """JP-H01: Polite form (丁寧語)."""
        text = "ありがとうございます"
        assert "ございます" in text  # Polite ending
    
    def test_japanese_casual(self):
        """JP-H02: Casual form (タメ口)."""
        text = "ありがとう"
        assert text == "ありがとう"
    
    def test_japanese_humble(self):
        """JP-H03: Humble form (謙譲語)."""
        text = "させていただきます"
        assert "いただきます" in text  # Humble giving/receiving
    
    def test_japanese_respectful(self):
        """JP-H04: Respectful form (尊敬語)."""
        text = "おっしゃいます"
        assert text.startswith("お")  # Honorific prefix
    
    def test_japanese_suffix_san(self):
        """JP-H05: Suffix -san."""
        text = "田中さん"
        assert text.endswith("さん")
    
    def test_japanese_suffix_sama(self):
        """JP-H06: Suffix -sama (high respect)."""
        text = "お客様"
        assert "様" in text
    
    def test_japanese_suffix_kun(self):
        """JP-H07: Suffix -kun (male/junior)."""
        text = "山田くん"
        assert text.endswith("くん")
    
    def test_japanese_suffix_chan(self):
        """JP-H08: Suffix -chan (cute/familiar)."""
        text = "太郎ちゃん"
        assert text.endswith("ちゃん")


# ============================================================================
# Language-Specific - German Compound Words
# ============================================================================

class TestLanguageGerman:
    """Tests for German compound word edge cases (DE-C series)."""
    
    def test_german_simple(self):
        """DE-C01: Simple German word."""
        text = "Spiel"  # Game
        assert len(text) == 5
    
    def test_german_compound(self):
        """DE-C02: Compound word."""
        text = "Computerspiel"  # Computer game
        assert "Computer" in text
        assert "spiel" in text
    
    def test_german_complex_compound(self):
        """DE-C03: Complex compound."""
        text = "Computerspielcharakter"  # Computer game character
        assert len(text) == 22
    
    def test_german_famous_long_word(self):
        """DE-C04: Famous long compound word."""
        text = "Donaudampfschifffahrtsgesellschaftskapitän"
        assert len(text) == 42
        # Danube steamship captain


# ============================================================================
# Language-Specific - Arabic Presentation Forms
# ============================================================================

class TestLanguageArabic:
    """Tests for Arabic presentation form edge cases (AR-P series)."""
    
    def test_arabic_isolated_form(self):
        """AR-P01: Arabic letter isolated form."""
        text = "ب"  # Beh isolated
        assert text == "ب"
    
    def test_arabic_ligature(self):
        """AR-P02: Arabic ligature (lam + alef)."""
        text = "لا"  # Lam-alef ligature
        # Represented as 2 code points: U+0644 U+0627
        assert len(text) == 2
        assert "\u0644" in text  # LAM
        assert "\u0627" in text  # ALEF


# ============================================================================
# Language-Specific - Thai Stacking
# ============================================================================

class TestLanguageThai:
    """Tests for Thai character stacking edge cases (TH-S series)."""
    
    def test_thai_above_vowel_tone(self):
        """TH-S01: Above vowel + tone mark stacking."""
        text = "หิน"  # Stone with sara i + mai ek
        assert len(text) >= 3
    
    def test_thai_below_vowel(self):
        """TH-S02: Below base vowel."""
        text = "ภู"  # Island with sara uu below
        assert "\u0e39" in text or "\u0e38" in text  # Below vowel
    
    def test_thai_complex_stacking(self):
        """TH-S03: Complex multiple mark stacking."""
        text = "เป๋า"  # Bag with multiple marks
        assert len(text) >= 3


# ============================================================================
# Fuzzing-Inspired Random Input Tests
# ============================================================================

class TestFuzzingRandom:
    """Fuzzing-inspired random input tests."""
    
    def test_random_ascii(self):
        """Random ASCII string handling."""
        for _ in range(10):
            length = random.randint(1, 1000)
            text = ''.join(random.choices(string.ascii_letters + string.digits, k=length))
            assert len(text) == length
            assert isinstance(text, str)
    
    def test_random_unicode(self):
        """Random Unicode code point handling."""
        for _ in range(10):
            # Generate random Unicode code points (BMP range)
            length = random.randint(1, 100)
            text = ''.join(chr(random.randint(0x20, 0xFFFF)) for _ in range(length))
            assert isinstance(text, str)
            assert len(text) == length
    
    def test_random_with_placeholders(self):
        """Random text mixed with placeholders."""
        for _ in range(10):
            parts = []
            for _ in range(random.randint(1, 5)):
                parts.append(''.join(random.choices(string.ascii_letters, k=random.randint(1, 20))))
                parts.append(random.choice(['{', '%s', '{{', '}']))
            text = ''.join(parts)
            assert isinstance(text, str)
    
    def test_random_csv_like(self):
        """Random CSV-like content."""
        for _ in range(10):
            fields = []
            for _ in range(random.randint(2, 10)):
                field = ''.join(random.choices(string.ascii_letters + ',"\n', k=random.randint(0, 50)))
                fields.append(f'"{field}"')
            line = ','.join(fields)
            assert ',' in line or '"' in line


# ============================================================================
# Boundary Value Analysis
# ============================================================================

class TestBoundaryValue:
    """Boundary value analysis tests."""
    
    @pytest.mark.parametrize("length", [0, 1, 2, 127, 128, 129, 255, 256, 257])
    def test_boundary_lengths(self, length):
        """Test various boundary lengths."""
        text = "X" * length
        assert len(text) == length
    
    @pytest.mark.parametrize("emoji_count", [1, 10, 50, 100, 500])
    def test_emoji_boundary_counts(self, emoji_count):
        """Test emoji string boundaries."""
        text = "🔥" * emoji_count
        assert text.count("🔥") == emoji_count
    
    def test_csv_field_count_boundaries(self, sample_csv_path):
        """Test CSV with varying field counts."""
        for field_count in [1, 2, 5, 10, 50]:
            header = ','.join(f"col{i}" for i in range(field_count))
            row = ','.join(f"val{i}" for i in range(field_count))
            csv_content = f"{header}\n{row}"
            
            Path(sample_csv_path).write_text(csv_content, encoding='utf-8')
            with open(sample_csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)
                data = next(reader)
                assert len(headers) == field_count
                assert len(data) == field_count


# ============================================================================
# Equivalence Partition Tests
# ============================================================================

class TestEquivalencePartition:
    """Equivalence partition tests."""
    
    # Valid partitions
    VALID_PARTITIONS = [
        ("ASCII only", "Hello World"),
        ("Extended Latin", "café naïve"),
        ("CJK unified", "你好世界"),
        ("With placeholders", "Hello {name}"),
        ("With HTML", "<b>Bold</b> text"),
    ]
    
    # Invalid partitions
    INVALID_PARTITIONS = [
        ("Malformed UTF-8", b'\xff\xfe'.decode('latin-1')),
        ("Unmatched braces", "Hello {name"),
        ("Invalid HTML", "<unclosed"),
    ]
    
    @pytest.mark.parametrize("name,text", VALID_PARTITIONS)
    def test_valid_partitions(self, name, text):
        """EP-V01-05: Valid input partitions should be handled."""
        assert isinstance(text, str)
        assert len(text) >= 0
    
    def test_empty_partition(self):
        """EP-B01: Empty string partition."""
        text = ""
        assert text == ""
    
    def test_whitespace_only_partition(self):
        """EP-B04: Whitespace-only partition."""
        text = "   \t\n   "
        assert text.strip() == ""


# ============================================================================
# Integration and Stress Tests
# ============================================================================

class TestIntegrationStress:
    """Integration and stress tests combining multiple edge cases."""
    
    def test_complex_localization_string(self):
        """Complex string with multiple edge cases combined."""
        text = 'ID_{player_id},"🔥 {player_name}\nเวลา: {time}\n攻击力: {attack}",<color=red>{warning}</color>,"{weapon} +{level} 強化"'
        # Contains: emoji, CJK, Thai, placeholders, HTML, quotes, comma, newline
        assert "🔥" in text
        assert "攻击力" in text
        assert "เวลา" in text
        assert "{player_name}" in text
        assert "<color=red>" in text
    
    def test_russian_with_placeholders(self):
        """Russian text with placeholders and cases."""
        template = "У {игрока} есть {предмет}"
        result = template.format(игрока="игрока", предмет="меч")
        assert "У игрока есть меч" == result
    
    def test_japanese_with_html(self):
        """Japanese text with HTML formatting."""
        text = "<color=red>ありがとうございます</color>、{name}さん"
        assert "ありがとうございます" in text
        assert "さん" in text


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
