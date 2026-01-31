# 系统架构

## Pipeline 流程图

```
┌─────────────────┐
│   Raw CSV       │
│  (user input)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Normalize      │ ← workflow/placeholder_schema.yaml
│  - 占位符冻结  │
│  - Header 清洗 │
│  - 长文本检测  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Glossary        │ ← glossary/generic_terms_zh.txt
│ - Extract       │
│ - Build         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Translation    │ ← workflow/style_guide.md
│  (LLM Batch)    │ ← glossary/compiled.yaml
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Hard QA        │ ← workflow/forbidden_patterns.txt
│  - 规则校验    │
│  - Repair Loop │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Soft QA        │ ← workflow/style_guide.md
│  (LLM Quality)  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Export         │
│  - 占位符还原  │
│  - 格式转换    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Final CSV      │
└─────────────────┘
```

## 模块职责

| 模块 | 脚本 | 职责 |
|------|------|------|
| Normalize | normalize_guard.py | 占位符冻结, Header 清洗, 长文本检测 |
| Glossary | extract_terms.py, glossary_translate_llm.py | 术语提取与翻译 |
| Translation | translate_llm.py | LLM 批量翻译 |
| Hard QA | qa_hard.py, repair_loop_v2.py | 规则校验, 自动修复 |
| Soft QA | soft_qa_llm.py | LLM 质量审查 |
| Export | rehydrate_export.py | 占位符还原, 最终导出 |
| Support | runtime_adapter.py, trace_config.py | LLM 路由, Trace 管理 |

## 数据流

```
[Input CSV]
    ↓ (raw text)
[Normalized CSV] + [Placeholder Map]
    ↓ (frozen placeholders)
[Translated CSV]
    ↓ (target language)
[QA Reports] (Hard + Soft)
    ↓ (validation results)
[Final Export CSV]
    ↓ (restored placeholders)
[Deliverable]
```

## 核心组件

### Runtime Adapter (runtime_adapter.py)

LLM 调用的统一接口:

- **LLMClient**: 封装 HTTP 调用,支持多模型路由
- **LLMRouter**: 根据 `config/llm_routing.yaml` 选择模型
- **Trace**: 自动记录所有 LLM 调用到 `llm_trace.jsonl`

### Repair Loop (repair_loop_v2.py)

自动修复引擎:

- **BatchRepairLoop**: 批量处理修复任务
- **Multi-round**: 最多 3 轮修复,逐步升级模型
- **Validation**: 每次修复后验证,确保不引入新错误

### QA System

双层质量保障:

1. **Hard QA** (qa_hard.py): 规则校验
   - Token 匹配
   - 标签平衡
   - 禁用模式检测
   - 新占位符检测

2. **Soft QA** (soft_qa_llm.py): LLM 审查
   - 术语一致性
   - 风格符合度
   - 上下文准确性

## 配置文件

| 文件 | 用途 |
|------|------|
| `config/llm_routing.yaml` | 模型路由配置 |
| `config/pricing.yaml` | 模型定价配置 |
| `config/repair_config.yaml` | Repair Loop 配置 |
| `workflow/placeholder_schema.yaml` | 占位符模式定义 |
| `workflow/forbidden_patterns.txt` | 禁用模式列表 |
| `workflow/style_guide.md` | 翻译风格指南 |

## 扩展性

### 添加新模型

1. 在 `config/llm_routing.yaml` 添加模型配置
2. 在 `config/pricing.yaml` 添加定价信息
3. 测试并验证

### 添加新语言对

1. 创建新的 style guide (e.g., `workflow/style_guide_ja.md`)
2. 更新 glossary 配置
3. 调整 `normalize_guard.py` 的分词逻辑 (如需要)

### 自定义 QA 规则

1. 编辑 `workflow/forbidden_patterns.txt` 添加禁用模式
2. 修改 `qa_hard.py` 添加新的校验逻辑
3. 更新 `workflow/soft_qa_rubric.yaml` 调整 Soft QA 标准
