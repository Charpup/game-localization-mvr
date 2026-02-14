# Rehydrate Export 使用说明

## 功能概述

`rehydrate_export.py` 是游戏本地化 workflow 的最后一步，负责将 tokenized 翻译文本还原为原始占位符格式。

## 使用方法

```bash
python scripts/rehydrate_export.py <translated_csv> <placeholder_map_json> <final_csv>
```

### 示例

```bash
python scripts/rehydrate_export.py \
  data/translated.csv \
  data/placeholder_map.json \
  data/final.csv
```

## 输入文件

### translated_csv

翻译后的 CSV 文件，必需列：
- `string_id`: 字符串 ID
- `target_text` (或 `translated_text`, `target_zh`, `tokenized_target`): 目标翻译文本

### placeholder_map_json

占位符映射文件（由 normalize_guard.py 生成）

## 输出文件

### final_csv

还原后的最终 CSV 文件，包含：
- 所有原始列
- `rehydrated_text`: 还原后的文本（插入在目标翻译列之后）

## 工作原理

### 1. 加载映射

从 `placeholder_map.json` 加载 token 到原始占位符的映射：

```json
{
  "PH_1": "{0}",
  "PH_2": "{level}",
  "TAG_1": "</color>",
  "TAG_2": "<color=#FF00FF>"
}
```

### 2. 提取 Token

使用正则表达式 `⟦(PH_\d+|TAG_\d+)⟧` 提取文本中的所有 token。

### 3. 验证 Token

检查每个 token 是否在映射表中：
- ✅ 如果所有 token 都存在 → 继续还原
- ❌ 如果发现未知 token → **立即报错并退出**

### 4. 还原文本

将每个 token 替换为对应的原始占位符：

```
⟦PH_1⟧ → {0}
⟦TAG_2⟧ → <color=#FF00FF>
```

## 严格验证模式

**重要**：此脚本采用严格验证模式，**不做任何修复或容错**。

### 发现未知 Token 时

脚本会：
1. 打印详细错误信息
2. 立即退出（exit code 1）
3. 不生成输出文件

**示例错误**：
```
❌ FATAL ERROR: Row 4, string_id 'item_count': Unknown token(s) found: ['PH_99']
These tokens are not in placeholder_map.json.
This should have been caught by QA validation.

❌ Rehydration FAILED
   Please run qa_hard.py to validate translations before rehydrating.
```

### 为什么这样设计？

- **质量保证**：确保所有翻译都经过 QA 验证
- **问题追溯**：未知 token 表明 QA 流程有问题
- **数据完整性**：避免生成不完整或错误的输出

## 运行示例

### 成功案例

```bash
$ python scripts/rehydrate_export.py data/translated_good.csv data/placeholder_map.json data/final.csv

🚀 Starting rehydrate export...
   Input CSV: data\translated_good.csv
   Placeholder map: data\placeholder_map.json
   Output CSV: data\final.csv

✅ Loaded 11 placeholder mappings

✅ Using 'target_text' as target translation field

✅ Wrote 7 rows to data\final.csv

📊 Rehydrate Summary:
   Total rows processed: 7
   Total tokens restored: 11
   Output file: data\final.csv

✅ Rehydration complete!
```

### 失败案例

```bash
$ python scripts/rehydrate_export.py data/translated_bad.csv data/placeholder_map.json data/final.csv

🚀 Starting rehydrate export...
   Input CSV: data\translated_bad.csv
   Placeholder map: data\placeholder_map.json
   Output CSV: data\final.csv

✅ Loaded 11 placeholder mappings

✅ Using 'target_text' as target translation field


❌ FATAL ERROR: Row 4, string_id 'item_count': Unknown token(s) found: ['PH_99']
These tokens are not in placeholder_map.json.
This should have been caught by QA validation.

❌ Rehydration FAILED
   Please run qa_hard.py to validate translations before rehydrating.
```

## 还原示例

### C# 占位符

| Token 化 | 还原后 |
|---------|--------|
| `Welcome ⟦PH_1⟧ to the game!` | `Welcome {0} to the game!` |
| `Level ⟦PH_2⟧` | `Level {level}` |

