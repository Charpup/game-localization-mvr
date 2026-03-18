import json
import os

TRACE_PATH = "data/llm_trace.jsonl"
STEP = "destructive_batch_v1"
TARGET_MODEL = "gpt-5.2"

def debug_failures():
    if not os.path.exists(TRACE_PATH):
        print("Trace file not found.")
        return

    with open(TRACE_PATH, "r", encoding="utf-8") as f:
        for line in f:
            try:
                event = json.loads(line)
                if event.get("step") == STEP and (event.get("selected_model") == TARGET_MODEL or event.get("model") == TARGET_MODEL):
                    if event.get("type") == "llm_call":
                        print(f"--- SUCCESSFUL CALL (but maybe failed validation) ---")
                        print(f"Latency: {event.get('latency_ms')}ms")
                        print(f"Output: {event.get('output')[:200]}...")
                    elif event.get("type") == "llm_error":
                        print(f"--- ERROR EVENT ---")
                        print(f"Kind: {event.get('kind')}")
                        print(f"Msg: {event.get('msg')}")
            except:
                continue

if __name__ == "__main__":
    debug_failures()
