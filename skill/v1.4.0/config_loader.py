"""Unified configuration loader for loc-mVR."""
from pathlib import Path
import yaml
import os
import json
from typing import Dict, Any, Optional, List


class ConfigLoader:
    """Load and validate configuration files for loc-mVR."""
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize ConfigLoader.
        
        Args:
            config_dir: Path to configuration directory. 
                       Defaults to parent/config relative to this file.
        """
        if config_dir is None:
            config_dir = Path(__file__).parent.parent / 'config'
        self.config_dir = Path(config_dir)
        self._cache: Dict[str, Any] = {}
    
    def _get_cache_key(self, *parts) -> str:
        """Generate cache key from path parts."""
        return str(Path(*parts))
    
    def load_language_pairs(self) -> Dict[str, Any]:
        """
        Load language_pairs.yaml.
        
        Returns:
            Dictionary containing language pair configurations.
            
        Raises:
            FileNotFoundError: If language_pairs.yaml doesn't exist.
            yaml.YAMLError: If YAML parsing fails.
        """
        cache_key = self._get_cache_key('language_pairs')
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        path = self.config_dir / 'language_pairs.yaml'
        if not path.exists():
            raise FileNotFoundError(f"Language pairs config not found: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        self._cache[cache_key] = data
        return data
    
    def load_prompt(self, name: str, lang: str = 'en') -> str:
        """
        Load prompt template for specified language.
        
        Falls back to English if requested language version doesn't exist.
        
        Args:
            name: Name of the prompt template (without .txt extension)
            lang: Language code (default: 'en')
            
        Returns:
            Prompt template text content.
            
        Raises:
            FileNotFoundError: If neither localized nor English version exists.
        """
        cache_key = self._get_cache_key('prompts', lang, name)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Try localized version first
        path = self.config_dir / 'prompts' / lang / f'{name}.txt'
        
        # Fall back to English if not found
        if not path.exists():
            path = self.config_dir / 'prompts' / 'en' / f'{name}.txt'
        
        if not path.exists():
            raise FileNotFoundError(
                f"Prompt template not found: {name} (lang: {lang} or en)"
            )
        
        content = path.read_text(encoding='utf-8')
        self._cache[cache_key] = content
        return content
    
    def load_qa_rules(self, lang: str = 'en') -> Dict[str, Any]:
        """
        Load QA rules for specified language.
        
        Args:
            lang: Language code (default: 'en')
            
        Returns:
            Dictionary containing QA rules configuration.
            
        Raises:
            FileNotFoundError: If QA rules file doesn't exist.
            yaml.YAMLError: If YAML parsing fails.
        """
        cache_key = self._get_cache_key('qa_rules', lang)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        path = self.config_dir / 'qa_rules' / f'{lang}.yaml'
        if not path.exists():
            # Try fallback to English
            if lang != 'en':
                path = self.config_dir / 'qa_rules' / 'en.yaml'
            if not path.exists():
                raise FileNotFoundError(f"QA rules not found for language: {lang}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        self._cache[cache_key] = data
        return data
    
    def load_workflow_config(self, name: str = 'default') -> Dict[str, Any]:
        """
        Load workflow configuration.
        
        Args:
            name: Workflow configuration name (default: 'default')
            
        Returns:
            Dictionary containing workflow configuration.
        """
        cache_key = self._get_cache_key('workflows', name)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        path = self.config_dir / 'workflows' / f'{name}.yaml'
        if not path.exists():
            raise FileNotFoundError(f"Workflow config not found: {path}")
        
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        self._cache[cache_key] = data
        return data
    
    def load_env_config(self) -> Dict[str, str]:
        """
        Load environment variables with loc-mVR prefix.
        
        Returns:
            Dictionary of environment variables.
        """
        prefix = 'LOCMVR_'
        return {
            key[len(prefix):]: value
            for key, value in os.environ.items()
            if key.startswith(prefix)
        }
    
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported language codes.
        
        Returns:
            List of supported language codes.
        """
        pairs = self.load_language_pairs()
        languages = set()
        for pair in pairs.get('pairs', []):
            languages.add(pair.get('source'))
            languages.add(pair.get('target'))
        return sorted(list(languages))
    
    def clear_cache(self) -> None:
        """Clear the configuration cache."""
        self._cache.clear()
    
    def reload(self, name: str) -> Any:
        """
        Reload a specific configuration (bypass cache).
        
        Args:
            name: Configuration name to reload
            
        Returns:
            Reloaded configuration data.
        """
        # Remove from cache if present
        keys_to_remove = [k for k in self._cache if name in k]
        for key in keys_to_remove:
            del self._cache[key]
        
        # Reload based on name pattern
        if name == 'language_pairs':
            return self.load_language_pairs()
        elif name.startswith('qa_rules'):
            lang = name.split('/')[-1] if '/' in name else 'en'
            return self.load_qa_rules(lang)
        elif name.startswith('workflows'):
            workflow_name = name.split('/')[-1] if '/' in name else 'default'
            return self.load_workflow_config(workflow_name)
        else:
            raise ValueError(f"Unknown configuration: {name}")


class ConfigValidator:
    """Validate configuration file structure and content."""
    
    REQUIRED_LANGUAGE_PAIR_FIELDS = ['source', 'target', 'enabled']
    REQUIRED_QA_RULE_FIELDS = ['rules', 'severity_levels']
    
    @staticmethod
    def validate_language_pairs(data: Dict[str, Any]) -> List[str]:
        """
        Validate language pairs configuration.
        
        Args:
            data: Loaded language pairs data
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not isinstance(data, dict):
            errors.append("Language pairs must be a dictionary")
            return errors
        
        pairs = data.get('pairs', [])
        if not isinstance(pairs, list):
            errors.append("'pairs' must be a list")
            return errors
        
        for i, pair in enumerate(pairs):
            if not isinstance(pair, dict):
                errors.append(f"Pair {i} must be a dictionary")
                continue
            
            for field in ConfigValidator.REQUIRED_LANGUAGE_PAIR_FIELDS:
                if field not in pair:
                    errors.append(f"Pair {i} missing required field: {field}")
        
        return errors
    
    @staticmethod
    def validate_qa_rules(data: Dict[str, Any]) -> List[str]:
        """
        Validate QA rules configuration.
        
        Args:
            data: Loaded QA rules data
            
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not isinstance(data, dict):
            errors.append("QA rules must be a dictionary")
            return errors
        
        for field in ConfigValidator.REQUIRED_QA_RULE_FIELDS:
            if field not in data:
                errors.append(f"Missing required field: {field}")
        
        return errors
