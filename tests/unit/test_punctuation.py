import unittest
from src.scripts.lib_text import sanitize_punctuation

class TestPunctuationSanitizer(unittest.TestCase):
    def test_basic_replace(self):
        mappings = [{'source': '...', 'target': '…'}]
        self.assertEqual(sanitize_punctuation("Loading...", mappings), "Loading…")
        
    def test_brackets_mapping(self):
        mappings = [
            {'source': '【', 'target': '«'},
            {'source': '】', 'target': '»'}
        ]
        text = "【系统】提示"
        expected = "«系统»提示"
        self.assertEqual(sanitize_punctuation(text, mappings), expected)
        
    def test_no_mapping(self):
        self.assertEqual(sanitize_punctuation("Hello", []), "Hello")
        
    def test_empty(self):
        self.assertEqual(sanitize_punctuation("", []), "")

if __name__ == '__main__':
    unittest.main()
