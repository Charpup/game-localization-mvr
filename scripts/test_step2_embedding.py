#!/usr/bin/env python3
"""Step 2: Embedding API Connectivity Test"""
import sys
sys.path.insert(0, 'scripts')

from runtime_adapter import EmbeddingClient

print("=== Embedding API 连通性测试 ===")
client = EmbeddingClient()

# 单条测试
emb = client.embed_single('测试文本')
print(f'✅ 单条向量化成功，维度: {len(emb)}')

# 批量测试
texts = ['攻击力', '防御力', '生命值']
embs = client.embed_batch(texts)
print(f'✅ 批量向量化成功，形状: {embs.shape}')

# 相似度测试
sim = client.cosine_similarity(embs[0], embs[1])
print(f'✅ 余弦相似度计算成功: {sim:.4f}')

print('\n=== Embedding API 连通性: PASS ===')
