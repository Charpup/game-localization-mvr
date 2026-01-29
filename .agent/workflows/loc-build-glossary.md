---
description: 从候选术语构建术语表初稿
---

# /loc-build-glossary 工作流

从 `data/term_candidates.yaml` 生成 `data/glossary.yaml` 初稿（需人工审批）。

## 前置条件

- 已完成 `/loc-extract-terms`，生成了 `data/term_candidates.yaml`

## 输出格式

`data/glossary.yaml` 使用 v2.0 entries 列表格式：

```yaml
entries:
  - term_zh: "木叶"
    term_ru: "Коноха"
    status: "approved"
    notes: "官方常见译法"
  - term_zh: "忍术"
    term_ru: "дзюцу"
    status: "proposed"
    notes: ""
  - term_zh: "抽卡"
    term_ru: ""
    status: "banned"
    notes: "避免口语，可改为 Призыв/Набор"
```

## 状态说明

| 状态 | 翻译脚本行为 |
|------|-------------|
| `approved` | **强制使用**指定译法 |
| `proposed` | 仅作参考，LLM 可采纳或不采纳 |
| `banned` | **禁止**自创别名，需人工定稿 |

## 执行步骤

### 1. 从候选术语创建初稿

手动或使用 LLM 将高频术语转为 glossary 格式。

### 2. 人工审批

1. 打开 `data/glossary.yaml`
2. 将确定的术语标记为 `approved`
3. 不确定的保留 `proposed`
4. 不适合的标记为 `banned`

### 3. 验证格式

确保 YAML 语法正确：

```powershell
python -c "import yaml; yaml.safe_load(open('data/glossary.yaml', encoding='utf-8'))"
```

### 4. 编译为运行时格式

使用 compilation 脚本将审批后的通过项编译为 `compiled.yaml`（含 version/hash）：

```bash
python scripts/glossary_compile.py \
    --approved data/glossary.yaml \
    --out_compiled glossary/compiled.yaml \
    --resolve_by_scope
```

## 下一步

审批完成后，继续执行 `/loc-normalize` 和 `/loc-translate`。

## 注意事项

1. **保守原则**：不确定的术语应标记为 `proposed`，而非 `approved`
2. **增量更新**：可随时添加新术语，脚本会按需加载命中项
3. **空译法**：`banned` 状态的术语 `term_ru` 可为空
