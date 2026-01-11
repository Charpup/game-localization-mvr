---
description: 还原 token 并导出最终包
---

目标：把 token 还原为原始占位符/标签，生成最终交付包 data/final.csv

要求：
1) 如果 scripts/rehydrate_export.py 不存在，则创建它。
2) 运行命令：python scripts/rehydrate_export.py data/translated.csv data/placeholder_map.json data/final.csv
3) 输出 final.csv 前 10 行用于验证（仅终端打印，不要贴到聊天里）。
4) 若还原后出现占位符不匹配或标签不平衡，视为失败：写入 data/qa_hard_report.json 并要求回到 /loc_repair。

交付标准：final.csv 可直接给客户端导入。
