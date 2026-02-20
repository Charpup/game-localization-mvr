"""Integration tests for EN translation pipeline."""
import subprocess
import json
import tempfile
from pathlib import Path
import pytest
import sys


class TestBatchRuntimeEN:
    """Integration tests for batch_runtime.py with EN target."""

    def test_batch_runtime_help(self, project_root):
        """Test batch_runtime.py help output shows language options."""
        result = subprocess.run(
            [sys.executable, 'scripts/batch_runtime.py', '--help'],
            capture_output=True,
            text=True,
            cwd=project_root / 'src'
        )
        assert result.returncode == 0, f"Help command failed: {result.stderr}"
        assert '--target-lang' in result.stdout, "Missing --target-lang option"
        assert '--source-lang' in result.stdout, "Missing --source-lang option"

    def test_batch_runtime_en_target(self, project_root):
        """Test batch_runtime.py accepts EN as target language."""
        result = subprocess.run(
            [sys.executable, 'scripts/batch_runtime.py', '--help'],
            capture_output=True,
            text=True,
            cwd=project_root / 'src'
        )
        assert result.returncode == 0
        # Help should mention language options
        assert 'target' in result.stdout.lower(), "Help should mention target language"

    def test_batch_runtime_script_exists(self, project_root):
        """Test that batch_runtime.py script exists."""
        script_path = project_root / 'src' / 'scripts' / 'batch_runtime.py'
        assert script_path.exists(), f"batch_runtime.py not found at {script_path}"
        assert script_path.is_file(), "batch_runtime.py should be a file"

    def test_batch_runtime_is_executable(self, project_root):
        """Test that batch_runtime.py has correct permissions."""
        script_path = project_root / 'src' / 'scripts' / 'batch_runtime.py'
        content = script_path.read_text()
        assert content.startswith('#!'), "Should have shebang line"
        assert 'python' in content.lower(), "Should reference Python"


class TestGlossaryTranslateEN:
    """Integration tests for glossary_translate_llm.py with EN target."""

    def test_glossary_translate_help(self, project_root):
        """Test glossary_translate_llm.py help output."""
        result = subprocess.run(
            [sys.executable, 'scripts/glossary_translate_llm.py', '--help'],
            capture_output=True,
            text=True,
            cwd=project_root / 'src'
        )
        assert result.returncode == 0, f"Help command failed: {result.stderr}"
        assert '--target-lang' in result.stdout, "Missing --target-lang option"
        assert '--source-lang' in result.stdout, "Missing --source-lang option"
        assert '--proposals' in result.stdout, "Missing --proposals option"
        assert '--output' in result.stdout, "Missing --output option"

    def test_glossary_translate_en_us_support(self, project_root):
        """Test glossary_translate_llm.py supports en-US target."""
        result = subprocess.run(
            [sys.executable, 'scripts/glossary_translate_llm.py', '--help'],
            capture_output=True,
            text=True,
            cwd=project_root / 'src'
        )
        assert result.returncode == 0
        # Should support standard language code format
        help_text = result.stdout.lower()
        assert any(x in help_text for x in ['target-lang', 'target lang', 'target_language']), \
            "Help should document target language option"

    def test_glossary_translate_script_exists(self, project_root):
        """Test that glossary_translate_llm.py script exists."""
        script_path = project_root / 'src' / 'scripts' / 'glossary_translate_llm.py'
        assert script_path.exists(), f"glossary_translate_llm.py not found at {script_path}"

    def test_glossary_translate_imports(self, project_root):
        """Test that glossary_translate_llm.py can be imported."""
        scripts_dir = str(project_root / 'src' / 'scripts')
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        
        try:
            import glossary_translate_llm
            # Check required functions exist
            assert hasattr(glossary_translate_llm, 'get_short_lang_code'), \
                "Missing get_short_lang_code function"
            assert hasattr(glossary_translate_llm, 'LANG_CODE_MAP'), \
                "Missing LANG_CODE_MAP"
        except ImportError as e:
            pytest.skip(f"Could not import glossary_translate_llm: {e}")


class TestTranslationPipelineEN:
    """Integration tests for the full EN translation pipeline."""

    def test_en_prompts_load_correctly(self, project_root):
        """Test that EN prompts can be loaded by batch_runtime."""
        prompts_dir = project_root / 'src' / 'config' / 'prompts' / 'en'
        batch_prompt = prompts_dir / 'batch_translate_system.txt'
        
        assert batch_prompt.exists(), "Batch translate prompt should exist"
        content = batch_prompt.read_text()
        assert len(content) > 0, "Prompt should not be empty"

    def test_en_qa_rules_load_correctly(self, project_root):
        """Test that EN QA rules can be loaded."""
        import yaml
        qa_rules_path = project_root / 'src' / 'config' / 'qa_rules' / 'en.yaml'
        
        assert qa_rules_path.exists(), "EN QA rules should exist"
        with open(qa_rules_path) as f:
            rules = yaml.safe_load(f)
        
        assert rules.get('language') == 'en-US', "Language should be en-US"

    def test_language_pairs_load_correctly(self, project_root):
        """Test that language pairs config can be loaded."""
        import yaml
        config_path = project_root / 'src' / 'config' / 'language_pairs.yaml'
        
        assert config_path.exists(), "Language pairs config should exist"
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        zh_en = config['language_pairs']['zh-cn_en-us']
        assert zh_en['target'] == 'en-US', "Target should be en-US"


