# TriadDev: v1.4.0 端到端测试计划

**Date**: 2026-02-21  
**Location**: /root/.openclaw/workspace/projects/game-localization-mvr/test_v140/  
**Status**: 🔄 准备测试

---

## 测试目标

验证 v1.4.0 Skill 的完整工作流程，包括：
1. ✅ 术语库提取 (extract_terms)
2. ✅ 术语翻译 (glossary_translate)
3. ✅ 主翻译流程 (batch_runtime)
4. ✅ QA 质检 (soft_qa)
5. ✅ 术语自动晋升 (autopromote)
6. ✅ Round 2 刷新 (refresh)

---

## 测试结构

```
test_v140/
├── input/               # 待测试的中文文本
├── output/              # 翻译结果输出
├── workflow/            # style guide, config
├── glossary/            # 术语库文件
│   ├── extracted/       # 提取的术语
│   ├── proposals/       # 待审核术语
│   ├── approved/        # 已批准术语
│   └── compiled/        # 编译后的术语库
└── reports/             # QA 报告, metrics
```

---

## Phase 1: 准备 (等待 Master 上传)

### 1.1 接收测试文档
- **位置**: test_v140/input/
- **格式**: CSV (id, source_zh, context)
- **世界观**: Naruto

### 1.2 统计规模
- 行数统计
- 字符数统计
- 预估 token 消耗

---

## Phase 2: Style Guide 适配

### 2.1 创建 EN Style Guide
基于现有的 RU style guide，创建 EN 版本：
- 语域与口吻
- 术语一致性规则
- 格式与占位符
- 标点与排版
- UI 长度限制

### 2.2 配置更新
- workflow/config.yaml
- language_pairs.yaml

---

## Phase 3: 术语库建立流程

### 3.1 提取术语
```bash
loc-mvr glossary --action extract \
  --input test_v140/input/data.csv \
  --output test_v140/glossary/extracted/terms_raw.yaml
```

### 3.2 术语翻译
```bash
loc-mvr glossary --action translate \
  --input test_v140/glossary/extracted/terms_raw.yaml \
  --output test_v140/glossary/proposals/terms_en.yaml \
  --target-lang en-US
```

### 3.3 术语审核 (Manual)
- Master 审核 proposals
- 移动到 approved/

### 3.4 术语编译
```bash
loc-mvr glossary --action compile \
  --input test_v140/glossary/approved/ \
  --output test_v140/glossary/compiled/glossary_en.yaml
```

---

## Phase 4: 主翻译流程

### 4.1 Batch Translation
```bash
loc-mvr translate \
  --input test_v140/input/data.csv \
  --output test_v140/output/translated_en.csv \
  --target-lang en-US \
  --style-guide test_v140/workflow/style_guide_en.md \
  --glossary test_v140/glossary/compiled/glossary_en.yaml
```

---

## Phase 5: QA 流程

### 5.1 Soft QA
```bash
loc-mvr qa \
  --input test_v140/output/translated_en.csv \
  --style-guide test_v140/workflow/style_guide_en.md \
  --glossary test_v140/glossary/compiled/glossary_en.yaml \
  --output test_v140/reports/qa_report.json
```

### 5.2 问题修复 (如有)
- 提取 failed items
- Round 2 refresh

---

## Phase 6: 术语自动晋升

### 6.1 Autopromote
```bash
loc-mvr glossary --action autopromote \
  --input test_v140/reports/qa_report.json \
  --threshold 0.95 \
  --output test_v140/glossary/approved/autopromoted.yaml
```

---

## Phase 7: Round 2 Refresh

### 7.1 识别需要刷新的条目
- 基于 QA 报告
- 术语变更检测

### 7.2 Refresh Translation
```bash
loc-mvr translate --action refresh \
  --input test_v140/output/translated_en.csv \
  --changes test_v140/glossary/changes.yaml \
  --output test_v140/output/translated_en_v2.csv
```

---

## 预期结果

- 完整翻译: 100%
- QA 通过率: >90%
- 术语一致性: 100%
- Autopromote 率: ~30%

---

**Status**: 🔄 **等待 Master 上传测试文档**