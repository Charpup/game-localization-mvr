#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate sample_30k.csv with 30,000 rows of synthetic data for performance testing.

This script creates representative game localization data with:
- Simple Chinese text
- Text with placeholders ({0}, %d, etc.)
- Text with Unity/HTML tags (<color>, <b>, <i>)
- Mixed content
- Various lengths and complexity levels
"""

import csv
import random
import sys
from pathlib import Path

# Sample Chinese vocabulary for game localization
NOUNS = [
    "战士", "法师", "盗贼", "牧师", "猎人", "骑士", "巫师", "刺客",
    "武器", "护甲", "盾牌", "长剑", "法杖", "弓箭", "匕首", "战斧",
    "药水", "卷轴", "宝石", "金币", "经验", "等级", "技能", "天赋",
    "任务", "副本", "公会", "队伍", "好友", "敌人", "首领", "怪物",
    "攻击", "防御", "治疗", "魔法", "暴击", "闪避", "命中", "格挡",
    "森林", "山脉", "河流", "城堡", "村庄", "洞穴", "沙漠", "雪原",
    "火焰", "冰霜", "雷电", "暗影", "圣光", "自然", "奥术", "鲜血",
    "龙", "恶魔", "精灵", "兽人", "亡灵", "巨魔", "牛头人", "矮人"
]

VERBS = [
    "获得", "使用", "装备", "学习", "升级", "击败", "完成", "接受",
    "攻击", "施放", "治疗", "召唤", "召唤", "发现", "探索", "收集",
    "制造", "交易", "出售", "购买", "修理", "强化", "附魔", "镶嵌",
    "进入", "离开", "传送", "复活", "休息", "训练", "挑战", "征服"
]

ADJECTIVES = [
    "强大的", "神秘的", "古老的", "稀有的", "传说的", "史诗的", "普通的", "破旧的",
    "锋利的", "坚固的", "迅捷的", "智慧的", "勇敢的", "狡猾的", "神圣的", "邪恶的",
    "燃烧的", "冰冻的", "闪耀的", "黑暗的", "光明的", "狂暴的", "宁静的", "致命的"
]

PLACEHOLDERS = [
    "{0}", "{1}", "{2}", "{name}", "{player}", "{target}", "{value}", "{amount}",
    "%d", "%s", "%f", "%1$d", "%2$s",
    "[NAME]", "[ITEM]", "[TARGET]", "[VALUE]",
]

TAGS_OPEN = [
    '<color=#FF0000>', '<color=#00FF00>', '<color=#0000FF>', '<color=#FFFF00>',
    '<b>', '<i>', '<size=14>', '<size=16>'
]

TAGS_CLOSE = [
    '</color>', '</b>', '</i>', '</size>'
]

CONTEXTS = [
    "ui_button", "ui_label", "dialogue", "quest_desc", "item_name", 
    "item_desc", "skill_name", "skill_desc", "npc_name", "npc_dialogue",
    "system_msg", "error_msg", "tooltip", "loading_tip", "achievement"
]


def generate_simple_text():
    """Generate simple Chinese text without placeholders or tags."""
    patterns = [
        lambda: f"{random.choice(ADJECTIVES)}{random.choice(NOUNS)}",
        lambda: f"{random.choice(VERBS)}{random.choice(NOUNS)}",
        lambda: f"{random.choice(NOUNS)}的{random.choice(NOUNS)}",
        lambda: f"{random.choice(ADJECTIVES)}{random.choice(NOUNS)}之{random.choice(NOUNS)}",
        lambda: random.choice(NOUNS),
        lambda: f"{random.choice(VERBS)}了{random.choice(ADJECTIVES)}{random.choice(NOUNS)}",
    ]
    return random.choice(patterns)()


def generate_with_placeholders():
    """Generate text with placeholder patterns."""
    base = generate_simple_text()
    placeholder = random.choice(PLACEHOLDERS)
    
    patterns = [
        lambda: f"{base}：{placeholder}",
        lambda: f"{placeholder}{base}",
        lambda: f"{base}{placeholder}",
        lambda: f"{placeholder}获得了{base}",
        lambda: f"使用{placeholder}来{random.choice(VERBS)}{base}",
        lambda: f"{base}（{placeholder}）",
        lambda: f"{random.choice(VERBS)}{placeholder}点{base}",
    ]
    return random.choice(patterns)()


def generate_with_tags():
    """Generate text with Unity/HTML tags."""
    base = generate_simple_text()
    tag_open = random.choice(TAGS_OPEN)
    
    # Match close tag
    if "color" in tag_open:
        tag_close = "</color>"
    elif "<b>" in tag_open:
        tag_close = "</b>"
    elif "<i>" in tag_open:
        tag_close = "</i>"
    else:
        tag_close = "</size>"
    
    patterns = [
        lambda: f"{tag_open}{base}{tag_close}",
        lambda: f"{tag_open}{base}{tag_close}已{random.choice(VERBS)}",
        lambda: f"{base}：{tag_open}{random.choice(ADJECTIVES)}{tag_close}",
        lambda: f"{tag_open}警告{tag_close}{base}",
        lambda: f"{tag_open}{random.choice(VERBS)}中...{tag_close}",
    ]
    return random.choice(patterns)()


def generate_complex():
    """Generate text with both placeholders and tags."""
    base = generate_simple_text()
    placeholder = random.choice(PLACEHOLDERS)
    tag_open = random.choice(TAGS_OPEN)
    
    # Match close tag
    if "color" in tag_open:
        tag_close = "</color>"
    elif "<b>" in tag_open:
        tag_close = "</b>"
    elif "<i>" in tag_open:
        tag_close = "</i>"
    else:
        tag_close = "</size>"
    
    patterns = [
        lambda: f"{tag_open}{placeholder}{tag_close}{base}",
        lambda: f"{base}：{tag_open}{placeholder}{tag_close}",
        lambda: f"{tag_open}{base}{tag_close}×{placeholder}",
        lambda: f"{random.choice(VERBS)}{tag_open}{placeholder}{tag_close}获得{base}",
    ]
    return random.choice(patterns)()


def generate_long_text():
    """Generate longer text that exceeds the 500 char threshold."""
    parts = []
    for _ in range(random.randint(5, 10)):
        parts.append(generate_simple_text())
    
    # Add some complexity
    if random.random() > 0.5:
        parts.append(f"奖励：{random.choice(PLACEHOLDERS)}")
    if random.random() > 0.5:
        parts.append(f"目标：{random.choice(PLACEHOLDERS)}")
    
    return "。".join(parts) + "。"


def generate_row(row_id: int):
    """Generate a single row of data."""
    # Determine row type (weighted distribution)
    row_type = random.choices(
        ["simple", "placeholder", "tags", "complex", "long"],
        weights=[40, 25, 15, 15, 5]
    )[0]
    
    if row_type == "simple":
        source_zh = generate_simple_text()
    elif row_type == "placeholder":
        source_zh = generate_with_placeholders()
    elif row_type == "tags":
        source_zh = generate_with_tags()
    elif row_type == "complex":
        source_zh = generate_complex()
    else:  # long
        source_zh = generate_long_text()
    
    return {
        "string_id": f"TEST_{row_id:08d}",
        "source_zh": source_zh,
        "context": random.choice(CONTEXTS),
    }


def main():
    output_path = Path(__file__).parent.parent / "tests" / "data" / "sample_30k.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Generating 30,000 rows of synthetic data...")
    print(f"Output: {output_path}")
    
    # Set seed for reproducibility
    random.seed(42)
    
    row_count = 30000
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["string_id", "source_zh", "context"])
        writer.writeheader()
        
        for i in range(row_count):
            row = generate_row(i)
            writer.writerow(row)
            
            # Progress indicator
            if (i + 1) % 5000 == 0:
                print(f"  Generated {i + 1}/{row_count} rows...")
    
    print(f"✅ Successfully generated {row_count} rows!")
    
    # Print statistics
    print("\n📊 Data Statistics:")
    print(f"  - Simple text: ~40%")
    print(f"  - With placeholders: ~25%")
    print(f"  - With tags: ~15%")
    print(f"  - Complex (both): ~15%")
    print(f"  - Long text (>500 chars): ~5%")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
