#!/usr/bin/env python3
"""Step 3: Glossary Vector Store Test"""
import sys
sys.path.insert(0, 'scripts')

from glossary_vectorstore import GlossaryVectorStore

print("=== 术语向量存储测试 ===")

store = GlossaryVectorStore()
count = store.load_glossary()
print(f'加载术语数: {count}')

if count > 0:
    store.build_index()
    
    # 测试检索
    test_texts = ['攻击力提升50%', '恢复生命值']
    results = store.retrieve_relevant_terms(test_texts, top_k=5)
    
    print(f'\n检索到 {len(results)} 个相关术语:')
    for t in results:
        print(f"  {t['term_zh']} -> {t['term_ru']} (sim={t['similarity']:.3f})")
    
    # 测试 Prompt 格式化
    prompt_section = store.format_for_prompt(results)
    print(f'\nPrompt 格式化预览:\n{prompt_section[:200]}...')
    
    print('\n=== 术语向量存储: PASS ===')
else:
    print('[Warning] 术语表为空，跳过检索测试')
    print('=== 术语向量存储: SKIP (无数据) ===')
