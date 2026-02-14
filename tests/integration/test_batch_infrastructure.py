#!/usr/bin/env python3
"""批次基础设施单元测试"""

import unittest
import json
import os
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from runtime_adapter import BatchConfig, log_llm_progress, parse_llm_response, get_batch_config


class TestBatchConfig(unittest.TestCase):
    """测试批次配置管理"""

    def test_load_config(self):
        """测试配置加载"""
        config = get_batch_config()
        self.assertIsNotNone(config.models)
        self.assertIn("gpt-4.1-mini", config.models)

    def test_get_batch_size_normal(self):
        """测试获取常规批次大小"""
        config = get_batch_config()

        # gpt-4.1-mini: max_batch_size=50
        size = config.get_batch_size("gpt-4.1-mini", "normal")
        self.assertEqual(size, 50)

        # claude-haiku: max_batch_size=50
        size = config.get_batch_size("claude-haiku-4-5-20251001", "normal")
        self.assertEqual(size, 50)

    def test_get_batch_size_long_text(self):
        """测试获取长文本批次大小"""
        config = get_batch_config()

        # gpt-4.1-mini: max_batch_size_long_text=1
        size = config.get_batch_size("gpt-4.1-mini", "long_text")
        self.assertEqual(size, 1)

        # claude-haiku: max_batch_size_long_text=10
        size = config.get_batch_size("claude-haiku-4-5-20251001", "long_text")
        self.assertEqual(size, 10)

    def test_get_cooldown(self):
        """测试获取冷却期"""
        config = get_batch_config()

        # gpt-4.1-mini: cooldown_required=0
        cooldown = config.get_cooldown("gpt-4.1-mini")
        self.assertEqual(cooldown, 0)

        # claude-haiku: cooldown_required=30
        cooldown = config.get_cooldown("claude-haiku-4-5-20251001")
        self.assertEqual(cooldown, 30)

    def test_get_timeout(self):
        """测试获取超时配置"""
        config = get_batch_config()

        # normal timeout
        timeout = config.get_timeout("gpt-4.1-mini", "normal")
        self.assertEqual(timeout, 180)

        # long_text timeout
        timeout = config.get_timeout("gpt-4.1-mini", "long_text")
        self.assertEqual(timeout, 300)


class TestLogProgress(unittest.TestCase):
    """测试进度日志"""

    def setUp(self):
        """测试前准备"""
        self.test_log = "reports/test_progress.jsonl"
        if os.path.exists(self.test_log):
            os.remove(self.test_log)

    def tearDown(self):
        """测试后清理"""
        if os.path.exists(self.test_log):
            os.remove(self.test_log)

    def test_log_creation(self):
        """测试日志创建"""
        log_llm_progress("test_step", "batch_complete", {
            "batch_index": 1,
            "total_batches": 5,
            "batch_size": 10,
            "status": "SUCCESS",
            "latency_ms": 12000
        }, log_file=self.test_log)

        self.assertTrue(os.path.exists(self.test_log))

    def test_log_format(self):
        """测试日志格式"""
        log_llm_progress("test_step", "batch_complete", {
            "batch_index": 1,
            "total_batches": 5,
            "status": "SUCCESS"
        }, log_file=self.test_log)

        with open(self.test_log, "r", encoding="utf-8") as f:
            line = f.readline()
            event = json.loads(line)

            self.assertIn("timestamp", event)
            self.assertEqual(event["step"], "test_step")
            self.assertEqual(event["event"], "batch_complete")
            self.assertEqual(event["data"]["status"], "SUCCESS")


class TestParseResponse(unittest.TestCase):
    """测试响应解析"""

    def test_parse_clean_json(self):
        """测试解析干净的 JSON"""
        response = '''{"items": [{"id": "1", "result": "test1"}, {"id": "2", "result": "test2"}]}'''
        expected = [{"id": "1"}, {"id": "2"}]

        items = parse_llm_response(response, expected)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["id"], "1")

    def test_parse_markdown_wrapped(self):
        """测试解析 Markdown 包裹的 JSON"""
        response = '''```json
{"items": [{"id": "1", "result": "test1"}]}
```'''
        expected = [{"id": "1"}]

        items = parse_llm_response(response, expected)
        self.assertEqual(len(items), 1)

    def test_parse_missing_items(self):
        """测试缺少 items 键"""
        response = '''{"data": [{"id": "1"}]}'''
        expected = [{"id": "1"}]

        with self.assertRaises(ValueError) as ctx:
            parse_llm_response(response, expected)

        self.assertIn("Missing 'items' key", str(ctx.exception))

    def test_parse_id_mismatch(self):
        """测试 ID 不匹配"""
        response = '''{"items": [{"id": "1"}, {"id": "3"}]}'''
        expected = [{"id": "1"}, {"id": "2"}]

        with self.assertRaises(ValueError) as ctx:
            parse_llm_response(response, expected)

        self.assertIn("ID mismatch", str(ctx.exception))


if __name__ == "__main__":
    # 切换到项目根目录以正确加载配置
    os.chdir(Path(__file__).parent.parent)
    
    # 运行测试
    unittest.main(verbosity=2)
