# Game Localization MVR - Workspace Rules

本文档定义了本地化工作流的核心规则和约束。

---

## 1. LLM 调用规则

### 1.1 必须经由 runtime_adapter

所有 LLM 调用**必须**通过 `runtime_adapter.py`，禁止直接调用 HTTP API。

```python
# ✅ 正确
from runtime_adapter import LLMClient
llm = LLMClient()
result = llm.chat(system=..., user=..., metadata={"step": "translate"})

# ❌ 禁止
import requests
resp = requests.post("https://api.openai.com/v1/chat/completions", ...)
```

### 1.2 必须传 metadata.step

所有 `llm.chat()` 调用**必须**传 `metadata={"step": "..."}` 参数。

有效的 step 值：
- `translate` - translate_llm.py
- `soft_qa` - soft_qa_llm.py
- `repair` - repair_loop.py
- `glossary_autopromote` - glossary_autopromote.py

```python
# ✅ 正确
llm.chat(system=..., user=..., metadata={"step": "translate", "batch_id": "0"})

# ❌ 禁止 (会被记录为 unknown)
llm.chat(system=..., user=...)
```

### 1.3 Trace 必须开启

`runtime_adapter` 必须写 trace 到 `data/llm_trace.jsonl`。

环境变量 `LLM_TRACE_PATH` 可自定义路径，但不可设为空。

---

## 2. Metrics 计费规则

### 2.1 优先使用 usage 精准计费

成本计算优先使用 LLM 响应中的 `usage` 字段（prompt_tokens, completion_tokens）。

### 2.2 无 usage 则 fallback 估算

若 `usage` 缺失，则按字符数估算 tokens：
```
tokens ≈ ceil(chars / 4)
```

估算的调用数会在报告中标注为 `estimated_calls`。

### 2.3 计费模式

支持两种模式（config/pricing.yaml）：

1. **multiplier** - 平台倍率计费
2. **per_1m** - 标准每百万 token 计费

---

## 3. Glossary 规则

### 3.1 autopromote 只产生 proposed

`glossary_autopromote.py` **只能**产生 `status: proposed` 的条目。

禁止自动将条目改为 `approved`。

```yaml
# ✅ autopromote 输出
entries:
  - term_zh: "忍术"
    term_ru: "Ниндзюцу"
    status: "proposed"  # 只能是 proposed
```

### 3.2 approved 必须人工审核

只有人工审核后，才能将 `proposed` 改为 `approved`。

### 3.3 Scope 分域控制

Glossary 按 scope 组织，至少区分：
- `language_pair` - 语言对 (zh-CN->ru-RU)
- `ip/project` - IP 或项目 (ip_naruto, project_xxx)

```
glossary/
├── global.yaml              # scope: global
└── zhCN_ruRU/
    ├── base.yaml            # scope: base
    ├── ip_naruto.yaml       # scope: ip_naruto
    └── project_xxx.yaml     # scope: project_xxx
```

### 3.4 冲突检测

若 proposed 的 `term_zh` 已有不同的 `approved` `term_ru`，则标记为冲突并**不纳入** proposals。

---

## 4. 占位符规则

### 4.1 必须先冻结再翻译

所有占位符/标签必须先由 `normalize_guard.py` 冻结为 token，再交给模型处理。

```bash
# 正确顺序
python scripts/normalize_guard.py --input ... --output ...
python scripts/translate_llm.py --input normalized.csv ...
```

### 4.2 禁止翻译未冻结的文本

未经 `normalize_guard.py` 处理的文本**不得**直接翻译。

---

## 5. QA 规则

### 5.1 qa_hard 是阻断门槛

在导出最终包之前，**必须**运行 `qa_hard.py`。

若 `qa_hard_report.json` 中 `has_errors=true`，则停止并进入修复流程。

### 5.2 修复只改被标记行

`repair_loop.py` 只能修改被 `qa_hard_report.json` 或 `repair_tasks.jsonl` 标记的行。

禁止全表重写。

---

## 6. 文件落盘规则

### 6.1 中间产物必须落盘

所有中间产物**必须**落盘为文件（CSV / JSON / YAML）。

禁止把关键结果只写在聊天里或内存中。

### 6.2 必须产出可验证证据

每一步必须产出"可验证证据"：
- 运行了哪些命令（终端日志）
- 产生了哪些文件（路径 + 简要摘要）

---

## 7. 版本与可复现规则

### 7.1 版本号记录

若脚本/规则版本变化，必须在输出文件头部或 report 中记录版本号/时间戳。

### 7.2 checkpoint 支持

`repair_loop.py` 必须保存 `repair_checkpoint.json` 以支持断点续传。

---

## 规则版本

- Version: 2.0
- Last Updated: 2026-01-12
- Changelog:
  - 2.0: 增加 metrics 和 glossary autopromote 规则
  - 1.0: 初始版本
