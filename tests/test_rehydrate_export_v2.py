#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test suite for rehydrate_export.py v2.0
目标: 90%+ 测试覆盖率
"""

import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 添加 scripts 到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from scripts.rehydrate_export import RehydrateExporter


class TestRehydrateExporterInit(unittest.TestCase):
    """测试 RehydrateExporter 初始化"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.translated_csv = Path(self.temp_dir) / 'translated.csv'
        self.placeholder_map = Path(self.temp_dir) / 'placeholder_map.json'
        self.final_csv = Path(self.temp_dir) / 'final.csv'
        
        # 创建空的占位符映射
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump({}, f)
    
    def tearDown(self):
        # 清理临时文件
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_default_initialization(self):
        """测试默认参数初始化"""
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        self.assertEqual(exporter.translated_csv, self.translated_csv)
        self.assertEqual(exporter.placeholder_map_path, self.placeholder_map)
        self.assertEqual(exporter.final_csv, self.final_csv)
        self.assertFalse(exporter.overwrite_mode)
        self.assertEqual(exporter.target_lang, "ru-RU")
        self.assertEqual(exporter.map_version, "unknown")
        self.assertEqual(exporter.total_rows, 0)
        self.assertEqual(exporter.tokens_restored, 0)
        self.assertEqual(exporter.punctuation_converted, 0)
    
    def test_overwrite_mode_initialization(self):
        """测试覆盖模式初始化"""
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv),
            overwrite_mode=True,
            target_lang="zh-CN"
        )
        
        self.assertTrue(exporter.overwrite_mode)
        self.assertEqual(exporter.target_lang, "zh-CN")
    
    def test_custom_punctuation_map_path(self):
        """测试自定义标点符号映射路径"""
        custom_path = Path(self.temp_dir) / 'custom_punctuation.yaml'
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv),
            punctuation_map_path=str(custom_path)
        )
        
        self.assertEqual(exporter.punctuation_map_path, custom_path)


