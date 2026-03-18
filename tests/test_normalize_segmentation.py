
import os
import pytest
from scripts.normalize_guard import PlaceholderFreezer

SCHEMA_PATH = "workflow/placeholder_schema.yaml"

@pytest.fixture
def freezer():
    if not os.path.exists(SCHEMA_PATH):
        pytest.skip(f"Schema not found at {SCHEMA_PATH}")
    return PlaceholderFreezer(SCHEMA_PATH)

def test_chinese_segmentation(freezer):
    text = "提升自身攻击力{0}点"
    # Ensure counters are reset if needed, though new instance should be clean
    # freezer.reset_counters() 
    
    frozen, mapping = freezer.freeze_text(text, source_lang='zh-CN')

    # Verify segmentation (spaces added)
    # Expected: "提升 自身 攻击力 {0} 点" -> tokens -> "提升 自身 攻击力 ⟦PH_1⟧ 点"
    # Note: Token format depends on schema. Default in code was PH_{n}.
    # We check if spaces exist between Chinese chars/words.
    
    print(f"Original: {text}")
    print(f"Frozen: {frozen}")
    
    assert ' ' in frozen, "Should have spaces for segmentation"
    assert '自身' in frozen, "Should preserve Chinese words"
    
    # Check if placeholder is frozen (format ⟦...⟧)
    # The exact token name depends on schema patterns, but it should replace {0}
    assert '{0}' not in frozen
    assert '⟦' in frozen

def test_non_chinese_passthrough(freezer):
    text = "Increase attack by {0}"
    frozen, _ = freezer.freeze_text(text, source_lang='en-US')
    
    # English shouldn't have extra spaces added by jieba
    # Though jieba.lcut might not affect english much, we guard it with `if source_lang.startswith('zh')`
    
    # Original spaces count
    original_spaces = text.count(' ')
    frozen_spaces = frozen.count(' ')
    
    # Frozen text will replace {0} with token, which might have spaces around it or not depending on regex replacement?
    # Actually regex replacement just swaps.
    # So space count should stay relatively same, definitely not exploding like segmented chinese.

    print(f"Frozen EN: {frozen}")
    assert frozen_spaces == original_spaces, "English should not differ in space count"


def test_color_tag_and_short_closing_tag_is_tokenized(freezer):
    text = "<color=#ffffff>选择一条</c><color=#f6bd0f>新增</color><color=#ffffff>的属性</c>"

    frozen, local_map = freezer.freeze_text(text, source_lang='zh-CN')

    # 问题复现路径里，</c> 与 <color=...> 一起出现时不会再被模型直接处理
    assert '</c>' not in frozen
    assert '<c>' not in frozen

    # 至少有一类标签会被识别为 TAG_ token
    assert any(token.startswith('TAG_') for token in local_map.keys())

    # 至少出现这两个可识别的闭合/开标签原样映射
    assert '</c>' in local_map.values()
    assert any(value.startswith('<color=#') for value in local_map.values())
