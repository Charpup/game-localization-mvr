import csv
import os
import json
import hashlib
import re

POOL_FILE = "data/normalized_pool_v1.csv"
OUTPUT_DIR = "data"

def calculate_sha256(filepath):
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()

def extract_placeholders(text):
    patterns = [
        r"\{\d+\}", r"\{[a-zA-Z_][a-zA-Z0-9_]*\}",
        r"%s", r"%d", r"\$\{[^\}]+\}",
        r"\{\{[^\}]+\}\}", r"<[^>]+>", r"\[[^\]]+\]",
        r"【[^】]+】"
    ]
    ph = []
    for pat in patterns:
        ph.extend(re.findall(pat, text))
    return ph

def is_polluted(text):
    pollutants = ['{', '}', ':', ',', '"', '\\', '<color', '\n']
    return any(p in text for p in pollutants) or '\n' in text

def prepare_assets():
    pool = []
    with open(POOL_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pool.append(row)

    # Sort common helpers
    pool_by_len = sorted(pool, key=lambda x: len(x["source_zh"]), reverse=True)
    
    # --- Template A: Extreme Length Mix ---
    # 10% Long (12), 60% Short (72), 20% Medium (24), 10% Placeholder (12)
    long_rows = pool_by_len[:12]
    # Short rows (len <= 6)
    short_pool = [r for r in pool if len(r["source_zh"]) <= 6 and r not in long_rows]
    short_rows = short_pool[:72]
    # Medium rows (len 20-50 approx)
    medium_pool = [r for r in pool if 20 <= len(r["source_zh"]) <= 60 and r not in long_rows and r not in short_rows]
    medium_rows = medium_pool[:24]
    # Placeholder heavy
    ph_pool = [r for r in pool if extract_placeholders(r["source_zh"]) and r not in long_rows and r not in short_rows and r not in medium_rows]
    ph_rows = ph_pool[:12]
    
    template_a = long_rows + short_rows + medium_rows + ph_rows
    # Fill to 120 if short
    if len(template_a) < 120:
        remaining = [r for r in pool if r not in template_a]
        template_a += remaining[:120 - len(template_a)]
    
    # --- Template B: JSON/Escape Pollution ---
    # 40% Polluted (48), 60% Normal (72)
    polluted_pool = [r for r in pool if is_polluted(r["source_zh"])]
    polluted_rows = polluted_pool[:48]
    normal_pool = [r for r in pool if not is_polluted(r["source_zh"]) and r not in polluted_rows]
    normal_rows = normal_pool[:72]
    template_b = polluted_rows + normal_rows
    if len(template_b) < 120:
         remaining = [r for r in pool if r not in template_b]
         template_b += remaining[:120 - len(template_b)]

    # --- Template C: Placeholder Stress ---
    # 60% Multi-placeholder (72), 40% Normal (48)
    multi_ph_pool = sorted(pool, key=lambda x: len(extract_placeholders(x["source_zh"])), reverse=True)
    multi_ph_rows = multi_ph_pool[:72]
    normal_c_pool = [r for r in pool if r not in multi_ph_rows]
    normal_c_rows = normal_c_pool[:48]
    template_c = multi_ph_rows + normal_c_rows

    results = {
        "A": template_a[:120],
        "B": template_b[:120],
        "C": template_c[:120]
    }

    for key, data in results.items():
        name = f"destructive_v1_template_{key}"
        csv_path = os.path.join(OUTPUT_DIR, f"{name}.csv")
        meta_path = os.path.join(OUTPUT_DIR, f"{name}.meta.json")
        
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=["string_id", "source_zh"])
            writer.writeheader()
            for row in data:
                writer.writerow({"string_id": row["string_id"], "source_zh": row["source_zh"]})
        
        sha = calculate_sha256(csv_path)
        meta = {
            "gate": "destructive_batch_v1",
            "template": key,
            "source_dataset_id": "normalized_pool_v1",
            "total_rows": len(data),
            "sha256": sha,
            "rules_version": "1.0",
            "immutable": True
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
            
        print(f"Generated {csv_path} (sha256: {sha[:8]}...)")

if __name__ == "__main__":
    prepare_assets()