class TestLoadPlaceholderMap(unittest.TestCase):
    """测试加载占位符映射"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.translated_csv = Path(self.temp_dir) / 'translated.csv'
        self.placeholder_map = Path(self.temp_dir) / 'placeholder_map.json'
        self.final_csv = Path(self.temp_dir) / 'final.csv'
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_load_v20_format(self):
        """测试加载 v2.0 格式 (有 metadata 和 mappings)"""
        data = {
            "metadata": {
                "version": "2.0",
                "created": "2026-02-14",
                "total_entries": 5
            },
            "mappings": {
                "PH_001": "Player",
                "PH_002": "NPC",
                "TAG_001": "<b>bold</b>"
            }
        }
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.load_placeholder_map()
        
        self.assertTrue(result)
        self.assertEqual(exporter.map_version, "2.0")
        self.assertEqual(exporter.placeholder_map["PH_001"], "Player")
        self.assertEqual(len(exporter.placeholder_map), 3)
    
    def test_load_v10_format(self):
        """测试加载 v1.0 格式 (直接是 dict)"""
        data = {
            "PH_001": "Player",
            "PH_002": "NPC",
            "TAG_001": "<b>bold</b>"
        }
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.load_placeholder_map()
        
        self.assertTrue(result)
        self.assertEqual(exporter.map_version, "1.0")
        self.assertEqual(exporter.placeholder_map["PH_001"], "Player")
        self.assertEqual(len(exporter.placeholder_map), 3)
    
    def test_load_missing_version_metadata(self):
        """测试加载缺少 version 的 metadata"""
        data = {
            "metadata": {
                "created": "2026-02-14"
            },
            "mappings": {
                "PH_001": "Player"
            }
        }
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.load_placeholder_map()
        
        self.assertTrue(result)
        self.assertEqual(exporter.map_version, "2.0")  # 默认值
    
    def test_load_file_not_found(self):
        """测试文件不存在"""
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(Path(self.temp_dir) / 'nonexistent.json'),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.load_placeholder_map()
        
        self.assertFalse(result)
    
    def test_load_invalid_json(self):
        """测试无效的 JSON"""
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            f.write("invalid json {")
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.load_placeholder_map()
        
        self.assertFalse(result)
    
    def test_load_empty_mapping(self):
        """测试空映射"""
        data = {
            "metadata": {"version": "2.0"},
            "mappings": {}
        }
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.load_placeholder_map()
        
        self.assertTrue(result)
        self.assertEqual(len(exporter.placeholder_map), 0)


class TestExtractTokens(unittest.TestCase):
    """测试 token 提取"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.translated_csv = Path(self.temp_dir) / 'translated.csv'
        self.placeholder_map = Path(self.temp_dir) / 'placeholder_map.json'
        self.final_csv = Path(self.temp_dir) / 'final.csv'
        
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump({}, f)
        
        self.exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_extract_single_token(self):
        """测试提取单个 token"""
        text = "Hello ⟦PH_001⟧, welcome!"
        tokens = self.exporter.extract_tokens(text)
        
        self.assertEqual(tokens, {"PH_001"})
    
    def test_extract_multiple_tokens(self):
        """测试提取多个 token"""
        text = "⟦PH_001⟧ attacks ⟦PH_002⟧ with ⟦TAG_001⟧"
        tokens = self.exporter.extract_tokens(text)
        
        self.assertEqual(tokens, {"PH_001", "PH_002", "TAG_001"})
    
    def test_extract_duplicate_tokens(self):
        """测试提取重复 token (应该去重)"""
        text = "⟦PH_001⟧ and ⟦PH_001⟧ are the same"
        tokens = self.exporter.extract_tokens(text)
        
        self.assertEqual(tokens, {"PH_001"})
    
    def test_extract_no_tokens(self):
        """测试没有 token 的文本"""
        text = "Hello, world!"
        tokens = self.exporter.extract_tokens(text)
        
        self.assertEqual(tokens, set())
    
    def test_extract_empty_text(self):
        """测试空文本"""
        text = ""
        tokens = self.exporter.extract_tokens(text)
        
        self.assertEqual(tokens, set())
    
    def test_extract_none_text(self):
        """测试 None 文本"""
        text = None
        tokens = self.exporter.extract_tokens(text)
        
        self.assertEqual(tokens, set())
    
    def test_extract_various_patterns(self):
        """测试各种 token 格式"""
        text = "⟦PH_999⟧ ⟦TAG_123⟧ ⟦PH_001⟧"
        tokens = self.exporter.extract_tokens(text)
        
        self.assertEqual(tokens, {"PH_999", "TAG_123", "PH_001"})


