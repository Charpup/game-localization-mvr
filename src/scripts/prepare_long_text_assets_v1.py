import pandas as pd
import json
import hashlib
import os

POOL_FILE = "data/normalized_pool_v1.csv"
OUTPUT_CSV = "data/destructive_v1_template_A_v2.csv"
OUTPUT_META = "data/destructive_v1_template_A_v2.meta.json"

def calculate_sha256(filepath):
    sha = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            sha.update(chunk)
    return sha.hexdigest()

def prepare_assets():
    if not os.path.exists(POOL_FILE):
        print(f"❌ Error: {POOL_FILE} not found.")
        return

    pool = pd.read_csv(POOL_FILE)
    
    # 根据指令要求：80% 长文本 (> 300 字符), 20% 其他
    # 30 行总数 -> 24 行长文本, 6 行其他
    
    long_text_pool = pool[pool['source_zh'].str.len() > 300]
    
    if len(long_text_pool) < 24:
        print(f"⚠️ Warning: Only found {len(long_text_pool)} long rows (>300 chars). Using all of them.")
        selected_long = long_text_pool
    else:
        selected_long = long_text_pool.sample(n=24, random_state=42)
        
    other_pool = pool[~pool['string_id'].isin(selected_long['string_id'])]
    if len(other_pool) < 6:
        selected_others = other_pool
    else:
        selected_others = other_pool.sample(n=6, random_state=42)
        
    # 合并并随机打乱
    template_a_v2 = pd.concat([selected_long, selected_others]).sample(frac=1, random_state=42)
    
    # 补齐到 30 行（以防万一）
    if len(template_a_v2) < 30:
        remaining = pool[~pool['string_id'].isin(template_a_v2['string_id'])].sample(n=30-len(template_a_v2), random_state=42)
        template_a_v2 = pd.concat([template_a_v2, remaining])

    # 保存
    template_a_v2.to_csv(OUTPUT_CSV, index=False, lineterminator='\n')
    print(f"✅ Generated {OUTPUT_CSV} ({len(template_a_v2)} rows)")
    
    # 生成元数据
    sha256 = calculate_sha256(OUTPUT_CSV)
    meta = {
        "gate": "long_text_gate_v1",
        "template": "A_v2",
        "source_dataset_id": "normalized_pool_v1",
        "total_rows": len(template_a_v2),
        "sha256": sha256,
        "rules_version": "1.0",
        "immutable": True
    }
    
    with open(OUTPUT_META, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print(f"✅ Generated {OUTPUT_META}")

if __name__ == "__main__":
    prepare_assets()
