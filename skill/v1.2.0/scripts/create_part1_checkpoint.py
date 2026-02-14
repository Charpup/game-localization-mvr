"""
Create Part1 checkpoint lock from current checkpoint.
Part1 ended at 18,820 rows completed.
"""
import json

# Load current checkpoint
with open('data/translate_checkpoint.json', 'r', encoding='utf-8') as f:
    ckpt = json.load(f)

print(f"Original checkpoint: {len(ckpt.get('done_ids', {}))} done_ids")

# Part 1 断点: 18,820 行
PART1_ROWS = 18820

# 只保留前 PART1_ROWS 个 done_ids
done_ids = ckpt.get('done_ids', {})
keys = list(done_ids.keys())[:PART1_ROWS]
part1_done_ids = {k: done_ids[k] for k in keys}

# 创建 Part1 checkpoint
part1_ckpt = {
    "done_ids": part1_done_ids,
    "stats": {
        "ok": PART1_ROWS,
        "escalated": 0
    },
    "batch_idx": 0  # 重置 batch_idx
}

# 保存 Part1 锁定副本
output_path = 'data/test06_outputs/checkpoint_part1.lock.json'
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(part1_ckpt, f, ensure_ascii=False, indent=2)

print(f"Part1 checkpoint created: {len(part1_done_ids)} done_ids")
print(f"Saved to: {output_path}")
