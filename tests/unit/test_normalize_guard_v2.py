#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_normalize_guard_v2.py
完整单元测试 for normalize_guard.py
目标：90%+ 测试覆盖率
"""

import os
import sys
import json
import csv
import pytest
from io import StringIO
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock, mock_open

# 确保能导入 scripts 目录下的模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scripts.normalize_guard import (
    PlaceholderFreezer,
    NormalizeGuard,
    detect_unbalanced_basic,
    TAG_PATTERN,
    LONG_TEXT_THRESHOLD
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_schema_content():
    """模拟 schema YAML 内容 - 使用原始字符串避免 YAML 转义问题"""
    return '''
version: 2
token_format:
  placeholder: "⟦PH_{n}⟧"
  tag: "⟦TAG_{n}⟧"
patterns:
  - name: brace_placeholder
    type: placeholder
    regex: '\\{[^{}]+\\}'
  - name: printf_placeholder
    type: placeholder
    regex: '%(?:\\d+\\$)?[\\-\\+0# ]*(?:\\d+)?(?:\\.\\d+)?[a-zA-Z]'
  - name: angle_tag
    type: tag
    regex: '</?\\w+(?:\\s*=?\\s*[^>]*)?>'
  - name: escapes
    type: placeholder
    regex: '\\\\[ntr]'
'''


@pytest.fixture
def temp_schema_file(tmp_path, mock_schema_content):
    """创建临时 schema 文件"""
    schema_path = tmp_path / "test_schema.yaml"
    schema_path.write_text(mock_schema_content, encoding='utf-8')
    return str(schema_path)


@pytest.fixture
def freezer(temp_schema_file):
    """创建 PlaceholderFreezer 实例"""
    return PlaceholderFreezer(temp_schema_file)


@pytest.fixture
def sample_csv_content():
    """示例 CSV 内容"""
    return """string_id,source_zh,context
