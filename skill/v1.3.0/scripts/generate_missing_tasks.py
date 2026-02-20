
import csv
import json
import io
import sys
from pathlib import Path

# Fix Windows stdout
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def main():
    root = Path("..")
    repaired_csv = root / "data/Production Batch/01. Omni Production_go/Production_go_repaired.csv"
    norm_csv = root / "data/Production Batch/01. Omni Production_go/Production_go_normalized.csv"
    output_tasks = root / "data/Production Batch/01. Omni Production_go/tasks_missing_rows.jsonl"
    
    # Load normalized source text map
    norm_map = {}
    with open(norm_csv, "r", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            norm_map[r["string_id"]] = r
            
    tasks = []
    
    with open(repaired_csv, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            target = r.get("target_text", "").strip()
            # If empty or missing
            if not target:
                sid = r["string_id"]
                norm_row = norm_map.get(sid, {})
                
                task = {
                    "string_id": sid,
                    "source_text": norm_row.get("tokenized_zh") or norm_row.get("source_zh") or "",
                    "current_translation": "",
                    "issues": [{"type": "empty_translation", "severity": "critical"}],
                    "severity": "critical",
                    "max_length_target": norm_row.get("max_length_target") or 0,
                    "content_type": "string"
                }
                tasks.append(task)
                
    print(f"Found {len(tasks)} empty rows.")
    
    if tasks:
        with open(output_tasks, "w", encoding="utf-8") as f:
            for t in tasks:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
        print(f"Generated tasks file: {output_tasks}")

if __name__ == "__main__":
    main()
