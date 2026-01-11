---
description: Repair Loop - Auto-fix hard and soft QA issues
---

# /loc-repair-loop Workflow

## 目标

自动修复 hard QA 与 soft QA 标红行，输出：
- `data/repaired.csv` - 只改动被标记行
- `data/repair_checkpoint.json` - 支持断点续传

## 执行命令

```bash
python scripts/repair_loop.py \
  data/translated.csv \
  data/qa_hard_report.json \
  data/repair_tasks.jsonl \
  workflow/style_guide.md \
  data/glossary.yaml \
  --out_csv data/repaired.csv \
  --checkpoint data/repair_checkpoint.json \
  --max_retries 4 \
  --only_soft_major
```

## 输入文件

| 文件 | 说明 |
|------|------|
| `data/translated.csv` | 原始翻译结果 |
| `data/qa_hard_report.json` | Hard QA 报告（阻断类错误） |
| `data/repair_tasks.jsonl` | Soft QA 修复任务 |

## 输出文件

| 文件 | 说明 |
|------|------|
| `data/repaired.csv` | 修复后的完整 CSV |
| `data/repair_checkpoint.json` | 断点续传检查点 |
| `data/escalate_list.csv` | 无法自动修复的条目 |

## 修复策略

1. **Hard fail 优先**：先修 hard QA 标红行（否则出不了包）
2. **Soft major 次之**：只修 major（minor 留人工润色）
3. **每行验证**：修复后立即验证 token 数量和无中文

## 选项说明

- `--only_soft_major`：只处理 major 级别的 soft issues
- `--max_retries`：每行最大重试次数（默认 4）
- `--checkpoint`：断点续传文件路径

## 后续步骤

1. 用 `repaired.csv` 覆盖 `translated.csv`（或让后续步骤读取 `repaired.csv`）：
   ```bash
   copy data\repaired.csv data\translated.csv
   ```

2. 重新运行 `/loc-qa-hard` 验证：
   ```bash
   python scripts/qa_hard.py data/translated.csv data/placeholder_map.json data/qa_hard_report.json workflow/placeholder_schema.yaml
   ```

3. 循环直到：
   - PASS（has_errors=false）
   - 或错误稳定进入 `escalate_list.csv`

## 断点续传

如果中途中断，再次运行相同命令会从 checkpoint 恢复：
- 已修复的行会被跳过
- 统计数据会累积

要重新开始，删除 checkpoint：
```bash
del data\repair_checkpoint.json
```