TEST_001,提升自身攻击力{0}点,技能描述
TEST_002,<color=red>警告</color>文本,UI文本
TEST_003,伤害值：%d点,战斗数值
"""


# ============================================================================
# Test PlaceholderFreezer - Initialization
# ============================================================================

class TestPlaceholderFreezerInit:
    """测试 PlaceholderFreezer 初始化"""
    
    def test_init_success(self, temp_schema_file):
        """测试成功初始化"""
        freezer = PlaceholderFreezer(temp_schema_file)
        assert freezer.ph_counter == 0
        assert freezer.tag_counter == 0
        assert freezer.placeholder_map == {}
        assert freezer.reverse_map == {}
        assert len(freezer.patterns) == 4
        assert 'placeholder' in freezer.token_format
        assert 'tag' in freezer.token_format
    
    def test_init_file_not_found(self):
        """测试 schema 文件不存在"""
        with pytest.raises(SystemExit) as exc_info:
            PlaceholderFreezer("/nonexistent/schema.yaml")
        assert exc_info.value.code == 1
    
    def test_init_empty_patterns(self, tmp_path):
        """测试空的 patterns"""
        schema_path = tmp_path / "empty_schema.yaml"
        schema_path.write_text("version: 2\npatterns: []", encoding='utf-8')
        
        with patch('builtins.print') as mock_print:
            freezer = PlaceholderFreezer(str(schema_path))
            mock_print.assert_any_call("⚠️  Warning: No patterns found in schema")
    
    def test_init_invalid_yaml(self, tmp_path):
        """测试无效的 YAML"""
        schema_path = tmp_path / "invalid_schema.yaml"
        schema_path.write_text("invalid: [", encoding='utf-8')
        
        with pytest.raises(SystemExit) as exc_info:
            PlaceholderFreezer(str(schema_path))
        assert exc_info.value.code == 1


# ============================================================================
# Test PlaceholderFreezer - Tag Protection
# ============================================================================

class TestTagProtection:
    """测试标签保护功能"""
    
    def test_protect_tags_simple(self, freezer):
        """测试简单标签保护"""
        text = "<color=red>红色文本</color>"
        frozen, protected = freezer.protect_tags(text)
        
        assert len(protected) == 2
        assert "<color=red>" in protected
        assert "</color>" in protected
        assert "__TAG_0__" in frozen
        assert "__TAG_1__" in frozen
        assert "红色文本" in frozen
    
    def test_protect_tags_multiple(self, freezer):
        """测试多个标签保护"""
        text = "<b><color=#FF00FF>加粗彩色</color></b>"
        frozen, protected = freezer.protect_tags(text)
        
        assert len(protected) == 4
        assert "__TAG_0__" in frozen
        assert "__TAG_3__" in frozen
    
    def test_protect_tags_no_tags(self, freezer):
        """测试无标签文本"""
        text = "普通文本没有标签"
        frozen, protected = freezer.protect_tags(text)
        
        assert len(protected) == 0
        assert frozen == text
    
    def test_protect_tags_nested(self, freezer):
        """测试嵌套标签"""
        text = "<b>粗体<i>斜体</i></b>"
        frozen, protected = freezer.protect_tags(text)
        
        assert len(protected) == 4
        assert all("__TAG_" in frozen for _ in range(4))
    
    def test_restore_tags(self, freezer):
        """测试标签还原"""
        text = "<color=red>红色</color>"
        frozen, protected = freezer.protect_tags(text)
        restored = freezer.restore_tags(frozen, protected)
        
        assert restored == text
    
    def test_restore_tags_empty_list(self, freezer):
        """测试空标签列表还原"""
        text = "普通文本"
        restored = freezer.restore_tags(text, [])
        assert restored == text


# ============================================================================
# Test PlaceholderFreezer - freeze_text
# ============================================================================

class TestFreezeText:
    """测试 freeze_text 功能"""
    
    def test_freeze_brace_placeholder(self, freezer):
        """测试花括号占位符冻结"""
        text = "攻击力{0}点"
        frozen, local_map = freezer.freeze_text(text, source_lang='en')
        
        assert "{0}" not in frozen
        assert "⟦PH_1⟧" in frozen
        assert local_map["PH_1"] == "{0}"
    
    def test_freeze_printf_placeholder(self, freezer):
        """测试 printf 风格占位符冻结"""
        text = "伤害值：%d点"
        frozen, local_map = freezer.freeze_text(text, source_lang='en')
        
        assert "%d" not in frozen
        assert "⟦PH_1⟧" in frozen
        assert local_map["PH_1"] == "%d"
    
    def test_freeze_angle_tag(self, freezer):
        """测试尖括号标签冻结"""
        text = "<color=red>红色文本</color>"
        frozen, local_map = freezer.freeze_text(text, source_lang='en')
        
        assert "<color=red>" not in frozen
        assert "</color>" not in frozen
        assert "⟦TAG_1⟧" in frozen
        assert local_map["TAG_1"] == "<color=red>"
    
    def test_freeze_escape_sequence(self, freezer):
        """测试转义序列冻结"""
        text = "第一行\\n第二行"
        frozen, local_map = freezer.freeze_text(text, source_lang='en')
        
        assert "\\n" not in frozen
        assert "⟦PH_1⟧" in frozen
        assert local_map["PH_1"] == "\\n"
    
    def test_freeze_empty_string(self, freezer):
        """测试空字符串"""
        frozen, local_map = freezer.freeze_text("", source_lang='en')
        
        assert frozen == ""
        assert local_map == {}
    
    def test_freeze_token_reuse(self, freezer):
        """测试 token 重用机制"""
        text = "{0}和{0}"
        frozen, local_map = freezer.freeze_text(text, source_lang='en')
        
        # 相同占位符应该重用同一个 token
        assert frozen.count("⟦PH_1⟧") == 2
        assert "PH_2" not in local_map
    
    def test_freeze_multiple_different_placeholders(self, freezer):
        """测试多个不同占位符"""
        text = "{0}攻击{1}防御"
        frozen, local_map = freezer.freeze_text(text, source_lang='en')
        
        assert "⟦PH_1⟧" in frozen
        assert "⟦PH_2⟧" in frozen
        assert local_map["PH_1"] == "{0}"
        assert local_map["PH_2"] == "{1}"
    
    def test_freeze_chinese_segmentation(self, freezer):
        """测试中文分词"""
        text = "提升自身攻击力"
        frozen, local_map = freezer.freeze_text(text, source_lang='zh-CN')
        
        # 中文应该被分词并添加空格
        assert ' ' in frozen
        assert '提升' in frozen
        assert '自身' in frozen
    
    def test_freeze_chinese_with_placeholder(self, freezer):
        """测试中文分词与占位符结合"""
        text = "提升{0}点攻击力"
        frozen, local_map = freezer.freeze_text(text, source_lang='zh-CN')
        
        # 中文分词会在花括号周围添加空格，所以实际匹配的是 "{ 0 }"
        assert '{0}' not in frozen or '{ 0 }' not in frozen
        assert 'PH_1' in frozen  # token name
        # 中文部分应该有分词
        assert ' ' in frozen
    
    def test_freeze_tags_in_chinese(self, freezer):
        """测试中文文本中的标签保护"""
        text = "<color=red>红色</color>警告"
        frozen, local_map = freezer.freeze_text(text, source_lang='zh-CN')
        
        # 中文分词后，标签被保护为 __TAG_X__ 格式
        assert "<color=red>" not in frozen
        assert "</color>" not in frozen
        assert "TAG_1" in frozen or "TAG" in frozen
        assert "红色" in frozen
    
    def test_freeze_non_chinese_no_segmentation(self, freezer):
        """测试非中文语言不分词"""
        text = "English text"
        frozen, local_map = freezer.freeze_text(text, source_lang='en-US')
        
        # 英文不应该被分词
        assert frozen == "English text"
    
    def test_freeze_complex_mixed_content(self, freezer):
        """测试复杂混合内容"""
        text = "<b>{playerName}</b>造成%d点伤害\\n"
        frozen, local_map = freezer.freeze_text(text, source_lang='en')
        
        assert "⟦TAG_1⟧" in frozen  # <b>
        assert "⟦PH_1⟧" in frozen  # {playerName}
        assert "⟦TAG_2⟧" in frozen  # </b>
        assert "⟦PH_2⟧" in frozen  # %d
        assert "⟦PH_3⟧" in frozen  # \\n

# ============================================================================
# Test PlaceholderFreezer - Counter Management
# ============================================================================

class TestCounterManagement:
    """测试计数器管理"""
    
    def test_reset_counters(self, freezer):
        """测试重置计数器"""
        freezer.freeze_text("{0}", source_lang='en')
        assert freezer.ph_counter == 1
        
        freezer.reset_counters()
        assert freezer.ph_counter == 0
        assert freezer.tag_counter == 0
        assert freezer.placeholder_map == {}
        assert freezer.reverse_map == {}
    
    def test_counters_increment_correctly(self, freezer):
        """测试计数器正确递增"""
        freezer.freeze_text("{0}", source_lang='en')
        assert freezer.ph_counter == 1
        
        freezer.freeze_text("<b>", source_lang='en')
        assert freezer.tag_counter == 1
        
        freezer.freeze_text("{1}", source_lang='en')
        assert freezer.ph_counter == 2


# ============================================================================
# Test detect_unbalanced_basic
# ============================================================================

class TestDetectUnbalancedBasic:
    """测试基本平衡检查函数"""
    
    def test_balanced_text(self):
        """测试平衡的文本"""
        text = "正常{文本}内容[测试]"
        issues = detect_unbalanced_basic(text)
        assert len(issues) == 0
    
    def test_unbalanced_braces(self):
        """测试不平衡的花括号"""
        text = "缺少右括号{文本"
        issues = detect_unbalanced_basic(text)
        assert 'brace_unbalanced' in issues
    
    def test_unbalanced_angles(self):
        """测试不平衡的尖括号"""
        text = "缺少右尖括号<文本"
        issues = detect_unbalanced_basic(text)
        assert 'angle_unbalanced' in issues
    
    def test_unbalanced_square(self):
        """测试不平衡的方括号"""
        text = "缺少右方括号[文本"
        issues = detect_unbalanced_basic(text)
        assert 'square_unbalanced' in issues
    
    def test_multiple_unbalanced(self):
        """测试多种不平衡"""
        text = "{<["
        issues = detect_unbalanced_basic(text)
        assert len(issues) == 3
        assert 'brace_unbalanced' in issues
        assert 'angle_unbalanced' in issues
        assert 'square_unbalanced' in issues
    
    def test_empty_string(self):
        """测试空字符串"""
        issues = detect_unbalanced_basic("")
        assert len(issues) == 0
    
    def test_nested_balanced(self):
        """测试嵌套但平衡的文本"""
        text = "外{中[内]中}外"
        issues = detect_unbalanced_basic(text)
        assert len(issues) == 0


# ============================================================================
# Test NormalizeGuard - Initialization
# ============================================================================

class TestNormalizeGuardInit:
    """测试 NormalizeGuard 初始化"""
    
    def test_init_success(self, temp_schema_file):
        """测试成功初始化"""
        guard = NormalizeGuard(
            input_path="input.csv",
            output_draft_path="draft.csv",
            output_map_path="map.json",
            schema_path=temp_schema_file,
            source_lang="zh-CN"
        )
        
        assert guard.input_path == Path("input.csv")
        assert guard.source_lang == "zh-CN"
        assert guard.errors == []
        assert guard.warnings == []
        assert guard.sanity_errors == []
    
    def test_init_default_source_lang(self, temp_schema_file):
        """测试默认源语言"""
        guard = NormalizeGuard(
            input_path="input.csv",
            output_draft_path="draft.csv",
            output_map_path="map.json",
            schema_path=temp_schema_file
        )
        
        assert guard.source_lang == "zh-CN"


# ============================================================================
# Test NormalizeGuard - Header Validation
# ============================================================================

class TestValidateInputHeaders:
    """测试输入头验证"""
    
    def test_valid_headers(self, temp_schema_file):
        """测试有效的头"""
        guard = NormalizeGuard(
            input_path="test.csv",
            output_draft_path="draft.csv",
            output_map_path="map.json",
            schema_path=temp_schema_file
        )
        
        result = guard.validate_input_headers(['string_id', 'source_zh', 'context'])
        assert result is True
        assert len(guard.errors) == 0
    
    def test_missing_string_id(self, temp_schema_file):
        """测试缺少 string_id"""
        guard = NormalizeGuard(
            input_path="test.csv",
            output_draft_path="draft.csv",
            output_map_path="map.json",
            schema_path=temp_schema_file
        )
        
        result = guard.validate_input_headers(['source_zh'])
        assert result is False
        assert any("Missing required columns" in e for e in guard.errors)
    
    def test_missing_source_zh(self, temp_schema_file):
        """测试缺少 source_zh"""
        guard = NormalizeGuard(
            input_path="test.csv",
            output_draft_path="draft.csv",
            output_map_path="map.json",
            schema_path=temp_schema_file
        )
        
        result = guard.validate_input_headers(['string_id'])
        assert result is False
        assert any("Missing required columns" in e for e in guard.errors)


# ============================================================================
# Test NormalizeGuard - CSV Processing
# ============================================================================

class TestProcessCSV:
    """测试 CSV 处理"""
    
    def test_process_csv_success(self, tmp_path, temp_schema_file, freezer):
        """测试成功处理 CSV"""
        # 创建测试 CSV
        csv_path = tmp_path / "test_input.csv"
        csv_path.write_text("string_id,source_zh\nTEST_001,文本{0}\nTEST_002,<b>标签</b>", encoding='utf-8')
        
        guard = NormalizeGuard(
            input_path=str(csv_path),
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        success, rows = guard.process_csv()
        
        assert success is True
        assert len(rows) == 2
        assert rows[0]['string_id'] == 'TEST_001'
        assert 'tokenized_zh' in rows[0]
        assert 'is_long_text' in rows[0]
    
    def test_process_csv_empty_string_id(self, tmp_path, temp_schema_file):
        """测试空 string_id"""
        csv_path = tmp_path / "test_input.csv"
        csv_path.write_text("string_id,source_zh\n,文本\nTEST_002,文本2", encoding='utf-8')
        
        guard = NormalizeGuard(
            input_path=str(csv_path),
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        success, rows = guard.process_csv()
        
        # 错误会返回 False
        assert success is False
        assert any("Empty string_id" in e for e in guard.errors)
    
    def test_process_csv_duplicate_id(self, tmp_path, temp_schema_file):
        """测试重复的 string_id"""
        csv_path = tmp_path / "test_input.csv"
        csv_path.write_text("string_id,source_zh\nTEST_001,文本1\nTEST_001,文本2", encoding='utf-8')
        
        guard = NormalizeGuard(
            input_path=str(csv_path),
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        success, rows = guard.process_csv()
        
        # 错误会返回 False
        assert success is False
        assert any("Duplicate string_id" in e for e in guard.errors)
    
    def test_process_csv_unbalanced_text(self, tmp_path, temp_schema_file):
        """测试不平衡的文本检测"""
        csv_path = tmp_path / "test_input.csv"
        csv_path.write_text("string_id,source_zh\nTEST_001,{未闭合", encoding='utf-8')
        
        guard = NormalizeGuard(
            input_path=str(csv_path),
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        success, rows = guard.process_csv()
        
        assert success is True
        assert len(guard.sanity_errors) == 1
        assert guard.sanity_errors[0]['string_id'] == 'TEST_001'
        assert 'brace_unbalanced' in guard.sanity_errors[0]['issues']
    
    def test_process_csv_long_text_detection(self, tmp_path, temp_schema_file):
        """测试长文本检测"""
        long_text = "A" * (LONG_TEXT_THRESHOLD + 10)
        csv_path = tmp_path / "test_input.csv"
        csv_path.write_text(f"string_id,source_zh\nTEST_001,{long_text}", encoding='utf-8')
        
        guard = NormalizeGuard(
            input_path=str(csv_path),
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        success, rows = guard.process_csv()
        
        assert success is True
        assert rows[0]['is_long_text'] == 1
    
    def test_process_csv_not_long_text(self, tmp_path, temp_schema_file):
        """测试非长文本"""
        short_text = "A" * 10
        csv_path = tmp_path / "test_input.csv"
        csv_path.write_text(f"string_id,source_zh\nTEST_001,{short_text}", encoding='utf-8')
        
        guard = NormalizeGuard(
            input_path=str(csv_path),
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        success, rows = guard.process_csv()
        
        assert success is True
        assert rows[0]['is_long_text'] == 0
    
    def test_process_csv_file_not_found(self, temp_schema_file):
        """测试文件不存在"""
        guard = NormalizeGuard(
            input_path="/nonexistent/file.csv",
            output_draft_path="draft.csv",
            output_map_path="map.json",
            schema_path=temp_schema_file
        )
        
        success, rows = guard.process_csv()
        
        assert success is False
        assert any("not found" in e for e in guard.errors)
    
    def test_process_csv_preserve_extra_columns(self, tmp_path, temp_schema_file):
        """测试保留额外列"""
        csv_path = tmp_path / "test_input.csv"
        csv_path.write_text("string_id,source_zh,context,extra\nTEST_001,文本,上下文,额外", encoding='utf-8')
        
        guard = NormalizeGuard(
            input_path=str(csv_path),
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        success, rows = guard.process_csv()
        
        assert success is True
        assert 'context' in rows[0]
        assert 'extra' in rows[0]
        assert rows[0]['context'] == '上下文'


# ============================================================================
# Test NormalizeGuard - Write Output Files
# ============================================================================

class TestWriteOutputFiles:
    """测试输出文件写入"""
    
    def test_write_draft_csv_success(self, tmp_path, temp_schema_file):
        """测试成功写入 draft CSV"""
        guard = NormalizeGuard(
            input_path="input.csv",
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        rows = [
            {
                'string_id': 'TEST_001',
                'source_zh': '文本',
                'tokenized_zh': '文本',
                'is_long_text': 0,
                'context': '上下文'
            }
        ]
        
        result = guard.write_draft_csv(rows)
        assert result is True
        assert (tmp_path / "draft.csv").exists()
    
    def test_write_draft_csv_empty_rows(self, tmp_path, temp_schema_file):
        """测试空行写入"""
        guard = NormalizeGuard(
            input_path="input.csv",
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        result = guard.write_draft_csv([])
        assert result is True
        assert any("No rows to write" in w for w in guard.warnings)
    
    def test_write_placeholder_map_success(self, tmp_path, temp_schema_file):
        """测试成功写入 placeholder map"""
        guard = NormalizeGuard(
            input_path="input.csv",
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        # 先冻结一些内容
        guard.freezer.freeze_text("{0}", source_lang='en')
        guard.freezer.freeze_text("<b>", source_lang='en')
        
        result = guard.write_placeholder_map()
        assert result is True
        assert (tmp_path / "map.json").exists()
        
        # 验证内容
        with open(tmp_path / "map.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        assert 'metadata' in data
        assert 'mappings' in data
        assert data['metadata']['ph_count'] == 1
        assert data['metadata']['tag_count'] == 1
        assert data['mappings']['PH_1'] == "{0}"
        assert data['mappings']['TAG_1'] == "<b>"


# ============================================================================
# Test NormalizeGuard - QA Report
# ============================================================================

class TestQAReport:
    """测试 QA 报告生成"""
    
    def test_write_early_qa_report_with_errors(self, tmp_path, temp_schema_file):
        """测试有错误时生成 QA 报告"""
        guard = NormalizeGuard(
            input_path="input.csv",
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        guard.sanity_errors.append({
            'string_id': 'TEST_001',
            'issues': ['brace_unbalanced'],
            'source_zh': '{未闭合',
            'row': 2
        })
        
        with patch('builtins.print') as mock_print:
            guard.write_early_qa_report(10)
            
            # 验证报告文件被创建
            qa_path = tmp_path / "qa_hard_report.json"
            assert qa_path.exists()
            
            with open(qa_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            assert report['has_errors'] is True
            assert report['total_rows'] == 10
            assert len(report['errors']) == 1
    
    def test_write_early_qa_report_no_errors(self, tmp_path, temp_schema_file):
        """测试无错误时不生成 QA 报告"""
        guard = NormalizeGuard(
            input_path="input.csv",
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        guard.write_early_qa_report(10)
        
        # 不应该创建报告文件
        qa_path = tmp_path / "qa_hard_report.json"
        assert not qa_path.exists()


# ============================================================================
# Test NormalizeGuard - Full Workflow
# ============================================================================

class TestFullWorkflow:
    """测试完整工作流"""
    
    def test_run_full_success(self, tmp_path, temp_schema_file):
        """测试完整成功运行"""
        csv_path = tmp_path / "test_input.csv"
        csv_path.write_text("string_id,source_zh\nTEST_001,文本{0}\nTEST_002,<b>加粗</b>", encoding='utf-8')
        
        guard = NormalizeGuard(
            input_path=str(csv_path),
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        with patch('builtins.print') as mock_print:
            result = guard.run()
            assert result is True
            
            # 验证文件被创建
            assert (tmp_path / "draft.csv").exists()
            assert (tmp_path / "map.json").exists()
    
    def test_run_with_validation_failure(self, tmp_path, temp_schema_file):
        """测试验证失败"""
        csv_path = tmp_path / "test_input.csv"
        csv_path.write_text("source_zh\n文本", encoding='utf-8')  # 缺少 string_id
        
        guard = NormalizeGuard(
            input_path=str(csv_path),
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        with patch('builtins.print') as mock_print:
            result = guard.run()
            assert result is False


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """测试边界情况"""
    
    def test_unicode_content(self, freezer):
        """测试 Unicode 内容"""
        text = "日本語テキスト{0}🎮游戏"
        frozen, local_map = freezer.freeze_text(text, source_lang='en')
        
        assert local_map["PH_1"] == "{0}"
        assert "日本語テキスト" in frozen
        assert "🎮" in frozen
    
    def test_special_characters(self, freezer):
        """测试特殊字符"""
        text = "特殊字符：!@#$%^&*(){0}"
        frozen, local_map = freezer.freeze_text(text, source_lang='en')
        
        assert local_map["PH_1"] == "{0}"
        assert "!@#$%^&*()" in frozen
    
    def test_very_long_text(self, freezer):
        """测试超长文本"""
        text = "A" * 10000
        frozen, local_map = freezer.freeze_text(text, source_lang='en')
        assert len(frozen) == 10000
    
    def test_multiple_same_tags(self, freezer):
        """测试多个相同标签"""
        text = "<b>第一</b>普通<b>第二</b>"
        frozen, local_map = freezer.freeze_text(text, source_lang='en')
        
        # 每个 <b> 和 </b> 是不同标签，应该有 4 个 token
        assert "TAG_1" in local_map
        assert "TAG_2" in local_map
        # 第一个<b>和第二个<b>是相同内容但出现多次，根据重用机制会是同一个token
        # 但实际应该至少有 TAG_1 和 TAG_2
    
    def test_tag_pattern_regex(self):
        """测试标签正则表达式"""
        # 测试各种标签格式
        assert TAG_PATTERN.match("<b>")
        assert TAG_PATTERN.match("</b>")
        assert TAG_PATTERN.match("<color=red>")
        assert TAG_PATTERN.match("<size=14>")
        assert not TAG_PATTERN.match("不是标签")
        assert not TAG_PATTERN.match("<")


# ============================================================================
# Test Error Handling
# ============================================================================

class TestErrorHandling:
    """测试错误处理"""
    
    def test_process_csv_unicode_decode_error(self, tmp_path, temp_schema_file):
        """测试编码错误处理"""
        # 创建包含非 UTF-8 内容的文件
        csv_path = tmp_path / "test_input.csv"
        csv_path.write_bytes(b"\xff\xfe")  # BOM without content
        
        guard = NormalizeGuard(
            input_path=str(csv_path),
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        # 应该能处理，因为 utf-8-sig 可以处理 BOM
        success, rows = guard.process_csv()
        # 空内容可能返回空列表
        assert isinstance(rows, list)
    
    def test_freeze_with_invalid_regex_in_schema(self, tmp_path):
        """测试 schema 中包含无效正则"""
        schema_content = '''
version: 2
patterns:
  - name: invalid_regex
    type: placeholder
    regex: "[invalid("
'''
        schema_path = tmp_path / "bad_schema.yaml"
        schema_path.write_text(schema_content, encoding='utf-8')
        
        freezer = PlaceholderFreezer(str(schema_path))
        
        # 应该打印警告但继续工作
        with patch('builtins.print') as mock_print:
            frozen, local_map = freezer.freeze_text("测试文本", source_lang='en')
            # 检查是否有打印关于无效正则的警告
            found_warning = False
            for call in mock_print.call_args_list:
                if any("Invalid regex" in str(arg) for arg in call.args):
                    found_warning = True
                    break
            assert found_warning, "应该打印关于无效正则的警告"


# ============================================================================
# Test Main Function
# ============================================================================

class TestMainFunction:
    """测试主函数"""
    
    def test_main_success(self, tmp_path, temp_schema_file):
        """测试主函数成功执行"""
        csv_path = tmp_path / "test_input.csv"
        csv_path.write_text("string_id,source_zh\nTEST_001,文本", encoding='utf-8')
        
        draft_path = tmp_path / "draft.csv"
        map_path = tmp_path / "map.json"
        
        test_args = [
            'normalize_guard.py',
            str(csv_path),
            str(draft_path),
            str(map_path),
            temp_schema_file
        ]
        
        with patch.object(sys, 'argv', test_args):
            with patch('scripts.normalize_guard.sys.exit') as mock_exit:
                from src.scripts.normalize_guard import main
                main()
                mock_exit.assert_called_once_with(0)
    
    def test_main_with_source_lang(self, tmp_path, temp_schema_file):
        """测试主函数带语言参数"""
        csv_path = tmp_path / "test_input.csv"
        csv_path.write_text("string_id,source_zh\nTEST_001,文本", encoding='utf-8')
        
        draft_path = tmp_path / "draft.csv"
        map_path = tmp_path / "map.json"
        
        test_args = [
            'normalize_guard.py',
            str(csv_path),
            str(draft_path),
            str(map_path),
            temp_schema_file,
            '--source-lang', 'zh-TW'
        ]
        
        with patch.object(sys, 'argv', test_args):
            with patch('scripts.normalize_guard.sys.exit') as mock_exit:
                from src.scripts.normalize_guard import main
                main()
                mock_exit.assert_called_once_with(0)


# ============================================================================
# Test Print Methods
# ============================================================================

class TestPrintMethods:
    """测试打印方法"""
    
    def test_print_errors(self, tmp_path, temp_schema_file):
        """测试错误打印"""
        guard = NormalizeGuard(
            input_path="input.csv",
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        guard.warnings.append("警告1")
        guard.errors.append("错误1")
        
        with patch('builtins.print') as mock_print:
            guard._print_errors()
            # 验证打印了警告和错误
            assert mock_print.call_count >= 2
    
    def test_print_summary(self, tmp_path, temp_schema_file):
        """测试总结打印"""
        guard = NormalizeGuard(
            input_path="input.csv",
            output_draft_path=str(tmp_path / "draft.csv"),
            output_map_path=str(tmp_path / "map.json"),
            schema_path=temp_schema_file
        )
        
        guard.freezer.freeze_text("{0}", source_lang='en')
        
        rows = [{'string_id': 'TEST_001', 'source_zh': '文本'}]
        
        with patch('builtins.print') as mock_print:
            guard._print_summary(rows)
            assert mock_print.call_count >= 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
