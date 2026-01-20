---
description: 从 input.csv 提取候选术语
---

目标：从 data/input.csv 提取中文术语候选，输出 data/term_candidates.yaml

要求：

1) 如果 scripts/extract_terms.py 不存在则创建它（Python 3，使用 jieba 分词）。
2) 运行：python scripts/extract_terms.py data/input.csv data/term_candidates.yaml
3) 打印候选数量与前 20 个 term_zh（仅终端打印）。
4) 不要在聊天里写长解释，重点是落盘产物 term_candidates.yaml。

可选参数：

- --mode heuristic：无 jieba 依赖的启发式提取
- --mode weighted：基于 normalized.csv 的加权提取（需 module_tag 列）
- --mode llm：使用 LLM API（实验性，需配置 workflow/llm_config.yaml）
- --glossary data/glossary.yaml：排除已知术语
- --blacklist glossary/generic_terms_zh.txt：通用词黑名单（仅 weighted 模式）

输出必须落盘，不要把主要结果写在聊天里。
