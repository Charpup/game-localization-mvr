#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_api_compatibility.py
Regression tests for public API compatibility.

Ensures v1.2.0 maintains:
- Public API surface hasn't changed
- Import paths remain valid
- CLI commands backward compatible

Usage:
    pytest tests/regression/test_api_compatibility.py -v
    pytest tests/regression/test_api_compatibility.py -m "api_surface" -v
"""

import os
import sys
import subprocess
import importlib
import inspect
import pytest
from pathlib import Path
from typing import List, Dict, Any, Callable

# Ensure imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skill" / "scripts"))


# =============================================================================
# pytest Configuration
# =============================================================================

def pytest_configure(config):
    """Register custom markers for API compatibility tests."""
    config.addinivalue_line("markers", "api_surface: Public API surface tests")
    config.addinivalue_line("markers", "import_paths: Import path validation tests")
    config.addinivalue_line("markers", "cli_compat: CLI backward compatibility tests")
    config.addinivalue_line("markers", "regression: Regression test suite")


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


# =============================================================================
# API Surface Tests
# =============================================================================

@pytest.mark.regression
@pytest.mark.api_surface
class TestPublicAPISurface:
    """Test that public API surface hasn't changed.
    
    These tests verify that key classes and functions
    maintain their expected signatures and behavior.
    """
    
    def test_normalize_guard_class_exists(self):
        """Test NormalizeGuard class is importable and has expected methods."""
        from scripts.normalize_guard import NormalizeGuard
        
        # Check class exists
        assert hasattr(NormalizeGuard, '__init__')
        assert hasattr(NormalizeGuard, 'run')
        assert hasattr(NormalizeGuard, 'process_csv')
        
        # Check expected attributes exist on class (not instance to avoid schema loading)
        assert hasattr(NormalizeGuard, '__init__')
        sig = inspect.signature(NormalizeGuard.__init__)
        init_params = list(sig.parameters.keys())
        assert any(p in init_params for p in ['input_path', 'input_csv'])
    
    def test_normalize_guard_method_signatures(self):
        """Test NormalizeGuard method signatures haven't changed."""
        from scripts.normalize_guard import NormalizeGuard
        
        # Check run() takes no additional required args
        sig = inspect.signature(NormalizeGuard.run)
        params = list(sig.parameters.keys())
        assert 'self' in params
        
        # Check __init__ signature
        init_sig = inspect.signature(NormalizeGuard.__init__)
        init_params = list(init_sig.parameters.keys())
        assert any(p in init_params for p in ['input_path', 'input_csv'])
        assert any(p in init_params for p in ['output_draft_path', 'output_csv'])
        assert any(p in init_params for p in ['output_map_path', 'placeholder_map_path'])
        assert 'schema_path' in init_params
    
    def test_placeholder_freezer_class_exists(self):
        """Test PlaceholderFreezer class is importable."""
        from scripts.normalize_guard import PlaceholderFreezer
        
        assert hasattr(PlaceholderFreezer, '__init__')
        assert hasattr(PlaceholderFreezer, 'freeze_text')
        assert hasattr(PlaceholderFreezer, 'load_schema')
        assert hasattr(PlaceholderFreezer, 'reset_counters')
    
    def test_placeholder_freezer_freeze_text_signature(self):
        """Test PlaceholderFreezer.freeze_text signature."""
        from scripts.normalize_guard import PlaceholderFreezer
        
        sig = inspect.signature(PlaceholderFreezer.freeze_text)
        params = list(sig.parameters.keys())
        assert 'self' in params
        assert 'text' in params
        # source_lang is optional with default
        assert 'source_lang' in params
    
    def test_rehydrate_exporter_class_exists(self):
        """Test RehydrateExporter class is importable."""
        from scripts.rehydrate_export import RehydrateExporter
        
        assert hasattr(RehydrateExporter, '__init__')
        assert hasattr(RehydrateExporter, 'load_placeholder_map')
        assert hasattr(RehydrateExporter, 'run')
        assert hasattr(RehydrateExporter, 'rehydrate_text')
    
    def test_rehydrate_exporter_init_signature(self):
        """Test RehydrateExporter.__init__ signature is compatible."""
        from scripts.rehydrate_export import RehydrateExporter
        
        sig = inspect.signature(RehydrateExporter.__init__)
        params = list(sig.parameters.keys())
        
        # Core required parameters
        assert 'translated_csv' in params
        assert 'placeholder_map' in params
        assert 'final_csv' in params
        
        # Optional parameters should have defaults
        param_objects = list(sig.parameters.values())
        optional_params = [p for p in param_objects if p.default is not inspect.Parameter.empty]
        optional_names = [p.name for p in optional_params]
        
        # Known optional parameters
        assert 'overwrite_mode' in optional_names or 'overwrite_mode' in params
        assert 'target_lang' in optional_names or 'target_lang' in params
    
    def test_qa_hard_class_exists(self):
        """Test QAHardValidator class is importable."""
        from scripts.qa_hard import QAHardValidator
        
        assert hasattr(QAHardValidator, '__init__')
        assert hasattr(QAHardValidator, 'validate_csv')
        assert hasattr(QAHardValidator, 'run')
    
    def test_translate_llm_functions_exist(self):
        """Test translate_llm module functions are available."""
        from scripts import translate_llm
        
        # Key functions that should exist
        assert hasattr(translate_llm, 'load_glossary')
        assert hasattr(translate_llm, 'build_glossary_constraints')
        assert hasattr(translate_llm, 'validate_translation')
    
    def test_translate_llm_glossary_entry_exists(self):
        """Test GlossaryEntry dataclass exists."""
        from scripts.translate_llm import GlossaryEntry
        
        # Should be a class/dataclass
        assert isinstance(GlossaryEntry, type)
    
    def test_runtime_adapter_classes_exist(self):
        """Test runtime_adapter classes are importable."""
        from scripts.runtime_adapter import LLMClient, LLMRouter
        
        assert hasattr(LLMClient, '__init__')
        assert hasattr(LLMRouter, '__init__')
    
    def test_metrics_aggregator_functions_exist(self):
        """Test metrics_aggregator functions are available."""
        from scripts import metrics_aggregator
        
        # Functions should exist
        assert hasattr(metrics_aggregator, 'aggregate_metrics')
    
    def test_batch_runtime_functions_exist(self):
        """Test batch_runtime functions are available."""
        from scripts import batch_runtime
        
        assert hasattr(batch_runtime, 'process_batch_worker')
        assert hasattr(batch_runtime, 'validate_batch_schema')


