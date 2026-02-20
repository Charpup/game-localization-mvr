"""Unit tests for multi-language support."""
import pytest
from pathlib import Path
import yaml
import json


class TestLanguageConfiguration:
    """Tests for language configuration files."""

    def test_language_pairs_yaml_exists(self, project_root):
        """Test that language_pairs.yaml exists and is valid."""
        config_path = project_root / 'src' / 'config' / 'language_pairs.yaml'
        assert config_path.exists(), f"language_pairs.yaml not found at {config_path}"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        assert 'language_pairs' in config, "Missing 'language_pairs' key"
        assert 'zh-cn_en-us' in config['language_pairs'], "Missing 'zh-cn_en-us' pair"
        assert 'zh-cn_ru-ru' in config['language_pairs'], "Missing 'zh-cn_ru-ru' pair"

    def test_language_pairs_structure(self, language_pairs_config):
        """Test that language pairs have required fields."""
        pairs = language_pairs_config.get('language_pairs', {})
        for pair_key, pair_config in pairs.items():
            assert 'name' in pair_config, f"Missing 'name' in {pair_key}"
            assert 'source' in pair_config, f"Missing 'source' in {pair_key}"
            assert 'target' in pair_config, f"Missing 'target' in {pair_key}"
            assert 'default_model' in pair_config, f"Missing 'default_model' in {pair_key}"

    def test_zh_en_pair_configuration(self, language_pairs_config):
        """Test specific configuration for ZH-EN pair."""
        zh_en = language_pairs_config.get('language_pairs', {}).get('zh-cn_en-us', {})
        assert zh_en.get('source') == 'zh-CN', "Source should be zh-CN"
        assert zh_en.get('target') == 'en-US', "Target should be en-US"
        assert zh_en.get('default_model') == 'kimi-k2.5', "Default model should be kimi-k2.5"


class TestENPrompts:
    """Tests for EN prompt templates."""

    def test_en_prompts_exist(self, project_root):
        """Test that EN prompt templates exist."""
        prompts_dir = project_root / 'src' / 'config' / 'prompts' / 'en'
        assert (prompts_dir / 'batch_translate_system.txt').exists(), \
            "Missing batch_translate_system.txt"
        assert (prompts_dir / 'glossary_translate_system.txt').exists(), \
            "Missing glossary_translate_system.txt"
        assert (prompts_dir / 'soft_qa_system.txt').exists(), \
            "Missing soft_qa_system.txt"

    def test_batch_translate_system_prompt_content(self, project_root):
        """Test batch translate system prompt has required content."""
        prompt_path = project_root / 'src' / 'config' / 'prompts' / 'en' / 'batch_translate_system.txt'
        if prompt_path.exists():
            content = prompt_path.read_text()
            assert len(content) > 0, "Prompt should not be empty"
            # Check for common translation prompt elements
            assert any(word in content.lower() for word in ['translate', 'translation']), \
                "Prompt should mention translation"

    def test_glossary_translate_system_prompt_content(self, project_root):
        """Test glossary translate system prompt has required content."""
        prompt_path = project_root / 'src' / 'config' / 'prompts' / 'en' / 'glossary_translate_system.txt'
        if prompt_path.exists():
            content = prompt_path.read_text()
            assert len(content) > 0, "Prompt should not be empty"
            assert any(word in content.lower() for word in ['glossary', 'term', 'terminology']), \
                "Prompt should mention glossary or terms"

    def test_soft_qa_system_prompt_content(self, project_root):
        """Test soft QA system prompt has required content."""
        prompt_path = project_root / 'src' / 'config' / 'prompts' / 'en' / 'soft_qa_system.txt'
        if prompt_path.exists():
            content = prompt_path.read_text()
            assert len(content) > 0, "Prompt should not be empty"
            assert any(word in content.lower() for word in ['qa', 'quality', 'check', 'review']), \
                "Prompt should mention QA or quality"


class TestENQARules:
    """Tests for EN QA rules configuration."""

    def test_en_qa_rules_exist(self, project_root):
        """Test that EN QA rules exist."""
        qa_rules_path = project_root / 'src' / 'config' / 'qa_rules' / 'en.yaml'
        assert qa_rules_path.exists(), f"en.yaml not found at {qa_rules_path}"

    def test_en_qa_rules_structure(self, en_qa_rules):
        """Test EN QA rules structure."""
        assert en_qa_rules.get('language') == 'en-US', "Language should be en-US"
        assert 'grammar_rules' in en_qa_rules, "Missing 'grammar_rules'"
        assert 'forbidden_patterns' in en_qa_rules, "Missing 'forbidden_patterns'"

    def test_grammar_rules_format(self, en_qa_rules):
        """Test grammar rules have proper format."""
        rules = en_qa_rules.get('grammar_rules', [])
        for rule in rules:
            assert 'name' in rule, "Grammar rule missing 'name'"
            assert 'pattern' in rule, f"Grammar rule '{rule.get('name')}' missing 'pattern'"

    def test_forbidden_patterns_format(self, en_qa_rules):
        """Test forbidden patterns have proper format."""
        patterns = en_qa_rules.get('forbidden_patterns', [])
        for pattern in patterns:
            assert 'pattern' in pattern, "Forbidden pattern missing 'pattern'"
            assert 'severity' in pattern, "Forbidden pattern missing 'severity'"
            assert pattern['severity'] in ['critical', 'error', 'warning', 'info'], \
                f"Invalid severity: {pattern['severity']}"

    def test_placeholder_rules(self, en_qa_rules):
        """Test placeholder rules configuration."""
        placeholder_rules = en_qa_rules.get('placeholder_rules', {})
        if placeholder_rules:
            assert 'patterns' in placeholder_rules, "Missing 'patterns' in placeholder_rules"
            assert 'must_preserve' in placeholder_rules, "Missing 'must_preserve' in placeholder_rules"


