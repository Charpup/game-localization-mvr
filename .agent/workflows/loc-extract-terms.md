---
description: 从 data/draft.csv 提取候选术语
---

目标：从 `data/draft.csv` 先按中文项目风格上下文提取术语候选，输出 `data/term_candidates.yaml`。

命令：

```bash
python scripts/extract_terms.py data/draft.csv data/term_candidates.yaml \
  --mode segmented \
  --seg-backend pkuseg,thulac,lac,jieba,heuristic \
  --style-profile data/style_profile.yaml \
  --domain-hint "ui"
```

可选参数补充：

- `--seg-backend`：分词后端链路（默认 `pkuseg,thulac,lac,jieba,heuristic`）
- `--mode llm`：改用 LLM 提取（需 `llm` 配置）
- `--min-freq`：最小出现次数（默认 2）
- `--min-termness`：加权模式下的词性得分阈值（默认 0.3）
- `--glossary data/glossary.yaml`：已存在术语会自动排除
- `--stopwords-config`：补充 stopwords/实体配置
- `--blacklist`：加权模式禁用词
- `--output-evidence`：输出 evidence 旁证文件

输出结构（关键）：

- `critical`：高置信度（默认映射 `approved`，建议纳入 glossary 审批）
- `proposed`：中置信度（默认映射 `proposed`）
- `low_confidence`：低置信度（默认映射 `banned`，一般不进入 glossary）
- 每条候选包含：
  - `term_zh`、`score`、`status`
  - `metrics`（stability / context / boundary / module_mix）
  - `evidence`（`string_id`、`module_tag`、`context`、`backend_chain`）

执行规则：

- 无输出可落盘的情况下只输出命令与文件路径，不在对话窗口重复输出大量条目。
- 术语候选进入 `loc-build-glossary` 做人工审批。