### Unity 标签

| Token 化 | 还原后 |
|---------|--------|
| `⟦TAG_2⟧Rare Item⟦TAG_1⟧` | `<color=#FF00FF>Rare Item</color>` |

### Printf 风格

| Token 化 | 还原后 |
|---------|--------|
| `You have ⟦PH_3⟧ items` | `You have %d items` |

### 转义序列

| Token 化 | 还原后 |
|---------|--------|
| `First line⟦PH_7⟧Second line` | `First line\nSecond line` |

## 工作流集成

Rehydrate Export 是本地化流程的最后一步：

```
1. Normalize → 冻结占位符
   input.csv → draft.csv + placeholder_map.json

2. Translate → 翻译 tokenized 文本
   draft.csv → translated.csv

3. QA Hard → 验证翻译质量
   translated.csv → qa_report.json
   (必须 has_errors: false)

4. Rehydrate Export (本脚本) → 还原占位符
   translated.csv → final.csv
```

## 最佳实践

### 1. 始终先运行 QA

在运行 rehydrate 之前，**必须**先运行 `qa_hard.py` 并确保没有错误：

```bash
# 1. 运行 QA
python scripts/qa_hard.py data/translated.csv data/placeholder_map.json workflow/placeholder_schema.yaml workflow/forbidden_patterns.txt data/qa_report.json

# 2. 检查报告
# 确保 has_errors: false

# 3. 运行 rehydrate
python scripts/rehydrate_export.py data/translated.csv data/placeholder_map.json data/final.csv
```

### 2. 检查退出码

在自动化脚本中检查退出码：

```bash
if python scripts/rehydrate_export.py ...; then
    echo "Rehydration successful"
else
    echo "Rehydration failed - check QA report"
    exit 1
fi
```

### 3. 保留中间文件

保留所有中间文件以便追溯：
- `draft.csv` - tokenized 源文本
- `translated.csv` - tokenized 翻译
- `qa_report.json` - QA 验证报告
- `final.csv` - 还原后的最终文本

## 输出文件格式

### 示例输出

```csv
string_id,source_zh,tokenized_zh,target_text,rehydrated_text,translator,status,context,max_length
welcome_msg,欢迎 {0} 来到游戏！,欢迎 ⟦PH_1⟧ 来到游戏！,Welcome ⟦PH_1⟧ to the game!,Welcome {0} to the game!,AI,approved,主菜单欢迎语,50
level_up,恭喜！你已升至 {level} 级,恭喜！你已升至 ⟦PH_2⟧ 级,Level ⟦PH_2⟧,Level {level},AI,approved,升级提示,40
```

### 关键列

- **target_text**: tokenized 翻译文本
- **rehydrated_text**: 还原后的最终文本（可直接用于游戏）

## 故障排除

### 错误：Unknown token(s) found

**原因**：翻译文本中包含映射表中不存在的 token。

**解决方案**：
1. 运行 `qa_hard.py` 检查翻译
2. 修复 QA 报告中的所有错误
3. 重新运行 rehydrate

### 错误：No target translation field found

**原因**：CSV 文件中没有翻译列。

**解决方案**：确保 CSV 包含以下列之一：
- `target_text`
- `translated_text`
- `target_zh`
- `tokenized_target`

### 错误：Placeholder map not found

**原因**：找不到 `placeholder_map.json` 文件。

**解决方案**：确保先运行 `normalize_guard.py` 生成映射文件。

## 依赖

- Python 3.7+
- 无额外依赖（仅使用标准库）

## 退出码

- `0`: 还原成功
- `1`: 发现错误或运行失败

## 与其他脚本的关系

```
normalize_guard.py
    ↓ 生成
placeholder_map.json ←─┐
    ↓                  │
    ├─→ qa_hard.py     │
    │                  │
    └─→ rehydrate_export.py (使用)
```

## 安全性

- ✅ 不修改原始文件
- ✅ 严格验证所有 token
- ✅ 发现问题立即停止
- ✅ 详细的错误报告
