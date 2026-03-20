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
  --style-profile data/style_profile.yaml \
  --batch_size 40 \
  --out_report data/qa_soft_report.json \
  --out_tasks data/repair_tasks.jsonl
```

## 输出文件

| 文件 | 说明 |
|------|------|
| `data/qa_soft_report.json` | 汇总：major/minor 数量、总任务数 |
| `data/repair_tasks.jsonl` | 每行一个 JSON 任务，供 repair_loop 消费 |

> [!NOTE]
> `workflow/soft_qa_rubric.yaml` 参数是 v1.0 遗留及其，脚本 v2.0 会忽略其内容（内置了基于 style guide 的评审逻辑），但为了保持命令行兼容性，仍需在调用时提供该位置参数。

## 评审维度

- `terminology_consistency` - 术语是否遵守 glossary（含风格优先级映射）
- `style_contract` - 术语优先法、角色名策略、变量与禁译项
- `length` - 按钮/长文长度约束（含 per-row 上限）
- `placeholder` - 占位符与变量完整性
- `ambiguity_high_risk` - 同源语义可能歧义点
- `punctuation` - 标点/引号/标签语义风险

## 要求

- **不阻断流水线**：即使有 major issues，也不停止后续步骤
- **必须落盘输出**：report 和 tasks 必须写入文件
- **驱动 Repair Loop**：输出用于下一步自动修复（建议先处理 major）

## 后续步骤

1. 查看 `qa_soft_report.json` 确认问题数量
2. 运行 `/loc-repair-loop` 自动修复
