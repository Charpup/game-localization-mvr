
import csv
import statistics
from pathlib import Path

INPUT_FILE = "data/Production Batch/01. Omni Production_go/Production_go_normalized.csv"

def main():
    if not Path(INPUT_FILE).exists():
        print(f"File not found: {INPUT_FILE}")
        return

    lengths = []
    
    with open(INPUT_FILE, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        print(f"Headers: {headers}")
        
        has_long_col = "is_long_text" in headers
        print(f"Has 'is_long_text' column: {has_long_col}")
        
        for row in reader:
            text = row.get("tokenized_zh") or row.get("source_zh") or ""
            lengths.append(len(text))

    if not lengths:
        print("No data found.")
        return

    print(f"\nTotal Rows: {len(lengths)}")
    print(f"Min Length: {min(lengths)}")
    print(f"Max Length: {max(lengths)}")
    print(f"Avg Length: {statistics.mean(lengths):.2f}")
    print(f"Median Length: {statistics.median(lengths):.2f}")
    
    # Distribution buckets
    buckets = [0, 50, 100, 200, 500, 1000]
    dist = {b: 0 for b in buckets}
    
    for l in lengths:
        for b in reversed(buckets):
            if l >= b:
                dist[b] += 1
                break
                
    print("\nLength Distribution (chars):")
    for b in buckets:
        count = dist[b]
        pct = (count / len(lengths)) * 100
        print(f" >= {b}: {count} ({pct:.2f}%)")
        
    # Estimate token usage (heuristic: 1.5 chars per token for ZH + prompts)
    est_tokens_per_50_batch = (statistics.mean(lengths) * 1.5 * 50) + 1000 # +1000 for prompt boilerplate
    print(f"\nEst. Tokens per 50-batch (Avg): {est_tokens_per_50_batch:.0f}")
    
    est_tokens_max_50_batch = (max(lengths) * 1.5 * 50) + 1000
    print(f"Est. Tokens per 50-batch (Worst-case if all max): {est_tokens_max_50_batch:.0f}")

if __name__ == "__main__":
    main()
