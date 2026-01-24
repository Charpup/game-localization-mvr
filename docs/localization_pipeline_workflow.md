# 本地化流水线工作流 - 完整指南 (v2.0)

本文档定义了本地化项目的端到端工作流，确保符合 **Localization MVR Rules v2.0** 规范。

---

## 1. 流水线架构与核心规则

流水线基于“安全第一”的架构，包含三个主要关卡：

- **标准化关卡 (Normalization Gate)**：在 LLM 接触前保护占位符和标签。
- **硬规则关卡 (Hard Rule Gate)**：若违反技术限制（如记号不匹配、语法错误）则阻断交付。
- **软质量关卡 (Soft Quality Gate)**：审计语言质量和风格指南的遵守情况。

### 📜 强制执行的 MVR 规则摘要

1. **文件化留痕**：所有中间产物必须落盘为 JSON/CSV 文件。
2. **强制令牌化**：严禁在未运行 `normalize_guard.py` 的情况下直接翻译文本。
3. **硬规则阻断**：`qa_hard.py` 报错**必须**停止流水线并进入修复流程。
4. **统一入口**：所有 LLM 调用必须通过 `scripts/runtime_adapter.py`。

---

## 2. 第 1 阶段：准备与标准化 (Preparation)

**目标**：准备源文本并识别技术约束。

### [步骤 1] 占位符冻结 (Normalization)

保护 UI 标签、变量（如 `{0}`）和特殊标记，将其替换为唯一的记号（如 `⟦PH_1⟧`）。

```bash
python scripts/normalize_guard.py \
  --input data/source.csv \
  --output data/draft.csv \
  --map data/placeholder_map.json \
  --schema workflow/placeholder_schema.yaml
```

### [步骤 2] 场景与元数据打标 (Tagging) - 可选

识别 UI 上下文（按钮、对话框等）并设置长度约束。

```bash
python scripts/normalize_tagger.py \
  --input data/draft.csv \
  --output data/normalized.csv
```

---

## 3. 第 2 阶段：风格与术语表初始化 (Setup)

**目标**：确立语言锚点。

### [步骤 3] 风格指南生成 (Style Guide)

如果尚未定义，根据样本或准则创建 `style_guide.md`。

```bash
python scripts/style_guide_generate.py --output workflow/style_guide.md
```

### [步骤 4] 术语提取与筛选 (Term Extraction)

从源文本中识别潜在术语，供人工审批。

```bash
python scripts/extract_terms.py data/normalized.csv --out data/term_candidates.yaml
```

### [步骤 5] 术语表编译 (Glossary Compile)

将审批后的条目编译为高性能的运行时格式。

```bash
python scripts/glossary_compile.py \
  --approved glossary/approved.yaml \
  --out_compiled glossary/compiled.yaml
```

---

## 4. 第 3 阶段：翻译与硬规则循环 (Phase 3: Loop A)

**目标**：获得技术上有效的初步翻译。

### [步骤 6] LLM 初翻 (Translation)

在遵守术语表和风格指南的前提下翻译令牌化文本。

```bash
python scripts/translate_llm.py \
  data/normalized.csv \
  data/translated.csv \
  --style workflow/style_guide.md \
  --glossary glossary/compiled.yaml
```

### [步骤 7] 硬规则校验 (Hard QA)

检查记号不匹配、标签不平衡或禁用词。

```bash
python scripts/qa_hard.py \
  data/translated.csv \
  data/placeholder_map.json \
  --out_report data/qa_hard_report.json
```

### [步骤 8] 自动修复循环 - 硬规则 (Repair Hard)

若质量报告显示错误，运行专门的修复提示词。

```bash
python scripts/repair_loop.py \
  --input data/translated.csv \
  --report data/qa_hard_report.json \
  --mode repair_hard \
  --out_csv data/repaired_v1.csv
```

---

## 5. 第 4 阶段：软质量审计与安全 (Phase 4: Loop B)

**目标**：确保语言表达的卓越性。

### [步骤 9] 软质量审计 (Soft QA Audit)

基于 LLM 的语言审计，检查语气、简洁度和歧义。

```bash
python scripts/soft_qa_llm.py \
  data/repaired_v1.csv \
  --out_tasks data/repair_tasks.jsonl
```

### [步骤 10] 自动修复循环 - 软质量 (Repair Soft Major)

修复 Soft QA 中标记的主要语言问题，同时不破坏硬规则限制。

```bash
python scripts/repair_loop.py \
  --input data/repaired_v1.csv \
  --tasks data/repair_tasks.jsonl \
  --mode repair_soft_major \
  --out_csv data/repaired_final.csv
```

---

## 6. 第 5 阶段：导出与交付 (Export)

**目标**：恢复原始格式以便集成。

### [步骤 11] 令牌还原 (Rehydration)

将记号（如 `⟦PH_1⟧`）替换回原始的占位符。

```bash
python scripts/rehydrate_export.py \
  data/repaired_final.csv \
  data/placeholder_map.json \
  data/final_export.csv
```

---

## 7. 第 6 阶段：生命周期维护与优化 (Lifecycle)

**目标**：审计成本、更新术语并针对变化进行增量刷新。

### [步骤 12] 术语自动晋升 (Glossary Autopromote)

分析修复过程，识别缺失术语或更优译法。

```bash
python scripts/glossary_autopromote.py \
  --before data/translated.csv \
  --after data/repaired_final.csv
```

### [步骤 13] 第二轮刷新 (Round 2 Refresh)

根据术语表的变更，对已翻译内容进行最小化的增量刷新。

1. 计算术语差异：

```bash
python scripts/glossary_delta.py --old old_glossary.yaml --new new_glossary.yaml
```

2. 增量翻译刷新：

```bash
python scripts/translate_refresh.py \
  --input data/repaired_final.csv \
  --glossary new_glossary.yaml \
  --out_csv data/refreshed_final.csv
```

### [步骤 14] 指标统计 (Metrics)

基于 `llm_trace.jsonl` 计算成本和调用统计。

```bash
python scripts/metrics_aggregator.py \
  --trace data/llm_trace.jsonl \
  --out_md reports/metrics_report.md
```
