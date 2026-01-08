# Normalize Guard 使用说明

## 功能概述

`normalize_guard.py` 是游戏本地化 workflow 的第一步，负责：

1. **冻结占位符和标签**：将 `{0}`, `%s`, `<color=#FF00FF>` 等替换为统一的 token 格式 `⟦PH_1⟧`, `⟦TAG_1⟧`
2. **生成 draft.csv**：包含原文和 tokenized 文本
3. **生成 placeholder_map.json**：记录 token 到原始占位符的映射

## 使用方法

```bash
python scripts/normalize_guard.py <input_csv> <output_draft_csv> <output_map_json> <schema_yaml>
```

### 示例

```bash
python scripts/normalize_guard.py \
  data/input.csv \
  data/draft.csv \
  data/placeholder_map.json \
  workflow/placeholder_schema.yaml
```

## 输入文件格式

### input.csv

必需列：
- `string_id`: 字符串唯一标识符
- `source_zh`: 源文本（中文）

可选列：
- `context`: 上下文说明
- `max_length`: 最大长度限制

示例：
```csv
string_id,source_zh,context,max_length
welcome_msg,欢迎 {0} 来到游戏！,主菜单欢迎语,50
level_up,恭喜！你已升至 {level} 级,升级提示,40
color_text,<color=#FF00FF>稀有物品</color>获得！,战利品提示,60
```

## 输出文件格式

### draft.csv

包含以下列：
- `string_id`: 字符串 ID
- `source_zh`: 原始源文本
- `tokenized_zh`: token 化后的文本
- 其他从输入文件继承的列

示例：
```csv
string_id,source_zh,tokenized_zh,context,max_length
welcome_msg,欢迎 {0} 来到游戏！,欢迎 ⟦PH_1⟧ 来到游戏！,主菜单欢迎语,50
level_up,恭喜！你已升至 {level} 级,恭喜！你已升至 ⟦PH_2⟧ 级,升级提示,40
color_text,<color=#FF00FF>稀有物品</color>获得！,⟦TAG_1⟧稀有物品⟦TAG_2⟧获得！,战利品提示,60
```

### placeholder_map.json

记录所有 token 到原始占位符的映射：

```json
{
  "metadata": {
    "generated_at": "2026-01-09T01:36:20+08:00",
    "input_file": "data/input.csv",
    "total_placeholders": 9,
    "version": "1.0"
  },
  "mappings": {
    "PH_1": "{0}",
    "PH_2": "{level}",
    "PH_3": "%d",
    "TAG_1": "<color=#FF00FF>",
    "TAG_2": "</color>"
  }
}
```

## 支持的占位符类型

根据 `placeholder_schema.yaml` 配置，支持：

### 占位符 (PH)
- **C# 数字占位符**: `{0}`, `{1}`, `{2}` → `⟦PH_1⟧`, `⟦PH_2⟧`
- **C# 命名占位符**: `{playerName}`, `{level}` → `⟦PH_3⟧`, `⟦PH_4⟧`
- **Printf 风格**: `%s`, `%d`, `%f` → `⟦PH_5⟧`, `⟦PH_6⟧`
- **转义序列**: `\n`, `\t` → `⟦PH_7⟧`, `⟦PH_8⟧`

### 标签 (TAG)
- **Unity 颜色标签**: `<color=#FF00FF>`, `</color>` → `⟦TAG_1⟧`, `⟦TAG_2⟧`
- **Unity 大小标签**: `<size=14>`, `</size>` → `⟦TAG_3⟧`, `⟦TAG_4⟧`
- **Unity 样式标签**: `<b>`, `</b>`, `<i>`, `</i>` → `⟦TAG_5⟧`, `⟦TAG_6⟧`

## 工作原理

1. **加载 Schema**: 从 `placeholder_schema.yaml` 读取占位符模式定义
2. **扫描文本**: 使用正则表达式匹配所有占位符和标签
3. **生成 Token**: 
   - 占位符按顺序生成 `PH_1`, `PH_2`, ...
   - 标签按顺序生成 `TAG_1`, `TAG_2`, ...
4. **替换文本**: 将原始占位符替换为 `⟦TOKEN⟧` 格式
5. **记录映射**: 保存 token 到原始文本的映射关系

## 验证规则

脚本会进行以下验证：

- ✅ 检查必需列是否存在
- ✅ 验证 `string_id` 不为空
- ✅ 检测重复的 `string_id`
- ✅ 规范化空白字符

## 输出示例

运行脚本后会显示：

```
🚀 Starting normalize guard...
   Input: data/input.csv
   Output draft: data/draft.csv
   Output map: data/placeholder_map.json
   Schema: workflow/placeholder_schema.yaml

✅ Loaded 16 placeholder patterns from schema
  Row 2 (welcome_msg): Froze 1 placeholders
  Row 3 (level_up): Froze 1 placeholders
  Row 4 (item_count): Froze 1 placeholders
  Row 5 (color_text): Froze 2 placeholders
  Row 6 (multi_placeholder): Froze 3 placeholders
  Row 7 (newline_test): Froze 1 placeholders
  Row 8 (printf_style): Froze 2 placeholders

✅ Wrote 7 rows to data/draft.csv
✅ Wrote 11 placeholder mappings to data/placeholder_map.json

📊 Summary:
   Total strings processed: 7
   Total placeholders frozen: 11
   PH tokens: 9
   TAG tokens: 2
   Warnings: 0

✅ Normalization complete!
```

## 下一步

生成 `draft.csv` 后，可以：

1. 将 `tokenized_zh` 列交给翻译人员或 AI 翻译
2. 翻译时保持所有 `⟦PH_X⟧` 和 `⟦TAG_X⟧` token 不变
3. 使用 `qa_hard.py` 验证翻译质量
4. 使用 `rehydrate_export.py` 还原 token 并导出最终文件

## 依赖

- Python 3.7+
- PyYAML (`pip install pyyaml`)

## 故障排除

### 错误：Missing required columns
确保输入 CSV 包含 `string_id` 和 `source_zh` 列。

### 错误：Duplicate string_id
检查输入文件中是否有重复的 `string_id`。

### 警告：Schema file not found
脚本会使用默认模式，但建议提供完整的 `placeholder_schema.yaml`。

## 自定义占位符模式

编辑 `workflow/placeholder_schema.yaml` 添加新模式：

```yaml
placeholder_patterns:
  - name: "custom_pattern"
    pattern: '\[\w+\]'  # 正则表达式
    type: "PH"          # PH 或 TAG
    description: "Custom square bracket placeholders"
```

模式按定义顺序匹配，更具体的模式应放在前面。
