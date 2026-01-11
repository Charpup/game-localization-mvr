---
description: Soft QA - LLM-based translation quality review
---

# /loc-soft-qa Workflow

## 目标

对 `data/translated.csv` 做软质量评审，输出：
- `data/qa_soft_report.json` - 汇总报告
- `data/repair_tasks.jsonl` - 可执行的修复任务

## 执行命令

```bash
python scripts/soft_qa_llm.py \
  data/translated.csv \
  workflow/style_guide.md \
  data/glossary.yaml \
  workflow/soft_qa_rubric.yaml \
  --batch_size 40 \
  --out_report data/qa_soft_report.json \
  --out_tasks data/repair_tasks.jsonl
```

## 输出文件

| 文件 | 说明 |
|------|------|
| `data/qa_soft_report.json` | 汇总：major/minor 数量、总任务数 |
| `data/repair_tasks.jsonl` | 每行一个 JSON 任务，供 repair_loop 消费 |

## 评审维度

- `style_officialness` - 系统文案是否官方、清晰
- `anime_tone` - 二次元口语是否适度
- `terminology_consistency` - 术语是否遵守 glossary
- `ui_brevity` - 按钮/短提示是否过长
- `ambiguity` - 是否存在歧义风险

## 要求

- **不阻断流水线**：即使有 major issues，也不停止后续步骤
- **必须落盘输出**：report 和 tasks 必须写入文件
- **驱动 Repair Loop**：输出用于下一步自动修复

## 后续步骤

1. 查看 `qa_soft_report.json` 确认问题数量
2. 运行 `/loc-repair-loop` 自动修复