class TestLanguageCodeMapping:
    """Tests for language code mapping functionality."""

    def test_lang_code_map(self, lang_code_map):
        """Test language code mapping."""
        assert lang_code_map['en-US'] == 'en', "en-US should map to 'en'"
        assert lang_code_map['ru-RU'] == 'ru', "ru-RU should map to 'ru'"
        assert lang_code_map['ja-JP'] == 'ja', "ja-JP should map to 'ja'"

    def test_lang_code_map_coverage(self, lang_code_map):
        """Test that major language codes are covered."""
        required_codes = ['en-US', 'en-GB', 'ru-RU', 'ja-JP', 'ko-KR']
        for code in required_codes:
            assert code in lang_code_map, f"Missing language code: {code}"

    def test_zh_codes(self, lang_code_map):
        """Test Chinese language code mappings."""
        assert lang_code_map.get('zh-CN') == 'zh', "zh-CN should map to 'zh'"
        assert lang_code_map.get('zh-TW') == 'zh_tw', "zh-TW should map to 'zh_tw'"

    def test_european_codes(self, lang_code_map):
        """Test European language code mappings."""
        assert lang_code_map.get('fr-FR') == 'fr', "fr-FR should map to 'fr'"
        assert lang_code_map.get('de-DE') == 'de', "de-DE should map to 'de'"
        assert lang_code_map.get('es-ES') == 'es', "es-ES should map to 'es'"
        assert lang_code_map.get('it-IT') == 'it', "it-IT should map to 'it'"


class TestDynamicFieldNaming:
    """Tests for dynamic field naming functionality."""

    def test_get_target_field_name(self, project_root):
        """Test target field name generation from glossary_translate_llm."""
        import sys
        scripts_dir = str(project_root / 'src' / 'scripts')
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        
        try:
            from glossary_translate_llm import get_short_lang_code
            # Test the function that generates target field names
            assert get_short_lang_code('en-US') == 'en', "en-US should produce 'en'"
            assert get_short_lang_code('ru-RU') == 'ru', "ru-RU should produce 'ru'"
            assert get_short_lang_code('ja-JP') == 'ja', "ja-JP should produce 'ja'"
            assert get_short_lang_code('zh-CN') == 'zh', "zh-CN should produce 'zh'"
        except ImportError:
            pytest.skip("glossary_translate_llm module not available")

    def test_target_field_name_format(self, project_root):
        """Test that target field names follow expected format."""
        import sys
        scripts_dir = str(project_root / 'src' / 'scripts')
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        
        try:
            from glossary_translate_llm import get_short_lang_code
            # Field names should be term_{short_code}
            assert f"term_{get_short_lang_code('en-US')}" == 'term_en'
            assert f"term_{get_short_lang_code('ru-RU')}" == 'term_ru'
            assert f"term_{get_short_lang_code('ja-JP')}" == 'term_ja'
        except ImportError:
            pytest.skip("glossary_translate_llm module not available")

    def test_unknown_language_fallback(self, project_root):
        """Test fallback behavior for unknown language codes."""
        import sys
        scripts_dir = str(project_root / 'src' / 'scripts')
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        
        try:
            from glossary_translate_llm import get_short_lang_code
            # For unknown codes, should return the first part lowercased
            assert get_short_lang_code('xx-YY') == 'xx', "Unknown code should fallback to first part"
            assert get_short_lang_code('abc') == 'abc', "Single part code should return as-is"
        except ImportError:
            pytest.skip("glossary_translate_llm module not available")


class TestPromptDirectoryStructure:
    """Tests for prompt directory structure."""

    def test_prompts_dir_exists(self, project_root):
        """Test that prompts directory exists."""
        prompts_dir = project_root / 'src' / 'config' / 'prompts'
        assert prompts_dir.exists(), "Prompts directory should exist"
        assert prompts_dir.is_dir(), "Prompts should be a directory"

    def test_en_prompts_dir_exists(self, project_root):
        """Test that EN prompts subdirectory exists."""
        en_prompts_dir = project_root / 'src' / 'config' / 'prompts' / 'en'
        assert en_prompts_dir.exists(), "EN prompts directory should exist"
        assert en_prompts_dir.is_dir(), "EN prompts should be a directory"

    def test_ru_prompts_dir_exists(self, project_root):
        """Test that RU prompts subdirectory exists (for comparison)."""
        ru_prompts_dir = project_root / 'src' / 'config' / 'prompts' / 'ru'
        assert ru_prompts_dir.exists(), "RU prompts directory should exist"

    def test_en_prompt_files_are_text(self, project_root):
        """Test that EN prompt files are text files."""
        en_prompts_dir = project_root / 'src' / 'config' / 'prompts' / 'en'
        if en_prompts_dir.exists():
            for prompt_file in en_prompts_dir.glob('*.txt'):
                content = prompt_file.read_text()
                assert isinstance(content, str), f"{prompt_file.name} should be text"


class TestQARulesDirectoryStructure:
    """Tests for QA rules directory structure."""

    def test_qa_rules_dir_exists(self, project_root):
        """Test that QA rules directory exists."""
        qa_rules_dir = project_root / 'src' / 'config' / 'qa_rules'
        assert qa_rules_dir.exists(), "QA rules directory should exist"

    def test_en_qa_rules_is_yaml(self, project_root):
        """Test that EN QA rules is a valid YAML file."""
        qa_rules_path = project_root / 'src' / 'config' / 'qa_rules' / 'en.yaml'
        assert qa_rules_path.suffix == '.yaml', "Should be YAML file"
        # Should be parseable
        with open(qa_rules_path) as f:
            content = yaml.safe_load(f)
        assert content is not None, "Should be valid YAML"
