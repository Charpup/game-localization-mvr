#!/usr/bin/env python3
"""批次基础设施单元测试"""

import unittest
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from runtime_adapter import BatchConfig, LLMClient, log_llm_progress, parse_llm_response, get_batch_config


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

        # gpt-4.1-mini: max_batch_size=10
        size = config.get_batch_size("gpt-4.1-mini", "normal")
        self.assertEqual(size, 10)

        # claude-haiku: max_batch_size=25
        size = config.get_batch_size("claude-haiku-4-5-20251001", "normal")
        self.assertEqual(size, 25)

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

        # claude-haiku: cooldown_required=0
        cooldown = config.get_cooldown("claude-haiku-4-5-20251001")
        self.assertEqual(cooldown, 0)

    def test_get_timeout(self):
        """测试获取超时配置"""
        config = get_batch_config()

        # normal timeout
        timeout = config.get_timeout("gpt-4.1-mini", "normal")
        self.assertEqual(timeout, 120)

        # long_text timeout
        timeout = config.get_timeout("gpt-4.1-mini", "long_text")
        self.assertEqual(timeout, 180)


class TestLogProgress(unittest.TestCase):
    """测试进度日志"""

    def setUp(self):
        """测试前准备"""
        self.temp_dir = TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.temp_dir.name)
        self.test_log = Path("reports/test_step_progress.jsonl")
        if self.test_log.exists():
            self.test_log.unlink()

    def tearDown(self):
        """测试后清理"""
        os.chdir(self.old_cwd)
        self.temp_dir.cleanup()

    def test_log_creation(self):
        """测试日志创建"""
        log_llm_progress("test_step", "batch_complete", {
            "batch_index": 1,
            "total_batches": 5,
            "batch_size": 10,
            "status": "SUCCESS",
            "latency_ms": 12000
        }, silent=True)

        self.assertTrue(self.test_log.exists())

    def test_log_format(self):
        """测试日志格式"""
        log_llm_progress("test_step", "batch_complete", {
            "batch_index": 1,
            "total_batches": 5,
            "status": "SUCCESS"
        }, silent=True)

        with self.test_log.open("r", encoding="utf-8") as f:
            line = f.readline()
            event = json.loads(line)

            self.assertIn("timestamp", event)
            self.assertEqual(event["step"], "test_step")
            self.assertEqual(event["event"], "batch_complete")
            self.assertEqual(event["status"], "SUCCESS")


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
        """测试 data 键也会被接受为有效结果列表"""
        response = '''{"data": [{"id": "1"}]}'''
        expected = [{"id": "1"}]

        items = parse_llm_response(response, expected)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "1")

    def test_parse_id_mismatch(self):
        """测试 ID 不匹配"""
        response = '''{"items": [{"id": "1"}, {"id": "3"}]}'''
        expected = [{"id": "1"}, {"id": "2"}]

        with self.assertRaises(ValueError) as ctx:
            parse_llm_response(response, expected)

        self.assertIn("PARSE_SCHEMA_MISMATCH", str(ctx.exception))

    def test_parse_thinking_wrapped_translations_with_string_id(self):
        """测试去除 thinking 并兼容 translations/string_id 结构"""
        response = """<thinking>internal reasoning</thinking>
{"translations": [{"string_id": "1", "target_ru": "Привет"}]}"""
        expected = [{"id": "1"}]

        items = parse_llm_response(response, expected)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "1")
        self.assertEqual(items[0]["target_ru"], "Привет")

    def test_parse_greedy_extracts_embedded_json_array(self):
        """测试从带前后缀文本中提取嵌入的 JSON 数组"""
        response = """Model summary:
[{"string_id": "1", "target_ru": "Alpha"}]
End of response."""
        expected = [{"id": "1"}]

        items = parse_llm_response(response, expected)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "1")
        self.assertEqual(items[0]["target_ru"], "Alpha")


class TestCredentialDiscovery(unittest.TestCase):
    """测试 API Key 发现与优先级"""

    def test_load_api_key_prefers_explicit_file_over_discovered_and_env(self):
        """显式文件应优先于自动发现文件和直接环境变量"""
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            explicit_path = tmp_path / "explicit.key"
            explicit_path.write_text("api key: explicit-key", encoding="utf-8")
            (tmp_path / ".llm_env").write_text("LLM_API_KEY=discovered-key", encoding="utf-8")

            old_cwd = os.getcwd()
            old_file = os.environ.get("LLM_API_KEY_FILE")
            old_key = os.environ.get("LLM_API_KEY")
            try:
                os.chdir(tmp_path)
                os.environ["LLM_API_KEY_FILE"] = str(explicit_path)
                os.environ["LLM_API_KEY"] = "env-key"

                self.assertEqual(LLMClient._load_api_key(), "explicit-key")
            finally:
                os.chdir(old_cwd)
                if old_file is None:
                    os.environ.pop("LLM_API_KEY_FILE", None)
                else:
                    os.environ["LLM_API_KEY_FILE"] = old_file
                if old_key is None:
                    os.environ.pop("LLM_API_KEY", None)
                else:
                    os.environ["LLM_API_KEY"] = old_key

    def test_load_api_key_discovers_working_directory_file_before_env_var(self):
        """工作目录凭据文件应在直接环境变量前被发现"""
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / ".llm_env").write_text("LLM_API_KEY=discovered-key", encoding="utf-8")

            old_cwd = os.getcwd()
            old_file = os.environ.get("LLM_API_KEY_FILE")
            old_key = os.environ.get("LLM_API_KEY")
            try:
                os.chdir(tmp_path)
                os.environ.pop("LLM_API_KEY_FILE", None)
                os.environ["LLM_API_KEY"] = "env-key"

                self.assertEqual(LLMClient._load_api_key(), "discovered-key")
            finally:
                os.chdir(old_cwd)
                if old_file is None:
                    os.environ.pop("LLM_API_KEY_FILE", None)
                else:
                    os.environ["LLM_API_KEY_FILE"] = old_file
                if old_key is None:
                    os.environ.pop("LLM_API_KEY", None)
                else:
                    os.environ["LLM_API_KEY"] = old_key


if __name__ == "__main__":
    # 切换到项目根目录以正确加载配置
    os.chdir(Path(__file__).parent.parent)
    
    # 运行测试
    unittest.main(verbosity=2)
