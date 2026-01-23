---
description: 可选：推断 UI 场景标签
---

目标：基于 data/draft.csv 推断每行的 context 标签（UI/button/dialog/system/etc），输出 data/context.json 或在 draft.csv 增加列 context。

要求：

1) 不要改变 token（例如 ⟦PH_1⟧ 必须原样保留）。
2) 输出格式必须是 JSON（key=string_id，value=标签对象），或 CSV 新列。
3) 标签集合建议：button/tab/toast/dialog_title/dialog_body/tutorial/combat_log/quest_objective/system_error/marketing
4) 执行脚本：

```bash
python scripts/normalize_tagger.py --input data/source.csv --output data/normalized.csv
```

5) 输出：`data/normalized.csv`，包含 module_tag, module_confidence, len_tier 等增强列。

不要生成大段解释，重点是可复用的结构化输出。