class TestRehydrateText(unittest.TestCase):
    """测试文本还原功能"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.translated_csv = Path(self.temp_dir) / 'translated.csv'
        self.placeholder_map = Path(self.temp_dir) / 'placeholder_map.json'
        self.final_csv = Path(self.temp_dir) / 'final.csv'
        
        data = {
            "metadata": {"version": "2.0"},
            "mappings": {
                "PH_001": "Player",
                "PH_002": "NPC",
                "TAG_001": "<b>bold</b>",
                "TAG_002": "{color:red}"
            }
        }
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        
        self.exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        self.exporter.load_placeholder_map()
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_rehydrate_single_token(self):
        """测试还原单个 token"""
        text = "Hello ⟦PH_001⟧!"
        result = self.exporter.rehydrate_text(text, "STR_001", 1)
        
        self.assertEqual(result, "Hello Player!")
        self.assertEqual(self.exporter.tokens_restored, 1)
    
    def test_rehydrate_multiple_tokens(self):
        """测试还原多个 token"""
        text = "⟦PH_001⟧ attacks ⟦PH_002⟧"
        result = self.exporter.rehydrate_text(text, "STR_002", 1)
        
        self.assertEqual(result, "Player attacks NPC")
        self.assertEqual(self.exporter.tokens_restored, 2)
    
    def test_rehydrate_tag_tokens(self):
        """测试还原 TAG token"""
        text = "This is ⟦TAG_001⟧text⟦TAG_001⟧"
        result = self.exporter.rehydrate_text(text, "STR_003", 1)
        
        self.assertEqual(result, "This is <b>bold</b>text<b>bold</b>")
    
    def test_rehydrate_no_tokens(self):
        """测试无 token 的文本"""
        text = "Hello, world!"
        result = self.exporter.rehydrate_text(text, "STR_004", 1)
        
        self.assertEqual(result, "Hello, world!")
    
    def test_rehydrate_empty_text(self):
        """测试空文本"""
        text = ""
        result = self.exporter.rehydrate_text(text, "STR_005", 1)
        
        self.assertEqual(result, "")
    
    def test_rehydrate_none_text(self):
        """测试 None 文本"""
        text = None
        result = self.exporter.rehydrate_text(text, "STR_006", 1)
        
        self.assertIsNone(result)
    
    def test_rehydrate_unknown_token(self):
        """测试未知的 token (返回 None 并记录错误)"""
        # 使用符合格式的未知 token (PH_999 不在映射中)
        text = "Hello ⟦PH_999⟧!"
        result = self.exporter.rehydrate_text(text, "STR_007", 1)
        
        # 未知 token 导致返回 None
        self.assertIsNone(result)
        # 错误被记录在列表中
        self.assertEqual(len(self.exporter.errors), 1)
        self.assertIn("Unknown token", self.exporter.errors[0])
    
    def test_rehydrate_mixed_known_unknown_tokens(self):
        """测试混合已知和未知 token"""
        text = "⟦PH_001⟧ and ⟦PH_999⟧"
        result = self.exporter.rehydrate_text(text, "STR_008", 1)
        
        # 有未知 token 时返回 None
        self.assertIsNone(result)
        self.assertEqual(len(self.exporter.errors), 1)
    
    def test_rehydrate_duplicate_tokens(self):
        """测试重复 token 的还原 (应该都替换，但计数时去重)"""
        text = "⟦PH_001⟧ and ⟦PH_001⟧ are the same"
        result = self.exporter.rehydrate_text(text, "STR_009", 1)
        
        self.assertEqual(result, "Player and Player are the same")
        # 代码使用 set 去重，所以只计数一次
        self.assertEqual(self.exporter.tokens_restored, 1)
    
    def test_rehydrate_special_characters_in_original(self):
        """测试原始值中包含特殊字符"""
        text = "Color: ⟦TAG_002⟧"
        result = self.exporter.rehydrate_text(text, "STR_010", 1)
        
        self.assertEqual(result, "Color: {color:red}")


class TestNormalizePunctuation(unittest.TestCase):
    """测试标点符号转换"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.translated_csv = Path(self.temp_dir) / 'translated.csv'
        self.placeholder_map = Path(self.temp_dir) / 'placeholder_map.json'
        self.final_csv = Path(self.temp_dir) / 'final.csv'
        
        # 创建临时标点符号配置
        config_dir = Path(self.temp_dir) / 'config' / 'punctuation'
        config_dir.mkdir(parents=True)
        
        base_yaml = config_dir / 'base.yaml'
        with open(base_yaml, 'w', encoding='utf-8') as f:
            f.write("replace:\n  '...': '…'\n  '【': '«'\n  '】': '»'\n")
        
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump({"mappings": {}}, f)
        
        self.exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('scripts.lib_text.sanitize_punctuation')
    @patch('scripts.lib_text.load_punctuation_config')
    def test_normalize_punctuation_basic(self, mock_load, mock_sanitize):
        """测试基本标点符号转换"""
        mock_load.return_value = [{'source': '...', 'target': '…'}]
        mock_sanitize.return_value = "Loading…"
        
        self.exporter.punctuation_mappings = [{'source': '...', 'target': '…'}]
        result = self.exporter.normalize_punctuation("Loading...")
        
        self.assertEqual(result, "Loading…")
        self.assertEqual(self.exporter.punctuation_converted, 1)
    
    @patch('scripts.lib_text.sanitize_punctuation')
    @patch('scripts.lib_text.load_punctuation_config')
    def test_normalize_no_change(self, mock_load, mock_sanitize):
        """测试无变化的文本"""
        mock_load.return_value = []
        mock_sanitize.return_value = "Hello world"
        
        self.exporter.punctuation_mappings = []
        result = self.exporter.normalize_punctuation("Hello world")
        
        self.assertEqual(result, "Hello world")
        self.assertEqual(self.exporter.punctuation_converted, 0)
    
    def test_normalize_empty_text(self):
        """测试空文本"""
        self.exporter.punctuation_mappings = [{'source': '...', 'target': '…'}]
        result = self.exporter.normalize_punctuation("")
        
        self.assertEqual(result, "")
    
    def test_normalize_none_text(self):
        """测试 None 文本"""
        self.exporter.punctuation_mappings = [{'source': '...', 'target': '…'}]
        result = self.exporter.normalize_punctuation(None)
        
        self.assertIsNone(result)
    
    def test_normalize_no_mappings(self):
        """测试无映射配置"""
        self.exporter.punctuation_mappings = []
        result = self.exporter.normalize_punctuation("Loading...")
        
        self.assertEqual(result, "Loading...")