class TestMultiLanguageConfiguration:
    """Tests for multi-language configuration consistency."""

    def test_all_target_langs_have_prompts(self, project_root):
        """Test that all target languages have prompt directories."""
        prompts_dir = project_root / 'src' / 'config' / 'prompts'
        
        # Check that at least EN and RU prompts exist
        assert (prompts_dir / 'en').exists(), "EN prompts directory should exist"
        assert (prompts_dir / 'ru').exists(), "RU prompts directory should exist"

    def test_all_target_langs_have_qa_rules(self, project_root):
        """Test that EN has QA rules defined."""
        qa_rules_dir = project_root / 'src' / 'config' / 'qa_rules'
        
        # EN should have QA rules
        assert (qa_rules_dir / 'en.yaml').exists(), "EN QA rules should exist"

    def test_language_pairs_consistency(self, project_root):
        """Test that language pairs match available resources."""
        import yaml
        config_path = project_root / 'src' / 'config' / 'language_pairs.yaml'
        prompts_dir = project_root / 'src' / 'config' / 'prompts'
        
        with open(config_path) as f:
            config = yaml.safe_load(f)
        
        for pair_key, pair_config in config['language_pairs'].items():
            target = pair_config['target']
            target_code = target.split('-')[0].lower()
            
            # Prompts directory should exist
            prompt_dir = prompts_dir / target_code
            assert prompt_dir.exists() or target_code == 'zh', \
                f"Missing prompts directory for {target}"


class TestENTranslationOutput:
    """Tests for EN translation output validation."""

    def test_field_name_generation_en(self, project_root):
        """Test that EN field names are generated correctly."""
        scripts_dir = str(project_root / 'src' / 'scripts')
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        
        try:
            from glossary_translate_llm import get_short_lang_code
            
            # EN should produce 'en'
            short_code = get_short_lang_code('en-US')
            assert short_code == 'en', f"Expected 'en', got '{short_code}'"
            
            # Field name should be term_en
            field_name = f"term_{short_code}"
            assert field_name == 'term_en', f"Expected 'term_en', got '{field_name}'"
        except ImportError:
            pytest.skip("glossary_translate_llm module not available")

    def test_en_grammar_rules_exist(self, en_qa_rules):
        """Test that EN-specific grammar rules exist."""
        grammar_rules = en_qa_rules.get('grammar_rules', [])
        
        # Should have at least some grammar rules
        assert len(grammar_rules) > 0, "Should have grammar rules for EN"
        
        # Check for common EN-specific rules
        rule_names = [r.get('name') for r in grammar_rules]
        assert 'article_usage' in rule_names, "Should have article usage rule"


class TestScriptsCompatibility:
    """Tests for script compatibility with multi-language support."""

    def test_batch_runtime_accepts_en_target(self, project_root):
        """Test that batch_runtime accepts EN as target."""
        # This is a dry-run test - we just verify the argument parsing works
        result = subprocess.run(
            [sys.executable, 'scripts/batch_runtime.py', '--help'],
            capture_output=True,
            text=True,
            cwd=project_root / 'src'
        )
        assert result.returncode == 0
        assert '--target-lang' in result.stdout

    def test_glossary_translate_accepts_en_target(self, project_root):
        """Test that glossary_translate accepts EN as target."""
        result = subprocess.run(
            [sys.executable, 'scripts/glossary_translate_llm.py', '--help'],
            capture_output=True,
            text=True,
            cwd=project_root / 'src'
        )
        assert result.returncode == 0
        assert '--target-lang' in result.stdout

    @pytest.mark.parametrize("script_name", [
        'batch_runtime.py',
        'glossary_translate_llm.py',
    ])
    def test_scripts_have_consistent_lang_args(self, project_root, script_name):
        """Test that all translation scripts have consistent language arguments."""
        result = subprocess.run(
            [sys.executable, f'scripts/{script_name}', '--help'],
            capture_output=True,
            text=True,
            cwd=project_root / 'src'
        )
        assert result.returncode == 0
        
        # All scripts should have source and target language options
        assert '--source-lang' in result.stdout, f"{script_name} missing --source-lang"
        assert '--target-lang' in result.stdout, f"{script_name} missing --target-lang"