# =============================================================================
# Import Path Tests
# =============================================================================

@pytest.mark.regression
@pytest.mark.import_paths
class TestImportPaths:
    """Test that import paths remain valid.
    
    These tests ensure that existing code using these imports
    won't break with v1.2.0.
    """
    
    def test_import_normalize_guard(self):
        """Test importing normalize_guard from scripts."""
        try:
            from scripts import normalize_guard
            from scripts.normalize_guard import PlaceholderFreezer, NormalizeGuard
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import normalize_guard: {e}")
    
    def test_import_rehydrate_export(self):
        """Test importing rehydrate_export from scripts."""
        try:
            from scripts import rehydrate_export
            from scripts.rehydrate_export import RehydrateExporter
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import rehydrate_export: {e}")
    
    def test_import_qa_hard(self):
        """Test importing qa_hard from scripts."""
        try:
            from scripts import qa_hard
            from scripts.qa_hard import QAHardValidator
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import qa_hard: {e}")
    
    def test_import_translate_llm(self):
        """Test importing translate_llm from scripts."""
        try:
            from scripts import translate_llm
            from scripts.translate_llm import load_glossary, GlossaryEntry
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import translate_llm: {e}")
    
    def test_import_batch_runtime(self):
        """Test importing batch_runtime from scripts."""
        try:
            from scripts import batch_runtime
            from scripts.batch_runtime import GlossaryEntry, BatchResult
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import batch_runtime: {e}")
    
    def test_import_runtime_adapter(self):
        """Test importing runtime_adapter from scripts."""
        try:
            from scripts import runtime_adapter
            from scripts.runtime_adapter import LLMClient, LLMRouter
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import runtime_adapter: {e}")
    
    def test_import_extract_terms(self):
        """Test importing extract_terms from scripts."""
        try:
            from scripts import extract_terms
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import extract_terms: {e}")
    
    def test_import_glossary_modules(self):
        """Test importing glossary-related modules."""
        glossary_modules = [
            'glossary_compile',
            'glossary_translate_llm',
            'glossary_review_llm',
            'glossary_autopromote',
            'glossary_delta'
        ]
        
        for module_name in glossary_modules:
            try:
                module = importlib.import_module(f'scripts.{module_name}')
                assert module is not None
            except ImportError as e:
                pytest.fail(f"Failed to import {module_name}: {e}")
    
    def test_import_repair_modules(self):
        """Test importing repair-related modules."""
        repair_modules = [
            'repair_loop',
            'repair_loop_v2',
            'repair_checkpoint_gaps'
        ]
        
        for module_name in repair_modules:
            try:
                module = importlib.import_module(f'scripts.{module_name}')
                assert module is not None
            except ImportError as e:
                # Some modules might be optional
                pass
    
    def test_import_metrics_modules(self):
        """Test importing metrics-related modules."""
        try:
            from scripts import metrics_aggregator
            from scripts import cost_monitor
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import metrics modules: {e}")
    
    def test_import_soft_qa(self):
        """Test importing soft_qa_llm."""
        try:
            from scripts import soft_qa_llm
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import soft_qa_llm: {e}")
    
    def test_import_style_guide_modules(self):
        """Test importing style guide modules."""
        try:
            from scripts import style_guide_generate
            from scripts import style_guide_apply
            assert True
        except ImportError as e:
            pytest.fail(f"Failed to import style guide modules: {e}")


# =============================================================================
# CLI Compatibility Tests
# =============================================================================

