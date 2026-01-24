#!/usr/bin/env python3
import yaml
import json

print('=== Phase 4: 配置验证 ===')
print('')

# 1. 验证 llm_routing.yaml
print('--- llm_routing.yaml ---')
with open('config/llm_routing.yaml', 'r') as f:
    routing = yaml.safe_load(f)

steps = list(routing.get('routing', {}).keys())
print(f'Chat 模型步骤: {len(steps)}')
for step in steps[:5]:
    cfg = routing['routing'][step]
    default = cfg.get('default') if cfg else 'null'
    print(f'  {step}: {default}')
print(f'  ... 共 {len(steps)} 个')

print('')

embedding = routing.get('embedding', {})
print(f'Embedding 默认模型: {embedding.get("default", "未配置")}')
usage = embedding.get('usage', {})
for use_case, cfg in usage.items():
    print(f'  {use_case}: model={cfg.get("model")}, top_k={cfg.get("top_k", "N/A")}')

print('')

# 2. 验证 batch_runtime_v2.json
print('--- batch_runtime_v2.json ---')
with open('config/batch_runtime_v2.json', 'r') as f:
    batch_cfg = json.load(f)

models = list(batch_cfg.get('models', {}).keys())
print(f'已配置模型: {len(models)}')
for model in models:
    cfg = batch_cfg['models'][model]
    print(f'  {model}: batch={cfg.get("max_batch_size")}, status={cfg.get("status")}')

print('')

# 3. 交叉验证
print('--- 交叉验证 ---')
routing_models = set()
for step, cfg in routing.get('routing', {}).items():
    if cfg and cfg.get('default'):
        routing_models.add(cfg['default'])
    for fb in (cfg.get('fallback') or []) if cfg else []:
        routing_models.add(fb)

embedding_default = embedding.get('default')
if embedding_default:
    routing_models.add(embedding_default)
for fb in embedding.get('fallback', []):
    routing_models.add(fb)

batch_models = set(batch_cfg.get('models', {}).keys())
missing_in_batch = routing_models - batch_models - {None, 'null'}
if missing_in_batch:
    print(f'⚠️ routing 中引用但 batch 中未定义: {missing_in_batch}')
else:
    print('✅ 所有模型都有 batch 配置 (含 Embedding)')

if 'text-embedding-3-small' in batch_models:
    print('✅ text-embedding-3-small 已配置')
else:
    print('❌ text-embedding-3-small 缺失')

print('')
print('=== 验证完成 ===')
