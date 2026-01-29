import json
with open('data/translate_checkpoint.json', 'r', encoding='utf-8') as f:
    ckpt = json.load(f)
print(f"Stats: ok={ckpt['stats'].get('ok', 0)}, escalated={ckpt['stats'].get('escalated', 0)}")
print(f"batch_idx: {ckpt.get('batch_idx', 0)}")
print(f"Done IDs count: {len(ckpt.get('done_ids', {}))}")
