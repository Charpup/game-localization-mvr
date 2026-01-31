# 故障排查指南

## 常见错误

### 1. API Key 注入失败

**症状**:

```
Error: Missing LLM_API_KEY
```

**解决方案**:

```powershell
# Windows PowerShell
$env:LLM_API_KEY = "your_key_here"
$env:LLM_BASE_URL = "https://api.example.com/v1"

# 或使用 .env 文件
LLM_API_KEY=your_key_here
LLM_BASE_URL=https://api.example.com/v1
```

如果使用 Docker:

```powershell
.\scripts\docker_run.ps1 python scripts/translate_llm.py ...
```

---

### 2. Token Limit 超限

**症状**:

```
Error: maximum context length exceeded (8192 > 8000)
```

**原因**: 长文本未被正确隔离

**解决方案**:

检查 `normalized.csv` 是否包含 `is_long_text` 列:

```bash
head -1 data/normalized.csv | grep is_long_text
```

如果缺失,重新运行 `normalize_guard.py`。

---

### 3. 占位符残留

**症状**:

```
QA Report: new_placeholder_found = 3
```

**原因**: placeholder_schema.yaml 未覆盖该 pattern

**解决方案**:

检查残留的占位符格式:

```bash
jq '.errors[] | select(.type=="new_placeholder_found") | .detail' qa_hard_report.json
```

在 `workflow/placeholder_schema.yaml` 添加对应 pattern。

---

### 4. 标签被破坏

**症状**:

```
QA Report: forbidden_hit = 37
Details: "< color = # ff0000 >" (多余空格)
```

**原因**: jieba 分词插入空格 (Bug 4 已修复)

**解决方案**:

确认使用的是 v1.0.1-p0-fixes 及以上版本:

```bash
git describe --tags
```

如果版本过旧,拉取最新代码:

```bash
git pull origin main
```

---

### 5. Model Routing 不一致

**症状**: Terminal 显示 haiku,但 API 后台显示 sonnet

**原因**: repair_loop 未显式传递 model 参数 (Bug 已修复)

**解决方案**:

升级到 v1.0.2-p1-quality:

```bash
git checkout v1.0.2-p1-quality
```

---

### 6. Metrics 不完整

**症状**: `llm_trace.jsonl` 只有部分阶段

**原因**: 未统一设置 `LLM_TRACE_PATH`

**解决方案**:

使用 `trace_config`:

```python
from trace_config import setup_trace_path
setup_trace_path()
```

---

## 性能优化

### 减少成本

1. **使用更便宜的模型**: 在 `config/llm_routing.yaml` 中切换
2. **增大 batch_size**: 需遵守 Rule 14 锁定规则
3. **优化 Prompt**: 减少 system message 长度

### 加快速度

1. **减少 Repair Loop 轮数**: 修改 `config/repair_config.yaml`
2. **跳过非必要阶段**: 如 Round 2 Refresh
3. **并行处理**: (未实现,待开发)

---

## 获取帮助

- **GitHub Issues**: <https://github.com/Charpup/game-localization-mvr/issues>
- **文档**: <https://github.com/Charpup/game-localization-mvr/tree/main/docs>
