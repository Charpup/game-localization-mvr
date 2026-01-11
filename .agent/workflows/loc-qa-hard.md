---
description: 硬规则校验：能否出包的门槛
---

目标：对 data/translated.csv 做确定性硬校验，输出 data/qa_hard_report.json

校验项必须包含：
- placeholder/token 数量是否一致（source vs target）
- 标签平衡（<> {} [] 等按 schema）
- 禁用词/非法字符（读取 workflow/forbidden_patterns.txt）
- 目标文本是否意外包含未冻结的占位符形态（例如出现新的 {xxx}）

要求：
1) 如果 scripts/qa_hard.py 不存在，则创建它。
2) 运行命令：python scripts/qa_hard.py data/translated.csv data/placeholder_map.json workflow/placeholder_schema.yaml workflow/forbidden_patterns.txt data/qa_hard_report.json
3) 若 has_errors=true，则在终端输出错误计数 summary，并列出前 10 条出错 string_id（同时写入 data/qa_hard_preview.txt）。
4) 若 has_errors=false，输出“PASS”并说明总行数与校验覆盖项（简短即可）。

重点：报告必须落盘为 JSON。