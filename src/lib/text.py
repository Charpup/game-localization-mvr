# src/lib/text.py - Text processing utilities
"""Text processing utilities for localization."""

import re
from typing import List, Tuple, Optional


class TextProcessor:
    """Utility class for text processing operations."""
    
    @staticmethod
    def normalize_text(text: str) -> str:
        """Normalize text for processing."""
        # Remove extra whitespace
        text = ' '.join(text.split())
        # Normalize unicode quotes
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace(''', "'").replace(''', "'")
        return text
    
    @staticmethod
    def extract_placeholders(text: str) -> List[Tuple[str, str]]:
        """Extract placeholder patterns from text."""
        # Common placeholder patterns: {name}, {{name}}, %s, %d, etc.
        patterns = [
            (r'\{\{(\w+)\}\}', 'double_brace'),
            (r'\{(\w+)\}', 'single_brace'),
            (r'%[sdif]', 'printf'),
            (r'\$\w+', 'variable'),
        ]
        
        results = []
        for pattern, ptype in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                results.append((match, ptype))
        return results
    
    @staticmethod
    def calculate_similarity(text1: str, text2: str) -> float:
        """Calculate simple similarity score between two texts."""
        # Simple Jaccard similarity for quick comparison
        set1 = set(text1.lower().split())
        set2 = set(text2.lower().split())
        
        if not set1 and not set2:
            return 1.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        return intersection / union if union > 0 else 0.0
