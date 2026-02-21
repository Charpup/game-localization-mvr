"""
loc-mVR v1.4.0 Scripts Package

Core translation pipeline scripts organized by category:
- core: Main translation workflow scripts
- utils: Utility libraries and helpers
- debug: Debugging and diagnostic tools
- testing: Test runners and acceptance scripts
- deprecated: Legacy scripts (preserved for reference)

Usage:
    from scripts.core.batch_runtime import process_batch_worker
    from scripts.utils.lib_text import load_punctuation_config
"""

__version__ = '1.4.0'
__all__ = ['core', 'utils', 'debug', 'testing']
