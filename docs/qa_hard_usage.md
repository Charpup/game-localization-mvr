# QA Hard 使用说明

## 功能概述

`qa_hard.py` 是游戏本地化 workflow 的质量检查脚本，负责对 tokenized 翻译文本进行硬性规则校验。

## 使用方法

```bash
python scripts/qa_hard.py <translated_csv> <placeholder_map_json> <schema_yaml> <forbidden_txt> <report_json>
```

### 示例

```bash
python scripts/qa_hard.py \
  data/translated.csv \
  data/placeholder_map.json \
  workflow/placeholder_schema.yaml \
  workflow/forbidden_patterns.txt \
  data/qa_report.json
```

## 输入文件

### translated_csv

翻译后的 CSV 文件，必需列：
- `string_id`: 字符串 ID
- `tokenized_zh`: 源文本（tokenized）
- `target_text` (或 `translated_text`, `target_zh`, `tokenized_target`): 目标翻译文本

### placeholder_map_json

占位符映射文件（由 normalize_guard.py 生成）

### schema_yaml

占位符 schema 定义（用于标签平衡检查）

### forbidden_txt

禁用模式列表（正则表达式）

## 检查项目

### 1. Token 匹配检查 (token_mismatch)

验证源文本和目标文本中的 token 是否完全匹配。

**检查内容**：
- 缺失的 token（源文本有，目标文本没有）
- 多余的 token（目标文本有，源文本没有）

**示例错误**：
```json
{
  "type": "token_mismatch",
  "string_id": "welcome_msg",
  "detail": "missing ⟦PH_1⟧ in target_text",
  "source": "欢迎 ⟦PH_1⟧ 来到游戏！",
  "target": "Welcome to the game!"
}
```

### 2. 标签平衡检查 (tag_unbalanced)

验证开放标签和闭合标签是否成对出现。

**检查内容**：
- 开放标签数量（如 `<color=#FF00FF>`）
- 闭合标签数量（如 `</color>`）
- 两者是否相等

**示例错误**：
```json
{
  "type": "tag_unbalanced",
  "string_id": "color_text",
  "detail": "unbalanced tags: 1 opening, 0 closing",
  "target": "⟦TAG_2⟧Rare Item obtained!",
  "opening_tags": ["TAG_2"],
  "closing_tags": []
}
```

### 3. 禁用模式检查 (forbidden_hit)

检查翻译文本是否包含禁用的模式。

**常见禁用模式**：
- 机器翻译标记：`[机器翻译]`, `[MT]`
- 占位符文本：`TODO`, `FIXME`, `[TBD]`
- 不当内容
- 编码问题字符

**示例错误**：
```json
{
  "type": "forbidden_hit",
  "string_id": "printf_style",
  "detail": "matched forbidden pattern: TODO",
  "target": "⟦PH_9⟧ defeated ⟦PH_8⟧! TODO"
}
```

### 4. 新占位符检查 (new_placeholder_found)

检查翻译文本中是否出现了未经冻结的新占位符。

**检测模式**：
- C# 占位符：`{0}`, `{playerName}`
- Printf 风格：`%s`, `%d`
- Unity 标签：`<color=#FF00FF>`, `</color>`

**示例错误**：
```json
{
  "type": "new_placeholder_found",
  "string_id": "level_up",
  "detail": "found unfrozen C# named placeholder: {level}",
  "target": "You've reached level {level}"
}
```

## 输出报告格式

### 报告结构

```json
{
  "has_errors": true,
  "total_rows": 7,
  "error_counts": {
    "token_mismatch": 5,
    "tag_unbalanced": 1,
    "forbidden_hit": 1,
    "new_placeholder_found": 1
  },
  "errors": [
    {
      "row": 2,
      "string_id": "welcome_msg",
      "type": "token_mismatch",
      "detail": "missing ⟦PH_1⟧ in target_text",
      "source": "欢迎 ⟦PH_1⟧ 来到游戏！",
      "target": "Welcome to the game!"
    }
  ],
  "metadata": {
    "generated_at": "2026-01-09T01:52:20.488834",
    "input_file": "data\\translated.csv",
    "total_errors": 8
  }
}
```

### 关键字段

- **has_errors**: 是否有错误（布尔值）
- **total_rows**: 检查的总行数
- **error_counts**: 各类错误的数量统计
- **errors**: 详细错误列表
- **metadata**: 报告元数据

## 运行示例

### 成功案例（无错误）

```bash
$ python scripts/qa_hard.py data/translated_good.csv data/placeholder_map.json workflow/placeholder_schema.yaml workflow/forbidden_patterns.txt data/qa_report_good.json

🚀 Starting QA Hard validation...
✅ Loaded 11 placeholder mappings
✅ Loaded schema with 8 tag patterns
✅ Loaded 28 forbidden patterns
✅ Using 'target_text' as target translation field

📊 QA Validation Summary:
   Total rows checked: 7
   Total errors: 0

✅ All checks passed!
   Report saved to: data\qa_report_good.json
```

### 失败案例（有错误）

```bash
$ python scripts/qa_hard.py data/translated_bad.csv data/placeholder_map.json workflow/placeholder_schema.yaml workflow/forbidden_patterns.txt data/qa_report_bad.json

🚀 Starting QA Hard validation...
✅ Loaded 11 placeholder mappings
✅ Loaded schema with 8 tag patterns
✅ Loaded 28 forbidden patterns
✅ Using 'target_text' as target translation field

📊 QA Validation Summary:
   Total rows checked: 7
   Total errors: 8

   ❌ Token mismatch: 5
   ❌ Tag unbalanced: 1
   ❌ Forbidden patterns: 1
   ❌ New placeholders found: 1

❌ Validation FAILED with 8 errors
   See detailed report: data\qa_report_bad.json

   Sample errors:
   - [token_mismatch] welcome_msg: missing ⟦PH_1⟧ in target_text
   - [token_mismatch] level_up: missing ⟦PH_2⟧ in target_text
   - [new_placeholder_found] level_up: found unfrozen C# named placeholder: {level}
   - [token_mismatch] item_count: extra ⟦PH_99⟧ in target_text
   - [tag_unbalanced] color_text: unbalanced tags: 1 opening, 0 closing
```

## 工作流集成

QA Hard 是本地化流程的第三步：

1. **Normalize** → 冻结占位符
2. **Translate** → 翻译 tokenized 文本
3. **QA Hard** (本脚本) → 验证翻译质量
4. **Rehydrate** → 还原占位符并导出

## 最佳实践

### 1. 在翻译过程中频繁运行

建议在翻译过程中定期运行 QA 检查，及早发现问题。

### 2. 修复所有错误后再导出

只有当 `has_errors: false` 时才应该进行下一步的还原导出。

### 3. 审查报告中的所有错误

不要忽略任何错误类型，每个错误都可能导致游戏运行时问题。

### 4. 自定义禁用模式

根据项目需求编辑 `forbidden_patterns.txt`，添加项目特定的禁用模式。

## 故障排除

### 错误：Missing required fields

确保 CSV 文件包含 `string_id` 和 `tokenized_zh` 列，以及至少一个目标翻译列。

### 错误：No target translation field found

CSV 文件中没有找到翻译列。支持的列名：
- `target_text`
- `translated_text`
- `target_zh`
- `tokenized_target`

### 大量 forbidden_hit 误报

检查 `forbidden_patterns.txt` 中的正则表达式是否正确转义。
- 使用 `\[` 和 `\]` 匹配字面括号
- 避免过于宽泛的模式

## 依赖

- Python 3.7+
- PyYAML

## 退出码

- `0`: 所有检查通过
- `1`: 发现错误或运行失败