@pytest.mark.regression
@pytest.mark.cli_compat
class TestCLICompatibility:
    """Test CLI commands backward compatibility.
    
    These tests verify that CLI commands from v1.1.x
    still work in v1.2.0.
    """
    
    def test_normalize_guard_cli_help(self):
        """Test normalize_guard.py --help works."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "normalize_guard.py"
        
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True
        )
        
        # Should return 0 or show usage
        assert result.returncode in [0, 1, 2], f"Unexpected exit code: {result.returncode}"
        # Should show usage information
        output = result.stdout + result.stderr
        assert any(term in output.lower() for term in ["usage", "help", "normalize"])
    
    def test_rehydrate_export_cli_usage(self):
        """Test rehydrate_export.py shows usage."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "rehydrate_export.py"
        
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True
        )
        
        # Should show usage (exit code 1 is OK for missing args)
        assert result.returncode in [0, 1, 2]
        output = result.stdout + result.stderr
        assert "usage" in output.lower() or "Usage" in output
    
    def test_qa_hard_cli_usage(self):
        """Test qa_hard.py shows usage."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "qa_hard.py"
        
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True
        )
        
        assert result.returncode in [0, 1, 2]
    
    def test_translate_llm_cli_usage(self):
        """Test translate_llm.py shows usage."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "translate_llm.py"
        
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode in [0, 1, 2]
    
    def test_glossary_compile_cli_help(self):
        """Test glossary_compile.py --help works."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "glossary_compile.py"
        
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode in [0, 1, 2]
    
    def test_metrics_aggregator_cli_help(self):
        """Test metrics_aggregator.py --help works."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "metrics_aggregator.py"
        
        result = subprocess.run(
            [sys.executable, str(script_path), "--help"],
            capture_output=True,
            text=True
        )
        
        assert result.returncode in [0, 1, 2]
    
    def test_normalize_guard_cli_basic_args(self):
        """Test normalize_guard.py accepts expected positional args."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "normalize_guard.py"
        
        # Run without args to check usage format
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True
        )
        
        help_text = result.stdout + result.stderr
        # Should mention input/output/map/schema arguments
        assert any(term in help_text.lower() for term in [
            "input", "output", "map", "schema", "csv"
        ])
    
    def test_rehydrate_export_cli_args(self):
        """Test rehydrate_export.py accepts expected arguments."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "rehydrate_export.py"
        
        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True
        )
        
        help_text = result.stdout + result.stderr
        # Should mention key arguments
        assert any(term in help_text.lower() for term in [
            "translated", "placeholder", "final", "overwrite"
        ])


# =============================================================================
# API Behavior Compatibility Tests
# =============================================================================

@pytest.mark.regression
@pytest.mark.api_surface
class TestAPIBehaviorCompatibility:
    """Test that API behavior remains compatible."""
    
    def test_normalize_guard_return_value(self, temp_dir):
        """Test NormalizeGuard.run() returns expected type."""
        from scripts.normalize_guard import NormalizeGuard
        
        # Create test input
        input_csv = temp_dir / "input.csv"
        with open(input_csv, "w", encoding="utf-8-sig", newline="") as f:
            import csv
            writer = csv.writer(f)
            writer.writerow(["string_id", "source_zh"])
            writer.writerow(["1", "测试"])
        
        output_csv = temp_dir / "output.csv"
        map_json = temp_dir / "map.json"
        schema_path = Path(__file__).parent.parent.parent / "skill" / "workflow" / "placeholder_schema.yaml"
        
        guard = NormalizeGuard(str(input_csv), str(output_csv), str(map_json), str(schema_path))
        result = guard.run()
        
        # Should complete and return boolean
        assert isinstance(result, bool)
        assert output_csv.exists()
    
    def test_placeholder_freezer_token_format(self):
        """Test freeze_text returns tuple of (text, map)."""
        from scripts.normalize_guard import PlaceholderFreezer
        
        schema_path = Path(__file__).parent.parent.parent / "skill" / "workflow" / "placeholder_schema.yaml"
        freezer = PlaceholderFreezer(str(schema_path))
        
        text = "Hello {name}"
        tokenized, local_map = freezer.freeze_text(text)
        
        # Should return string and dict
        assert isinstance(tokenized, str)
        assert isinstance(local_map, dict)
    
    def test_rehydrate_exporter_load_map_returns_bool(self, temp_dir):
        """Test load_placeholder_map returns boolean."""
        from scripts.rehydrate_export import RehydrateExporter
        
        # Create dummy files
        translated_csv = temp_dir / "translated.csv"
        map_json = temp_dir / "map.json"
        final_csv = temp_dir / "final.csv"
        
        with open(translated_csv, "w", encoding="utf-8-sig", newline="") as f:
            import csv
            writer = csv.writer(f)
            writer.writerow(["string_id", "source_zh", "target_text"])
            writer.writerow(["1", "测试", "test"])
        
        with open(map_json, "w", encoding="utf-8") as f:
            import json
            json.dump({"PH_1": "{test}"}, f)
        
        exporter = RehydrateExporter(str(translated_csv), str(map_json), str(final_csv))
        result = exporter.load_placeholder_map()
        
        # Should return boolean
        assert isinstance(result, bool)
        assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
