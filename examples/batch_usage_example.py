#!/usr/bin/env python3
"""批次调用使用示例"""

import sys
import os
from pathlib import Path

# 切换到项目根目录
os.chdir(Path(__file__).parent.parent)

sys.path.insert(0, "scripts")

from runtime_adapter import batch_llm_call
import json


def example_glossary_translate():
    """示例: 词汇表翻译"""

    # 模拟数据
    rows = [
        {"id": f"term_{i}", "source_text": f"测试术语{i}"}
        for i in range(1, 26)  # 25 个词条
    ]

    # 系统提示
    system_prompt = """You are a professional translator.
Translate glossary terms from Chinese to Russian.
Return ONLY a JSON object with 'items' array containing id and translated_text."""

    # 用户提示模板
    def user_prompt_template(items):
        return json.dumps({"items": items}, ensure_ascii=False)

    # 批次调用
    print("\n=== 示例: 词汇表翻译 ===\n")

    try:
        results = batch_llm_call(
            step="example_glossary_translate",
            rows=rows,
            model="claude-haiku-4-5-20251001",
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            content_type="normal",
            retry=1,
            allow_fallback=True
        )

        print(f"\n成功翻译 {len(results)} 个词条")
        print(f"示例结果: {results[0]}")

    except Exception as e:
        print(f"\n翻译失败: {e}")


if __name__ == "__main__":
    example_glossary_translate()
