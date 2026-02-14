import json
ckpt = json.load(open('data/test06_outputs/checkpoint_part1.lock.json', 'r', encoding='utf-8'))
done_ids = ckpt.get('done_ids', {})
print(f"Part1 Lock Done IDs: {len(done_ids)}")
print(f"Stats: {ckpt.get('stats', {})}")
print(f"batch_idx: {ckpt.get('batch_idx', 0)}")
keys = list(done_ids.keys())[:5]
print(f"Sample IDs: {keys}")
