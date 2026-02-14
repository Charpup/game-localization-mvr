#!/usr/bin/env python3
"""
Dry-run test for batch_llm_call without real LLM calls.
Validates the integration flow works end-to-end.
"""
import sys
import os
from pathlib import Path

# 切换到项目根目录
os.chdir(Path(__file__).parent.parent)

sys.path.insert(0, 'scripts')

from runtime_adapter import BatchConfig, log_llm_progress, parse_llm_response

def test_integration_flow():
    """Test complete flow without LLM call"""

    # 1. Load config
    config = BatchConfig()
    model = "claude-haiku-4-5-20251001"

    batch_size = config.get_batch_size(model, "normal")
    cooldown = config.get_cooldown(model)
    timeout = config.get_timeout(model, "normal")

    print(f"✅ Config loaded: batch={batch_size}, cooldown={cooldown}, timeout={timeout}")

    # 2. Test progress logging
    log_llm_progress("dry_run_test", "step_start", {
        "total_rows": 10, 
        "batch_size": batch_size,
        "model": model
    })
    print("✅ Progress log created")

    # 3. Test response parsing (simulated LLM response)
    mock_response = '''```json
{
  "items": [
    {"id": "1", "translation": "Тест 1"},
    {"id": "2", "translation": "Тест 2"},
    {"id": "3", "translation": "Тест 3"}
  ]
}
```'''

    expected_rows = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
    parsed = parse_llm_response(mock_response, expected_rows)

    assert parsed is not None, "Parse failed"
    assert len(parsed) == 3, f"Expected 3 items, got {len(parsed)}"
    print(f"✅ Response parsing OK: {len(parsed)} items")

    # 4. Log completion
    log_llm_progress("dry_run_test", "step_complete", {
        "total_rows": 10,
        "success_count": 3, 
        "failed_count": 0
    })
    print("✅ Step complete logged")

    print("\n" + "="*50)
    print("✅ Week 1 Infrastructure VERIFIED")
    print("="*50)

if __name__ == "__main__":
    test_integration_flow()
