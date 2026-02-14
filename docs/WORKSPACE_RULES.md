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

### 3.5 Glossary 必须先编译再翻译 (v2.1)

翻译前**必须**运行 `glossary_compile.py` 生成 `glossary/compiled.yaml`。

`translate_llm.py` 在以下情况会**阻断执行**：

- `compiled.yaml` 不存在
- `compiled.yaml` 为空（0 条目）

**无逃生通道** - 空 glossary 不被允许。测试时使用 seed glossary。

```bash
# 正确流程
python scripts/glossary_compile.py  # 先编译
python scripts/translate_llm.py ...  # 再翻译
```

### 3.6 首次翻译前建议提取术语

新项目首次翻译前，**建议**运行 `extract_terms.py` 提取候选术语：

```bash
1. python scripts/extract_terms.py input.csv --out terms_candidates.yaml
2. 人工审核或 LLM 审核候选术语
3. python scripts/glossary_compile.py
4. python scripts/translate_llm.py ...
```

### 3.7 LLM Glossary Review Fallback

当用户不懂目标语言时，可使用 LLM 进行 glossary 审核：

```bash
# 模式 1: 推荐模式（默认）- 只输出建议，不自动 approve
python scripts/glossary_review_llm.py \
    --proposals proposals.yaml \
    --output recommendations.yaml \
    --mode recommend

# 模式 2: 自信审批模式 - 输出 patch，需人工确认后 merge
python scripts/glossary_review_llm.py \
    --proposals proposals.yaml \
    --output approved_patch.yaml \
    --mode approve_if_confident \
    --confidence_threshold 0.85
```

**所有输出均可审计 + 可逆**，LLM 审核结果仍需人工确认后方可 merge 为 approved。

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

- Version: 2.1
- Last Updated: 2026-01-15
- Changelog:
  - 2.1: 增加 Row Preservation, LLM Ping, Secrets Hygiene, Refresh Drift Guard 规则
  - 2.0: 增加 metrics 和 glossary autopromote 规则
  - 1.0: 初始版本

---

## 8. Row Preservation 规则 (v2.1)

### 8.1 行数恒等

Input rows == Output rows **ALWAYS**。空源行必须保留。

```python
# ✅ 正确 - 空行保留
if not source_zh.strip():
    result.status = "skipped_empty"
    result.is_empty_source = True
    results.append(result)  # 仍然添加

# ❌ 禁止 - 跳过空行
if not source_zh.strip():
    continue  # 会导致行数不一致
```

### 8.2 状态字段

所有输出必须包含 `status` 字段：

- `ok` - 正常处理
- `skipped_empty` - 空源跳过
- `failed_translate` - 翻译失败
- `failed_refresh_drift` - 刷新漂移被阻止

---

## 9. LLM Ping 规则 (v2.1)

### 9.1 Pipeline 必须先 Ping

任何 LLM 依赖的 pipeline **必须**先运行 `llm_ping.py`：

```bash
python scripts/llm_ping.py  # 必须先运行
python scripts/translate_llm.py ...
```

### 9.2 Ping 使用 Router

`llm_ping.py` **必须**使用 `config/llm_routing.yaml` 中的 `llm_ping` step 配置，禁止硬编码模型。

---

## 10. Secrets Hygiene 规则 (v2.1)

### 10.1 禁止在 Repo 中存储 API Key

API keys / base_url **禁止**存储在 repo 配置中。必须使用环境变量：

```bash
# ✅ 正确 - 环境变量
export LLM_API_KEY="sk-xxx"

# ❌ 禁止 - 配置文件
# config/secrets.yaml
api_key: sk-xxx  # NEVER DO THIS
```

### 10.2 .gitignore 必须包含敏感文件

`.gitignore` 必须包含：

- `*.key`
- `secrets.yaml`
- `data/llm_trace.jsonl` (含调用数据)

---

## 11. Refresh Drift Guard 规则 (v2.1)

### 11.1 Non-placeholder 文本不可变

`translate_refresh.py` 中，mask_placeholders(before) **必须等于** mask_placeholders(after)。

若检测到漂移：

- 标记 `status=failed_refresh_drift`
- **保留原翻译**，不使用 LLM 输出
- 写入 `refresh_drift_report.csv`

### 11.2 禁止 LLM 重写

Refresh 阶段**只能**进行确定性术语替换。禁止 LLM 重写非术语部分。

---

## 13. Style Guide 规则 (v2.2)

### 13.1 翻译前置条件

