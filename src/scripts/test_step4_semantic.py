#!/usr/bin/env python3
"""Step 4: Semantic Scorer Test"""
import sys
sys.path.insert(0, 'scripts')

from semantic_scorer import SemanticScorer

print("=== 语义一致性评分测试 ===")

scorer = SemanticScorer()

# 测试数据: 包含正确翻译和故意错误翻译
pairs = [
    {'id': '1', 'source_zh': '生命值', 'target_ru': 'Здоровье'},           # 正确
    {'id': '2', 'source_zh': '攻击力', 'target_ru': 'Атака'},              # 正确
    {'id': '3', 'source_zh': '防御力', 'target_ru': 'Защита'},             # 正确
    {'id': '4', 'source_zh': '金币', 'target_ru': 'Абсолютно другое'},     # 故意错误
    {'id': '5', 'source_zh': '技能描述文本', 'target_ru': '123456'},       # 完全无关
]

results = scorer.score_batch(pairs)

print('\n评分结果:')
print('-' * 50)
for i, r in enumerate(results):
    src = pairs[i]['source_zh']
    tgt = pairs[i]['target_ru'][:20]
    print(f"ID={r['id']}: score={r['semantic_score']:.3f}, status={r['semantic_status']:8} | {src} -> {tgt}")

# 验证逻辑
correct_scores = [results[i]['semantic_score'] for i in range(3)]
wrong_scores = [results[i]['semantic_score'] for i in range(3, 5)]

avg_correct = sum(correct_scores) / len(correct_scores)
avg_wrong = sum(wrong_scores) / len(wrong_scores)

print(f'\n正确翻译平均分: {avg_correct:.3f}')
print(f'错误翻译平均分: {avg_wrong:.3f}')

if avg_correct > avg_wrong:
    print('\n✅ 语义评分可区分正确/错误翻译')
    print('=== 语义一致性评分: PASS ===')
else:
    print('\n❌ 语义评分未能区分正确/错误翻译')
    print('=== 语义一致性评分: FAIL ===')
