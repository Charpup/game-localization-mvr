---
description: 只修复标红行
---

目标：仅修复 data/qa_hard_report.json 标记的错误行，更新 data/translated.csv（或生成 data/repaired.csv）。

强约束：
1) 只修改被标红的行；其他行必须逐字保持 target_text 不变。
2) 修复时不得破坏 token；不得引入新的占位符形态。
3) 修复完成后必须重新运行 /loc_qa_hard，直到 PASS 或明确进入人工处理列表。

输出：
- 更新后的 CSV（translated.csv 或 repaired.csv）
- 人工处理清单 data/escalate_list.csv（包含 string_id、错误原因、建议人工怎么改）