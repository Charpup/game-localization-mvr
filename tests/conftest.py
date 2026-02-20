"""Pytest configuration and shared fixtures for game-localization-mvr tests."""
import pytest
import sys
from pathlib import Path

# Add src directory to Python path for imports
PROJECT_ROOT = Path(__file__).parent.parent
SRC_DIR = PROJECT_ROOT / 'src'
sys.path.insert(0, str(SRC_DIR))


@pytest.fixture
def project_root():
    """Return the project root directory."""
    return PROJECT_ROOT


@pytest.fixture
def src_dir():
    """Return the src directory."""
    return SRC_DIR


@pytest.fixture
def config_dir():
    """Return the config directory."""
    return SRC_DIR / 'config'


@pytest.fixture
def scripts_dir():
    """Return the scripts directory."""
    return SRC_DIR / 'scripts'


@pytest.fixture
def test_data_dir():
    """Return the test data directory."""
    return PROJECT_ROOT / 'tests' / 'data'


@pytest.fixture
def language_pairs_config():
    """Load and return the language_pairs.yaml configuration."""
    import yaml
    config_path = SRC_DIR / 'config' / 'language_pairs.yaml'
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f)
    return {}


@pytest.fixture
def en_qa_rules():
    """Load and return the EN QA rules configuration."""
    import yaml
    rules_path = SRC_DIR / 'config' / 'qa_rules' / 'en.yaml'
    if rules_path.exists():
        with open(rules_path) as f:
            return yaml.safe_load(f)
    return {}


@pytest.fixture(scope='session')
def lang_code_map():
    """Return the language code mapping from glossary_translate_llm."""
    # Import here to avoid issues if module not available
    try:
        from scripts.glossary_translate_llm import LANG_CODE_MAP
        return LANG_CODE_MAP
    except ImportError:
        # Fallback mapping if import fails
        return {
            "zh-CN": "zh",
            "zh-TW": "zh_tw",
            "en-US": "en",
            "en-GB": "en",
            "ru-RU": "ru",
            "ja-JP": "ja",
            "ko-KR": "ko",
            "fr-FR": "fr",
            "de-DE": "de",
            "es-ES": "es",
            "pt-BR": "pt",
            "it-IT": "it",
            "ar-SA": "ar",
            "th-TH": "th",
            "vi-VN": "vi",
            "id-ID": "id",
        }
