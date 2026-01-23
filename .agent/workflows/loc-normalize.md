目标：对原始输入做标准化处理，生成 draft.csv

执行顺序（必须按序执行，不可跳过）：

1. **Ingest** (Header 标准化):
   python scripts/normalize_ingest.py --input data/input.csv --output data/source_raw.csv

2. **Tagger** (分类 + 长文本标记):
   python scripts/normalize_tagger.py --input data/source_raw.csv --output data/normalized.csv

3. **Guard** (占位符冻结):
   python scripts/normalize_guard.py data/normalized.csv data/draft.csv data/placeholder_map.json workflow/placeholder_schema.yaml

注意：

- 步骤 1 会自动处理 id/zh 等非标准 header。
- 步骤 2 会针对 ID 前缀进行分类，并生成 `is_long_text` 标记供后续批次调用优化。
- 如果置信度低，步骤 2 会自动触发 LLM Fallback 进行分类。
- 如遇未知占位符或括号不平衡，步骤 3 会中断并报错。

输出必须落盘，不要把主要结果写在聊天里。