class TestLoadPunctuationMappings(unittest.TestCase):
    """测试加载标点符号映射"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.translated_csv = Path(self.temp_dir) / 'data' / 'translated.csv'
        self.placeholder_map = Path(self.temp_dir) / 'placeholder_map.json'
        self.final_csv = Path(self.temp_dir) / 'final.csv'
        
        # 创建必要的目录结构
        self.translated_csv.parent.mkdir(parents=True)
        self.config_dir = Path(self.temp_dir) / 'config' / 'punctuation'
        self.config_dir.mkdir(parents=True)
        
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump({"mappings": {}}, f)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('scripts.lib_text.load_punctuation_config')
    def test_load_punctuation_mappings_success(self, mock_load):
        """测试成功加载标点符号映射"""
        mock_load.return_value = [
            {'source': '...', 'target': '…'},
            {'source': '【', 'target': '«'}
        ]
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.load_punctuation_mappings()
        
        self.assertTrue(result)
        self.assertEqual(len(exporter.punctuation_mappings), 2)
        mock_load.assert_called_once()
    
    @patch('scripts.lib_text.load_punctuation_config')
    def test_load_punctuation_mappings_empty(self, mock_load):
        """测试加载空标点符号映射"""
        mock_load.return_value = []
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.load_punctuation_mappings()
        
        self.assertTrue(result)
        self.assertEqual(len(exporter.punctuation_mappings), 0)


class TestNormalizePunctuation(unittest.TestCase):
    """测试标点符号转换"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.translated_csv = Path(self.temp_dir) / 'translated.csv'
        self.placeholder_map = Path(self.temp_dir) / 'placeholder_map.json'
        self.final_csv = Path(self.temp_dir) / 'final.csv'
        
        # 创建临时标点符号配置
        config_dir = Path(self.temp_dir) / 'config' / 'punctuation'
        config_dir.mkdir(parents=True)
        
        base_yaml = config_dir / 'base.yaml'
        with open(base_yaml, 'w', encoding='utf-8') as f:
            f.write("replace:\n  '...': '…'\n  '【': '«'\n  '】': '»'\n")
        
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump({"mappings": {}}, f)
        
        self.exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('scripts.lib_text.sanitize_punctuation')
    @patch('scripts.lib_text.load_punctuation_config')
    def test_normalize_punctuation_basic(self, mock_load, mock_sanitize):
        """测试基本标点符号转换"""
        mock_load.return_value = [{'source': '...', 'target': '…'}]
        mock_sanitize.return_value = "Loading…"
        
        self.exporter.punctuation_mappings = [{'source': '...', 'target': '…'}]
        result = self.exporter.normalize_punctuation("Loading...")
        
        self.assertEqual(result, "Loading…")
        self.assertEqual(self.exporter.punctuation_converted, 1)
    
    @patch('scripts.lib_text.sanitize_punctuation')
    @patch('scripts.lib_text.load_punctuation_config')
    def test_normalize_no_change(self, mock_load, mock_sanitize):
        """测试无变化的文本"""
        mock_load.return_value = []
        mock_sanitize.return_value = "Hello world"
        
        self.exporter.punctuation_mappings = []
        result = self.exporter.normalize_punctuation("Hello world")
        
        self.assertEqual(result, "Hello world")
        self.assertEqual(self.exporter.punctuation_converted, 0)
    
    def test_normalize_empty_text(self):
        """测试空文本"""
        self.exporter.punctuation_mappings = [{'source': '...', 'target': '…'}]
        result = self.exporter.normalize_punctuation("")
        
        self.assertEqual(result, "")
    
    def test_normalize_none_text(self):
        """测试 None 文本"""
        self.exporter.punctuation_mappings = [{'source': '...', 'target': '…'}]
        result = self.exporter.normalize_punctuation(None)
        
        self.assertIsNone(result)
    
    def test_normalize_no_mappings(self):
        """测试无映射配置"""
        self.exporter.punctuation_mappings = []
        result = self.exporter.normalize_punctuation("Loading...")
        
        self.assertEqual(result, "Loading...")


