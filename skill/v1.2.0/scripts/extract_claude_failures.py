import json
import os

trace_file = r"data/llm_trace_gate.jsonl"
output_file = r"reports/claude_v4_failure_raw.json"
target_models = ["claude-haiku-4-5-20251001", "claude-sonnet-4-5-20250929"]
target_step = "empty_gate_v4"

extracted = []

if not os.path.exists(trace_file):
    print(f"Error: {trace_file} not found.")
    exit(1)

with open(trace_file, "r", encoding="utf-8") as f:
    for line in f:
        try:
            entry = json.loads(line)
            metadata = entry.get("metadata", {})
            model = entry.get("model") or metadata.get("model_override")
            
            if metadata.get("step") == target_step:
                extracted.append({
                    "model": entry.get("model"),
                    "model_override": metadata.get("model_override"),
                    "metadata": metadata,
                    "system_prompt": entry.get("system"),
                    "user_prompt": entry.get("user"),
                    "raw_response": entry.get("text"),
                    "latency_ms": entry.get("latency_ms")
                })
        except Exception as e:
            continue

os.makedirs("reports", exist_ok=True)
with open(output_file, "w", encoding="utf-8") as f:
    json.dump(extracted, f, indent=2, ensure_ascii=False)

print(f"Successfully extracted {len(extracted)} entries to {output_file}")
for i, entry in enumerate(extracted):
    print(f"\n--- Entry {i+1}: {entry['model']} ---")
    print(f"Raw Response: {entry['raw_response']}")
