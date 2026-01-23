---
description: 还原 token 并导出最终包
---

目标：把 token 还原为原始占位符/标签，生成最终交付包 data/final.csv

要求：

1) 如果 scripts/rehydrate_export.py 不存在，则创建它。
2) 运行命令：python scripts/rehydrate_export.py data/translated.csv data/placeholder_map.json data/final.csv
3) 输出 final.csv 前 10 行用于验证（仅终端打印，不要贴到聊天里）。
4) 若还原后出现占位符不匹配，脚本会直接报错退出（Exit Code 1），并在终端打印 "FATAL ERROR"。此时需人工介入或回退到 Repair 阶段。注意：rehydrate_export.py 不会写入 qa_hard_report.json，该文件应由上一步的 qa_hard.py 生成。

交付标准：final.csv 可直接给客户端导入。