class TestProcessCSV(unittest.TestCase):
    """测试 CSV 处理功能"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.translated_csv = Path(self.temp_dir) / 'translated.csv'
        self.placeholder_map = Path(self.temp_dir) / 'placeholder_map.json'
        self.final_csv = Path(self.temp_dir) / 'output' / 'final.csv'
        
        # 创建占位符映射
        data = {
            "metadata": {"version": "2.0"},
            "mappings": {
                "PH_001": "Player",
                "PH_002": "NPC"
            }
        }
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump(data, f)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def create_csv(self, data, fieldnames=None):
        """辅助函数: 创建 CSV 文件"""
        if fieldnames is None:
            fieldnames = ['string_id', 'source_text', 'target_text']
        
        with open(self.translated_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
    
    def test_process_csv_basic(self):
        """测试基本 CSV 处理"""
        data = [
            {'string_id': 'STR_001', 'source_text': 'Hello', 'target_text': '你好 ⟦PH_001⟧'},
            {'string_id': 'STR_002', 'source_text': 'Attack', 'target_text': '⟦PH_001⟧攻击⟦PH_002⟧'}
        ]
        self.create_csv(data)
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.run()
        
        self.assertTrue(result)
        self.assertEqual(exporter.total_rows, 2)
        self.assertEqual(exporter.tokens_restored, 3)
        
        # 验证输出文件
        self.assertTrue(self.final_csv.exists())
        with open(self.final_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]['rehydrated_text'], '你好 Player')
            self.assertEqual(rows[1]['rehydrated_text'], 'Player攻击NPC')
    
    def test_process_csv_overwrite_mode(self):
        """测试覆盖模式"""
        data = [
            {'string_id': 'STR_001', 'source_text': 'Hello', 'target_text': '你好 ⟦PH_001⟧'}
        ]
        self.create_csv(data)
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv),
            overwrite_mode=True
        )
        
        result = exporter.run()
        
        self.assertTrue(result)
        
        # 验证输出文件 - target_text 应该被修改
        with open(self.final_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            self.assertEqual(rows[0]['target_text'], '你好 Player')
            # 不应该有 rehydrated_text 列
            self.assertNotIn('rehydrated_text', rows[0])
    
    def test_process_csv_different_target_fields(self):
        """测试不同的目标字段名"""
        # 测试 translated_text 字段
        data = [
            {'string_id': 'STR_001', 'source_text': 'Hello', 'translated_text': '你好 ⟦PH_001⟧'}
        ]
        self.create_csv(data, ['string_id', 'source_text', 'translated_text'])
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.run()
        self.assertTrue(result)
    
    def test_process_csv_target_zh_field(self):
        """测试 target_zh 字段"""
        data = [
            {'string_id': 'STR_001', 'source_text': 'Hello', 'target_zh': '你好 ⟦PH_001⟧'}
        ]
        self.create_csv(data, ['string_id', 'source_text', 'target_zh'])
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.run()
        self.assertTrue(result)
    
    def test_process_csv_tokenized_target_field(self):
        """测试 tokenized_target 字段"""
        data = [
            {'string_id': 'STR_001', 'source_text': 'Hello', 'tokenized_target': '你好 ⟦PH_001⟧'}
        ]
        self.create_csv(data, ['string_id', 'source_text', 'tokenized_target'])
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.run()
        self.assertTrue(result)
    
    def test_process_csv_missing_string_id(self):
        """测试缺少 string_id 列"""
        data = [
            {'id': 'STR_001', 'text': 'Hello'}
        ]
        self.create_csv(data, ['id', 'text'])
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.run()
        self.assertFalse(result)
    
    def test_process_csv_no_target_field(self):
        """测试没有目标字段"""
        data = [
            {'string_id': 'STR_001', 'source_text': 'Hello'}
        ]
        self.create_csv(data, ['string_id', 'source_text'])
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.run()
        self.assertFalse(result)
    
    def test_process_csv_unknown_token(self):
        """测试包含未知 token 的 CSV (应该失败)"""
        data = [
            {'string_id': 'STR_001', 'source_text': 'Hello', 'target_text': '你好 ⟦PH_999⟧'}
        ]
        self.create_csv(data)
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.run()
        # 有未知 token 时应该返回 False
        self.assertFalse(result)
        self.assertEqual(len(exporter.errors), 1)
    
    def test_process_csv_empty_rows(self):
        """测试空行处理"""
        data = [
            {'string_id': 'STR_001', 'source_text': 'Hello', 'target_text': ''},
            {'string_id': 'STR_002', 'source_text': 'World', 'target_text': None}
        ]
        self.create_csv(data)
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.run()
        self.assertTrue(result)
        self.assertEqual(exporter.total_rows, 2)
    
    def test_process_csv_file_not_found(self):
        """测试 CSV 文件不存在"""
        exporter = RehydrateExporter(
            translated_csv=str(Path(self.temp_dir) / 'nonexistent.csv'),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.run()
        self.assertFalse(result)


class TestWriteFinalCSV(unittest.TestCase):
    """测试写入最终 CSV 功能"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.translated_csv = Path(self.temp_dir) / 'translated.csv'
        self.placeholder_map = Path(self.temp_dir) / 'placeholder_map.json'
        self.final_csv = Path(self.temp_dir) / 'output' / 'final.csv'
        
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump({"mappings": {}}, f)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_write_creates_directory(self):
        """测试自动创建输出目录"""
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        rows = [{'string_id': 'STR_001', 'target_text': 'Hello'}]
        result = exporter.write_final_csv(rows, ['string_id', 'target_text'], 'target_text')
        
        self.assertTrue(result)
        self.assertTrue(self.final_csv.parent.exists())
        self.assertTrue(self.final_csv.exists())
    
    def test_write_add_column_mode(self):
        """测试添加列模式"""
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        exporter.overwrite_mode = False
        
        rows = [{'string_id': 'STR_001', 'target_text': 'Hello', 'rehydrated_text': 'World'}]
        result = exporter.write_final_csv(rows, ['string_id', 'target_text'], 'target_text')
        
        self.assertTrue(result)
        
        with open(self.final_csv, 'r', encoding='utf-8-sig') as f:
            content = f.read()
            self.assertIn('rehydrated_text', content)
    
    def test_write_overwrite_mode(self):
        """测试覆盖模式"""
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv),
            overwrite_mode=True
        )
        
        rows = [{'string_id': 'STR_001', 'target_text': 'Modified'}]
        result = exporter.write_final_csv(rows, ['string_id', 'target_text'], 'target_text')
        
        self.assertTrue(result)
        
        with open(self.final_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            row = next(reader)
            self.assertEqual(row['target_text'], 'Modified')


class TestPrintSummary(unittest.TestCase):
    """测试打印总结功能"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.translated_csv = Path(self.temp_dir) / 'translated.csv'
        self.placeholder_map = Path(self.temp_dir) / 'placeholder_map.json'
        self.final_csv = Path(self.temp_dir) / 'final.csv'
        
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump({"mappings": {}}, f)
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    @patch('builtins.print')
    def test_print_summary(self, mock_print):
        """测试总结输出"""
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        exporter.map_version = "2.0"
        exporter.total_rows = 100
        exporter.tokens_restored = 250
        exporter.punctuation_converted = 50
        
        exporter.print_summary()
        
        # 验证打印了关键信息
        print_calls = [call for call in mock_print.call_args_list]
        self.assertTrue(len(print_calls) > 0)


class TestEdgeCases(unittest.TestCase):
    """测试边界情况"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.translated_csv = Path(self.temp_dir) / 'translated.csv'
        self.placeholder_map = Path(self.temp_dir) / 'placeholder_map.json'
        self.final_csv = Path(self.temp_dir) / 'final.csv'
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_unicode_in_placeholder_value(self):
        """测试占位符值包含 Unicode 字符"""
        data = {
            "metadata": {"version": "2.0"},
            "mappings": {
                "PH_001": "玩家 🎮",
                "PH_002": "日本語テキスト"
            }
        }
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        
        csv_data = [
            {'string_id': 'STR_001', 'target_text': '⟦PH_001⟧ 你好 ⟦PH_002⟧'}
        ]
        with open(self.translated_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['string_id', 'target_text'])
            writer.writeheader()
            writer.writerows(csv_data)
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.run()
        self.assertTrue(result)
    
    def test_large_csv_processing(self):
        """测试大量数据行处理"""
        data = {
            "metadata": {"version": "2.0"},
            "mappings": {"PH_001": "Player"}
        }
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        
        # 创建 1000 行数据
        csv_data = [
            {'string_id': f'STR_{i:04d}', 'target_text': f'你好 ⟦PH_001⟧ {i}'}
            for i in range(1000)
        ]
        with open(self.translated_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['string_id', 'target_text'])
            writer.writeheader()
            writer.writerows(csv_data)
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.run()
        self.assertTrue(result)
        self.assertEqual(exporter.total_rows, 1000)
        self.assertEqual(exporter.tokens_restored, 1000)
    
    def test_nested_brackets_in_text(self):
        """测试文本中包含嵌套括号"""
        data = {
            "metadata": {"version": "2.0"},
            "mappings": {"PH_001": "Value"}
        }
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        
        csv_data = [
            {'string_id': 'STR_001', 'target_text': 'Text [with] brackets ⟦PH_001⟧'}
        ]
        with open(self.translated_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['string_id', 'target_text'])
            writer.writeheader()
            writer.writerows(csv_data)
        
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.run()
        self.assertTrue(result)


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.translated_csv = Path(self.temp_dir) / 'translated.csv'
        self.placeholder_map = Path(self.temp_dir) / 'placeholder_map.json'
        self.final_csv = Path(self.temp_dir) / 'output' / 'final.csv'
    
    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_full_workflow(self):
        """测试完整工作流程"""
        # 创建占位符映射
        placeholder_data = {
            "metadata": {
                "version": "2.0",
                "created": "2026-02-14"
            },
            "mappings": {
                "PH_001": "Player",
                "PH_002": "NPC",
                "TAG_001": "<b>",
                "TAG_002": "</b>"
            }
        }
        with open(self.placeholder_map, 'w', encoding='utf-8') as f:
            json.dump(placeholder_data, f)
        
        # 创建翻译 CSV
        csv_data = [
            {
                'string_id': 'DIALOG_001',
                'source_text': 'Hello [PH_001], welcome!',
                'target_text': '你好 ⟦PH_001⟧，欢迎！'
            },
            {
                'string_id': 'DIALOG_002',
                'source_text': '[PH_001] attacks [PH_002]',
                'target_text': '⟦PH_001⟧攻击了⟦PH_002⟧'
            },
            {
                'string_id': 'UI_001',
                'source_text': '<b>Bold text</b>',
                'target_text': '⟦TAG_001⟧粗体文本⟦TAG_002⟧'
            }
        ]
        with open(self.translated_csv, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['string_id', 'source_text', 'target_text'])
            writer.writeheader()
            writer.writerows(csv_data)
        
        # 执行导出
        exporter = RehydrateExporter(
            translated_csv=str(self.translated_csv),
            placeholder_map=str(self.placeholder_map),
            final_csv=str(self.final_csv)
        )
        
        result = exporter.run()
        
        # 验证结果
        self.assertTrue(result)
        self.assertEqual(exporter.total_rows, 3)
        # PH_001 出现2次但只计数唯一 token (每行去重): 2+1+2 = 5
        self.assertEqual(exporter.tokens_restored, 5)
        self.assertTrue(self.final_csv.exists())
        
        # 验证输出内容
        with open(self.final_csv, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            
            self.assertEqual(len(rows), 3)
            self.assertEqual(rows[0]['rehydrated_text'], '你好 Player，欢迎！')
            self.assertEqual(rows[1]['rehydrated_text'], 'Player攻击了NPC')
            self.assertEqual(rows[2]['rehydrated_text'], '<b>粗体文本</b>')


class TestMainFunction(unittest.TestCase):
    """测试 main 函数"""
    
    @patch('sys.argv', ['rehydrate_export.py', 'input.csv', 'map.json', 'output.csv'])
    @patch('scripts.rehydrate_export.RehydrateExporter')
    def test_main_basic(self, mock_exporter_class):
        """测试 main 函数基本调用"""
        mock_exporter = Mock()
        mock_exporter.run.return_value = True
        mock_exporter_class.return_value = mock_exporter
        
        from scripts.rehydrate_export import main
        
        with self.assertRaises(SystemExit) as cm:
            main()
        
        self.assertEqual(cm.exception.code, 0)
        mock_exporter_class.assert_called_once_with(
            translated_csv='input.csv',
            placeholder_map='map.json',
            final_csv='output.csv',
            overwrite_mode=False
        )
    
    @patch('sys.argv', ['rehydrate_export.py', 'input.csv', 'map.json', 'output.csv', '--overwrite'])
    @patch('scripts.rehydrate_export.RehydrateExporter')
    def test_main_overwrite_flag(self, mock_exporter_class):
        """测试 main 函数带 --overwrite 标志"""
        mock_exporter = Mock()
        mock_exporter.run.return_value = True
        mock_exporter_class.return_value = mock_exporter
        
        from scripts.rehydrate_export import main
        
        with self.assertRaises(SystemExit) as cm:
            main()
        
        self.assertEqual(cm.exception.code, 0)
        mock_exporter_class.assert_called_once_with(
            translated_csv='input.csv',
            placeholder_map='map.json',
            final_csv='output.csv',
            overwrite_mode=True
        )
    
    @patch('sys.argv', ['rehydrate_export.py', 'input.csv', 'map.json', 'output.csv'])
    @patch('scripts.rehydrate_export.RehydrateExporter')
    def test_main_failure(self, mock_exporter_class):
        """测试 main 函数失败退出"""
        mock_exporter = Mock()
        mock_exporter.run.return_value = False
        mock_exporter_class.return_value = mock_exporter
        
        from scripts.rehydrate_export import main
        
        with self.assertRaises(SystemExit) as cm:
            main()
        
        self.assertEqual(cm.exception.code, 1)
    
    @patch('sys.argv', ['rehydrate_export.py'])
    def test_main_usage_error(self):
        """测试 main 函数参数错误"""
        from scripts.rehydrate_export import main
        
        with self.assertRaises(SystemExit) as cm:
            main()
        
        self.assertEqual(cm.exception.code, 1)


if __name__ == '__main__':
    unittest.main(verbosity=2)
