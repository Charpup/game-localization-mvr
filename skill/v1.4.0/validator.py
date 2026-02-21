"""Input validation utilities for loc-mVR."""
import csv
import re
from pathlib import Path
from typing import List, Tuple, Optional, Set
import json


class InputValidator:
    """Validate input files and parameters for loc-mVR."""
    
    # ISO 639-1 language codes (common languages)
    SUPPORTED_LANGUAGES: Set[str] = {
        'en', 'zh', 'ja', 'ko', 'fr', 'de', 'es', 'it', 'pt', 'ru',
        'ar', 'hi', 'th', 'vi', 'id', 'ms', 'pl', 'tr', 'nl', 'sv'
    }
    
    # CSV column requirements
    REQUIRED_CSV_COLUMNS = {'key', 'source', 'target'}
    OPTIONAL_CSV_COLUMNS = {'context', 'max_length', 'tags'}
    
    @staticmethod
    def validate_csv(path: str, strict: bool = False) -> Tuple[List[str], int]:
        """
        Validate CSV file format and content.
        
        Args:
            path: Path to CSV file
            strict: If True, require all optional columns
            
        Returns:
            Tuple of (headers, row_count)
            
        Raises:
            FileNotFoundError: If CSV file doesn't exist
            ValueError: If CSV format is invalid
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"CSV file not found: {path}")
        
        if not path.is_file():
            raise ValueError(f"Path is not a file: {path}")
        
        row_count = 0
        
        try:
            with open(path, 'r', encoding='utf-8-sig', newline='') as f:
                reader = csv.reader(f)
                headers = next(reader, None)
                
                if not headers:
                    raise ValueError("CSV file is empty or has no headers")
                
                # Normalize headers (lowercase, strip whitespace)
                headers = [h.strip().lower() for h in headers]
                
                # Check required columns
                header_set = set(headers)
                missing = InputValidator.REQUIRED_CSV_COLUMNS - header_set
                if missing:
                    raise ValueError(
                        f"Missing required columns: {', '.join(missing)}"
                    )
                
                # Validate rows
                for i, row in enumerate(reader, start=2):
                    if len(row) != len(headers):
                        raise ValueError(
                            f"Row {i}: Column count mismatch "
                            f"(expected {len(headers)}, got {len(row)})"
                        )
                    
                    # Check for empty required fields
                    for col in InputValidator.REQUIRED_CSV_COLUMNS:
                        col_idx = headers.index(col)
                        if not row[col_idx].strip():
                            raise ValueError(
                                f"Row {i}: Empty value in required column '{col}'"
                            )
                    
                    row_count += 1
                
                if row_count == 0:
                    raise ValueError("CSV file contains no data rows")
                
                return headers, row_count
                
        except UnicodeDecodeError as e:
            raise ValueError(f"CSV file encoding error: {e}")
        except csv.Error as e:
            raise ValueError(f"CSV parsing error: {e}")
    
    @staticmethod
    def validate_language_pair(source: str, target: str) -> bool:
        """
        Validate language pair is supported.
        
        Args:
            source: Source language code
            target: Target language code
            
        Returns:
            True if valid, raises ValueError otherwise
            
        Raises:
            ValueError: If language pair is invalid
        """
        source = source.lower().strip()
        target = target.lower().strip()
        
        if source == target:
            raise ValueError(
                f"Source and target languages are the same: {source}"
            )
        
        if source not in InputValidator.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported source language: {source}. "
                f"Supported: {', '.join(sorted(InputValidator.SUPPORTED_LANGUAGES))}"
            )
        
        if target not in InputValidator.SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Unsupported target language: {target}. "
                f"Supported: {', '.join(sorted(InputValidator.SUPPORTED_LANGUAGES))}"
            )
        
        return True
    
    @staticmethod
    def validate_language_pair_with_config(
        source: str, 
        target: str, 
        config_loader
    ) -> bool:
        """
        Validate language pair against configuration.
        
        Args:
            source: Source language code
            target: Target language code
            config_loader: ConfigLoader instance
            
        Returns:
            True if valid, raises ValueError otherwise
        """
        try:
            pairs = config_loader.load_language_pairs()
        except FileNotFoundError:
            # Fallback to basic validation
            return InputValidator.validate_language_pair(source, target)
        
        source = source.lower().strip()
        target = target.lower().strip()
        
        for pair in pairs.get('pairs', []):
            if (pair.get('source') == source and 
                pair.get('target') == target and 
                pair.get('enabled', True)):
                return True
        
        raise ValueError(
            f"Language pair not supported or disabled: {source} → {target}"
        )
    
    @staticmethod
    def validate_file_size(path: str, max_size_mb: float = 100) -> bool:
        """
        Validate file size is within limit.
        
        Args:
            path: Path to file
            max_size_mb: Maximum allowed size in MB
            
        Returns:
            True if valid
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file exceeds size limit
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")
        
        size_bytes = path.stat().st_size
        size_mb = size_bytes / (1024 * 1024)
        
        if size_mb > max_size_mb:
            raise ValueError(
                f"File size ({size_mb:.2f} MB) exceeds limit ({max_size_mb} MB)"
            )
        
        return True
    
    @staticmethod
    def validate_text_content(text: str, max_length: Optional[int] = None) -> bool:
        """
        Validate text content.
        
        Args:
            text: Text to validate
            max_length: Maximum allowed length
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If text is invalid
        """
        if text is None:
            raise ValueError("Text cannot be None")
        
        if not isinstance(text, str):
            raise ValueError(f"Text must be string, got {type(text).__name__}")
        
        if not text.strip():
            raise ValueError("Text cannot be empty or whitespace only")
        
        if max_length and len(text) > max_length:
            raise ValueError(
                f"Text length ({len(text)}) exceeds maximum ({max_length})"
            )
        
        return True
    
    @staticmethod
    def validate_json_structure(data: str, schema: Optional[dict] = None) -> dict:
        """
        Validate JSON string structure.
        
        Args:
            data: JSON string
            schema: Optional schema for validation
            
        Returns:
            Parsed JSON data
            
        Raises:
            ValueError: If JSON is invalid
        """
        try:
            parsed = json.loads(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
        
        if schema and not isinstance(parsed, dict):
            raise ValueError(f"JSON must be object, got {type(parsed).__name__}")
        
        return parsed
    
    @classmethod
    def add_supported_language(cls, code: str) -> None:
        """
        Add a language code to supported languages.
        
        Args:
            code: ISO 639-1 language code
        """
        code = code.lower().strip()
        if not re.match(r'^[a-z]{2}$', code):
            raise ValueError(f"Invalid language code format: {code}")
        cls.SUPPORTED_LANGUAGES.add(code)
    
    @classmethod
    def remove_supported_language(cls, code: str) -> None:
        """
        Remove a language code from supported languages.
        
        Args:
            code: ISO 639-1 language code
        """
        code = code.lower().strip()
        cls.SUPPORTED_LANGUAGES.discard(code)


class ValidationReport:
    """Collect and report validation results."""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
    
    def add_error(self, message: str) -> None:
        """Add an error message."""
        self.errors.append(message)
    
    def add_warning(self, message: str) -> None:
        """Add a warning message."""
        self.warnings.append(message)
    
    def add_info(self, message: str) -> None:
        """Add an info message."""
        self.info.append(message)
    
    def is_valid(self) -> bool:
        """Check if validation passed (no errors)."""
        return len(self.errors) == 0
    
    def to_dict(self) -> dict:
        """Convert report to dictionary."""
        return {
            'valid': self.is_valid(),
            'errors': self.errors,
            'warnings': self.warnings,
            'info': self.info
        }
    
    def __str__(self) -> str:
        """String representation of report."""
        lines = []
        
        if self.errors:
            lines.append(f"Errors ({len(self.errors)}):")
            for e in self.errors:
                lines.append(f"  ✗ {e}")
        
        if self.warnings:
            lines.append(f"Warnings ({len(self.warnings)}):")
            for w in self.warnings:
                lines.append(f"  ⚠ {w}")
        
        if self.info:
            lines.append(f"Info ({len(self.info)}):")
            for i in self.info:
                lines.append(f"  ℹ {i}")
        
        if not lines:
            lines.append("✓ Validation passed")
        
        return '\n'.join(lines)
