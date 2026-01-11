---
description: 冻结占位符 + 生成 draft.csv
---

目标：对 data/input.csv 做占位符/标签冻结（tokenize），生成：
- data/draft.csv（新增列 tokenized_zh，或用 source_zh 替换为 tokenized）
- data/placeholder_map.json（token ↔ 原始占位符映射）

要求：
1) 如果 scripts/normalize_guard.py 不存在，则创建它（Python 3）。
2) 运行命令：python scripts/normalize_guard.py data/input.csv data/draft.csv data/placeholder_map.json workflow/placeholder_schema.yaml
3) 命令成功后，打印 draft.csv 前 5 行（仅用于验证），并确认 placeholder_map.json 非空（如有占位符）。
4) 若发现未知占位符模式或源文本标签不平衡：停止并在 data/qa_hard_report.json 写入 has_errors=true 与原因（即使 qa_hard 尚未运行）。

输出必须落盘，不要把主要结果写在聊天里。
