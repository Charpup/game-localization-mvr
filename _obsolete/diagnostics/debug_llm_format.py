#!/usr/bin/env python3
"""Debug script to check LLM response format."""
import json
import sys
sys.path.insert(0, 'scripts')
from batch_utils import parse_json_array
from runtime_adapter import LLMClient

llm = LLMClient()

test_input = [
    {'string_id': '1', 'tokenized_zh': '测试文本一'},
    {'string_id': '2', 'tokenized_zh': '测试文本二'}
]

system = '''You MUST return a JSON ARRAY. Each item MUST have keys: string_id, target_ru.
Example: [{"string_id": "1", "target_ru": "Текст"}]'''

user = json.dumps(test_input, ensure_ascii=False)

result = llm.chat(system=system, user=user, metadata={'step': 'translate'})
print('=== RAW RESPONSE ===')
print('Length:', len(result.text))
print('First 500 chars:', result.text[:500])
print('Repr:', repr(result.text[:500]))
print()
print('=== PARSED ===')
parsed = parse_json_array(result.text)
print(parsed)
if parsed:
    for item in parsed:
        print(f"  string_id type: {type(item.get('string_id'))}, value: {repr(item.get('string_id'))}")