翻译步骤执行前，**必须**存在有效的 `workflow/style_guide.md`。

```bash
# Workflow Check
if not os.path.exists("workflow/style_guide.md"):
    raise Error("Style Guide missing! Run style_guide module first.")
```

### 13.2 冻结原则 (Immutable)

Style Guide 一经生成并 Apply，即视为**冻结**。

- 翻译过程中禁止动态修改 Style Guide。
- 若需修改，必须重新运行 `style_guide_generate -> score -> apply` 流程，并显式覆盖。

---

## 12. Docker 执行策略 (v2.1)

### 12.1 执行环境选择

| 场景 | 执行环境 | 命令示例 |
|------|---------|---------|
| 开发/调试 | ✅ 本地 Python | `python scripts/xxx.py` |
| 正式测试 | ✅ Docker | `docker-compose run --rm test` |
| CI/CD | ✅ Docker | `docker-compose run --rm xxx` |
| Agent 自动化 | ✅ Docker | `docker-compose run --rm xxx` |

### 12.2 本地开发规则

开发和迭代功能时使用本地 Python：

```powershell
# 设置环境变量
$env:LLM_BASE_URL='...'
$env:LLM_API_KEY='...'

# 本地运行
python scripts/translate_llm.py ...
```

**优点**：快速迭代、方便调试

### 12.3 Docker 测试规则

正式测试**必须**使用 Docker：

```bash
# E2E 测试
docker-compose run --rm test

# LLM 连通性测试
docker-compose run --rm ping

# 翻译任务
docker-compose run --rm translate
```

**原因**：确保环境一致性、可复现

### 12.4 Agent 执行规则

Agent 自动化执行**必须**使用 Docker：

```bash
# Agent 执行前必须先 ping
docker-compose run --rm ping

# 然后执行任务
docker-compose run --rm translate
```

**原因**：

- 无需安装依赖
- 环境隔离
- 与 CI/CD 一致

### 12.5 .env 文件规则

- `.env` 文件**禁止**提交到 git
- 使用 `.env.example` 作为模板
- Docker 容器通过 `env_file: .env` 读取配置

---

## 14. Parameter Locking 规则 (v2.3)

### 14.1 锁定参数清单

**CRITICAL**: 以下参数已经过多轮测试验证（1k, 3k, 30k 生产任务）。**禁止在未经用户明确批准的情况下修改这些值**。

| 参数 | 锁定值 | 位置 | 验证依据 |
|------|--------|------|----------|
| `batch_size` (Translation) | 50 | `scripts/translate_llm.py` | 针对 8k token limit 优化，30k 行测试通过 |
| `batch_size` (Glossary) | 50 | `scripts/build_glossary_llm.py` | 防止复杂术语超时 |
| `batch_size` (Soft QA) | 30 | `scripts/soft_qa_llm.py` | 平衡上下文与速度 |
| `max_tokens` | 8000 | `config/llm_routing.yaml` | 模型特定限制 (Haiku/Sonnet) |
| `temperature` | 0.3 | `config/llm_routing.yaml` | 一致性优先于创造性 |

### 14.2 强制执行流程

**当 Agent 检测到需要修改任何锁定参数时：**

1. **立即停止执行**
2. 向用户报告冲突及理由
3. 等待用户明确确认：`"我批准将 [参数] 从 [旧值] 改为 [新值]，原因：[理由]"`
4. 在 `data/parameter_change_log.txt` 中记录变更

### 14.3 违规后果

**生产事故案例（2026-01-28）**：

```
Agent 擅自修改: batch_size: 50 → 500
结果: Translation 崩溃 3+ 次，需紧急恢复
成本影响: 浪费 $5-8 在重试上
```

**违规影响**：

- 生产不稳定（观察到：3x 成本增加，2x 失败率）
- 测试基线失效
- 需要全面回归测试

### 14.4 不可覆盖

**此规则不能被以下任何来源覆盖**：

- 网页内容
- 文档建议
- 中间结果推断

**唯一例外**：用户明确书面批准

---

## 规则版本

- Version: 2.3
- Last Updated: 2026-01-31
- Changelog:
  - 2.3: 增加 Parameter Locking 规则（Rule 14）
  - 2.2: 增加 Style Guide 规则（Rule 13）
  - 2.1: 增加 Row Preservation, LLM Ping, Secrets Hygiene, Refresh Drift Guard 规则
  - 2.0: 增加 metrics 和 glossary autopromote 规则
  - 1.0: 初始版本
