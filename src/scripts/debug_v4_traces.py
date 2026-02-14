import json

with open('data/llm_trace_gate.jsonl', 'r', encoding='utf-8') as f:
    with open('reports/v4_debug.txt', 'w', encoding='utf-8') as out:
        for line in f:
            if 'empty_gate_v4' in line:
                try:
                    data = json.loads(line)
                    model = data.get('model') or data.get('metadata', {}).get('model_override')
                    output = data.get('output')
                    out.write(f"MODEL: {model}\n")
                    out.write(f"OUTPUT: {output}\n")
                    out.write("-" * 40 + "\n")
                except:
                    out.write(f"FAILED TO PARSE LINE: {line[:100]}...\n")
