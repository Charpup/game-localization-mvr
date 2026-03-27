---
description: 从 candidate buckets 生成 glossary 初稿（C 里程碑）
---

# /loc-build-glossary 工作流

从 `data/term_candidates.yaml` 生成 `data/glossary.yaml` 初稿，完成“术语候选→人工审批”的入口闭环。

## 前置条件

- 已完成 `/loc-extract-terms`
- `data/term_candidates.yaml` 中包含 `critical / proposed / low_confidence` 三档
- 运行前建议先确认 `scripts/style_sync_check.py` 已通过

## 输出格式

`data/glossary.yaml` 使用 v2.1 entries 列表格式：

```yaml
entries:
  - term_zh: "木叶"
    term_ru: "Коноха"
    status: "approved"           # critical 映射
    notes: "官方常见译法"
  - term_zh: "忍术"
    term_ru: "Ниндзюцу"
    status: "proposed"           # proposed 映射
    notes: "与现有风格映射一致"
  - term_zh: "抽卡"
    term_ru: ""
    status: "banned"             # low_confidence / 风格冲突命中
    notes: "不建议使用机翻"
```

## 状态说明

| 状态 | 与翻译脚本关系 |
|------|----------------|
| `approved` | `translate_llm.py` 强制使用 |
| `proposed` | `translate_llm.py` 仅参考 |
| `banned` | `translate_llm.py` 降级为人工确认 |

## 执行步骤

### 1. 加载候选与风格约束

按 `data/term_candidates.yaml` 的三档分类，优先处理 `critical`，其次 `proposed`。

### 2. 人工审批

对每条候选按以下策略设定：

1. `critical` → 可直接 `approved`
2. `proposed` → 需业务确认后 `approved` 或保留 `proposed`
3. `low_confidence`/疑似噪音 → 标记 `banned` 并说明原因

`style_profile.yaml` 命中的 `terminology.forbidden_terms`、`prohibited_aliases`、`banned_terms` 一律要求人工复核再入池。

### 3. 验证格式

```powershell
python -c "import yaml; yaml.safe_load(open('data/glossary.yaml', encoding='utf-8'))"
```

### 4. 编译为运行时格式

```bash
python scripts/glossary_compile.py \
  --approved data/glossary.yaml \
  --out_compiled glossary/compiled.yaml \
  --resolve_by_scope
```

## 下一步

审批完成后进入 `/loc-translate`；审批遗留项进入 `/loc-glossary-autopromote` 后续沉淀闭环。

## 注意事项

1. 保守策略：不确定项不应被直接 `approved`
2. `banned` 不一定禁止文本出现，只做“人工确认闸”控制
3. 每次改动后保持 `data/glossary.yaml` 与 `data/style_profile.yaml` 术语策略一致
