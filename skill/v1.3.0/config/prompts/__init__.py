"""
Dynamic prompt loader for loc-mVR v1.3.0

Supports loading prompt templates by language code.
"""

import os
from pathlib import Path

# Base directory for prompts
PROMPTS_DIR = Path(__file__).parent

# Available prompt types
PROMPT_TYPES = {
    "batch_translate": "batch_translate_system.txt",
    "glossary_translate": "glossary_translate_system.txt",
}

# Supported language codes
SUPPORTED_LANGUAGES = ["en", "ru"]


def load_prompt(prompt_type: str, lang: str = "en") -> str:
    """
    Load a prompt template by type and language.
    
    Args:
        prompt_type: Type of prompt (batch_translate, glossary_translate)
        lang: Language code (en, ru, etc.)
    
    Returns:
        Prompt template content as string
    
    Raises:
        ValueError: If prompt_type or lang is not supported
        FileNotFoundError: If prompt file does not exist
    """
    if prompt_type not in PROMPT_TYPES:
        raise ValueError(
            f"Unknown prompt type: {prompt_type}. "
            f"Supported: {list(PROMPT_TYPES.keys())}"
        )
    
    if lang not in SUPPORTED_LANGUAGES:
        raise ValueError(
            f"Unsupported language: {lang}. "
            f"Supported: {SUPPORTED_LANGUAGES}"
        )
    
    prompt_file = PROMPTS_DIR / lang / PROMPT_TYPES[prompt_type]
    
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    
    return prompt_file.read_text(encoding="utf-8")


def list_available_prompts() -> dict:
    """
    List all available prompts by language.
    
    Returns:
        Dictionary mapping language codes to available prompt types
    """
    result = {}
    for lang in SUPPORTED_LANGUAGES:
        lang_dir = PROMPTS_DIR / lang
        if lang_dir.exists():
            result[lang] = [
                pt for pt, filename in PROMPT_TYPES.items()
                if (lang_dir / filename).exists()
            ]
    return result


def add_language(lang_code: str) -> None:
    """
    Add support for a new language code.
    
    Args:
        lang_code: ISO language code (e.g., 'ja', 'de')
    """
    if lang_code not in SUPPORTED_LANGUAGES:
        SUPPORTED_LANGUAGES.append(lang_code)
        # Create directory if it doesn't exist
        lang_dir = PROMPTS_DIR / lang_code
        lang_dir.mkdir(exist_ok=True)
