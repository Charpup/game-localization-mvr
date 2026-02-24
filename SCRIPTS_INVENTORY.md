# Loc-MVR v1.4.0 脚本完整性检查报告

**检查时间**: 2026-02-22  
**分支**: reorg/v1.3.0-structure  
**参考分支**: origin/main

---

## 缺失脚本清单

### 已修复 ✅

| 脚本 | 路径 | 来源 | 状态 |
|------|------|------|------|
| runtime_adapter.py | src/scripts/runtime_adapter.py | origin/main | 已获取 |
| translate_llm.py | src/scripts/translate_llm.py | origin/main | 已获取 |
| qa_hard.py | src/scripts/qa_hard.py | origin/main | 已获取 |
| qa_soft.py | src/scripts/qa_soft.py | origin/main | 已获取 |
| glossary_translate_llm.py | src/scripts/glossary_translate_llm.py | origin/main | 已获取 |

---

### v1.4.0 Skill 中已有的脚本 ✅

位于 `/root/.openclaw/workspace/projects/game-localization-mvr/skill/v1.4.0/scripts/core/`:

| 脚本 | 用途 | 状态 |
|------|------|------|
| batch_runtime.py | 批量翻译运行时 | ✅ 存在 |
| batch_sanity_gate.py | 批处理前置检查 | ✅ 存在 |
| emergency_translate.py | 紧急单条翻译 | ✅ 存在 |
| glossary_translate_llm.py | 术语表翻译 | ✅ 存在 |
| repair_loop.py | 修复循环 v1 | ✅ 存在 |
| repair_loop_v2.py | 修复循环 v2 | ✅ 存在 |
| soft_qa_llm.py | 软质检 LLM | ✅ 存在 |
| translate_refresh.py | 翻译刷新 | ✅ 存在 |

---

### 检查方法

```bash
# 从 main 分支获取缺失脚本
git show origin/main:scripts/runtime_adapter.py > src/scripts/runtime_adapter.py
git show origin/main:scripts/translate_llm.py > src/scripts/translate_llm.py
git show origin/main:scripts/qa_hard.py > src/scripts/qa_hard.py
git show origin/main:scripts/qa_soft.py > src/scripts/qa_soft.py
git show origin/main:scripts/glossary_translate_llm.py > src/scripts/glossary_translate_llm.py
```

---

### 依赖关系

现在可以使用的完整 workflow:

```
src/scripts/
├── runtime_adapter.py      # LLM 客户端适配器 ✅
├── translate_llm.py        # 单条/批量翻译 ✅
├── qa_hard.py              # 硬质检 ✅
├── qa_soft.py              # 软质检 ✅
├── glossary_translate_llm.py  # 术语翻译 ✅
├── batch_runtime.py        # 批量运行时 ✅
├── repair_loop_v2.py       # 修复循环 ✅
└── ...
```

---

### 建议

现在可以使用原生工具执行完整 pipeline:

```bash
# 1. 术语提取
cd src/scripts
python3 extract_terms.py --input ../../test_v140/workflow/normalized_input.csv

# 2. 术语翻译
python3 glossary_translate_llm.py --input ../../test_v140/glossary/extracted/terms_raw.yaml

# 3. 批量翻译
python3 batch_runtime.py \
  --source-lang zh-CN \
  --target-lang en-US \
  --style-guide ../../test_v140/workflow/style_guide_en.md

# 4. QA
python3 qa_hard.py --input ../../test_v140/output/translated.csv
python3 qa_soft.py --input ../../test_v140/output/translated.csv

# 5. 修复
python3 repair_loop_v2.py --input ../../test_v140/output/translated.csv
```

---

**状态**: 缺失脚本已补齐，现在可以使用原生工具执行完整测试。
