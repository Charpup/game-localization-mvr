
import json
import yaml
from pathlib import Path

def main():
    root = Path("..")
    qa_report = root / "data/Production Batch/01. Omni Production_go/qa_hard_report.json"
    missing_tasks = root / "data/Production Batch/01. Omni Production_go/tasks_missing_rows.jsonl"
    output_tasks = root / "data/Production Batch/01. Omni Production_go/repair_tasks_all.jsonl"
    
    tasks = []
    
    # Load Hard QA Report
    if qa_report.exists():
        with open(qa_report, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "errors" in data:
                tasks.extend(data["errors"])
                print(f"Loaded {len(data['errors'])} tasks from QA Report.")
    
    # Load Missing Rows Tasks
    if missing_tasks.exists():
        count = 0
        with open(missing_tasks, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    tasks.append(json.loads(line))
                    count += 1
        print(f"Loaded {count} tasks from Missing Rows file.")
        
    # Deduplicate by string_id
    unique_tasks = {str(t['string_id']): t for t in tasks}
    print(f"Total unique tasks: {len(unique_tasks)}")
    
    # Write Combined
    with open(output_tasks, 'w', encoding='utf-8') as f:
        for t in unique_tasks.values():
            f.write(json.dumps(t, ensure_ascii=False) + "\n")
            
    print(f"✅ Saved combined tasks to: {output_tasks}")

if __name__ == "__main__":
    main()
