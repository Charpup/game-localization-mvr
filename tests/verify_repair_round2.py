
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import sys
import os

# Add scripts directory to path
sys.path.append(os.path.join(os.getcwd(), 'scripts'))

from repair_loop_v2 import BatchRepairLoop, RepairTask

class TestRepairLoopRounds(unittest.TestCase):
    def setUp(self):
        self.config = {
            "repair_loop": {
                "max_rounds": 2,
                "batch_size": 1,
                "rounds": {
                    1: {"model": "model-round-1", "prompt_variant": "standard"},
                    2: {"model": "model-round-2", "prompt_variant": "detailed"}
                }
            }
        }
        self.loop = BatchRepairLoop(self.config, qa_type="soft", output_dir=".")

    @patch('runtime_adapter.LLMClient')
    def test_round_2_model_args(self, MockLLMClient):
        # Setup mock
        mock_client = MockLLMClient.return_value
        mock_result = MagicMock()
        # Round 1 fails (returns empty list or non-JSON), Round 2 succeeds
        mock_result.text = '{"string_id": "1", "fixed_translation": "repaired_round_1"}' 
        
        # We need to control the mock to fail Round 1 but succeed Round 2?
        # Actually validation happens outside. 
        # So we can just checking the CALL arguments.
        
        mock_client.chat.return_value = mock_result

        # Setup data
        tasks = [RepairTask({"string_id": "1", "source_text": "src", "current_translation": "bad"})]
        df = pd.DataFrame([{"string_id": 1, "source_zh": "src", "target_ru": "bad"}])

        # Mock _validate_repair to fail Round 1, succeed Round 2
        # Round 1: validation failed
        # Round 2: validation passed
        
        original_validate = self.loop._validate_repair
        
        def side_effect_validate(translation, task):
            # Check call stack or something? 
            # Easier: if Loop is in Round 1, fail. Round 2, pass.
            # But _validate_repair doesn't know round directly.
            # We can check the translation content if we controlled it?
            return {"passed": False} # Always fail for now to force Round 2

        self.loop._validate_repair = MagicMock(side_effect=side_effect_validate)

        # Run
        try:
           self.loop.run(tasks, df)
        except Exception:
           pass # We expect it might escalate or finish

        # Verify calls
        # Expected: 2 calls to chat()
        # Call 1: Round 1, model="model-round-1"
        # Call 2: Round 2, model="model-round-2"
        
        calls = mock_client.chat.call_args_list
        self.assertTrue(len(calls) >= 2, f"Expected at least 2 calls, got {len(calls)}")
        
        # Check Round 1 args
        args1, kwargs1 = calls[0]
        metadata_1 = kwargs1.get('metadata', {})
        self.assertEqual(metadata_1.get('round'), 1)
        self.assertEqual(metadata_1.get('model_override'), "model-round-1")
        # Ensure 'model' is NOT in kwargs directly
        self.assertNotIn('model', kwargs1)

        # Check Round 2 args
        args2, kwargs2 = calls[1]
        metadata_2 = kwargs2.get('metadata', {})
        self.assertEqual(metadata_2.get('round'), 2)
        self.assertEqual(metadata_2.get('model_override'), "model-round-2")
        self.assertNotIn('model', kwargs2, "Round 2 call should not have 'model' kwarg")

        print("\n✅ Verification passed: Round 2 triggered with correct model_override and no 'model' arg crash.")

if __name__ == '__main__':
    unittest.main()
