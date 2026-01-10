---
description: AI 初翻：使用 LLM 翻译 tokenized 文本
---

# /loc-translate 工作流

目标：调用 `scripts/translate_llm.py`，把 `data/draft.csv` 翻译为目标语言，输出 `data/translated.csv`。

## 前置条件

1. `workflow/style_guide.md` 必须存在
2. `data/glossary.yaml` 如果存在则强制启用：
   - `approved` 必用
   - `banned` 禁用
   - `proposed` 仅参考
3. 环境变量必须已配置：

```powershell
$env:LLM_BASE_URL = "https://api.openai.com/v1"
$env:LLM_API_KEY = "your-api-key"
$env:LLM_MODEL = "gpt-4o-mini"
```

## 执行步骤

// turbo
### 1. 运行翻译脚本

```powershell
python scripts/translate_llm.py `
  data/draft.csv `
  data/translated.csv `
  workflow/style_guide.md `
  data/glossary.yaml `
  --target ru-RU `
  --batch_size 50 `
  --max_retries 4
```

### 2. 断点续传

如果中断/报错，**重复运行同一命令**即可断点续传。

进度保存在 `data/translate_checkpoint.json`。

### 3. 查看结果

运行结束后检查：
- `data/translated.csv` - 翻译结果
- `data/escalate_list.csv` - 需人工处理的失败行

## 输出文件

| 文件 | 说明 |
|------|------|
| `data/translated.csv` | 翻译结果（增加 `target_text` 列）|
| `data/translate_checkpoint.json` | 进度文件（用于断点续传）|
| `data/escalate_list.csv` | 升级清单（翻译失败的行）|

## 常用选项

```powershell
# 调整批次大小（控制成本）
--batch_size 20

# 调整重试次数
--max_retries 6

# 指定目标语言
--target zh-TW
```

## 环境变量说明

| 变量 | 说明 | 示例 |
|------|------|------|
| `LLM_BASE_URL` | API 基础 URL | `https://api.openai.com/v1` |
| `LLM_API_KEY` | API 密钥 | `sk-...` |
| `LLM_MODEL` | 模型名 | `gpt-4o-mini` |
| `LLM_TIMEOUT_S` | 超时秒数（可选） | `60` |

## 下一步

翻译完成后，运行 `/loc-qa-hard` 验证翻译质量。

## 注意事项

1. **不要在聊天里输出翻译内容**；一切以落盘文件为准
2. **Token 保护**：脚本会指示 LLM 保留所有 ⟦PH_X⟧ token
3. **升级清单**：`escalate_list.csv` 中的行需人工翻译或修复
