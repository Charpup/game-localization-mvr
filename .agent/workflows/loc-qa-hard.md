---
description: 硬规则校验：能否出包的门槛
---

# /loc-qa-hard Workflow

## 目标

对 `data/translated.csv` 做确定性硬校验，输出 `data/qa_hard_report.json`

## 校验项

- placeholder/token 数量是否一致（source vs target）
- 标签平衡（<> {} [] 等按 schema）
- 禁用词/非法字符（读取 workflow/forbidden_patterns.txt）
- 目标文本是否意外包含未冻结的占位符形态

## 执行命令

**简化版**（使用默认路径）：
```bash
python scripts/qa_hard.py
```

**完整版**（自定义路径）：
```bash
python scripts/qa_hard.py \
  data/translated.csv \
  data/placeholder_map.json \
  workflow/placeholder_schema.yaml \
  workflow/forbidden_patterns.txt \
  data/qa_hard_report.json
```

**验证 repaired.csv**：
```bash
python scripts/qa_hard.py data/repaired.csv
```

## 输出

- 若 `has_errors=true`：终端输出错误计数 summary，列出前 10 条出错 string_id
- 若 `has_errors=false`：输出 "PASS" 并说明总行数与校验覆盖项

## 要求

- 报告必须落盘为 JSON
- 若 has_errors=true，则阻断后续步骤，进入修复流程