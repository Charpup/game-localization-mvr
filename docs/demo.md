# Normalize Guard 演示

## 完整运行示例

### 1. 准备输入文件

**data/input.csv**:
```csv
string_id,source_zh,context,max_length
welcome_msg,欢迎 {0} 来到游戏！,主菜单欢迎语,50
level_up,恭喜！你已升至 {level} 级,升级提示,40
item_count,你有 %d 个物品,背包提示,30
color_text,<color=#FF00FF>稀有物品</color>获得！,战利品提示,60
multi_placeholder,玩家 {playerName} 在 {location} 获得了 {itemName},游戏日志,100
newline_test,第一行\n第二行,多行文本,50
printf_style,%s 击败了 %s！,战斗日志,80
```

### 2. 运行脚本

```bash
python scripts/normalize_guard.py \
  data/input.csv \
  data/draft.csv \
  data/placeholder_map.json \
  workflow/placeholder_schema.yaml
```

### 3. 脚本输出

```
🚀 Starting normalize guard...
   Input: data\input.csv
   Output draft: data\draft.csv
   Output map: data\placeholder_map.json
   Schema: workflow\placeholder_schema.yaml

✅ Loaded 16 placeholder patterns from schema
  Row 2 (welcome_msg): Froze 1 placeholders
  Row 3 (level_up): Froze 1 placeholders
  Row 4 (item_count): Froze 1 placeholders
  Row 5 (color_text): Froze 2 placeholders
  Row 6 (multi_placeholder): Froze 3 placeholders
  Row 7 (newline_test): Froze 1 placeholders
  Row 8 (printf_style): Froze 2 placeholders
✅ Wrote 7 rows to data\draft.csv
✅ Wrote 11 placeholder mappings to data\placeholder_map.json

📊 Summary:
   Total strings processed: 7
   Total placeholders frozen: 11
   PH tokens: 9
   TAG tokens: 2

✅ Normalization complete!
```

### 4. 生成的文件

#### data/draft.csv

包含 tokenized_zh 列，所有占位符已被冻结：

| string_id | source_zh | tokenized_zh | context | max_length |
|-----------|-----------|--------------|---------|------------|
| welcome_msg | 欢迎 {0} 来到游戏！ | 欢迎 ⟦PH_1⟧ 来到游戏！ | 主菜单欢迎语 | 50 |
| level_up | 恭喜！你已升至 {level} 级 | 恭喜！你已升至 ⟦PH_2⟧ 级 | 升级提示 | 40 |
| item_count | 你有 %d 个物品 | 你有 ⟦PH_3⟧ 个物品 | 背包提示 | 30 |
| color_text | \<color=#FF00FF>稀有物品\</color>获得！ | ⟦TAG_2⟧稀有物品⟦TAG_1⟧获得！ | 战利品提示 | 60 |
| multi_placeholder | 玩家 {playerName} 在 {location} 获得了 {itemName} | 玩家 ⟦PH_6⟧ 在 ⟦PH_5⟧ 获得了 ⟦PH_4⟧ | 游戏日志 | 100 |
| newline_test | 第一行\n第二行 | 第一行⟦PH_7⟧第二行 | 多行文本 | 50 |
| printf_style | %s 击败了 %s！ | ⟦PH_9⟧ 击败了 ⟦PH_8⟧！ | 战斗日志 | 80 |

#### data/placeholder_map.json

完整的 token 到原始占位符的映射：

```json
{
  "metadata": {
    "generated_at": "2026-01-09T01:42:07.011791",
    "input_file": "data\\input.csv",
    "total_placeholders": 11,
    "version": "1.0"
  },
  "mappings": {
    "PH_1": "{0}",
    "PH_2": "{level}",
    "PH_3": "%d",
    "TAG_1": "</color>",
    "TAG_2": "<color=#FF00FF>",
    "PH_4": "{itemName}",
    "PH_5": "{location}",
    "PH_6": "{playerName}",
    "PH_7": "\\n",
    "PH_8": "%s",
    "PH_9": "%s"
  }
}
```

### 5. 验证测试

运行测试脚本验证输出：

```bash
python scripts/test_normalize.py
```

输出：

```
🧪 Testing normalize_guard.py output...

✅ Output files exist
✅ Loaded 7 rows from draft CSV
✅ Loaded 11 placeholder mappings

✅ Test passed: welcome_msg
   Tokens: ['⟦PH_1⟧']
   Tokenized: 欢迎 ⟦PH_1⟧ 来到游戏！

✅ Test passed: color_text
   Tokens: ['⟦TAG_1⟧', '⟦TAG_2⟧']
   Tokenized: ⟦TAG_2⟧稀有物品⟦TAG_1⟧获得！

✅ Test passed: multi_placeholder
   Tokens: ['⟦PH_4⟧', '⟦PH_5⟧', '⟦PH_6⟧']
   Tokenized: 玩家 ⟦PH_6⟧ 在 ⟦PH_5⟧ 获得了 ⟦PH_4⟧

✅ Correct total placeholder count: 11

🎉 All tests passed!
```

## 占位符类型示例

### C# 数字占位符
- **原文**: `欢迎 {0} 来到游戏！`
- **Token化**: `欢迎 ⟦PH_1⟧ 来到游戏！`
- **映射**: `PH_1 → {0}`

### C# 命名占位符
- **原文**: `恭喜！你已升至 {level} 级`
- **Token化**: `恭喜！你已升至 ⟦PH_2⟧ 级`
- **映射**: `PH_2 → {level}`

### Printf 风格
- **原文**: `你有 %d 个物品`
- **Token化**: `你有 ⟦PH_3⟧ 个物品`
- **映射**: `PH_3 → %d`

### Unity 颜色标签
- **原文**: `<color=#FF00FF>稀有物品</color>获得！`
- **Token化**: `⟦TAG_2⟧稀有物品⟦TAG_1⟧获得！`
- **映射**: 
  - `TAG_2 → <color=#FF00FF>`
  - `TAG_1 → </color>`

### 多个占位符
- **原文**: `玩家 {playerName} 在 {location} 获得了 {itemName}`
- **Token化**: `玩家 ⟦PH_6⟧ 在 ⟦PH_5⟧ 获得了 ⟦PH_4⟧`
- **映射**: 
  - `PH_6 → {playerName}`
  - `PH_5 → {location}`
  - `PH_4 → {itemName}`

### 转义序列
- **原文**: `第一行\n第二行`
- **Token化**: `第一行⟦PH_7⟧第二行`
- **映射**: `PH_7 → \n`

## 下一步工作流程

1. **翻译阶段**: 
   - 翻译人员或 AI 翻译 `tokenized_zh` 列
   - 保持所有 `⟦PH_X⟧` 和 `⟦TAG_X⟧` token 不变
   - 可以调整 token 在句子中的位置以适应目标语言语法

2. **QA 验证**:
   - 使用 `qa_hard.py` 验证所有 token 是否完整保留
   - 检查长度限制
   - 检查禁用模式

3. **还原导出**:
   - 使用 `rehydrate_export.py` 将 token 还原为原始占位符
   - 导出为游戏引擎支持的格式（JSON/XML/Properties）

## 关键优势

✅ **安全**: 占位符被冻结，翻译过程中不会被意外修改  
✅ **可追踪**: 完整的映射记录，可以追溯每个 token  
✅ **灵活**: 支持多种占位符格式和自定义模式  
✅ **可验证**: 自动化测试确保输出正确性  
✅ **可扩展**: 易于添加新的占位符类型
